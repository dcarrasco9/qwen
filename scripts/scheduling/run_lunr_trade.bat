@echo off
REM LUNR Wheel Trade - Market Open Execution
REM Schedule this with Windows Task Scheduler for 9:30 AM ET

cd /d "C:\Users\dakot\Dev\projects\personal\qwen"

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the trade (5 contracts = ~$9,000 collateral for $10k allocation)
python scripts\market_open_trade.py --symbol LUNR --contracts 5

REM Pause to see output if run manually
if "%1"=="" pause
