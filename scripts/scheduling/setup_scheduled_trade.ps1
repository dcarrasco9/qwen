# Setup Scheduled Trade Task for Windows Task Scheduler
# Run this script as Administrator to create the scheduled task

param(
    [string]$Symbol = "LUNR",
    [int]$Contracts = 5,
    [string]$Time = "09:31",  # 9:31 AM (1 min after market open for stability)
    [switch]$DryRun
)

$TaskName = "WheelTrade_$Symbol"
$ProjectPath = "C:\Users\dakot\Dev\projects\personal\qwen"
$ScriptPath = "$ProjectPath\scripts\market_open_trade.py"

# Build arguments
$Arguments = "--symbol $Symbol --contracts $Contracts"
if ($DryRun) {
    $Arguments += " --dry-run"
    $TaskName += "_DryRun"
}

# Python executable (adjust if using venv)
$PythonPath = "python"
if (Test-Path "$ProjectPath\venv\Scripts\python.exe") {
    $PythonPath = "$ProjectPath\venv\Scripts\python.exe"
}

Write-Host "Setting up scheduled trade task..." -ForegroundColor Cyan
Write-Host "  Task Name: $TaskName"
Write-Host "  Symbol: $Symbol"
Write-Host "  Contracts: $Contracts"
Write-Host "  Time: $Time ET (weekdays only)"
Write-Host "  Dry Run: $DryRun"
Write-Host ""

# Remove existing task if exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" $Arguments" `
    -WorkingDirectory $ProjectPath

# Create trigger for weekdays at specified time (ET)
# Note: Windows Task Scheduler uses local time, adjust if needed
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At $Time

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Create the task
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Wheel strategy trade execution for $Symbol - $Contracts contracts at market open"

    Write-Host ""
    Write-Host "Task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To test the task immediately:"
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""
    Write-Host "To view task status:"
    Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""
    Write-Host "To remove the task:"
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""

    # Show Discord notification setup reminder
    Write-Host "IMPORTANT: Ensure DISCORD_WEBHOOK_URL is set in .env" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Host "Failed to create task: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try running PowerShell as Administrator" -ForegroundColor Yellow
    exit 1
}

# Option to run a test now
$runNow = Read-Host "Run a dry-run test now? (y/n)"
if ($runNow -eq "y" -or $runNow -eq "Y") {
    Write-Host ""
    Write-Host "Running dry-run test..." -ForegroundColor Cyan
    & $PythonPath $ScriptPath --symbol $Symbol --contracts $Contracts --dry-run
}
