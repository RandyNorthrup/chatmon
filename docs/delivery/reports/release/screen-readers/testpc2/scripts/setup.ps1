param([ValidateSet('folder', 'build', 'state')][string]$Mode, [string]$Label = 'before')
# testpc2, over ssh as Technician: the work folder for Chatmon's screen-reader probe, W:\chatmon-sr.
#   folder: W: pinned to the spare, W:\chatmon-sr made (Technician full control), nothing else touched.
#   build:  the source zip (scp'd to rec\) unpacked, a venv from C:\Python314 with packaging/requirements-test.txt
#           (--require-hashes), below normal priority (the PC is shared).
#   state:  what the probe could change, written to logs\state-<Label>.txt (registry keys, packages, processes).
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'  # children inherit it
$root = 'W:\chatmon-sr'
function Native([string]$what) { if ($LASTEXITCODE -ne 0) { throw "$what failed: exit $LASTEXITCODE" } }
"== $Mode $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')), $(whoami)"
if ($Mode -eq 'folder') {
    $disk = Get-Disk | Where-Object { $_.SerialNumber -eq '0025_38B8_21B7_37C0.' }
    $w = Get-Partition -DriveLetter W
    if (-not $disk -or $disk.FriendlyName -ne 'SAMSUNG MZVL2512HCJQ-00BH1' -or $disk.Size -ne 512110190592 -or $disk.IsBoot -or $w.DiskNumber -ne $disk.Number) {
        throw 'W: is not the pinned spare'
    }
    "W: is disk $($disk.Number), $($disk.FriendlyName), serial $($disk.SerialNumber), $($disk.Size) bytes, boot $($disk.IsBoot)"
    if (Test-Path $root) { throw "$root exists already" }
    New-Item -ItemType Directory $root, "$root\rec", "$root\logs", "$root\tmp", "$root\out" | Out-Null
    & icacls $root /grant 'TESTPC2\Technician:(OI)(CI)F' /Q | Out-Null; Native 'icacls'
    & icacls $root /setowner 'TESTPC2\Technician' /T /C /Q | Out-Null; Native 'icacls setowner'
    "made $root; W:\ holds: $((Get-ChildItem W:\ -Force | ForEach-Object Name) -join ', ')"
}
if ($Mode -eq 'build') {
    $zip = Get-ChildItem "$root\rec" -Filter 'chatmon-*.zip' | Select-Object -First 1
    "zip: $($zip.Name) $($zip.Length) bytes, SHA-256 $((Get-FileHash $zip.FullName).Hash)"
    Expand-Archive $zip.FullName "$root\src"
    & C:\Python314\python.exe -m venv "$root\venv"; Native 'venv'
    & "$root\venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-input --require-hashes -r "$root\src\packaging\requirements-test.txt" 2>&1 | Select-Object -Last 3
    Native 'pip install'
    & "$root\venv\Scripts\python.exe" -m pip freeze
    & "$root\venv\Scripts\python.exe" -c "import PyQt6.QtCore as q, comtypes; print('Qt', q.QT_VERSION_STR, 'PyQt', q.PYQT_VERSION_STR, 'comtypes', comtypes.__version__)"
    & icacls $root /setowner 'TESTPC2\Technician' /T /C /Q | Out-Null; Native 'icacls setowner'
}
if ($Mode -eq 'state') {
    $out = "$root\logs\state-$Label.txt"
    & {
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
    } | Out-File -FilePath $out -Encoding utf8
    Get-Content $out
}
