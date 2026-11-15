# testpc2: Chatmon's M4B toast drill (AC-03E), run by the scheduled task ChatmonM4BToastDrill as Technician in the
# signed-in console session (LogonType Interactive, RunLevel Limited), where Windows shows toasts. task.ps1 registers
# and starts it. Each step's output goes to W:\chatmon-m4b\logs\<step>.log as the tool wrote it (cmd.exe redirection:
# bytes, not Windows PowerShell's UTF-16), and its exit code to run.log. The drills run only if the toast probe and the
# plain test run are green with a toast really in Action Center.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { exit 2 }
$root = 'W:\chatmon-m4b'
$logs = "$root\logs"
$src = "$root\src"
$py = "$root\venv\Scripts\python.exe"
$env:TEMP = "$root\tmp"; $env:TMP = "$root\tmp"  # the harness's temporary copy and pytest's tmp_path stay in the work folder
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM = 'offscreen'  # as tests/drills/run.py and the suite run; toasts need the session, not a window
$env:PYTHONPATH = $src
$env:GIT_CONFIG_COUNT = '1'; $env:GIT_CONFIG_KEY_0 = 'safe.directory'; $env:GIT_CONFIG_VALUE_0 = 'W:/chatmon-m4b/src'
Set-Location $src

function Note([string]$line) { Add-Content -Path "$logs\run.log" -Value $line -Encoding ASCII }
function Step([string]$name, [string]$cmdline) {
    $start = Get-Date
    & cmd.exe /d /c "$cmdline > $logs\$name.log 2>&1"  # no spaces in these paths, so no quotes for cmd.exe to strip
    $code = $LASTEXITCODE
    Note "$name exit $code ($($start.ToString('HH:mm:ss'))-$((Get-Date).ToString('HH:mm:ss'))): $cmdline"
    return $code
}

$session = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
Note "run.ps1 started $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')) as $(whoami), session $session, in $src at $(& git rev-parse HEAD)"
Note "integrity: $((whoami /groups | Select-String 'Mandatory Label').Line.Trim())"

$probe = Step 'probe' "$py $root\rec\toast_probe.py"
$plain = Step 'plain-test' "$py -m pytest -v -rA -p no:cacheprovider tests/test_wintoast.py"
if ($probe -eq 0 -and $plain -eq 0) {
    Step 'drills-stdout' "$py tests\drills\run.py $root\rec\drill-spec.json --log $logs\drills.log --python $py" | Out-Null
    Step 'probe-drills-stdout' "$py tests\drills\run.py $root\rec\probe-spec.json --log $logs\probe-drills.log --python $py" | Out-Null
    Note "git status --porcelain after the drills: $(& git status --porcelain)"
} else {
    Note 'drills not run: the probe or the plain test run was not green'
}
Note "run.ps1 done $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
Set-Content -Path "$logs\done.txt" -Value 'done' -Encoding ASCII
