# testpc2, over ssh as Technician: what Chatmon's screen-reader probe could have changed, after cleanup.ps1, printed
# (the same sections as setup.ps1's state, which lived in the work folder cleanup removed). Deleted after it runs.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2"; exit 1 }
$Label = 'after'
    "== state $Label $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
    $os = Get-CimInstance Win32_OperatingSystem
    "last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    "-- processes (screen readers, captions, Python, Explorer windows)"
    Get-Process -Name Narrator, NVDA, nvda_slave, nvda_noUIAccess, LiveCaptions, python, pythonw -ErrorAction SilentlyContinue |
        ForEach-Object { "  $($_.Id) $($_.ProcessName) session $($_.SessionId) $($_.Path)" }
    "-- registry keys (each listed with its values)"
    foreach ($k in 'HKCU:\Software\Microsoft\Narrator', 'HKCU:\Software\Microsoft\LiveCaptions', 'HKCU:\Software\Microsoft\Speech_OneCore',
                   'HKCU:\Software\Classes\AppUserModelId', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings',
                   'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run', 'HKCU:\Software\Microsoft\Accessibility', 'HKCU:\Control Panel\Accessibility',
                   'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Accessibility') {
        if (-not (Test-Path $k)) { "$k : absent"; continue }
        Get-ChildItem $k -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.Name } | Sort-Object | ForEach-Object { "  key $_" }
        Get-Item $k | Select-Object -ExpandProperty Property | ForEach-Object { "  value $k : $_" }
    }
    "-- values under Narrator, LiveCaptions and the accessibility keys (each key and its subkeys)"
    foreach ($k in 'HKCU:\Software\Microsoft\Narrator', 'HKCU:\Software\Microsoft\LiveCaptions', 'HKCU:\Software\Microsoft\Accessibility',
                   'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Accessibility') {
        if (Test-Path $k) {
            @(Get-Item $k) + @(Get-ChildItem $k -Recurse -ErrorAction SilentlyContinue) | ForEach-Object {
                $item = $_; $item.Property | ForEach-Object { "  $($item.Name) : $_ = $((Get-ItemProperty -Path $item.PSPath -Name $_ -ErrorAction SilentlyContinue).$_)" }
            }
        }
    }
    "-- appx packages for speech and captions"
    Get-AppxPackage -Name '*Speech*' -ErrorAction SilentlyContinue | ForEach-Object { "  $($_.PackageFullName)" }
    Get-AppxPackage -Name '*LiveCaption*' -ErrorAction SilentlyContinue | ForEach-Object { "  $($_.PackageFullName)" }
    "-- Chatmon's folders"
    "  $env:LOCALAPPDATA\chatmon : $(Test-Path "$env:LOCALAPPDATA\chatmon")"
    "  $env:APPDATA\chatmon : $(Test-Path "$env:APPDATA\chatmon")"
    "  $env:APPDATA\nvda : $(Test-Path "$env:APPDATA\nvda")"
    "-- scheduled tasks under \"
    Get-ScheduledTask | Where-Object { $_.TaskPath -eq '\' } | ForEach-Object { "  $($_.TaskName) $($_.State)" }
    "-- claims"
    Get-ChildItem C:\TESTLAB_CLAIMS -Filter *.txt -ErrorAction SilentlyContinue | ForEach-Object { "  --- $($_.Name)"; Get-Content $_.FullName | ForEach-Object { "  $_" } }
