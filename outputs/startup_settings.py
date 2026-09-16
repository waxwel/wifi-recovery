"""Current-user logon startup; the installed app uses its preauthorized task."""
import os
from pathlib import Path
import winreg

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
    if enabled and not installed_executable().is_file():
        raise OSError('请先安装程序，再启用登录后自动启动。')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, f'"{installed_executable()}"')
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
