$ErrorActionPreference='Stop'
$resultPath=Join-Path $PSScriptRoot 'desktop-install-result.json'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as Administrator.' }
$destination=Join-Path $env:ProgramFiles 'WifiRecoveryApp'
$source=Join-Path $PSScriptRoot 'WifiRecovery.exe'
$taskName='WifiAutoRecover'
$taskWasEnabled=$false
$taskWasRunning=$false
$changedTask=$false
try {
    if (-not (Test-Path -LiteralPath $source)) { throw 'Missing desktop executable.' }
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination (Join-Path $destination 'WifiRecovery.exe') -Force
    $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $taskWasEnabled=$task.Settings.Enabled
        $taskWasRunning=$task.State -eq 'Running'
        Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $destination 'legacy-task-backup.xml') -Encoding UTF8
        $oldStatusPath="$env:ProgramData\WifiAutoRecover\status.json"
        for ($i=0;$i -lt 40;$i++) {
            $old=Get-Content -LiteralPath $oldStatusPath -Raw | ConvertFrom-Json
            if ($old.phase -notin @('Cycling','Reconnecting') -or ((Get-Date)-[datetime]$old.updatedAt).TotalSeconds -gt 90) { break }
            Start-Sleep -Seconds 1
        }
        if ($old.phase -in @('Cycling','Reconnecting') -and ((Get-Date)-[datetime]$old.updatedAt).TotalSeconds -lt 90) { throw 'Recovery is in progress. Retry when complete.' }
        $enabledGuids=@(Get-NetAdapter -Physical | Where-Object { $_.NdisPhysicalMedium -in @(1,9) -and $_.Status -eq 'Up' } | Select-Object -ExpandProperty InterfaceGuid)
        Disable-ScheduledTask -TaskName $taskName | Out-Null
        $changedTask=$true
        Stop-ScheduledTask -TaskName $taskName
        for ($i=0;$i -lt 20;$i++) {
            if ((Get-ScheduledTask -TaskName $taskName).State -ne 'Running') { break }
            Start-Sleep -Milliseconds 250
        }
        if ((Get-ScheduledTask -TaskName $taskName).State -eq 'Running') { throw 'Legacy task did not stop.' }
        Get-NetAdapter -Physical | Where-Object { $_.InterfaceGuid -in $enabledGuids -and $_.Status -eq 'Disabled' } | Enable-NetAdapter -Confirm:$false
    }
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" | Where-Object { $_.CommandLine -like '*Program Files\WifiAutoRecover\WifiStatus.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
    $launchTime=Get-Date
    & (Join-Path $PSScriptRoot 'Enable-OneTimeAuthorization.ps1')
    Start-ScheduledTask -TaskName 'WifiRecoveryDesktopLaunch'
    $fresh=$null
    for ($i=0;$i -lt 45;$i++) {
        Start-Sleep -Seconds 1
        $newStates=@(Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\WifiRecoveryApp\runs" -Filter 'status.json' -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
        if ($newStates.Count) {
            try {
                $candidate=Get-Content -LiteralPath $newStates[0].FullName -Raw | ConvertFrom-Json
                if ($candidate.version -ge 4 -and [datetime]$candidate.startedAt -ge $launchTime.AddSeconds(-1) -and $candidate.checks -gt 0 -and $candidate.phase -ne 'Stopped') { $fresh=$candidate; break }
            } catch { }
        }
    }
    if (-not $fresh) { throw 'Desktop monitor did not publish a new successful startup heartbeat. Inspect the application log.' }
    [pscustomobject]@{ success=$true; checkedAt=(Get-Date).ToString('o'); executable=(Join-Path $destination 'WifiRecovery.exe'); legacyTaskDisabled=$true; workerPid=$fresh.pid; phase=$fresh.phase } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    $reason=$_.Exception.Message
    # Do not restart the old task while the new app might still be monitoring.
    [pscustomobject]@{ success=$false; error=$reason; legacyTaskChanged=$changedTask; wasEnabled=$taskWasEnabled; wasRunning=$taskWasRunning } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
}
