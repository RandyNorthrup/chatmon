# testpc2, over ssh as Technician: NV Access's NVDA 2026.3.1 installer, from nvaccess.org, into W:\chatmon-sr\dl, checked
# against the SHA-256 NV Access publishes (on its GitHub release) and for its Authenticode signature.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'
$dl = 'W:\chatmon-sr\dl'
New-Item -ItemType Directory $dl -Force | Out-Null
$exe = "$dl\nvda_2026.3.1.exe"
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -UseBasicParsing -Uri 'https://download.nvaccess.org/releases/2026.3.1/nvda_2026.3.1.exe' -OutFile $exe
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
"size $((Get-Item $exe).Length) bytes, SHA-256 $hash"
if ($hash -ne '6F80A5B0CA720A7D0D314B5BE212F37388BBE81A1107AC3298C1821A1CD3F052') { Remove-Item $exe; throw "SHA-256 mismatch: $hash" }
$sig = Get-AuthenticodeSignature $exe
"signature: $($sig.Status); signer: $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne 'Valid') { throw "signature not valid: $($sig.Status)" }
