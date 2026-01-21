# Update scheduled tasks to Pacific Time
# Market opens 9:30 AM ET = 6:30 AM PT

$ProjectPath = "C:\Users\dakot\Dev\projects\personal\qwen"

# Remove and recreate LUNR task at 6:31 AM PT
$TaskName = "WheelTrade_LUNR"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing $TaskName"
}

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
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "LUNR wheel trade - 6:31 AM PT (9:31 AM ET)"

Write-Host "Created $TaskName at 6:31 AM PT"

# Remove and recreate ONDS task at 6:32 AM PT
$TaskName = "WheelTrade_ONDS"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing $TaskName"
}

$Action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "`"$ProjectPath\scripts\market_open_trade.py`" --symbol ONDS --contracts 9" `
    -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "06:32"

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "ONDS wheel trade - 6:32 AM PT (9:32 AM ET)"

Write-Host "Created $TaskName at 6:32 AM PT"

Write-Host ""
Write-Host "Scheduled Tasks Updated:" -ForegroundColor Green
Get-ScheduledTask -TaskName "WheelTrade_*" | Format-Table TaskName, State
