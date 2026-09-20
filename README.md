# Wi-Fi Recovery / Wi-Fi 自动恢复

Windows Wi-Fi 网络监控与自动恢复桌面程序，当前版本 **3.2**。

## 功能

- 使用 HTTPS 实际访问 Google、GitHub、百度等可配置网站，校验 TLS 证书；任一网站成功即避免不必要的恢复。
- 连续失败达到阈值后，重启无线网卡、打开 Wi-Fi 开关并连接原先保存的网络。
- 使用端与共享端模式；共享端每轮独立检查热点，即使网站正常，发现热点关闭也会自动开启。开启尝试至少间隔 30 秒；已开启或正在切换时不重复启动，使用端不管理热点。
- 状态概览、响应趋势、运行日志；检测间隔、超时、失败阈值和冷却时间可配置。
- 圆角界面、高 DPI 支持；启动时读取系统明暗主题，支持手动切换。
- 小窗口和高缩放下按需显示整页纵向、横向滚动条；支持滚轮、Shift+滚轮横向滚动和键盘焦点自动滚入视野。
- 安装后支持一次授权启动、可配置登录后自启；最小化继续监控，退出需要确认。

## 运行

在 Windows 10/11 x64 上运行 `WifiRecovery.exe`，无需安装 Python。网络恢复需要管理员权限。Windows PowerShell 5.1 是运行依赖，通常随系统提供。

独立 EXE 可以直接运行，但便携运行会请求管理员权限。一次授权和登录自启需要先安装到固定目录。在管理员 Windows PowerShell 中进入项目目录并执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\outputs\Install-DesktopApp.ps1
```

执行前需已有 `outputs/WifiRecovery.exe`（从发布页下载或自行构建）。安装脚本与 `Enable-OneTimeAuthorization.ps1` 应保持在同一目录。更新已有安装使用 `outputs/Update-DesktopApp.ps1`。

安装目录为 `%ProgramFiles%\WifiRecoveryApp`，授权任务为 `WifiRecoveryDesktopLaunch`，仅运行固定的已安装程序。日常启动不再请求 UAC；安装或更新仍需要管理员授权。设置页“开机自启”指当前用户登录 Windows 后启动，切换立即保存。其他电脑需要分别安装授权。

配置、网络配置名称和日志只保存在本机 `%LOCALAPPDATA%\WifiRecoveryApp`，不属于仓库。程序不读取或保存 Wi-Fi 密码。热点名称和密码需要提前在 Windows 设置中配置。

检测遵循系统路由，可能经过 VPN/TUN；不是强制绑定某张网卡的探测。手动禁用的网卡不会自动开启。硬件或驱动不支持热点、射频控制或无法唯一识别网卡时，界面会显示恢复错误。

## 从源码构建

使用 Windows x64 与 Python 3.12（包含 tkinter）：

```powershell
python -m pip install -r requirements-build.txt
python build.py
```

生成单文件 `outputs/WifiRecovery.exe`。工作脚本、图标和 Python 运行时已嵌入 EXE；构建缓存与 EXE 不提交到 Git。

## 验证

```powershell
python work/test_desktop_app.py
python work/test_config_equality.py
python work/test_dpi_layout.py
python work/test_refresh_efficiency.py
python work/test_system_theme.py
python work/test_theme_startup.py
python work/test_scroll_view.py
```

这些检查覆盖配置、界面、缩放、主题和模拟监控进程，不实际重启无线网卡。实际驱动恢复与登录自启需要在目标 Windows 设备上验证。

## 代码布局

- `outputs/WifiRecoveryApp.py`：控制器、配置、工作进程和授权启动。
- `outputs/WifiWorker.ps1`：HTTPS 检测、Wi-Fi 重连和热点恢复。
- `outputs/wifi_ui.py`、`rounded_theme.py`、`system_theme.py`：界面与主题。
- `outputs/startup_settings.py`：当前用户登录启动配置。
- `work/test_*.py`：回归验证。

## 开源许可

本项目原创代码和文档采用 [MIT License](LICENSE)。

Copyright (c) 2026 waxwel

允许使用、修改、分发和商业使用，包括闭源分发；复制或分发本软件或其重要部分时，须保留版权声明和完整许可声明。软件按“原样”提供，不附带任何保证。具体条款以 LICENSE 英文全文为准。

第三方依赖不因本项目采用 MIT 而改变其许可，参见 [第三方声明](THIRD_PARTY_NOTICES.md) 和 [许可文本](licenses/)。分发 EXE 时也应一并提供适用的版权和许可声明。
