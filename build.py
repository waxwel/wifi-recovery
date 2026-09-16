"""Build the Windows single-file executable from this checkout."""
import base64
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
source = root / 'outputs'
worker = (source / 'WifiWorker.ps1').read_bytes()
(source / 'worker_payload.py').write_text(
    'import base64\nWORKER_BYTES = base64.b64decode(' + repr(base64.b64encode(worker).decode('ascii')) + ')\n',
    encoding='utf-8')
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed',
    '--icon', str(source / 'WifiRecovery.ico'), '--name', 'WifiRecovery',
    '--add-data', str(root / 'LICENSE') + ';.',
    '--add-data', str(root / 'THIRD_PARTY_NOTICES.md') + ';.',
    '--add-data', str(root / 'licenses') + ';licenses',
    '--distpath', str(source), '--workpath', str(root / 'work' / 'build'),
    '--specpath', str(root / 'work'), str(source / 'WifiRecoveryApp.py'),
], check=True, cwd=root)
