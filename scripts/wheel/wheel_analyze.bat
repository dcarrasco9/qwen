@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
if "%1"=="" (
    echo Usage: wheel_analyze.bat SYMBOL
    echo Example: wheel_analyze.bat SSYS
) else (
    python -m qwen.wheel.cli analyze %1
)
pause
