@echo off
REM ONDS Wheel Trade - Market Open Execution
REM Schedule this with Windows Task Scheduler for 9:32 AM ET

cd /d "C:\Users\dakot\Dev\projects\personal\qwen"

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the trade (9 contracts = ~$9,450 collateral for $10k allocation)
python scripts\market_open_trade.py --symbol ONDS --contracts 9

REM Pause to see output if run manually
if "%1"=="" pause
