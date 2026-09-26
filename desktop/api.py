"""Thread-safe bridge. External content never becomes executable UI code."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from desktop.links import classify
from desktop.settings import ROOT, Settings, binaries


class DesktopAPI:
    def __init__(self, settings=None):
        self._settings = settings or Settings()
        self._lock = threading.RLock()
        self._process = None
        self._cancelled = False
        self._window = None
        self._state = {'phase': 'idle', 'tracks': [], 'title': '', 'error': None}

    def get_state(self):
        with self._lock:
            return copy.deepcopy({**self._state, 'settings': self._settings.value,
                                  'dependencies': {k: bool(v) for k, v in binaries().items()}})

    def classify_link(self, url):
        try:
            return {'ok': True, **classify(url).to_dict()}
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}

    def inspect_link(self, url, playlist=False):
        try:
            link = classify(url, playlist is True)
            with self._lock:
                if self._state['phase'] in ('inspecting', 'downloading', 'cancelling'):
                    raise ValueError('Aguarde a operação atual ou cancele para continuar.')
                self._state = {'phase': 'inspecting', 'tracks': [], 'title': '', 'error': None}
                self._start({'action': 'inspect', 'url': link.url})
            return {'ok': True}
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}

    def download_selected(self, ids):
        with self._lock:
            if self._state['phase'] not in ('ready', 'complete', 'cancelled', 'error'):
                return {'ok': False, 'error': 'Confira o link antes de baixar.'}
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                return {'ok': False, 'error': 'Seleção inválida.'}
            selected = [t for t in self._state['tracks'] if t['id'] in ids and t.get('status') != 'done']
            if not selected:
                return {'ok': False, 'error': 'Selecione pelo menos uma faixa ainda não baixada.'}
            deps = binaries()
            if not all(deps.values()):
                return {'ok': False, 'error': 'Componentes de áudio ausentes. Confira Configurações.'}
            for track in selected:
                track.update(status='queued', percent=0, error=None)
            self._state.update(phase='downloading', error=None, current=0, total=len(selected))
            self._start({'action': 'download', 'tracks': copy.deepcopy(selected), 'settings': dict(self._settings.value)})
            return {'ok': True}

    def _start(self, request):
        self._cancelled = False
        request['deps'] = binaries()
        threading.Thread(target=self._run, args=(request,), daemon=True).start()

    def _run(self, request):
        interpreter = Path(sys.executable)
        if interpreter.name.lower() == 'pythonw.exe':
            interpreter = interpreter.with_name('python.exe')
        command = [str(Path(sys.executable).with_name('FrequenciaWorker.exe')), '--worker'] if getattr(sys, 'frozen', False) else [str(interpreter), str(ROOT / 'desktop_app.py'), '--worker']
        process = None
        try:
            with self._lock:
                if self._cancelled:
                    self._state['phase'] = 'cancelled'
                    for track in self._state['tracks']:
                        if track.get('status') == 'queued':
                            track['status'] = 'cancelled'
                    return
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                           text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                           start_new_session=os.name != 'nt')
                self._process = process
            process.stdin.write(json.dumps(request, ensure_ascii=True) + '\n')
            process.stdin.close()
            deadline = time.monotonic() + (180 if request['action'] == 'inspect' else 1800 * len(request['tracks']))
            def watchdog():
                while process.poll() is None:
                    if time.monotonic() > deadline:
                        with self._lock:
                            self._state['error'] = 'O provedor excedeu o tempo limite. Tente novamente.'
                        self._kill(process)
                        return
                    time.sleep(.5)
            threading.Thread(target=watchdog, daemon=True).start()
            for line in process.stdout:
                if not line.startswith('FREQUENCIA:'):
                    continue
                event = json.loads(line.removeprefix('FREQUENCIA:'))
                with self._lock:
                    if self._cancelled:
                        continue
                    kind = event.pop('event')
                    if kind == 'preview':
                        self._state.update(event)
                    elif kind in ('track', 'match'):
                        for track in self._state['tracks']:
                            if track['id'] == event['id']:
                                track.update(event)
                        for key in ('current', 'total'):
                            if key in event:
                                self._state[key] = event[key]
                    elif kind == 'error':
                        self._state['error'] = event['error']
            code = process.wait()
            with self._lock:
                if self._cancelled:
                    self._state['phase'] = 'cancelled'
                    for track in self._state['tracks']:
                        if track.get('status') in ('queued', 'downloading', 'converting'):
                            track['status'] = 'cancelled'
                elif code or self._state.get('error'):
                    self._state.update(phase='error', error=self._state.get('error') or 'O processo de áudio foi interrompido.')
                    for track in self._state['tracks']:
                        if track.get('status') in ('queued', 'downloading', 'converting'):
                            track.update(status='error', error='Processamento interrompido. Tente novamente.')
                else:
                    if request['action'] == 'inspect' and not self._state['tracks']:
                        self._state.update(phase='error', error='Nenhuma faixa foi retornada pelo provedor.')
                    else:
                        self._state['phase'] = 'ready' if request['action'] == 'inspect' else 'complete'
        except Exception as exc:
            with self._lock:
                self._state.update(phase='cancelled' if self._cancelled else 'error',
                                   error=None if self._cancelled else str(exc))
                for track in self._state['tracks']:
                    if track.get('status') in ('queued', 'downloading', 'converting'):
                        track['status'] = 'cancelled' if self._cancelled else 'error'
        finally:
            if process:
                if process.poll() is None:
                    self._kill(process)
                process.wait()
                if process.stdout:
                    process.stdout.close()
            with self._lock:
                if self._process is process:
                    self._process = None

    def _kill(self, process):
        if process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def cancel(self):
        with self._lock:
            if self._state['phase'] not in ('inspecting', 'downloading', 'cancelling'):
                return {'ok': True}
            self._cancelled = True
            self._state['phase'] = 'cancelling'
            process = self._process
        if process:
            self._kill(process)
        return {'ok': True}

    def choose_directory(self):
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    def save_settings(self, directory, quality):
        try:
            with self._lock:
                value = self._settings.save(directory, quality)
            return {'ok': True, 'settings': value}
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}

    def open_directory(self):
        try:
            folder = Path(self._settings.value['directory'])
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == 'nt':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(folder)])
            else:
                subprocess.Popen(['xdg-open', str(folder)])
            return {'ok': True}
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}
