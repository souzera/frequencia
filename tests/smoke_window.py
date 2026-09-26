"""Optional real WebView2 bridge test. Run from the repository root on Windows."""
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import webview
from desktop.api import DesktopAPI
from desktop.settings import ROOT, Settings

api = DesktopAPI(Settings(ROOT / 'build' / 'smoke-settings.json'))
window = webview.create_window('Frequência · teste', str(ROOT / 'desktop/ui/index.html'), js_api=api, width=1180, height=800)
api._window = window
result = {'ok': False}


def verify():
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            loaded = window.evaluate_js("typeof window.pywebview?.api?.get_state === 'function' && !document.getElementById('inspect').disabled")
            if loaded:
                break
            time.sleep(.2)
        else:
            raise RuntimeError('The Python bridge did not initialize')
        data = window.evaluate_js("window.pywebview.api.get_state()")
        # Promise support varies between WebView2 versions; inspect DOM updated
        # by the bridge as the authoritative signal.
        result.update(ok=True, destination=window.evaluate_js("document.getElementById('destination').textContent"),
                      font=window.evaluate_js("document.fonts.check('12px Cascadia')"),
                      no_horizontal_overflow=window.evaluate_js('document.documentElement.scrollWidth <= innerWidth'))
        window.evaluate_js("document.querySelector('[data-page=settings]').click()")
        result['settings_visible'] = window.evaluate_js("!document.getElementById('settings').hidden")
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        (ROOT / 'build').mkdir(exist_ok=True)
        (ROOT / 'build' / 'smoke-window.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        window.destroy()


webview.start(verify, gui='edgechromium')
print(json.dumps(result))
raise SystemExit(0 if result['ok'] else 1)
