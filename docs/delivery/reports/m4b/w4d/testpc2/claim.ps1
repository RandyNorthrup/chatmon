param([ValidateSet('take', 'release', 'show')][string]$Mode = 'show')
# Chatmon's claim file on testpc2 (C:\Users\Randy\TestLab\README.md, shared-claims rules).
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
$dir = 'C:\TESTLAB_CLAIMS'
$file = Join-Path $dir 'chatmon.txt'
"-- other claims:"
Get-ChildItem $dir -Filter *.txt -ErrorAction SilentlyContinue | Where-Object Name -ne 'chatmon.txt' | ForEach-Object { "--- $($_.Name)"; Get-Content $_.FullName }
if ($Mode -eq 'take') {
    $start = Get-Date
    $end = $start.AddHours(2)
    $f = 'yyyy-MM-dd HH:mm zzz'
    $lines = @(
        "console $($start.ToString($f)) until $($end.ToString($f)): Chatmon M4B toast drill (AC-03E), a scheduled task in Technician's console session showing and hiding toasts",
        "drive 0025_38B8_21B7_37C0. $($start.ToString($f)) until $($end.ToString($f)): Chatmon writes W:\chatmon-m4b only (source, venv, logs), no erase; removed at the end"
    )
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory $dir | Out-Null }
    Set-Content -Path $file -Value $lines -Encoding ASCII
} elseif ($Mode -eq 'release') {
    if (Test-Path $file) { Remove-Item $file -Force }
}
"-- chatmon.txt:"
if (Test-Path $file) { Get-Content $file } else { "(none)" }
