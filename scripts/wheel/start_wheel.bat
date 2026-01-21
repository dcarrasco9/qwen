@echo off
echo Starting Qwen Wheel Automation...
cd /d "%~dp0"
call .venv\Scripts\activate
python -m qwen.wheel.cli start
pause
