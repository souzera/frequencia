import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from platformdirs import user_config_dir, user_downloads_dir

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def binaries():
    """Prefer shipped dependencies; PATH is only a developer convenience."""
    suffix = '.exe' if os.name == 'nt' else ''
    found = {}
    for name in ('ffmpeg', 'ffprobe', 'node'):
        local = ROOT / 'vendor' / (name + suffix)
        found[name] = str(local) if local.is_file() else shutil.which(name)
    return found


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(user_config_dir('Frequencia', appauthor=False)) / 'settings.json'
        self.value = {'directory': user_downloads_dir(), 'quality': '192'}
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                if isinstance(loaded.get('directory'), str) and Path(loaded['directory']).is_absolute():
                    self.value['directory'] = loaded['directory']
                if loaded.get('quality') in ('128', '192', '320'):
                    self.value['quality'] = loaded['quality']
        except (OSError, ValueError):
            pass

    def save(self, directory, quality):
        if not isinstance(directory, str) or not directory.strip() or not Path(directory).is_absolute():
            raise ValueError('Escolha uma pasta válida.')
        if quality not in ('128', '192', '320'):
            raise ValueError('Escolha uma qualidade disponível.')
        folder = Path(directory).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
        value = {'directory': str(folder), 'quality': quality}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump(value, f, ensure_ascii=False)
        try:
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)
        self.value = value
        return dict(value)
