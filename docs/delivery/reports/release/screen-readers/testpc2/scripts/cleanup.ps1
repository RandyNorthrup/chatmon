# testpc2, over ssh as Technician (elevated), after the logs were copied back: put back what Chatmon's screen-reader
# probe changed, against W:\chatmon-sr\logs\state-before.txt. Run from C:\Users\Technician\chatmon-sr, which goes last.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2: $env:COMPUTERNAME"; exit 1 }
$root = 'W:\chatmon-sr'
"== cleanup $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')), $(whoami)"
$os = Get-CimInstance Win32_OperatingSystem
"last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')) (unchanged: no restart happened)"
$before = @(Get-Content "$root\logs\state-before.txt")

"-- processes"
foreach ($name in 'Narrator', 'nvda', 'nvda_noUIAccess', 'nvda_slave', 'nvda_uiAccess', 'LiveCaptions') {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { "stopping $($_.ProcessName) $($_.Id)"; Stop-Process -Id $_.Id -Force }
}
# This script's own ancestry (the ssh session's shells) is never touched; nor anything outside the work folder.
$mine = @(); $p = $PID
while ($p -and $mine -notcontains $p) { $mine += $p; $p = (Get-CimInstance Win32_Process -Filter "ProcessId=$p").ParentProcessId }
@(Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -like "$root\*" -or $_.CommandLine -like '*W:\chatmon-sr\*') -and $mine -notcontains $_.ProcessId }) |
    ForEach-Object { "stopping $($_.ProcessId) $($_.CommandLine)"; Stop-Process -Id $_.ProcessId -Force }

"-- scheduled task"
Unregister-ScheduledTask -TaskName ChatmonScreenReaderProbe -Confirm:$false -ErrorAction SilentlyContinue
"ChatmonScreenReaderProbe registered: $([bool](Get-ScheduledTask -TaskName ChatmonScreenReaderProbe -ErrorAction SilentlyContinue))"

"-- Narrator's settings, back to before: HKCU\Software\Microsoft\Narrator held only NoRoam\RunningState = 0"
$n = 'HKCU:\Software\Microsoft\Narrator'
(Get-Item $n).Property | ForEach-Object { Remove-ItemProperty -Path $n -Name $_ }
Get-ChildItem $n | Where-Object PSChildName -ne 'NoRoam' | ForEach-Object { "removing $($_.Name)"; Remove-Item $_.PSPath -Recurse -Force }
(Get-Item "$n\NoRoam").Property | Where-Object { $_ -ne 'RunningState' } | ForEach-Object { Remove-ItemProperty -Path "$n\NoRoam" -Name $_ }
Set-ItemProperty -Path "$n\NoRoam" -Name RunningState -Value 0 -Type DWord

"-- keys that were absent before"
foreach ($k in 'HKCU:\Software\Microsoft\LiveCaptions', 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Accessibility',
               'HKCU:\Software\Classes\AppUserModelId\RandyNorthrup.Chatmon',
               'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings\RandyNorthrup.Chatmon') {
    if (Test-Path $k) { "removing $k"; Remove-Item $k -Recurse -Force }
}

"-- the speech platform's per-app keys made since (HKCU\Software\Microsoft\Speech_OneCore)"
$keptKeys = @($before | Where-Object { $_ -like '  key HKEY_CURRENT_USER\Software\Microsoft\Speech_OneCore*' } | ForEach-Object { $_.Substring(6) })
Get-ChildItem 'HKCU:\Software\Microsoft\Speech_OneCore' -Recurse -ErrorAction SilentlyContinue | Sort-Object { $_.Name.Length } | ForEach-Object {
    $name = $_.Name
    $parent = $name.Substring(0, $name.LastIndexOf('\'))
    if ($keptKeys -notcontains $name -and ($keptKeys -contains $parent -or $parent -eq 'HKEY_CURRENT_USER\Software\Microsoft\Speech_OneCore') -and (Test-Path $_.PSPath)) {
        "removing $name"
        Remove-Item $_.PSPath -Recurse -Force
    }
}

"-- Live captions' language pack (installed by its first run)"
$wasThere = @($before | Where-Object { $_ -like '  MicrosoftWindows.Speech.*' })
Get-AppxPackage -Name 'MicrosoftWindows.Speech.*' | Where-Object { $wasThere -notcontains "  $($_.PackageFullName)" } | ForEach-Object {
    "removing $($_.PackageFullName)"
    Remove-AppxPackage -Package $_.PackageFullName
}

"-- Chatmon's folder for Technician (absent before)"
if (Test-Path "$env:LOCALAPPDATA\chatmon") { Remove-Item "$env:LOCALAPPDATA\chatmon" -Recurse -Force }
"$env:LOCALAPPDATA\chatmon exists: $(Test-Path "$env:LOCALAPPDATA\chatmon")"
"$env:APPDATA\nvda exists: $(Test-Path "$env:APPDATA\nvda")"

"-- the work folder on W:, pinned first"
$disk = Get-Disk | Where-Object { $_.SerialNumber -eq '0025_38B8_21B7_37C0.' }
$w = Get-Partition -DriveLetter W
if ($disk -and $disk.FriendlyName -eq 'SAMSUNG MZVL2512HCJQ-00BH1' -and $disk.Size -eq 512110190592 -and -not $disk.IsBoot -and $w.DiskNumber -eq $disk.Number) {
    Set-Location C:\
    Remove-Item $root -Recurse -Force
    "W:\chatmon-sr exists: $(Test-Path $root); W:\ holds: $((Get-ChildItem W:\ -Force | ForEach-Object Name) -join ', ')"
} else { "W: is not the pinned spare: W:\chatmon-sr left in place" }

"-- claim"
$claim = 'C:\TESTLAB_CLAIMS\chatmon.txt'
if (Test-Path $claim) { Remove-Item $claim -Force }
"claim file exists: $(Test-Path $claim); claims left: $((Get-ChildItem C:\TESTLAB_CLAIMS -Filter *.txt | ForEach-Object Name) -join ', ')"

Set-Location C:\Users\Technician
Remove-Item -Path C:\Users\Technician\chatmon-sr -Recurse -Force
"C:\Users\Technician\chatmon-sr exists: $(Test-Path C:\Users\Technician\chatmon-sr)"
"cleanup done $((Get-Date).ToString('HH:mm:ss'))"
