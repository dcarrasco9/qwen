@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
if "%1"=="" (
    echo Usage: discord_analyze.bat SYMBOL
    echo Example: discord_analyze.bat SSYS
    pause
) else (
    python -m qwen.wheel.cli discord analyze %1
)
