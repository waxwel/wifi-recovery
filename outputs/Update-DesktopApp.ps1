$ErrorActionPreference='Stop'
$resultPath=Join-Path $PSScriptRoot 'desktop-upgrade-result.json'
try {
    $destination=Join-Path $env:ProgramFiles 'WifiRecoveryApp\WifiRecovery.exe'
    $source=Join-Path $PSScriptRoot 'WifiRecovery.exe'
    if (-not (Test-Path -LiteralPath $source)) { throw 'Missing new executable.' }
    $states=@(Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\WifiRecoveryApp\runs" -Filter status.json -Recurse | Sort-Object LastWriteTime -Descending)
    if ($states.Count) {
        $state=Get-Content -LiteralPath $states[0].FullName -Raw | ConvertFrom-Json
        if ($state.phase -ne 'Stopped') {
            Set-Content -LiteralPath (Join-Path $states[0].DirectoryName 'stop') -Value 'upgrade'
            for ($i=0;$i -lt 60;$i++) {
                Start-Sleep -Seconds 1
                $state=Get-Content -LiteralPath $states[0].FullName -Raw | ConvertFrom-Json
                if ($state.phase -eq 'Stopped' -or -not (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) { break }
            }
            if ($state.phase -ne 'Stopped' -and (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) { throw 'Monitor is still finishing recovery. Update aborted.' }
        }
    }
    $allowedPaths=@($destination,$source,(Join-Path $PSScriptRoot 'WifiRecovery-HD.exe'))
    $apps=@(Get-CimInstance Win32_Process -Filter "Name = 'WifiRecovery.exe' OR Name = 'WifiRecovery-HD.exe'" | Where-Object { $_.ExecutablePath -in $allowedPaths })
    foreach ($app in $apps) { Stop-Process -Id $app.ProcessId -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    Copy-Item -LiteralPath $destination -Destination "$destination.backup" -Force
    for ($copyAttempt=0;$copyAttempt -lt 15;$copyAttempt++) {
        try { Copy-Item -LiteralPath $source -Destination $destination -Force; break } catch { if ($copyAttempt -eq 14) { throw }; Start-Sleep -Seconds 1 }
    }
    $started=Get-Date
    & (Join-Path $PSScriptRoot 'Enable-OneTimeAuthorization.ps1')
    Start-ScheduledTask -TaskName 'WifiRecoveryDesktopLaunch'
    $fresh=$null
    for ($i=0;$i -lt 45;$i++) {
        Start-Sleep -Seconds 1
        $newStates=@(Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\WifiRecoveryApp\runs" -Filter status.json -Recurse | Sort-Object LastWriteTime -Descending)
        $candidate=Get-Content -LiteralPath $newStates[0].FullName -Raw | ConvertFrom-Json
        if ($candidate.version -eq 7 -and [datetime]$candidate.startedAt -ge $started.AddSeconds(-1) -and $candidate.checks -gt 0) { $fresh=$candidate; break }
    }
    if (-not $fresh) { throw 'New app did not publish a heartbeat.' }
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) { throw 'Installed executable does not match release.' }
    foreach ($oldFile in @("$destination.backup",(Join-Path $PSScriptRoot 'WifiRecovery-HD.exe'))) {
        if (Test-Path -LiteralPath $oldFile) { Remove-Item -LiteralPath $oldFile -Force }
    }
    $shell=New-Object -ComObject WScript.Shell
    foreach ($shortcutPath in @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Wi-Fi 自动恢复状态.lnk'),(Join-Path $PSScriptRoot 'Wi-Fi 自动恢复状态.lnk'))) {
        $shortcut=$shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath=$destination
        $shortcut.IconLocation="$destination,0"
        $shortcut.WorkingDirectory=Split-Path $destination
        $shortcut.Save()
    }
    [pscustomobject]@{ success=$true; checkedAt=(Get-Date).ToString('o'); version=$fresh.version; mode=$fresh.mode; phase=$fresh.phase; targets=$fresh.targets } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    [pscustomobject]@{ success=$false; error=$_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
}
