$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\QwenWheelBot.lnk")
$Shortcut.TargetPath = "C:\Users\dakot\Dev\projects\personal\qwen\start_wheel_bot.bat"
$Shortcut.WorkingDirectory = "C:\Users\dakot\Dev\projects\personal\qwen"
$Shortcut.WindowStyle = 7  # Minimized
$Shortcut.Save()
Write-Host "Startup shortcut created successfully!"
