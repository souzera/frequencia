"""Verify the packaged worker, assets and shipped tools without network access."""
import json
from pathlib import Path
import subprocess
import types
import sys
from PyInstaller.archive.readers import CArchiveReader

root = Path(__file__).resolve().parent.parent
bundle = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'dist' / 'Frequencia'


def fingerprint(code):
    return (code.co_code, code.co_names,
            tuple(fingerprint(c) if isinstance(c, types.CodeType) else c for c in code.co_consts))


archive = CArchiveReader(str(bundle / 'FrequenciaWorker.exe')).open_embedded_archive('PYZ.pyz')
for name in ('api', 'worker', 'links', 'settings'):
    packaged = archive.extract('desktop.' + name)
    current = compile((root / 'desktop' / (name + '.py')).read_text(encoding='utf-8'), 'source', 'exec')
    assert fingerprint(packaged) == fingerprint(current), f'Package contains an outdated desktop.{name}'

request = {'action': 'download', 'tracks': [], 'deps': {},
           'settings': {'directory': str(root / 'build' / 'smoke-output'), 'quality': '192'}}
process = subprocess.run([str(bundle / 'FrequenciaWorker.exe'), '--worker'],
                         input=json.dumps(request) + '\n', capture_output=True, text=True, encoding='utf-8', timeout=45)
assert process.returncode == 0, process.stderr
assert '"event": "complete"' in process.stdout, process.stdout
components = {}
for name in ('ffmpeg', 'ffprobe', 'node'):
    result = subprocess.run([str(bundle / '_internal' / 'vendor' / (name + '.exe')), '-version' if name != 'node' else '--version'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    components[name] = result.stdout.splitlines()[0]
assert (bundle / '_internal' / 'desktop' / 'ui' / 'fonts' / 'CascadiaCode-Regular.ttf').is_file()
assert (bundle / '_internal' / 'licenses' / 'Node-LICENSE.txt').is_file()
report = {'ok': True, 'worker': 'complete', 'bundled_components': components}
(root / 'build' / 'smoke-frozen.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
