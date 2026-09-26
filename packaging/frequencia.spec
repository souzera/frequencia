# Build with: python -m PyInstaller packaging/frequencia.spec --noconfirm
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).parent
vendor = root / 'vendor'
required = ['ffmpeg.exe', 'ffprobe.exe', 'node.exe']
for name in required:
    if not (vendor / name).is_file():
        raise SystemExit(f'Missing vendor/{name}. See README.md before building.')
if not (vendor / 'licenses').is_dir():
    raise SystemExit('Missing vendor/licenses. Include dependency licenses before shipping.')

datas = [(str(root / 'desktop' / 'ui'), 'desktop/ui'), (str(vendor / 'licenses'), 'licenses')]
binaries = [(str(vendor / name), 'vendor') for name in required]
hiddenimports = []
for package in ['yt_dlp', 'yt_dlp_ejs', 'spotdl', 'SpotipyFree', 'spotapi']:
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden

a = Analysis([str(root / 'desktop_app.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gtk', 'gi'], noarchive=False)
pyz = PYZ(a.pure)
# The UI has no console. The companion worker receives redirected standard
# handles and CREATE_NO_WINDOW; both share the same bundled dependencies.
icon = str(root / 'desktop' / 'ui' / 'assets' / 'frequencia.ico')
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Frequencia', console=False, icon=icon)
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FrequenciaWorker', console=True, icon=icon)
coll = COLLECT(exe, worker, a.binaries, a.datas, name='Frequencia', strip=False, upx=False)
