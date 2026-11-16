# testpc2, over ssh as Technician (elevated): NVDA's two IAccessible2 proxy DLLs stay loaded in explorer.exe (the shell,
# which other projects' windows live in, so it isn't restarted): delete them, and their folders, at the next restart.
if ($env:COMPUTERNAME -ne 'TESTPC2') { "not TESTPC2"; exit 1 }
Add-Type -Namespace Probe -Name Native -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)] public static extern bool MoveFileEx(string from, string to, int flags);'
$items = @(
    'W:\chatmon-sr\nvda\lib\2026.3.1\x64\IAccessible2proxy.dll', 'W:\chatmon-sr\nvda\lib\2026.3.1\x64\ISimpleDOM.dll',
    'W:\chatmon-sr\nvda\lib\2026.3.1\x64', 'W:\chatmon-sr\nvda\lib\2026.3.1', 'W:\chatmon-sr\nvda\lib', 'W:\chatmon-sr\nvda', 'W:\chatmon-sr')
foreach ($item in $items) {
    $ok = [Probe.Native]::MoveFileEx($item, [NullString]::Value, 4)  # MOVEFILE_DELAY_UNTIL_REBOOT: deleted at the next restart, in this order
    "$item : delete at next restart $(if ($ok) { 'scheduled' } else { 'FAILED ' + [Runtime.InteropServices.Marshal]::GetLastWin32Error() })"
}
$pending = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
"pending deletions naming chatmon-sr: $(@($pending | Where-Object { $_ -like '*chatmon-sr*' }).Count)"
