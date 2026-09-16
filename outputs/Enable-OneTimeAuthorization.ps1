$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as Administrator.' }
$executable=Join-Path $env:ProgramFiles 'WifiRecoveryApp\WifiRecovery.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Install WifiRecovery first.' }
$action=New-ScheduledTaskAction -Execute $executable -WorkingDirectory (Split-Path $executable)
$taskPrincipal=New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'WifiRecoveryDesktopLaunch' -Action $action -Principal $taskPrincipal -Settings $settings -Description 'Manually launch the installed Wi-Fi Recovery desktop app. No automatic trigger.' -Force | Out-Null
# Allow this account to read/run, but not modify the elevated task from a normal token.
$service=New-Object -ComObject 'Schedule.Service'
$service.Connect()
$task=$service.GetFolder('\').GetTask('WifiRecoveryDesktopLaunch')
$task.SetSecurityDescriptor(('D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGX;;;'+$identity.User.Value+')'),0)
