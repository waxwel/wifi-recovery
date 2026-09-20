# Requires Windows PowerShell 5.1 and Administrator privileges.
[CmdletBinding()]
param(
    [string]$WifiAdapterName = '',
    [string[]]$HttpsTargets = @('https://www.google.com/generate_204', 'https://github.com/', 'https://www.baidu.com/'),
    [ValidateRange(5, 3600)][int]$IntervalSeconds = 15,
    [ValidateRange(1, 100)][int]$FailureThreshold = 3,
    [ValidateRange(1, 30)][int]$HttpTimeoutSeconds = 8,
    [ValidateRange(1, 60)][int]$OffSeconds = 3,
    [ValidateRange(5, 300)][int]$ReconnectSeconds = 20,
    [ValidateRange(30, 86400)][int]$CooldownSeconds = 180,
    [string]$LogPath = "$env:ProgramData\WifiAutoRecover\monitor.log",
    [string]$StatusPath = "$env:ProgramData\WifiAutoRecover\status.json",
    [string]$ConfigPath = '',
    [string]$StopPath = '',
    [string]$WakePath = '',
    [int]$ParentProcessId = 0
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script as Administrator.'
}
if (-not $HttpsTargets.Count -or $HttpsTargets.Count -gt 10) {
    throw 'Provide between 1 and 10 HTTPS targets.'
}
foreach ($target in $HttpsTargets) {
    $uri = $null
    if (-not [uri]::TryCreate($target, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or $uri.UserInfo) {
        throw 'Targets must be absolute HTTPS URLs without embedded credentials.'
    }
}
Add-Type -AssemblyName System.Net.Http
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Write-MonitorLog([string]$Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    try {
        $directory = Split-Path -Parent $LogPath
        if ($directory) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
        if ((Test-Path -LiteralPath $LogPath) -and (Get-Item -LiteralPath $LogPath).Length -gt 5MB) {
            Move-Item -LiteralPath $LogPath -Destination "$LogPath.1" -Force
        }
        Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    } catch {
        Write-Warning "Could not write log: $($_.Exception.Message)"
    }
}

function Test-MonitorStop {
    if ($StopPath -and (Test-Path -LiteralPath $StopPath)) { return $true }
    if ($ParentProcessId -gt 0 -and -not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) { return $true }
    return $false
}

function Wait-MonitorDelay([int]$Seconds) {
    $deadline = [datetime]::UtcNow.AddSeconds($Seconds)
    while ([datetime]::UtcNow -lt $deadline) {
        if (Test-MonitorStop) { return }
        if ($WakePath -and (Test-Path -LiteralPath $WakePath)) { return }
        Start-Sleep -Milliseconds 250
    }
}

function Read-MonitorConfiguration {
    if (-not $ConfigPath) { return $null }
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    if ($config.mode -and $config.mode -notin @('client','host')) { throw 'Invalid device mode.' }
    foreach ($spec in @(@('interval',5,3600),@('threshold',1,100),@('timeout',1,30),@('cooldown',30,86400))) {
        $value = $config.($spec[0])
        if ($null -eq $value -or [double]$value -ne [int]$value -or $value -lt $spec[1] -or $value -gt $spec[2]) { throw "Invalid configuration field: $($spec[0])" }
    }
    if (@($config.urls).Count -lt 1 -or @($config.urls).Count -gt 10) { throw 'Provide 1-10 HTTPS URLs.' }
    foreach ($url in $config.urls) {
        $parsed=$null
        if (-not [uri]::TryCreate($url,[UriKind]::Absolute,[ref]$parsed) -or $parsed.Scheme -ne 'https' -or $parsed.UserInfo) { throw 'Invalid HTTPS URL.' }
    }
    return $config
}

function Get-SelectedWifiAdapter {
    $adapters = @(Get-NetAdapter -Physical | Where-Object {
        $_.NdisPhysicalMedium -in @(1, 9)
    })
    if ($WifiAdapterName) {
        $adapters = @($adapters | Where-Object { $_.Name -eq $WifiAdapterName })
    } else {
        $adapters = @($adapters | Where-Object { $_.Status -ne 'Not Present' })
        $up = @($adapters | Where-Object { $_.Status -eq 'Up' })
        if ($up.Count -eq 1) { $adapters=$up }
    }
    if ($adapters.Count -ne 1) {
        throw 'Cannot select exactly one physical Wi-Fi adapter. Supply -WifiAdapterName with its exact name.'
    }
    return $adapters[0]
}

function Get-HotspotManager {
    $null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
    $null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
    $profiles=@([Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles())
    $profile=$profiles | Where-Object { $_.NetworkAdapter.NetworkAdapterId -eq $adapterGuid } | Select-Object -First 1
    if (-not $profile) { throw 'Wi-Fi upstream profile is not ready. Hotspot will be retried.' }
    return [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
}

function Initialize-WifiNative {
    if ('WifiNative6' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class WifiNative6 {
 [DllImport("wlanapi.dll")] static extern uint WlanOpenHandle(uint v,IntPtr r,out uint negotiated,out IntPtr handle);
 [DllImport("wlanapi.dll")] static extern uint WlanCloseHandle(IntPtr h,IntPtr r);
 [DllImport("wlanapi.dll")] static extern void WlanFreeMemory(IntPtr p);
 [DllImport("wlanapi.dll")] static extern uint WlanQueryInterface(IntPtr h,ref Guid id,int opcode,IntPtr reserved,out uint size,out IntPtr data,out int kind);
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Parameters {
  public int mode; [MarshalAs(UnmanagedType.LPWStr)] public string profile;
  public IntPtr ssid; public IntPtr bssids; public int bssType; public uint flags;
 }
 [DllImport("wlanapi.dll",CharSet=CharSet.Unicode)] static extern uint WlanConnect(IntPtr h,ref Guid id,ref Parameters p,IntPtr r);
 static IntPtr Open() { uint v; IntPtr h; uint code=WlanOpenHandle(2,IntPtr.Zero,out v,out h); if(code!=0)throw new Win32Exception((int)code); return h; }
 public static string CurrentProfile(Guid id) {
  IntPtr h=Open(), data=IntPtr.Zero;
  try { uint size; int kind; uint code=WlanQueryInterface(h,ref id,7,IntPtr.Zero,out size,out data,out kind);
   if(code==5023 || code==1168)return null;
   if(code!=0)throw new Win32Exception((int)code);
   if(size<520 || Marshal.ReadInt32(data)!=1)return null;
   return Marshal.PtrToStringUni(IntPtr.Add(data,8),256).TrimEnd('\0');
  } finally { if(data!=IntPtr.Zero)WlanFreeMemory(data); WlanCloseHandle(h,IntPtr.Zero); }
 }
 public static void Connect(Guid id,string profile) {
  IntPtr h=Open(); try { Parameters p=new Parameters {mode=0,profile=profile,bssType=1};
   uint code=WlanConnect(h,ref id,ref p,IntPtr.Zero); if(code!=0)throw new Win32Exception((int)code);
  } finally { WlanCloseHandle(h,IntPtr.Zero); }
 }
}
'@
}

function Get-CurrentWifiProfile {
    Initialize-WifiNative
    return [WifiNative6]::CurrentProfile($adapterGuid)
}

function Wait-WinRtResult($Operation,[type]$ResultType) {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $converter=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task=$converter.MakeGenericMethod($ResultType).Invoke($null,@($Operation))
    if (-not $task.Wait(15000)) { throw 'Windows radio operation timed out.' }
    return ,$task.Result
}

function Get-AvailableWifiRadios {
    $radioType=[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]
    $listType=[System.Collections.Generic.IReadOnlyList``1].MakeGenericType($radioType)
    $radios=Wait-WinRtResult ($radioType::GetRadiosAsync()) $listType
    return @($radios | Where-Object { [string]$_.Kind -eq 'WiFi' })
}

function Get-WifiRadio([int]$WaitSeconds=0) {
    # Adapter enable may return before the driver republishes its WinRT radio.
    $deadline=[datetime]::UtcNow.AddSeconds($WaitSeconds)
    do {
        $wifi=@(Get-AvailableWifiRadios)
        $matched=@($wifi | Where-Object { $_.Name -eq $adapter.Name })
        if ($matched.Count -eq 1) { return $matched[0] }
        if ($wifi.Count -eq 1) { return $wifi[0] }
        $matched=@($wifi | Where-Object { $_.Name -eq $adapter.InterfaceDescription })
        if ($matched.Count -eq 1) { return $matched[0] }
        if ([datetime]::UtcNow -ge $deadline) { break }
        Write-MonitorStatus 'EnablingRadio'
        Start-Sleep -Milliseconds 1000
    } while ($true)
    if (-not $wifi.Count) { throw "Wi-Fi radio is not available after waiting ${WaitSeconds}s for the driver. Adapter=$($adapter.Name)." }
    $names=($wifi | ForEach-Object { "$($_.Name) [$($_.State)]" }) -join '; '
    throw "Multiple Wi-Fi radios remain ambiguous after ${WaitSeconds}s. Adapter=$($adapter.Name); candidates=$names"
}

function Enable-WifiRadio {
    $radio=Get-WifiRadio -WaitSeconds 30
    if ([string]$radio.State -eq 'On') { return 'On' }
    $accessType=[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]
    $null=[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime]
    $access=Wait-WinRtResult ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) $accessType
    if ([string]$access -ne 'Allowed') { throw "Windows denied Wi-Fi radio access: $access" }
    $result=Wait-WinRtResult ($radio.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) $accessType
    if ([string]$result -ne 'Allowed') { throw "Could not turn on Wi-Fi: $result" }
    for ($i=0;$i -lt 20;$i++) {
        if ([string]$radio.State -eq 'On') { return 'On' }
        Start-Sleep -Milliseconds 250
    }
    throw 'Wi-Fi switch did not reach On. Check hardware switch or airplane mode.'
}

function Connect-SavedWifi([string]$Profile) {
    if ([string]::IsNullOrWhiteSpace($Profile)) { throw 'No remembered Wi-Fi profile. Connect once in Windows or set a saved profile in the app.' }
    Initialize-WifiNative
    if ((Get-CurrentWifiProfile) -eq $Profile) { return $Profile }
    [WifiNative6]::Connect($adapterGuid,$Profile)
    $deadline=[datetime]::UtcNow.AddSeconds($ReconnectSeconds)
    while ([datetime]::UtcNow -lt $deadline) {
        if ((Get-CurrentWifiProfile) -eq $Profile) { return $Profile }
        if (Test-MonitorStop) { throw 'Stopped while waiting for Wi-Fi association; the Wi-Fi radio remains on.' }
        Start-Sleep -Milliseconds 500
    }
    throw 'Wi-Fi reconnection timed out. Check saved password, signal and network availability.'
}

function Enable-MobileHotspot {
    $manager=Get-HotspotManager
    if ([string]$manager.TetheringOperationalState -eq 'On') { return 'On' }
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $resultType=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
    $operation=$manager.StartTetheringAsync()
    $converter=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task=$converter.MakeGenericMethod($resultType).Invoke($null,@($operation))
    if (-not $task.Wait(30000)) { throw 'Hotspot start timed out; state will be checked on retry.' }
    $result=$task.Result
    if ([string]$result.Status -ne 'Success') { throw "Hotspot start failed: $($result.Status) $($result.AdditionalErrorMessage)" }
    if ([string]$manager.TetheringOperationalState -ne 'On') { throw 'Hotspot did not reach On state.' }
    return 'On'
}

function Write-MonitorStatus([string]$Phase) {
    if (-not $script:monitorStatus) { return }
    try {
        $script:monitorStatus.phase = $Phase
        $script:monitorStatus.updatedAt = (Get-Date).ToString('o')
        $script:monitorStatus.failures = $failures
        $script:monitorStatus.cooldownRemaining = if ($lastReset -eq [datetime]::MinValue) { 0 } else {
            [math]::Max(0, [math]::Ceiling($CooldownSeconds - ((Get-Date) - $lastReset).TotalSeconds))
        }
        $directory = Split-Path -Parent $StatusPath
        if ($directory) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
        $temporaryPath = "$StatusPath.$PID.tmp"
        $json = $script:monitorStatus | ConvertTo-Json -Depth 6
        [IO.File]::WriteAllText($temporaryPath, $json, (New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($StatusPath)) { [IO.File]::Replace($temporaryPath, $StatusPath, [System.Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($temporaryPath, $StatusPath) }
    } catch { Write-Warning "Could not write status: $($_.Exception.Message)" }
}

function Invoke-HttpsProbe([string]$Target) {
    $handler = New-Object System.Net.Http.HttpClientHandler
    # Follow OS routing (including TUN), without depending on a user's proxy settings.
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [timespan]::FromSeconds($HttpTimeoutSeconds)
    $request = New-Object System.Net.Http.HttpRequestMessage([Net.Http.HttpMethod]::Head, $Target)
    $request.Headers.TryAddWithoutValidation('Cache-Control', 'no-cache, no-store') | Out-Null
    $request.Headers.TryAddWithoutValidation('User-Agent', 'WifiAutoRecover/3.0') | Out-Null
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $response = $null
    $result = [ordered]@{ target=$Target; status='Error'; httpStatus=$null; latencyMs=$null; error=$null }
    try {
        $response = $client.SendAsync($request, [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $code = [int]$response.StatusCode
        $result.httpStatus = $code
        $expected = if (([uri]$Target).AbsolutePath -eq '/generate_204') { $code -eq 204 } else { $code -ge 200 -and $code -lt 300 }
        $result.status = if ($expected) { 'Success' } else { 'HttpError' }
        if (-not $expected) { $result.error = "Unexpected HTTP status: $code" }
    } catch {
        $result.error = $_.Exception.GetBaseException().Message
        if ($_.Exception.ToString() -match 'TaskCanceled|OperationCanceled') { $result.status = 'Timeout' }
    } finally {
        $timer.Stop()
        $result.latencyMs = $timer.ElapsedMilliseconds
        if ($null -ne $response) { $response.Dispose() }
        $request.Dispose()
        $client.Dispose()
    }
    return [pscustomobject]$result
}

function Test-Connectivity {
    $script:probeResults = @()
    $script:probeRoute = $null
    $link = @(Get-NetAdapter -Physical | Where-Object { $_.InterfaceGuid -eq $adapterGuid })
    $script:wifiLinkStatus = if ($link.Count -eq 1) { [string]$link[0].Status } else { 'Missing' }
    if ($script:wifiLinkStatus -ne 'Up') {
        foreach ($target in $HttpsTargets) {
            $script:probeResults += [pscustomobject]@{ target=$target; status='WifiNotConnected'; latencyMs=$null }
        }
        return $false
    }
    $script:probeRoute = 'System routing / TUN'
    foreach ($target in $HttpsTargets) {
        if (Test-MonitorStop) { return $false }
        $script:probeResults += Invoke-HttpsProbe $target
    }
    # Wi-Fi may have been switched off while an HTTPS request was pending.
    $link = @(Get-NetAdapter -Physical | Where-Object { $_.InterfaceGuid -eq $adapterGuid })
    $script:wifiLinkStatus = if ($link.Count -eq 1) { [string]$link[0].Status } else { 'Missing' }
    if ($script:wifiLinkStatus -ne 'Up') {
        foreach ($probe in $script:probeResults) { $probe.status='WifiNotConnected' }
        return $false
    }
    return @($script:probeResults | Where-Object { $_.status -eq 'Success' }).Count -gt 0
}

# A global mutex prevents a manual run and the scheduled task from running together.
$mutex = New-Object System.Threading.Mutex($false, 'Global\WifiAutoRecoverMonitor')
$ownsMutex = $false
try {
    try { $ownsMutex = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { throw 'Another Wi-Fi monitor is already running.' }
    $adapter = Get-SelectedWifiAdapter
    $adapterGuid = $adapter.InterfaceGuid
    Write-MonitorLog "Started. Adapter=$($adapter.Name); HTTPS targets=$($HttpsTargets -join ','); interval=${IntervalSeconds}s; threshold=$FailureThreshold."
    $failures = 0
    $lastReset = [datetime]::MinValue
    $deviceMode='client'
    $hotspotPending=$false
    $lastHotspotAttempt=[datetime]::MinValue
    $lastWifiProfile=''
    $preferredWifiProfile=''
    $profileCache=if ($ConfigPath) { Join-Path (Split-Path -Parent $ConfigPath) 'last-wifi-profile.json' } else { '' }
    if ($profileCache -and (Test-Path -LiteralPath $profileCache)) {
        try { $cached=Get-Content -LiteralPath $profileCache -Raw | ConvertFrom-Json; if ([string]$cached.adapter -eq [string]$adapterGuid) { $lastWifiProfile=[string]$cached.profile } } catch { }
    }
    $script:monitorStatus = [ordered]@{
        version=7; wifiRadio='Unknown'; wifiProfile=$lastWifiProfile; mode='client'; hotspotState='Unmanaged'; hotspotError=$null; probeMode='HTTPS'; pid=$PID; startedAt=(Get-Date).ToString('o'); updatedAt=$null
        adapter=$adapter.Name; adapterStatus=[string]$adapter.Status; probeInterface=$null
        targets=@($HttpsTargets); phase='Starting'; failures=0
        intervalSeconds=$IntervalSeconds; failureThreshold=$FailureThreshold
        cooldownSeconds=$CooldownSeconds; cooldownRemaining=0
        staleAfterSeconds=[math]::Max(90, $IntervalSeconds + $ReconnectSeconds + $OffSeconds + ($HttpsTargets.Count * [math]::Max(20, $HttpTimeoutSeconds)) + 30)
        checks=0; failedChecks=0; recoveryAttempts=0; lastRecoveryAt=$null
        lastCheckAt=$null; online=$null; probes=@(); history=@(); lastError=$null
    }
    Write-MonitorStatus 'Starting'
    $previousConfig = ''
    while ($true) {
        if (Test-MonitorStop) { break }
        if ($WakePath -and (Test-Path -LiteralPath $WakePath)) { Remove-Item -LiteralPath $WakePath -Force }
        if ($ConfigPath) {
            try {
                $configuration = Read-MonitorConfiguration
                $configSignature = $configuration | ConvertTo-Json -Compress
                if ($configSignature -ne $previousConfig) {
                    $IntervalSeconds=[int]$configuration.interval
                    $FailureThreshold=[int]$configuration.threshold
                    $HttpTimeoutSeconds=[int]$configuration.timeout
                    $CooldownSeconds=[int]$configuration.cooldown
                    $HttpsTargets=@($configuration.urls)
                    $preferredWifiProfile=[string]$configuration.wifi_profile
                    $deviceMode=if ($configuration.mode) { [string]$configuration.mode } else { 'client' }
                    $script:monitorStatus.mode=$deviceMode
                    if ($deviceMode -eq 'client') { $hotspotPending=$false; $script:monitorStatus.hotspotState='Unmanaged'; $script:monitorStatus.hotspotError=$null }
                    $failures=0
                    $previousConfig=$configSignature
                    $script:monitorStatus.targets=@($HttpsTargets)
                    $script:monitorStatus.intervalSeconds=$IntervalSeconds
                    $script:monitorStatus.failureThreshold=$FailureThreshold
                    $script:monitorStatus.cooldownSeconds=$CooldownSeconds
                    $script:monitorStatus.staleAfterSeconds=[math]::Max(90,$IntervalSeconds + $ReconnectSeconds + $OffSeconds + ($HttpsTargets.Count * [math]::Max(20,$HttpTimeoutSeconds)) + 30)
                    Write-MonitorLog 'Configuration applied.'
                }
            } catch { Write-MonitorLog "Configuration rejected; retaining previous settings: $($_.Exception.Message)" }
        }
        try {
            $currentProfile=Get-CurrentWifiProfile
            if ($currentProfile -and $currentProfile -ne $lastWifiProfile) {
                $lastWifiProfile=$currentProfile
                if ($profileCache) { @{ adapter=[string]$adapterGuid; profile=$lastWifiProfile } | ConvertTo-Json | Set-Content -LiteralPath $profileCache -Encoding UTF8 }
            }
            $script:monitorStatus.wifiProfile=$lastWifiProfile
        } catch { }
        try { $script:monitorStatus.wifiRadio=[string](Get-WifiRadio).State } catch { $script:monitorStatus.wifiRadio='Unknown' }
        Write-MonitorStatus 'Checking'
        $connected = Test-Connectivity
        if (Test-MonitorStop) { break }
        $script:monitorStatus.adapterStatus = $script:wifiLinkStatus
        $script:monitorStatus.probeInterface = $script:probeRoute
        $script:monitorStatus.checks++
        $script:monitorStatus.online = $connected
        $script:monitorStatus.lastCheckAt = (Get-Date).ToString('o')
        $script:monitorStatus.probes = @($script:probeResults)
        $successProbe = @($script:probeResults | Where-Object { $_.status -eq 'Success' })
        $latency = if ($successProbe.Count) { $successProbe[0].latencyMs } else { $null }
        $point = [pscustomobject]@{ time=$script:monitorStatus.lastCheckAt; online=$connected; latencyMs=$latency }
        $script:monitorStatus.history = @(@($script:monitorStatus.history) + $point | Select-Object -Last 120)
        $phase = if ($connected) { 'Online' } else { 'Offline' }
        if ($connected -and $successProbe.Count -lt $HttpsTargets.Count) { $phase = 'Degraded' }
        if ($script:wifiLinkStatus -eq 'Disabled') { $phase = 'Disabled' }
        elseif ($script:wifiLinkStatus -ne 'Up') { $phase = 'Disconnected' }
        if ($connected) {
            if ($failures -gt 0) { Write-MonitorLog 'Connectivity restored.' }
            $failures = 0
            $script:monitorStatus.lastError = $null
        } else {
            $script:monitorStatus.failedChecks++
            $failures++
            if ($script:wifiLinkStatus -eq 'Up') {
                Write-MonitorLog "All HTTPS targets failed. Consecutive failures=$failures."
            } else {
                Write-MonitorLog "Wi-Fi link is $script:wifiLinkStatus; skipping HTTPS. Consecutive failures=$failures."
            }
            if ($script:wifiLinkStatus -eq 'Disabled' -and $failures -eq 1) { Write-MonitorLog 'Adapter was already disabled; respecting manual disable.' }
            if ($script:wifiLinkStatus -ne 'Disabled' -and $failures -ge $FailureThreshold -and ((Get-Date) - $lastReset).TotalSeconds -ge $CooldownSeconds) {
                $lastReset = Get-Date
                try {
                    $current = @(Get-NetAdapter -Physical | Where-Object { $_.InterfaceGuid -eq $adapterGuid })
                    if ($current.Count -ne 1) { throw 'Selected adapter is currently missing.' }
                    if ($current[0].Status -eq 'Disabled') {
                        $phase = 'Disabled'
                        Write-MonitorLog 'Adapter was already disabled; respecting manual disable.'
                    } else {
                        $script:monitorStatus.recoveryAttempts++
                        $script:monitorStatus.lastRecoveryAt = (Get-Date).ToString('o')
                        Write-MonitorStatus 'Cycling'
                        Write-MonitorLog "Cycling Wi-Fi adapter: $($current[0].Name)."
                        # Always attempt to enable again, including after a disable error.
                        try {
                            $current[0] | Disable-NetAdapter -Confirm:$false -ErrorAction Stop
                            Wait-MonitorDelay $OffSeconds
                        } finally {
                            $enabled = $false
                            for ($attempt = 1; $attempt -le 3; $attempt++) {
                                try {
                                    $fresh = Get-NetAdapter -Physical | Where-Object { $_.InterfaceGuid -eq $adapterGuid }
                                    if (-not $fresh) { throw 'Adapter not found while enabling.' }
                                    $fresh | Enable-NetAdapter -Confirm:$false -ErrorAction Stop
                                    $enabled = $true
                                    break
                                } catch {
                                    Write-MonitorLog "Enable attempt $attempt failed: $($_.Exception.Message)"
                                    Wait-MonitorDelay 3
                                }
                            }
                            if (-not $enabled) { throw 'Could not enable Wi-Fi. Manual intervention is required.' }
                        }
                        Write-MonitorStatus 'EnablingRadio'
                        $script:monitorStatus.wifiRadio=Enable-WifiRadio
                        Write-MonitorLog 'Windows Wi-Fi switch is On.'
                        Write-MonitorStatus 'Reconnecting'
                        $targetProfile=if ($preferredWifiProfile) { $preferredWifiProfile } else { $lastWifiProfile }
                        $script:monitorStatus.wifiProfile=Connect-SavedWifi $targetProfile
                        $phase = 'Reconnecting'
                        Write-MonitorLog 'Wi-Fi enabled; resuming connectivity checks.'
                        Write-MonitorLog 'Saved Wi-Fi profile connection confirmed.'
                        if ($deviceMode -eq 'host') { $hotspotPending=$true; $lastHotspotAttempt=[datetime]::MinValue }
                        $failures = 0
                    }
                } catch {
                    $phase = 'Error'
                    $script:monitorStatus.lastError = $_.Exception.Message
                    Write-MonitorLog "Recovery failed: $($_.Exception.Message)"
                }
            }
        }
        # Hotspot health is independent of HTTPS health, including on first startup.
        # Re-read even during retry cooldown so an external successful start clears errors.
        if ($deviceMode -eq 'host' -and -not (Test-MonitorStop)) {
            try {
                $script:monitorStatus.hotspotState=[string](Get-HotspotManager).TetheringOperationalState
                switch ($script:monitorStatus.hotspotState) {
                    'On' { $hotspotPending=$false; $script:monitorStatus.hotspotError=$null }
                    'Off' { $hotspotPending=$true }
                    'InTransition' { $hotspotPending=$false; $script:monitorStatus.hotspotError=$null }
                    default { $hotspotPending=$true; $script:monitorStatus.hotspotError='Hotspot state is not available.' }
                }
            } catch {
                $hotspotPending=$true
                $script:monitorStatus.hotspotState='Unknown'
                $script:monitorStatus.hotspotError=$_.Exception.Message
            }
        }
        if ($deviceMode -eq 'host' -and $hotspotPending -and $script:monitorStatus.hotspotState -eq 'Off' -and $phase -ne 'Error' -and $script:wifiLinkStatus -ne 'Disabled' -and -not (Test-MonitorStop) -and ((Get-Date)-$lastHotspotAttempt).TotalSeconds -ge 30) {
            $lastHotspotAttempt=Get-Date
            Write-MonitorStatus 'StartingHotspot'
            try {
                $script:monitorStatus.hotspotState=Enable-MobileHotspot
                $script:monitorStatus.hotspotError=$null
                $hotspotPending=$false
                Write-MonitorLog 'Mobile hotspot is On.'
            } catch {
                $script:monitorStatus.hotspotState='Error'
                $script:monitorStatus.hotspotError=$_.Exception.Message
                Write-MonitorLog "Hotspot recovery failed; retrying in at least 30 seconds: $($_.Exception.Message)"
            }
        }
        if ($hotspotPending -and $phase -ne 'Error') { $phase='HotspotError' }
        Write-MonitorStatus $phase
        Wait-MonitorDelay $IntervalSeconds
    }
} finally {
    if ($ownsMutex) { Write-MonitorStatus 'Stopped'; $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
