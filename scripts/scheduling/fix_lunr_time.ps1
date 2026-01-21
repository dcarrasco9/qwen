# Fix LUNR scheduled task to 6:31 AM Pacific Time
$TaskName = "WheelTrade_LUNR"
$ProjectPath = "C:\Users\dakot\Dev\projects\personal\qwen"

# Force remove existing
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

# Create new task at 6:31 AM PT
$Action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "`"$ProjectPath\scripts\market_open_trade.py`" --symbol LUNR --contracts 5" `
    -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "06:31"

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "LUNR wheel trade - 6:31 AM PT (9:31 AM ET)" `
    -Force

Write-Host "Task times:"
Get-ScheduledTaskInfo -TaskName "WheelTrade_LUNR" | Select-Object TaskName, NextRunTime
Get-ScheduledTaskInfo -TaskName "WheelTrade_ONDS" | Select-Object TaskName, NextRunTime
