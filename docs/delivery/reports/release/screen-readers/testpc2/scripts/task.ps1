param([ValidateSet('run', 'remove')][string]$Mode = 'run', [string]$Name = 'job', [string]$Exe = '', [string]$ArgLine = '', [int]$TimeoutMinutes = 10)
# testpc2, over ssh as Technician: run one command in Technician's signed-in console session (where Narrator, Live
# captions and Chatmon's windows are; ssh's own logon has no desktop), through the on-demand scheduled task
# ChatmonScreenReaderProbe (no trigger, interactive logon, Limited: not elevated), and wait for it. The command goes
# to W:\chatmon-sr\rec\job.json for job.ps1; its output to W:\chatmon-sr\logs\<Name>.log. `remove` unregisters it.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
$task = 'ChatmonScreenReaderProbe'
$root = 'W:\chatmon-sr'
if ($Mode -eq 'remove') {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    "task $task registered after removal: $([bool](Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue))"
    exit 0
}
$claim = Get-Content C:\TESTLAB_CLAIMS\chatmon.txt -ErrorAction SilentlyContinue | Where-Object { $_ -like 'console *' }
if (-not $claim) { throw 'Chatmon holds no console claim: take it first (claim.ps1 console)' }
$console = (query user 2>&1 | Select-String '^\s*>?technician\s+console\s+(\d+)\s+Active')
if (-not $console) { throw 'Technician is not signed in and active at the console' }
foreach ($old in "$root\logs\$Name.log", "$root\logs\$Name.done") { if (Test-Path $old) { Remove-Item $old } }
@{ name = $Name; exe = $Exe; args = $ArgLine } | ConvertTo-Json | Set-Content "$root\rec\job.json" -Encoding UTF8
if (-not (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue)) {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $root\rec\job.ps1"
    $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\Technician" -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -Priority 7
    Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings -Description 'Chatmon screen-reader probe, on demand; removed after' | Out-Null
    $t = Get-ScheduledTask -TaskName $task
    "registered $task : user $($t.Principal.UserId), logon $($t.Principal.LogonType), run level $($t.Principal.RunLevel), triggers $(@($t.Triggers | Where-Object { $_ }).Count)"
}
"== $Name $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')): $Exe $ArgLine"
Start-ScheduledTask -TaskName $task
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while (-not (Test-Path "$root\logs\$Name.done") -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
"finished: $(Test-Path "$root\logs\$Name.done") $(if (Test-Path "$root\logs\$Name.done") { Get-Content "$root\logs\$Name.done" }) at $((Get-Date).ToString('HH:mm:ss'))"
if (Test-Path "$root\logs\$Name.log") { Get-Content "$root\logs\$Name.log" -Encoding UTF8 }
