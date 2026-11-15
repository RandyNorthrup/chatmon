param([ValidateSet('folder', 'build')][string]$Stage = 'folder', [string]$Zip = '', [string]$Tree = '')
# testpc2, over ssh as Technician (elevated): the work folder for Chatmon's M4B toast drill (AC-03E).
#   folder: pin W: to the Samsung spare (C:\Users\Randy\TestLab\README.md) and make W:\chatmon-m4b.
#   build:  unpack a commit's `git archive` zip (-Zip, a file in W:\chatmon-m4b) into W:\chatmon-m4b\src, check its
#           tree is that commit's to the bit (-Tree: `git rev-parse <commit>^{tree}`),
#           make a venv with C:\Python314 and install packaging/requirements-test.txt with --require-hashes.
# Native tools' exit codes are checked by hand: Windows PowerShell turns their stderr into errors otherwise.
$ErrorActionPreference = 'Continue'
function Fail([string]$why) { "FAILED: $why"; exit 1 }
function Native([string]$what) { if ($LASTEXITCODE -ne 0) { Fail "$what exited $LASTEXITCODE" } }

if ($env:COMPUTERNAME -ne 'TESTPC2') { Fail "not TESTPC2: $env:COMPUTERNAME" }
$root = 'W:\chatmon-m4b'
$tree = $Tree
$executable = @('bin/chatmon', 'packaging/build.py', 'packaging/linux/chatmon', 'packaging/linux/get-nfpm.sh',
    'packaging/linux/install-update', 'packaging/linux/postinstall.sh', 'packaging/linux/preremove.sh',
    'packaging/macos/scripts/postinstall')  # 100755 in the tree; a Windows checkout adds them as 100644

"== $Stage, $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')), $(whoami)"
$os = Get-CimInstance Win32_OperatingSystem
"last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss'))"
"claims:"
Get-ChildItem C:\TESTLAB_CLAIMS -Filter *.txt | ForEach-Object { "--- $($_.Name)"; Get-Content $_.FullName }

# W: must be the spare: SAMSUNG MZVL2512HCJQ-00BH1, serial 0025_38B8_21B7_37C0., 512110190592 bytes, not the boot disk.
$part = Get-Partition -DriveLetter W -ErrorAction SilentlyContinue
if (-not $part) { Fail 'no W:' }
$disk = Get-Disk -Number $part.DiskNumber
"W: is disk $($disk.Number): $($disk.FriendlyName), serial $($disk.SerialNumber), $($disk.Size) bytes, boot $($disk.IsBoot)"
if ($disk.FriendlyName -ne 'SAMSUNG MZVL2512HCJQ-00BH1' -or $disk.SerialNumber -ne '0025_38B8_21B7_37C0.' -or
    $disk.Size -ne 512110190592 -or $disk.IsBoot -or $disk.IsSystem) { Fail 'W: is not the Samsung spare' }

if ($Stage -eq 'folder') {
    if (Test-Path $root) { Fail "$root exists already: someone else's, or a run not cleaned up" }
    foreach ($d in $root, "$root\rec", "$root\logs", "$root\tmp") { New-Item -ItemType Directory $d | Out-Null }
    & icacls $root /grant 'TESTPC2\Technician:(OI)(CI)F' /Q | Out-Null; Native 'icacls'
    "made $root (Technician: full control)"
    # What exists before the run, so the cleanup removes only what the run added.
    $classes = 'HKCU:\Software\Classes\AppUserModelId'
    $wns = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings'
    $before = @()
    foreach ($k in $classes, $wns) {
        if (Test-Path $k) { $before += Get-ChildItem $k | Where-Object PSChildName -like 'RandyNorthrup.Chatmon*' | ForEach-Object { $_.Name } }
    }
    Set-Content "$root\logs\registry-before.txt" -Value $before -Encoding ASCII
    "Chatmon app IDs registered before the run: $($before.Count)"
    $before
    exit 0
}

# -- build
if (-not $Zip -or -not $Tree) { Fail 'build needs -Zip and -Tree' }
$zip = Join-Path $root $Zip
if (-not (Test-Path $zip)) { Fail "no $zip" }
"zip: $((Get-Item $zip).Length) bytes, SHA-256 $((Get-FileHash $zip -Algorithm SHA256).Hash)"
if (Test-Path "$root\src") { Fail "$root\src exists" }
New-Item -ItemType Directory "$root\src" | Out-Null
& tar.exe -xf $zip -C "$root\src"; Native 'tar'
$env:GIT_CONFIG_COUNT = '1'; $env:GIT_CONFIG_KEY_0 = 'safe.directory'; $env:GIT_CONFIG_VALUE_0 = 'W:/chatmon-m4b/src'
& git -C "$root\src" init -q; Native 'git init'
& git -C "$root\src" config core.autocrlf false; Native 'git config'  # keep git's bytes: LF, as the commit stores them
& git -C "$root\src" add -A 2>&1 | Out-Null; Native 'git add'
& git -C "$root\src" update-index --chmod=+x -- @executable; Native 'git update-index'
$made = (& git -C "$root\src" write-tree).Trim(); Native 'git write-tree'
"tree: $made (the commit's: $tree)"
if ($made -ne $tree) { Fail 'the unpacked tree is not the commit''s' }
& git -C "$root\src" -c user.name=chatmon-drill -c user.email=drill@testpc2.invalid commit -q -m "$Zip's tree, from git archive" ; Native 'git commit'
$status = & git -C "$root\src" status --porcelain
"git status --porcelain: $(if ($status) { $status } else { '(clean)' })"
"wintoast.py SHA-256: $((Get-FileHash "$root\src\chatmon\wintoast.py" -Algorithm SHA256).Hash.ToLower())"
"test_wintoast.py SHA-256: $((Get-FileHash "$root\src\tests\test_wintoast.py" -Algorithm SHA256).Hash.ToLower())"
"run.py SHA-256: $((Get-FileHash "$root\src\tests\drills\run.py" -Algorithm SHA256).Hash.ToLower())"

& C:\Python314\python.exe -m venv "$root\venv"; Native 'venv'
$py = "$root\venv\Scripts\python.exe"
& $py -m pip install --no-cache-dir --disable-pip-version-check --require-hashes -r "$root\src\packaging\requirements-test.txt" 2>&1 |
    Select-String -Pattern '^(Successfully|ERROR|error)' | ForEach-Object { $_.Line }
Native 'pip install'
"pip freeze:"
& $py -m pip freeze --disable-pip-version-check; Native 'pip freeze'
& $py -c "import sys, PyQt6.QtCore as q, pytest; print('python', sys.version.split()[0], 'pyqt6', q.PYQT_VERSION_STR, 'qt', q.QT_VERSION_STR, 'pytest', pytest.__version__)"; Native 'versions'
& icacls $root /setowner 'TESTPC2\Technician' /T /C /Q | Out-Null; Native 'icacls setowner'
"owner of $root and everything in it: Technician"
"setup done"
