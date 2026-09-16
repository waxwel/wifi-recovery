"""Wi-Fi Recovery desktop application. Its monitor exists only for this session."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk, messagebox
import uuid
from urllib.parse import urlsplit
from worker_payload import WORKER_BYTES
import wifi_ui
import startup_settings

DEFAULTS = dict(schema=6, mode='client', wifi_profile='', interval=15, threshold=3, timeout=8, cooldown=180,
                urls=['https://www.google.com/generate_204', 'https://github.com/', 'https://www.baidu.com/'])
LIMITS = dict(interval=(5, 3600), threshold=(1, 100), timeout=(1, 30), cooldown=(30, 86400))
DATA = Path(os.environ.get('LOCALAPPDATA', '.')) / 'WifiRecoveryApp'


def validate_config(raw):
    clean = {'schema': 6, 'mode': raw.get('mode', 'client'), 'wifi_profile': str(raw.get('wifi_profile', '')).strip()}
    if len(clean['wifi_profile']) > 255 or '\n' in clean['wifi_profile'] or '\r' in clean['wifi_profile'] or '\0' in clean['wifi_profile']:
        raise ValueError('Wi-Fi 配置名称无效')
    if clean['mode'] not in ('client', 'host'):
        raise ValueError('设备模式无效')
    for key, (low, high) in LIMITS.items():
        value = str(raw.get(key, ''))
        if not value.isdecimal() or not low <= int(value) <= high:
            raise ValueError(f'{key} 必须是 {low}～{high} 的整数')
        clean[key] = int(value)
    urls = raw.get('urls', [])
    if not isinstance(urls, list) or not 1 <= len(urls) <= 10:
        raise ValueError('请保留 1～10 个检测网址')
    normalized = []
    for url in urls:
        url = str(url).strip()
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError('网址端口无效') from None
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or any(c.isspace() for c in url):
            raise ValueError('网址须以 https:// 开头，不能含账号、空格或 #片段')
        if url in normalized:
            raise ValueError('检测网址不能重复')
        normalized.append(url)
    clean['urls'] = normalized
    return clean


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class Monitor:
    def __init__(self, data_dir=DATA):
        self.directory = Path(data_dir)
        self.config_path = self.directory / 'settings.json'
        self.run_dir = self.directory / 'runs' / uuid.uuid4().hex
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.process = None
        self.output = None
        self.start_error = ''

    @property
    def alive(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.alive:
            return
        if self.output:
            self.output.close()
        self.run_dir = self.directory / 'runs' / uuid.uuid4().hex
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.start_error = ''
        # Materialize from embedded bytes for EVERY run; never depend on _MEI lifetime.
        worker = self.run_dir / 'WifiWorker.ps1'
        try:
            worker.write_bytes(WORKER_BYTES)
        except OSError as exc:
            self.start_error = f'无法准备监控脚本：{exc}'
            return
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        args = [str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                '-File', str(worker), '-ConfigPath', str(self.config_path),
                '-StatusPath', str(self.run_dir / 'status.json'), '-LogPath', str(self.run_dir / 'monitor.log'),
                '-StopPath', str(self.run_dir / 'stop'), '-WakePath', str(self.run_dir / 'wake'),
                '-ParentProcessId', str(os.getpid())]
        self.output = (self.run_dir / 'worker-output.txt').open('wb')
        try:
            self.process = subprocess.Popen(args, stdout=self.output, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.start_error = f'无法启动监控：{exc}'
            self.output.close()
            self.output = None
            self.process = None

    def request_stop(self):
        (self.run_dir / 'stop').touch()

    def wake(self):
        if self.alive:
            (self.run_dir / 'wake').touch()

    def state(self):
        try:
            return json.loads((self.run_dir / 'status.json').read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            return {}

    def log(self):
        if self.start_error:
            return self.start_error
        path = self.run_dir / 'monitor.log'
        if not path.exists():
            path = self.run_dir / 'worker-output.txt'
        try:
            with path.open('rb') as stream:
                stream.seek(0, 2)
                length = stream.tell()
                stream.seek(max(0, length - 30000))
                raw = stream.read()
                if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
                    text = raw.decode('utf-16', errors='replace')
                else:
                    try:
                        text = raw.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        text = raw.decode(f'cp{ctypes.windll.kernel32.GetACP()}', errors='replace')
            return '\n'.join(text.splitlines()[-80:])
        except OSError:
            return ''


class App:
    def __init__(self, root, monitor, autostart=True):
        self.root, self.monitor = root, monitor
        self.closing = False
        self.stopping = False
        self.user_stopped = False
        self.last_log = None
        self.status_data = {}
        self.draft_dirty = False
        try:
            previous = json.loads(monitor.config_path.read_text(encoding='utf-8-sig'))
            if previous.get('schema', 0) < 5 and 'https://www.baidu.com/' not in previous.get('urls', []) and len(previous.get('urls', [])) < 10:
                previous['urls'].append('https://www.baidu.com/')
            self.config = validate_config(previous)
        except FileNotFoundError:
            self.config = validate_config(DEFAULTS)
        except (OSError, ValueError) as exc:
            messagebox.showwarning('配置读取失败', f'将使用默认值，旧文件保留为 settings.invalid.json。\n{exc}', parent=root)
            if monitor.config_path.exists():
                monitor.config_path.replace(monitor.config_path.with_name('settings.invalid.json'))
            self.config = validate_config(DEFAULTS)
        save_json(monitor.config_path, self.config)

        wifi_ui.build(self)
        if autostart:
            monitor.start()
        self.refresh()

    def change_startup(self):
        try:
            startup_settings.set_enabled(self.startup_choice.get() == '开启')
            self.startup_note.configure(text='已开启：登录 Windows 后自动启动监控。' if self.startup_choice.get() == '开启' else '已关闭：仅手动打开程序时启动监控。')
        except OSError as exc:
            self.startup_choice.set('开启' if startup_settings.is_enabled() else '关闭')
            messagebox.showerror('启动设置未保存', str(exc), parent=self.root)

    def mark_dirty(self, *_):
        if not hasattr(self, 'url_list'):
            return
        try:
            self.draft_dirty = self.draft_config() != self.config
        except ValueError:
            self.draft_dirty = True
        if hasattr(self, 'settings_note'):
            self.settings_note.configure(text='有未保存的修改。' if self.draft_dirty else '与已保存配置一致，无需保存。')

    def draft_config(self):
        return validate_config({**{k: v.get() for k, v in self.fields.items()}, 'wifi_profile': self.wifi_profile.get(), 'mode': 'host' if self.mode.get() == '共享端' else 'client', 'urls': list(self.url_list.get(0, 'end'))})

    def select_url(self, _=None):
        selected = self.url_list.curselection()
        if selected:
            self.url_entry.delete(0, 'end')
            self.url_entry.insert(0, self.url_list.get(selected[0]))

    def change_urls(self, mode):
        urls = list(self.url_list.get(0, 'end'))
        selected = self.url_list.curselection()
        try:
            if mode == 'add':
                urls.append(self.url_entry.get().strip())
            elif not selected:
                raise ValueError('请先选择一个网址')
            elif mode == 'edit':
                urls[selected[0]] = self.url_entry.get().strip()
            else:
                urls.pop(selected[0])
            checked = validate_config({**self.config, 'urls': urls})
        except ValueError as exc:
            messagebox.showerror('网址无效', str(exc), parent=self.root)
            return
        self.url_list.delete(0, 'end')
        for url in checked['urls']:
            self.url_list.insert('end', url)
        self.mark_dirty()

    def add_url(self): self.change_urls('add')
    def edit_url(self): self.change_urls('edit')
    def delete_url(self): self.change_urls('delete')

    def save_settings(self):
        try:
            config = self.draft_config()
            if config == self.config:
                self.mark_dirty()
                return
            save_json(self.monitor.config_path, config)
            self.config = config
            self.monitor.wake()
        except (ValueError, OSError) as exc:
            messagebox.showerror('无法保存', str(exc), parent=self.root)
            return
        self.draft_dirty = False
        self.settings_note.configure(text='已保存；运行中的检测完成后，将使用新配置。连续失败计数会清零。')

    def toggle_monitor(self):
        if self.stopping:
            return
        if self.monitor.alive:
            self.stopping = True
            self.user_stopped = True
            self.monitor.request_stop()
        else:
            self.user_stopped = False
            self.monitor.start()

    def request_exit(self):
        if self.closing:
            return
        text = '退出后将停止网络检测和自动恢复。确定退出吗？'
        if self.draft_dirty:
            text += '\n尚未保存的设置修改将丢弃。'
        if not messagebox.askyesno('确认退出', text, parent=self.root, default='no'):
            return
        self.closing = True
        self.stopping = True
        self.monitor.request_stop()
        self.toggle_button.configure(state='disabled')
        self.banner.configure(text='正在停止监控，请稍候…')
        self.detail.configure(text='若正在恢复网卡，会先完成重新启用；不会强行中断恢复操作。')

    def refresh(self):
        alive = self.monitor.alive
        if self.closing and not alive:
            if self.monitor.output:
                self.monitor.output.close()
            self.root.destroy()
            return
        if self.stopping and not alive:
            self.stopping = False
        if self.root.state() == 'iconic' and not self.closing:
            # The PowerShell worker keeps monitoring; hidden widgets need no paint.
            self.root.after(500, self.refresh)
            return
        data = self.monitor.state()
        self.status_data = data
        if not self.closing:
            if self.stopping:
                label = '正在暂停，等待当前操作完成…'
            elif not alive:
                label = '监控已暂停' if self.user_stopped else '监控未运行 · 请查看日志'
            else:
                labels = dict(Starting='正在启动', Checking='正在访问网站…', Online='网站 HTTPS 访问正常',
                              Degraded='部分网站不可达 · 保持连接', Offline='所有网站访问失败', Disconnected='Wi-Fi 未连接',
                              Disabled='Wi-Fi 网卡已禁用', Cycling='正在重启无线网卡', EnablingRadio='正在打开 Windows Wi-Fi 开关', Reconnecting='正在连接原 Wi-Fi 网络', Error='恢复操作异常 · 查看日志', StartingHotspot='正在开启移动热点', HotspotError='热点恢复失败 · 等待重试')
                label = labels.get(data.get('phase'), '正在启动检测…')
            self.banner.configure(text=label)
            self.toggle_button.configure(text='开始监控' if not alive else '暂停监控', state='disabled' if self.stopping else 'normal')
        table_key = (data.get('targets', self.config['urls']), data.get('probes', []))
        if table_key != getattr(self, '_table_key', None):
            self._table_key = table_key
            table_scroll = self.table.yview()[0]
            self.table.delete(*self.table.get_children())
            results = {p['target']: p for p in data.get('probes', [])}
            for url in data.get('targets', self.config['urls']):
                probe = results.get(url, {})
                label = {'Success': '成功', 'Timeout': '超时', 'Error': '连接 / TLS / DNS 失败', 'HttpError': 'HTTP 响应异常', 'WifiNotConnected': 'Wi-Fi 未连接，已跳过'}.get(probe.get('status'), '等待检测')
                if probe.get('httpStatus') and probe.get('status') != 'WifiNotConnected':
                    label += f' · {probe["httpStatus"]}'
                elapsed = f'{probe["latencyMs"]} ms' if probe.get('latencyMs') is not None else '—'
                tag = 'success' if probe.get('status') == 'Success' else 'waiting' if probe.get('status') in (None, 'WifiNotConnected') else 'error'
                self.table.insert('', 'end', values=(url, label, elapsed), tags=(tag,))
            self.table.yview_moveto(table_scroll)
        self.draw_chart()
        log = self.monitor.log()
        if log != self.last_log:
            self.log_text.configure(state='normal')
            self.log_text.delete('1.0', 'end')
            self.log_text.insert('1.0', log)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
            self.last_log = log
        wifi_ui.update(self, data, alive)
        self.root.after(500, self.refresh)

    def draw_chart(self):
        wifi_ui.draw_chart(self)


def launch_authorized_task():
    """Only the protected installed executable may use the fixed launch task."""
    installed = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'WifiRecoveryApp' / 'WifiRecovery.exe'
    if not getattr(sys, 'frozen', False) or Path(sys.executable).resolve() != installed.resolve():
        return False
    try:
        result = subprocess.run(
            [str(Path(os.environ['SystemRoot']) / 'System32' / 'schtasks.exe'),
             '/Run', '/TN', 'WifiRecoveryDesktopLaunch'],
            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    # Must run before Tk creates any HWND; render fonts at native screen DPI.
    ctypes.windll.user32.SetProcessDPIAware()
    if '--self-test' in sys.argv:
        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            monitor = Monitor(temporary)
            app = App(root, monitor, autostart=False)
            root.update()
            root.destroy()
            (Path(sys.argv[sys.argv.index('--self-test') + 1]) if len(sys.argv) > sys.argv.index('--self-test') + 1 else Path(temporary) / 'test.txt').write_text('GUI self-test passed', encoding='utf-8')
        return
    if not ctypes.windll.shell32.IsUserAnAdmin():
        if launch_authorized_task():
            return
        args = sys.argv[1:] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve()), *sys.argv[1:]]
        previous_reset = os.environ.get('PYINSTALLER_RESET_ENVIRONMENT')
        os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        try:
            result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, subprocess.list2cmdline(args), None, 1)
        finally:
            if previous_reset is None:
                os.environ.pop('PYINSTALLER_RESET_ENVIRONMENT', None)
            else:
                os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = previous_reset
        if result <= 32:
            messagebox.showerror('需要管理员权限', '未获得管理员权限，程序没有启动监控。')
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, 'Local\\WifiRecoveryDesktopApp')
    if not handle or ctypes.get_last_error() == 183:
        messagebox.showinfo('程序已打开', 'Wi-Fi 自动恢复已经在运行，请查看现有窗口。')
        return
    monitor = Monitor()
    root = tk.Tk()
    try:
        App(root, monitor)
        root.mainloop()
    finally:
        monitor.request_stop()
        if monitor.alive:
            # Orderly exit only: the worker always re-enables its adapter first.
            monitor.process.wait()
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
