# testpc2, over ssh as Technician: Narrator's typing echo and hints off for the speech-recap run (less speech in the
# room). These values didn't exist before the probe (Narrator wrote them on its first run today); cleanup removes them.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
foreach ($name in 'EchoChars', 'EchoWords', 'ReadHints') { Set-ItemProperty -Path HKCU:\Software\Microsoft\Narrator -Name $name -Value 0 -Type DWord }
Get-ItemProperty HKCU:\Software\Microsoft\Narrator | Select-Object EchoChars, EchoWords, ReadHints | Format-List | Out-String
New-Item -ItemType Directory W:\chatmon-sr\out\recap1 -Force | Out-Null
