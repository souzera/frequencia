"""Update only artwork in a separate copy of an existing unsigned Windows build.

Preserve the PyInstaller payload byte-for-byte; do not touch the running build.
Functional Python changes still require the normal full build.
"""
from pathlib import Path
import hashlib
import shutil
import sys

import pefile
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.utils.win32.icon import CopyIcons_FromIco
from PyInstaller.utils.win32.winutils import update_exe_pe_checksum

root = Path(__file__).resolve().parent.parent
source = root / 'dist' / 'Frequencia'
destination = root / 'dist' / 'Frequencia-icone-atualizado'
if destination.exists() and '--resume' not in sys.argv:
    raise SystemExit('The output directory already exists; keep or move it before running again.')
if not destination.exists():
    shutil.copytree(source, destination)
icon = root / 'desktop' / 'ui' / 'assets' / 'frequencia.ico'
for name in ('Frequencia.exe', 'FrequenciaWorker.exe'):
    executable = destination / name
    original = CArchiveReader(str(executable))
    with pefile.PE(str(executable)) as pe:
        payload = pe.get_overlay()
    if not payload:
        raise RuntimeError(f'No PyInstaller payload in {name}')
    CopyIcons_FromIco(str(executable), [str(icon)])
    # UpdateResource may preserve or discard the overlay, depending on Windows.
    # Restore the original payload exactly once after the new PE sections.
    with pefile.PE(str(executable)) as pe:
        offset = pe.get_overlay_data_start_offset()
    data = executable.read_bytes()
    executable.write_bytes(data[:offset] + payload if offset is not None else data + payload)
    update_exe_pe_checksum(str(executable))
    updated = CArchiveReader(str(executable))
    if updated.toc != original.toc:
        raise RuntimeError(f'Archive structure changed in {name}')
    with pefile.PE(str(executable)) as pe:
        assert pe.get_overlay() == payload, 'Executable payload was modified'
        group = next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id == 14)
        entry = group.directory.entries[0].directory.entries[0].data.struct
        raw = pe.get_data(entry.OffsetToData, entry.Size)
        assert int.from_bytes(raw[4:6], 'little') == 9, 'Expected nine icon sizes'
    print(name, 'icon updated; application payload preserved:', hashlib.sha256(payload).hexdigest())
shutil.copytree(root / 'desktop' / 'ui', destination / '_internal' / 'desktop' / 'ui', dirs_exist_ok=True)
print('Updated build:', destination)
