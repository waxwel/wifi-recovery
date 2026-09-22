import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outputs'))
import startup_settings as startup


class StartupTests(unittest.TestCase):
    def test_standalone_installs_itself_and_embedded_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'download.exe'; source.write_bytes(b'new executable')
            destination=Path(tmp)/'installed'/'WifiRecovery.exe'
            with patch.object(startup.sys,'frozen',True,create=True), patch.object(startup.sys,'executable',str(source)), patch.object(startup,'installed_executable',return_value=destination), patch.object(startup.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
                startup.prepare_startup()
                self.assertEqual(destination.read_bytes(),source.read_bytes())
                command=run.call_args.args[0]
                decoded=startup.base64.b64decode(command[-1]).decode('utf-16le')
                self.assertEqual(decoded, startup.AUTHORIZATION_SCRIPT)
                self.assertIn('WifiRecoveryDesktopLaunch',decoded)
                self.assertNotIn(str(source),decoded)
                self.assertEqual(list(destination.parent.glob('*.new')),[])

    def test_failed_setup_never_enables_login_entry(self):
        with patch.object(startup,'prepare_startup',side_effect=OSError('denied')), patch.object(startup.winreg,'CreateKeyEx') as create:
            with self.assertRaises(OSError): startup.set_enabled(True)
            create.assert_not_called()

    def test_disabling_does_not_install_or_authorize(self):
        with patch.object(startup,'prepare_startup') as prepare, patch.object(startup.winreg,'CreateKeyEx'), patch.object(startup.winreg,'DeleteValue') as delete:
            startup.set_enabled(False)
            prepare.assert_not_called()
            delete.assert_called_once()

    def test_installed_executable_not_copied_over_itself(self):
        with patch.object(startup.sys,'frozen',True,create=True), patch.object(startup.sys,'executable',str(startup.installed_executable())), patch.object(startup.shutil,'copyfile') as copy, patch.object(startup.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(OSError): startup.prepare_startup()
            copy.assert_not_called()


if __name__=='__main__': unittest.main()
