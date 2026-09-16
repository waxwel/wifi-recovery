import importlib.util
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import sys
import time
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'outputs/WifiRecoveryApp.py'
sys.path.insert(0,str(path.parent))
spec = importlib.util.spec_from_file_location('desktop', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeMonitor(module.Monitor):
    def __init__(self, directory):
        super().__init__(directory)
        self.running = False
        self.stop_requested = False
        self.wakes = 0
    @property
    def alive(self): return self.running
    def start(self): self.running = True
    def request_stop(self): self.stop_requested = True
    def wake(self): self.wakes += 1


class Tests(unittest.TestCase):
    def test_elevation_resets_bundle_environment(self):
        def launch(*args):
            self.assertEqual(module.os.environ.get('PYINSTALLER_RESET_ENVIRONMENT'), '1')
            return 33
        with patch.dict(module.os.environ, {'PYINSTALLER_RESET_ENVIRONMENT':'previous'}), patch.object(module.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=False), patch.object(module.ctypes.windll.shell32, 'ShellExecuteW', side_effect=launch):
            module.main()
            self.assertEqual(module.os.environ['PYINSTALLER_RESET_ENVIRONMENT'],'previous')

    def test_windows_log_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            monitor=module.Monitor(temporary)
            text='监控脚本不存在，请重新启动程序'
            encoding=f'cp{module.ctypes.windll.kernel32.GetACP()}'
            (monitor.run_dir/'worker-output.txt').write_bytes(text.encode(encoding))
            self.assertEqual(monitor.log(),text)

    def test_real_process_pause_resume_without_mei(self):
        # Real PowerShell process, but a harmless worker: no network operations.
        fixture = b'''param($ConfigPath,$StatusPath,$LogPath,$StopPath,$WakePath,$ParentProcessId)
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
while (-not (Test-Path -LiteralPath $StopPath)) {
    '{"phase":"Online","checks":1}' | Set-Content -LiteralPath $StatusPath -Encoding UTF8
    Start-Sleep -Milliseconds 100
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            monitor=module.Monitor(temporary)
            previous_run=None
            with patch.object(module, 'WORKER_BYTES', fixture), patch.object(sys, '_MEIPASS', str(Path(temporary)/'missing_MEI'), create=True):
                try:
                    for _ in range(3):
                        monitor.start()
                        deadline=time.monotonic()+10
                        while time.monotonic()<deadline and monitor.state().get('phase') != 'Online':
                            time.sleep(.1)
                        self.assertTrue(monitor.alive, monitor.log())
                        self.assertEqual(monitor.state().get('phase'), 'Online')
                        self.assertNotEqual(previous_run, monitor.run_dir)
                        self.assertEqual((monitor.run_dir/'WifiWorker.ps1').read_bytes(),fixture)
                        monitor.request_stop()
                        monitor.process.wait(timeout=5)
                        self.assertFalse(monitor.alive)
                        (monitor.run_dir/'WifiWorker.ps1').unlink()
                        previous_run=monitor.run_dir
                finally:
                    monitor.request_stop()
                    if monitor.alive: monitor.process.wait(timeout=5)
                    if monitor.output: monitor.output.close()

    def test_embedded_script_matches_source(self):
        self.assertEqual(module.WORKER_BYTES,(path.parent/'WifiWorker.ps1').read_bytes())

    def test_launch_failure_is_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            monitor=module.Monitor(temporary)
            with patch.object(module.subprocess, 'Popen', side_effect=OSError('模拟启动失败')):
                monitor.start()
            self.assertFalse(monitor.alive)
            self.assertIn('模拟启动失败',monitor.log())

    def test_config_migration_preserves_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            monitor = FakeMonitor(temporary)
            module.save_json(monitor.config_path, dict(interval=5, threshold=3, timeout=8, cooldown=180, urls=module.DEFAULTS['urls'][:2]))
            root=tk.Tk()
            root.withdraw()
            try:
                app=module.App(root,monitor,autostart=False)
                self.assertEqual(app.config['interval'],5)
                self.assertEqual(app.config['mode'],'client')
                self.assertIn('https://www.baidu.com/',app.config['urls'])
                self.assertEqual(app.config['schema'],6)
            finally: root.destroy()

    def test_validation(self):
        for change in [dict(interval='0'), dict(interval='1.5'), dict(urls=[]), dict(urls=['http://github.com']),
                       dict(urls=['https://x/a b']), dict(urls=['https://u:p@github.com']), dict(urls=['https://github.com']*2)]:
            with self.assertRaises(ValueError): module.validate_config({**module.DEFAULTS, **change})
        self.assertEqual(module.validate_config(module.DEFAULTS)['threshold'], 3)

    def test_settings_and_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            monitor = FakeMonitor(temporary)
            app = module.App(root, monitor)
            try:
                self.assertTrue(monitor.alive)
                app.fields['interval'].set('30')
                app.url_entry.delete(0, 'end')
                app.url_entry.insert(0, 'https://example.com/')
                app.add_url()
                self.assertEqual(app.url_list.size(), 4)
                app.url_list.selection_set(3)
                app.url_entry.delete(0, 'end')
                app.url_entry.insert(0, 'https://www.example.com/')
                app.edit_url()
                self.assertEqual(app.url_list.get(3), 'https://www.example.com/')
                app.url_list.selection_set(3)
                app.delete_url()
                app.mode.set('共享端')
                app.wifi_profile.set('Saved Test Network')
                app.save_settings()
                saved = json.loads(monitor.config_path.read_text(encoding='utf-8'))
                self.assertEqual(saved['interval'], 30)
                self.assertEqual(len(saved['urls']), 3)
                self.assertEqual(saved['mode'], 'host')
                self.assertEqual(saved['wifi_profile'], 'Saved Test Network')
                self.assertEqual(monitor.wakes, 1)
                with patch.object(module.messagebox, 'askyesno', return_value=False):
                    app.request_exit()
                self.assertFalse(app.closing)
                self.assertFalse(monitor.stop_requested)
                with patch.object(module.messagebox, 'askyesno', return_value=True):
                    app.request_exit()
                self.assertTrue(app.closing)
                self.assertTrue(monitor.stop_requested)
                with patch.object(root, 'destroy') as destroy:
                    app.refresh()
                    destroy.assert_not_called()
                    monitor.running = False
                    app.refresh()
                    destroy.assert_called_once()
                root.update_idletasks()
                self.assertLessEqual(root.winfo_reqwidth(), 1000)
                self.assertLessEqual(root.winfo_reqheight(), 850)
            finally:
                root.destroy()


if __name__ == '__main__': unittest.main()
