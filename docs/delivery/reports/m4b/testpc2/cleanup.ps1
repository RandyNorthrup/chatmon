# testpc2, over ssh as Technician (elevated), after the logs were copied back: put everything the M4B toast drill
# made back as it was. Run from C:\Users\Technician\chatmon-survey (where the first survey ran), which goes last.
$ErrorActionPreference = 'Continue'
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2: $env:COMPUTERNAME"; exit 1 }
$root = 'W:\chatmon-m4b'
$name = 'ChatmonM4BToastDrill'
"== cleanup $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')), $(whoami)"
$os = Get-CimInstance Win32_OperatingSystem
"last boot: $($os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')) (unchanged means no restart happened)"

Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
"task $name still registered: $([bool](Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue))"

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$root\*" -or $_.CommandLine -like '*chatmon-m4b*' -or $_.CommandLine -like '*chatmon-drill-*' })
"processes from the work folder: $($procs.Count)"
$procs | ForEach-Object { "  $($_.ProcessId) $($_.CommandLine)"; Stop-Process -Id $_.ProcessId -Force }

# App IDs the run registered (the tests remove theirs; Windows keeps a notification settings key per app ID it showed).
$before = @()
if (Test-Path "$root\logs\registry-before.txt") { $before = @(Get-Content "$root\logs\registry-before.txt") }
foreach ($k in 'HKCU:\Software\Classes\AppUserModelId', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings') {
    if (-not (Test-Path $k)) { continue }
    Get-ChildItem $k | Where-Object { $_.PSChildName -like 'RandyNorthrup.Chatmon*' -and $before -notcontains $_.Name } | ForEach-Object {
        "removing $($_.Name) (made during the run)"
        Remove-Item -Path $_.PSPath -Recurse -Force
    }
    $still = @(Get-ChildItem $k | Where-Object PSChildName -like 'RandyNorthrup.Chatmon*')
    "$k : Chatmon app IDs now $($still.Count), before the run $(@($before | Where-Object { $_ -like "*$(Split-Path $k -Leaf)*" }).Count)"
}

$pn = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications' -ErrorAction SilentlyContinue
"ToastEnabled now: $(if ($null -ne $pn.ToastEnabled) { $pn.ToastEnabled } else { 'absent (on), as before; never changed' })"

if (Test-Path $root) { Remove-Item -Path $root -Recurse -Force }
"W:\chatmon-m4b exists: $(Test-Path $root)"
"W:\ now holds: $((Get-ChildItem W:\ -Force | ForEach-Object Name) -join ', ')"

$claim = 'C:\TESTLAB_CLAIMS\chatmon.txt'
if (Test-Path $claim) { Remove-Item $claim -Force }
"claim file exists: $(Test-Path $claim); claims left: $((Get-ChildItem C:\TESTLAB_CLAIMS -Filter *.txt | ForEach-Object Name) -join ', ')"

Set-Location C:\Users\Technician
Remove-Item -Path C:\Users\Technician\chatmon-survey -Recurse -Force
"C:\Users\Technician\chatmon-survey exists: $(Test-Path C:\Users\Technician\chatmon-survey)"
"cleanup done"
