# Create startup shortcuts for Qwen Wheel Bot and Dashboard
$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"

# Wheel Bot shortcut
$BotShortcut = $WshShell.CreateShortcut("$StartupPath\QwenWheelBot.lnk")
$BotShortcut.TargetPath = "C:\Users\dakot\Dev\projects\personal\qwen\start_wheel_bot.bat"
$BotShortcut.WorkingDirectory = "C:\Users\dakot\Dev\projects\personal\qwen"
$BotShortcut.WindowStyle = 7  # Minimized
$BotShortcut.Save()
Write-Host "Created: QwenWheelBot.lnk"

# Dashboard shortcut
$DashShortcut = $WshShell.CreateShortcut("$StartupPath\QwenDashboard.lnk")
$DashShortcut.TargetPath = "C:\Users\dakot\Dev\projects\personal\qwen\start_dashboard.bat"
$DashShortcut.WorkingDirectory = "C:\Users\dakot\Dev\projects\personal\qwen"
$DashShortcut.WindowStyle = 7  # Minimized
$DashShortcut.Save()
Write-Host "Created: QwenDashboard.lnk"

Write-Host ""
Write-Host "Startup shortcuts created successfully!"
Write-Host "Both will start automatically on login."
