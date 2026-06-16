@echo off
setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
REM Go to project root (parent of scripts directory)
cd /d "%SCRIPT_DIR%.."

REM Set PYTHONPATH to project root
set PYTHONPATH=%cd%

REM Run the ETL pipeline
"%cd%\venv\Scripts\python.exe" "%SCRIPT_DIR%run_etl.py"

pause
