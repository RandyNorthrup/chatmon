param([ValidateSet('drive', 'console', 'release', 'show')][string]$Mode = 'show', [int]$Hours = 2)
# Chatmon's claim file on testpc2 (C:\Users\Randy\TestLab\README.md, shared-claims rules), for the screen-reader
# probe. `drive` claims writing W:\chatmon-sr (the spare, pinned below; nothing erased); `console` adds the signed-in
# desktop, refused while another project's claim names it; `release` deletes the file.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
$dir = 'C:\TESTLAB_CLAIMS'
$file = Join-Path $dir 'chatmon.txt'
$f = 'yyyy-MM-dd HH:mm zzz'
"== $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
"-- other claims:"
$others = @(Get-ChildItem $dir -Filter *.txt -ErrorAction SilentlyContinue | Where-Object Name -ne 'chatmon.txt')
$others | ForEach-Object { "--- $($_.Name) ($($_.LastWriteTime))"; Get-Content $_.FullName }
if ($Mode -eq 'drive') {
    $disk = Get-Disk | Where-Object { $_.SerialNumber -eq '0025_38B8_21B7_37C0.' }
    $w = Get-Partition -DriveLetter W -ErrorAction Stop
    if (-not $disk -or $disk.FriendlyName -ne 'SAMSUNG MZVL2512HCJQ-00BH1' -or $disk.Size -ne 512110190592 -or $disk.IsBoot -or $w.DiskNumber -ne $disk.Number) {
        throw "W: is not the pinned spare (SAMSUNG MZVL2512HCJQ-00BH1, 0025_38B8_21B7_37C0., 512110190592 bytes, not boot)"
    }
    "W: pinned: disk $($disk.Number) $($disk.FriendlyName) $($disk.SerialNumber) $($disk.Size) bytes, boot $($disk.IsBoot)"
    $start = Get-Date
    $line = "drive 0025_38B8_21B7_37C0. $($start.ToString($f)) until $($start.AddHours($Hours).ToString($f)): Chatmon screen-reader probe writes W:\chatmon-sr only (source, venv, logs), no erase; removed at the end"
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory $dir | Out-Null }
    $kept = @(if (Test-Path $file) { Get-Content $file | Where-Object { $_ -notlike 'drive *' } })
    Set-Content -Path $file -Value (@($line) + $kept) -Encoding ASCII
} elseif ($Mode -eq 'console') {
    $held = @($others | Where-Object { Select-String -Path $_.FullName -Pattern '^\s*console\b' -Quiet })
    if ($held) { throw "the console is claimed by: $(($held | ForEach-Object Name) -join ', ')" }
    $start = Get-Date
    $line = "console $($start.ToString($f)) until $($start.AddHours($Hours).ToString($f)): Chatmon screen-reader probe: Narrator (and Live captions or NVDA) with Chatmon on Technician's console, run by an on-demand scheduled task; it types and clicks there"
    $kept = @(if (Test-Path $file) { Get-Content $file | Where-Object { $_ -notlike 'console *' } })
    Set-Content -Path $file -Value ($kept + @($line)) -Encoding ASCII
} elseif ($Mode -eq 'release') {
    if (Test-Path $file) { Remove-Item $file -Force }
}
"-- chatmon.txt:"
if (Test-Path $file) { Get-Content $file } else { "(none)" }
