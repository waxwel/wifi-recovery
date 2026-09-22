"""Current-user logon startup; the installed app uses its preauthorized task."""
import os
from pathlib import Path
import winreg
import base64
import shutil
import subprocess
import sys
import tempfile
from authorization_payload import AUTHORIZATION_SCRIPT

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'WifiRecoveryDesktop'


def installed_executable():
    return Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'WifiRecoveryApp' / 'WifiRecovery.exe'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return value == f'"{installed_executable()}"'
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    if enabled:
        prepare_startup()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, f'"{installed_executable()}"')
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


def prepare_startup():
    """Install the standalone EXE and its fixed elevated launch task before opting in."""
    if not getattr(sys, 'frozen', False):
        raise OSError('请使用打包后的 EXE 设置开机自启。')
    source = Path(sys.executable).resolve()
    destination = installed_executable()
    if source != destination.resolve():
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Copy fully before replacing; a locked installation remains intact on failure.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.new', delete=False) as stream:
                temporary = Path(stream.name)
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        except OSError as exc:
            raise OSError('无法安装自启副本，请退出其他正在运行的版本后重试。\n' + str(exc)) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = base64.b64encode(AUTHORIZATION_SCRIPT.encode('utf-16le')).decode('ascii')
    try:
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-EncodedCommand', command],
                                capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError('自动启动授权任务配置失败，请重试。') from exc
    if result.returncode != 0:
        raise OSError('无法配置自动启动任务，请确认以管理员权限运行。')
