$t = Get-ScheduledTask -TaskName ChatmonM4BToastDrill
"triggers: $(if ($t.Triggers) { @($t.Triggers).Count } else { 0 })"
"notification settings keys:"
Get-ChildItem HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings | Where-Object PSChildName -like 'RandyNorthrup*' | ForEach-Object PSChildName
"AppUserModelId keys:"
Get-ChildItem HKCU:\Software\Classes\AppUserModelId -ErrorAction SilentlyContinue | Where-Object PSChildName -like 'RandyNorthrup*' | ForEach-Object PSChildName
"python processes:"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object { "$($_.ProcessId) $($_.ExecutablePath)" }
