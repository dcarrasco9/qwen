#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Install Qwen Wheel Bot as a Windows Service using Task Scheduler
    This allows the bot to run even when not logged in.

.DESCRIPTION
    Run this script as Administrator to set up the bot as a background service.
    The bot will start automatically when Windows boots (not just on login).
#>

$TaskName = "QwenWheelBotService"
$ScriptPath = "C:\Users\dakot\Dev\projects\personal\qwen\start_wheel_bot.bat"
$Description = "Qwen Wheel Strategy Discord Bot - runs continuously for notifications"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing Qwen Wheel Bot as a Windows Service..." -ForegroundColor Cyan

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action
$Action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory "C:\Users\dakot\Dev\projects\personal\qwen"

# Create trigger - at system startup
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Create principal - run whether logged in or not
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Register the task
$Task = New-ScheduledTask -Action $Action -Principal $Principal -Trigger $Trigger -Settings $Settings -Description $Description
Register-ScheduledTask -TaskName $TaskName -InputObject $Task

Write-Host ""
Write-Host "SUCCESS! Qwen Wheel Bot service installed." -ForegroundColor Green
Write-Host ""
Write-Host "The bot will now:" -ForegroundColor White
Write-Host "  - Start automatically when Windows boots" -ForegroundColor Gray
Write-Host "  - Run even when no user is logged in" -ForegroundColor Gray
Write-Host "  - Automatically restart if it crashes" -ForegroundColor Gray
Write-Host ""
Write-Host "To start the service now:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host ""
Write-Host "To check status:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Select-Object State" -ForegroundColor Gray
Write-Host ""
Write-Host "To uninstall:" -ForegroundColor Yellow
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Gray

# Ask to start now
$start = Read-Host "Start the service now? (Y/n)"
if ($start -ne 'n' -and $start -ne 'N') {
    Write-Host "Starting service..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    $status = (Get-ScheduledTask -TaskName $TaskName).State
    Write-Host "Service status: $status" -ForegroundColor Green
}
