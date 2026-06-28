@echo off
REM Double-click this file (Windows) to start the arbitrage dashboard.
REM It sets everything up the first time, then opens the dashboard in your browser.

cd /d "%~dp0"

echo Starting the arbitrage dashboard...

REM Find Python.
where py >nul 2>&1 && (set "PY=py") || (where python >nul 2>&1 && set "PY=python")
if not defined PY (
  echo.
  echo   Python is not installed yet.
  echo   Install it from https://www.python.org/downloads/
  echo   IMPORTANT: tick "Add Python to PATH" on the first screen of the installer.
  echo   Then double-click this file again.
  echo.
  pause
  exit /b 1
)

REM Create an isolated environment the first time, then reuse it.
if not exist ".venv" (
  echo First-time setup (this takes a minute)...
  %PY% -m venv .venv || (echo Setup failed. & pause & exit /b 1)
)

call .venv\Scripts\activate.bat
pip install -q --upgrade pip >nul 2>&1
pip install -q -r requirements.txt || (echo Install failed. & pause & exit /b 1)

python -m src.arb.webapp --open
pause
