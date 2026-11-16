# testpc2: run by the scheduled task ChatmonScreenReaderProbe as Technician in the signed-in console session
# (interactive logon, Limited). Runs the command task.ps1 wrote to W:\chatmon-sr\rec\job.json, below normal priority
# (what it starts inherits that), output to W:\chatmon-sr\logs\<name>.log as the tool wrote it, exit code to <name>.done.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { exit 2 }
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'
$root = 'W:\chatmon-sr'
$job = Get-Content "$root\rec\job.json" -Raw | ConvertFrom-Json
$env:TEMP = "$root\tmp"; $env:TMP = "$root\tmp"
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$exe = if ($job.exe) { $job.exe } else { "$root\venv\Scripts\python.exe" }
Set-Location "$root\src"
$session = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
"job $($job.name) in session $session as $(whoami), $((whoami /groups | Select-String 'Mandatory Label').Line.Trim() -replace '\s+', ' ')" | Set-Content "$root\logs\$($job.name).log" -Encoding UTF8
& cmd.exe /d /c "`"$exe`" $($job.args) >> $root\logs\$($job.name).log 2>&1"
Set-Content -Path "$root\logs\$($job.name).done" -Value "exit $LASTEXITCODE" -Encoding ASCII
