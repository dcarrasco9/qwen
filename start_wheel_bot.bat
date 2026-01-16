@echo off
REM Qwen Wheel Bot - Auto-start script
cd /d "C:\Users\dakot\Dev\projects\personal\qwen"
call .venv\Scripts\activate
python -m qwen.wheel.discord_bot
