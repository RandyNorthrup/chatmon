Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'powershell.exe', 'python.exe', 'pythonw.exe', 'cmd.exe' } |
    ForEach-Object { "$($_.ProcessId) parent $($_.ParentProcessId) session $($_.SessionId) $($_.CreationDate) $($_.CommandLine)" }
