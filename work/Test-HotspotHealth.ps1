$ErrorActionPreference='Stop'
$source=Get-Content (Join-Path $PSScriptRoot '..\outputs\WifiWorker.ps1') -Raw
$tokens=$null; $errors=$null
$null=[System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Worker syntax error' }
$start=$source.IndexOf('        # Hotspot health is independent')
$end=$source.IndexOf('        Write-MonitorStatus $phase',$start)
$block=[scriptblock]::Create($source.Substring($start,$end-$start))
function Get-HotspotManager { if($script:state -eq 'Throw'){throw 'Unavailable'}; [pscustomobject]@{TetheringOperationalState=$script:state} }
function Enable-MobileHotspot { $script:calls++; if($script:fail){throw 'Start rejected'}; 'On' }
function Test-MonitorStop { $script:stop }
function Get-Date { $script:now }
function Write-MonitorStatus { param($Phase) }
function Write-MonitorLog { param($Message) }
$script:calls=0; $script:fail=$false; $script:stop=$false
$script:now=[datetime]'2026-09-20T12:00:00'
$script:wifiLinkStatus='Up'
$script:monitorStatus=@{hotspotState='Unmanaged';hotspotError=$null}
$deviceMode='host'; $phase='Online'; $hotspotPending=$false; $lastHotspotAttempt=[datetime]::MinValue
$script:state='Off'; . $block
if($script:calls -ne 1 -or $hotspotPending){throw 'Healthy internet + hotspot Off did not start'}
$script:state='On'; . $block
if($script:calls -ne 1){throw 'Already On restarted'}
$script:state='Off'; $script:now=$script:now.AddSeconds(5); . $block
if($script:calls -ne 1){throw 'Cooldown bypassed'}
$script:now=$script:now.AddSeconds(30); $script:fail=$true; . $block
if($script:calls -ne 2 -or -not $hotspotPending -or -not $script:monitorStatus.hotspotError){throw 'Start failure not reported'}
$script:state='On'; . $block
if($hotspotPending -or $script:monitorStatus.hotspotError){throw 'External start did not clear error during cooldown'}
$script:now=$script:now.AddSeconds(30); $script:state='InTransition'; . $block
if($script:calls -ne 2){throw 'Duplicate start while transitioning'}
$script:state='Throw'; . $block
if($script:calls -ne 2 -or $script:monitorStatus.hotspotState -ne 'Unknown'){throw 'Query error handling'}
$script:state='Off'; $deviceMode='client'; . $block
if($script:calls -ne 2){throw 'Client started hotspot'}
$deviceMode='host'; $script:stop=$true; . $block
if($script:calls -ne 2){throw 'Started while stopping'}
$script:stop=$false; $script:fail=$false; $script:wifiLinkStatus='Disabled'; . $block
if($script:calls -ne 2){throw 'Manual disable ignored'}
$script:wifiLinkStatus='Up'; $phase='Offline'; . $block
if($script:calls -ne 3){throw 'Website failure prevented independent hotspot recovery'}
'PASS: independent hotspot health, cooldown, retries, external start, transitions, unknown state, client/stop/disabled guards'
