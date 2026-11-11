# Install Chatmon from its installer, check what it set up, run it, uninstall it, and check that it all
# went again. For CI's fresh Windows machines: it really installs, for the current user, with every option.
#   pwsh packaging/windows/test-install.ps1 dist\Chatmon-x.y.z-windows-x64-setup.exe x.y.z [-Unsigned]
# A release's installer and uninstaller must be signed by Randy Northrup; -Unsigned, for one built
# without signing, checks they aren't. chatmon.exe and chatmonw.exe are never signed: packaging/README.md.
param([Parameter(Mandatory)] [string]$Setup, [Parameter(Mandatory)] [string]$Version, [switch]$Unsigned)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$app = Join-Path $env:LOCALAPPDATA "Programs\Chatmon"
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Chatmon.lnk"
$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Chatmon.lnk"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

# Your PATH as the registry holds it: its type and its text, %VARIABLES% unexpanded.
function RawPath {
    $key = Get-Item HKCU:\Environment
    if ($key.GetValueNames() -notcontains "Path") { return "<none>" }
    "$($key.GetValueKind('Path')): $($key.GetValue('Path', $null, 'DoNotExpandEnvironmentNames'))"
}
$pathBefore = RawPath

function Check($what, $ok) {
    if (-not $ok) { throw "FAILED: $what" }
    Write-Host "ok: $what"
}
function Signature($what, $file, [switch]$Never) {
    $sig = Get-AuthenticodeSignature $file
    if ($Never -or $Unsigned) {
        Check "$what isn't signed ($($sig.Status))" ($sig.Status -eq "NotSigned")
    } else {
        $by = "$($sig.SignerCertificate.Subject), timestamped by $($sig.TimeStamperCertificate.Subject)"
        Check "$what is signed: $($sig.Status), by $by" (
            $sig.Status -eq "Valid" -and $sig.SignerCertificate.Subject -match "^CN=Randy Northrup(,|$)" -and $sig.TimeStamperCertificate)
    }
}
function Shortcut($path) { (New-Object -ComObject WScript.Shell).CreateShortcut($path).TargetPath }
function UserPath { ([Environment]::GetEnvironmentVariable("Path", "User") -split ";") | Where-Object { $_ } }
function Uninstall-Entry {
    Get-ChildItem HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall | Get-ItemProperty | Where-Object DisplayName -eq "Chatmon"
}

Signature "the installer" $Setup
$p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/TASKS=startmenu,desktop,path,autostart" -Wait -PassThru
Check "the installer finished (exit $($p.ExitCode))" ($p.ExitCode -eq 0)
Check "chatmon.exe and chatmonw.exe in $app" ((Test-Path "$app\chatmon.exe") -and (Test-Path "$app\chatmonw.exe"))
Signature "the uninstaller" "$app\unins000.exe"
Signature "chatmon.exe" "$app\chatmon.exe" -Never
Signature "chatmonw.exe" "$app\chatmonw.exe" -Never
Check "a Start menu entry that starts chatmonw.exe" ((Test-Path $startMenu) -and ((Shortcut $startMenu) -eq "$app\chatmonw.exe"))
Check "a desktop icon that starts chatmonw.exe" ((Test-Path $desktop) -and ((Shortcut $desktop) -eq "$app\chatmonw.exe"))
Check "its folder on your PATH" ((UserPath) -contains $app)
Check "starting at login" ((Get-ItemProperty $runKey -Name Chatmon -ErrorAction SilentlyContinue).Chatmon -eq "`"$app\chatmonw.exe`"")
$entry = Uninstall-Entry
Check "in Apps & features as Chatmon $Version" ($entry -and $entry.DisplayVersion -eq $Version)

python (Join-Path $root "packaging\build.py") smoke "$app\chatmon.exe" "$app\chatmonw.exe" --version $Version
Check "the installed Chatmon runs" ($LASTEXITCODE -eq 0)

# The uninstaller hands over to a copy of itself and returns at once: wait for the folder to go.
Start-Process "$app\unins000.exe" -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
for ($i = 0; $i -lt 60 -and ((Test-Path $app) -or (Uninstall-Entry)); $i++) { Start-Sleep 1 }
Check "its folder is gone" (-not (Test-Path $app))
Check "the Start menu entry and desktop icon are gone" (-not (Test-Path $startMenu) -and -not (Test-Path $desktop))
$pathAfter = RawPath
if ($pathAfter -ne $pathBefore) { Write-Host "PATH before: $pathBefore`nPATH after:  $pathAfter" }
Check "PATH is as it was, type and all" ($pathAfter -eq $pathBefore)
Check "it no longer starts at login" ($null -eq (Get-ItemProperty $runKey -Name Chatmon -ErrorAction SilentlyContinue))
Check "it's gone from Apps & features" ($null -eq (Uninstall-Entry))
