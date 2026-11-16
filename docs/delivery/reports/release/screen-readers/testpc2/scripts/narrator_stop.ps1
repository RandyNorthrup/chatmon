# testpc2, over ssh as Technician (elevated): stop Narrator when it no longer answers its own keys.
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2"; exit 1 }
$before = @(Get-Process -Name Narrator -ErrorAction SilentlyContinue)
"Narrator before: $(($before | ForEach-Object Id) -join ', ')"
$before | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$after = @(Get-Process -Name Narrator -ErrorAction SilentlyContinue)
"Narrator after: $(if ($after) { ($after | ForEach-Object Id) -join ', ' } else { 'not running' }) at $(Get-Date -Format HH:mm:ss)"
