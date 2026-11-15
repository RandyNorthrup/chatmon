# testpc2, over ssh as Technician: read-only survey before Chatmon's screen-reader probe (Narrator, Live captions,
# NVDA). Changes nothing.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2: $env:COMPUTERNAME"; exit 1 }
"== identity"
"computer: $env:COMPUTERNAME  user: $(whoami)"
$os = Get-CimInstance Win32_OperatingSystem
"os: $($os.Caption) $($os.Version) build $($os.BuildNumber) UBR $((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR)"
"last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss'))  now: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
"uuid: $((Get-CimInstance Win32_ComputerSystemProduct).UUID)"
"== claims"
if (Test-Path C:\TESTLAB_CLAIMS) {
    Get-ChildItem C:\TESTLAB_CLAIMS -Force | ForEach-Object { "--- $($_.FullName) ($($_.Length) bytes, $($_.LastWriteTime))"; Get-Content $_.FullName }
} else { "C:\TESTLAB_CLAIMS does not exist" }
"== sessions"
query user 2>&1
"== disks"
Get-Disk | Sort-Object Number | Format-Table -AutoSize Number, FriendlyName, SerialNumber, Size, BusType, IsBoot, IsSystem | Out-String -Width 200
Get-Volume | Where-Object DriveLetter | Format-Table -AutoSize DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining | Out-String -Width 200
"== W: top level"
if (Test-Path W:\) { Get-ChildItem W:\ -Force | Format-Table -AutoSize Mode, LastWriteTime, Name | Out-String -Width 200 }
"== audio"
Get-Service Audiosrv, AudioEndpointBuilder | Format-Table -AutoSize Name, Status, StartType | Out-String -Width 200
Get-CimInstance Win32_SoundDevice | Format-Table -AutoSize Name, Status, Manufacturer | Out-String -Width 200
Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | Format-Table -AutoSize Status, FriendlyName, InstanceId | Out-String -Width 250
"render endpoints (MMDevices, state 1 = active):"
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render' -ErrorAction SilentlyContinue | ForEach-Object {
    $state = (Get-ItemProperty $_.PSPath).DeviceState
    $name = (Get-ItemProperty "$($_.PSPath)\Properties" -ErrorAction SilentlyContinue).'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
    $form = (Get-ItemProperty "$($_.PSPath)\Properties" -ErrorAction SilentlyContinue).'{b3f8fa53-0004-438e-9003-51a46e139bfc},6'
    "  state $state  $name  ($form)  $($_.PSChildName)"
}
"== Narrator"
Get-Process -Name Narrator, NVDA, nvda_slave, LiveCaptions, python, pythonw -ErrorAction SilentlyContinue | Format-Table -AutoSize Id, ProcessName, SessionId, Path | Out-String -Width 200
foreach ($k in 'HKCU:\Software\Microsoft\Narrator', 'HKCU:\Software\Microsoft\Narrator\NoRoam', 'HKCU:\Software\Microsoft\Narrator\NarratorHome', 'HKCU:\Software\Microsoft\Narrator\QuickStart') {
    if (Test-Path $k) { "--- $k"; Get-ItemProperty $k | Select-Object * -ExcludeProperty PS* | Format-List | Out-String -Width 200 } else { "--- $k missing" }
}
"Narrator.exe: $(Test-Path C:\Windows\System32\Narrator.exe)"
"== Live captions"
"LiveCaptions.exe: $(Test-Path C:\Windows\System32\LiveCaptions.exe)"
foreach ($k in 'HKCU:\Software\Microsoft\LiveCaptions', 'HKCU:\Software\Microsoft\LiveCaptions\UI') {
    if (Test-Path $k) { "--- $k"; Get-ItemProperty $k | Select-Object * -ExcludeProperty PS* | Format-List | Out-String -Width 200 } else { "--- $k missing" }
}
Get-AppxPackage -Name '*Speech*' -ErrorAction SilentlyContinue | Format-Table -AutoSize Name, Version | Out-String -Width 200
Get-AppxPackage -Name '*LiveCaption*' -ErrorAction SilentlyContinue | Format-Table -AutoSize Name, Version | Out-String -Width 200
"== NVDA"
foreach ($p in 'C:\Program Files (x86)\NVDA', 'C:\Program Files\NVDA', "$env:APPDATA\nvda") { "$p : $(Test-Path $p)" }
"== screen reader flag (SPI_GETSCREENREADER) from this session is not the console's; skipped"
"== foreground lock"
Get-ItemProperty 'HKCU:\Control Panel\Desktop' -Name ForegroundLockTimeout, ForegroundFlashCount -ErrorAction SilentlyContinue | Format-List | Out-String -Width 200
"== notifications (HKCU of $(whoami))"
$pn = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications'
if (Test-Path $pn) { Get-ItemProperty $pn | Select-Object * -ExcludeProperty PS* | Format-List | Out-String -Width 200 } else { "$pn missing" }
"== Chatmon traces for Technician"
"LOCALAPPDATA\chatmon: $(Test-Path "$env:LOCALAPPDATA\chatmon")  APPDATA\chatmon: $(Test-Path "$env:APPDATA\chatmon")"
foreach ($k in 'HKCU:\Software\Classes\AppUserModelId', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings') {
    if (Test-Path $k) { "--- $k (Chatmon)"; Get-ChildItem $k | Where-Object PSChildName -like '*Chatmon*' | ForEach-Object Name }
}
$run = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue
"Run key values: $(($run.PSObject.Properties | Where-Object Name -notlike 'PS*' | ForEach-Object Name) -join ', ')"
"== scheduled tasks under \"
Get-ScheduledTask | Where-Object { $_.TaskPath -eq '\' } | Format-Table -AutoSize TaskName, State | Out-String -Width 200
"== tools"
& C:\Python314\python.exe --version
& git --version
"== console session's desktop"
Get-Process -IncludeUserName -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq 1 -and $_.MainWindowTitle } | Format-Table -AutoSize Id, ProcessName, MainWindowTitle | Out-String -Width 200
