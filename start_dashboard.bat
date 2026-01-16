@echo off
REM Qwen Dashboard - Auto-start script
cd /d "C:\Users\dakot\Dev\projects\personal\qwen"
call .venv\Scripts\activate
streamlit run qwen/dashboard_pro.py --server.headless true
