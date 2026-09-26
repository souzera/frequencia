"""Run the local desktop UI or an isolated, cancellable media worker."""
import sys


def main():
    if '--worker' in sys.argv:
        from desktop.worker import main as worker
        return worker()
    import webview
    from desktop.api import DesktopAPI
    from desktop.settings import ROOT
    api = DesktopAPI()
    window = webview.create_window('Frequência', str(ROOT / 'desktop' / 'ui' / 'index.html'),
                                   js_api=api, width=1180, height=800, min_size=(860, 640),
                                   background_color='#F7F8FA', text_select=True,
                                   frameless=True, easy_drag=False)
    api._window = window
    window.events.closing += lambda: api.cancel() and None
    webview.start(gui='edgechromium' if sys.platform == 'win32' else None,
                  icon=str(ROOT / 'desktop' / 'ui' / 'assets' / 'frequencia.ico'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
