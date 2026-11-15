$ErrorActionPreference = 'Continue'
"== identity"
"computer: $env:COMPUTERNAME  user: $(whoami)"
$os = Get-CimInstance Win32_OperatingSystem
"os: $($os.Caption) $($os.Version) build $($os.BuildNumber)"
"last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss'))  now: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
"uuid: $((Get-CimInstance Win32_ComputerSystemProduct).UUID)"
"== claims"
if (Test-Path C:\TESTLAB_CLAIMS) {
    Get-ChildItem C:\TESTLAB_CLAIMS -Force | ForEach-Object { "--- $($_.FullName) ($($_.Length) bytes, $($_.LastWriteTime))"; Get-Content $_.FullName }
} else { "C:\TESTLAB_CLAIMS does not exist" }
"== sessions"
query user 2>&1
"== disks"
Get-Disk | Sort-Object Number | Format-Table -AutoSize Number, FriendlyName, SerialNumber, Size, BusType, IsBoot, IsSystem, PartitionStyle | Out-String -Width 200
Get-Partition | Where-Object DriveLetter | Format-Table -AutoSize DiskNumber, PartitionNumber, DriveLetter, Size | Out-String -Width 200
Get-Volume | Where-Object DriveLetter | Format-Table -AutoSize DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining | Out-String -Width 200
"== W: top level"
if (Test-Path W:\) { Get-ChildItem W:\ -Force | Format-Table -AutoSize Mode, LastWriteTime, Name | Out-String -Width 200 }
"== notifications (HKCU of $(whoami))"
$pn = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications'
if (Test-Path $pn) { Get-ItemProperty $pn | Format-List | Out-String -Width 200 } else { "$pn missing" }
$ns = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings'
if (Test-Path $ns) { Get-ItemProperty $ns | Format-List | Out-String -Width 200 } else { "$ns missing" }
"== notification policy"
foreach ($p in 'HKCU:\Software\Policies\Microsoft\Windows\CurrentVersion\PushNotifications', 'HKLM:\Software\Policies\Microsoft\Windows\CurrentVersion\PushNotifications', 'HKCU:\Software\Policies\Microsoft\Windows\Explorer', 'HKLM:\Software\Policies\Microsoft\Windows\Explorer') {
    if (Test-Path $p) { "--- $p"; Get-ItemProperty $p | Format-List | Out-String -Width 200 } else { "--- $p missing" }
}
"== scheduled tasks under \ (non-Microsoft)"
Get-ScheduledTask | Where-Object { $_.TaskPath -eq '\' } | Format-Table -AutoSize TaskName, State | Out-String -Width 200
"== python"
& C:\Python314\python.exe --version
"== git"
& git --version
