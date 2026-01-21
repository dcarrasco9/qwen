@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python -m qwen.wheel.cli discord briefing
