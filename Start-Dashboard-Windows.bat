@echo off
setlocal enableextensions
cd /d "%~dp0"

echo ============================================================
echo   Arbitrage Dashboard launcher
echo ============================================================
echo Folder: %cd%
echo.

REM --- Guard: are the project files actually here? -----------
REM If not, you almost certainly double-clicked this from INSIDE the
REM zip preview without extracting it first.
if not exist "requirements.txt" (
  echo I can't find the project files in this folder.
  echo.
  echo This usually means the download was not unzipped, and you opened
  echo this file from inside the ZIP preview window.
  echo.
  echo HOW TO FIX:
  echo   1. Find the downloaded .zip file ^(probably in Downloads^).
  echo   2. Right-click it and choose "Extract All...".
  echo   3. Open the new extracted folder.
  echo   4. Double-click this launcher again from inside that folder.
  echo.
  pause
  exit /b 1
)

REM --- Find Python -------------------------------------------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python is not installed yet.
  echo.
  echo   Get it from https://www.python.org/downloads/
  echo   IMPORTANT: on the installer's FIRST screen, tick
  echo   "Add Python to PATH" before clicking Install.
  echo.
  echo Then double-click this launcher again.
  echo.
  pause
  exit /b 1
)
echo Using Python: %PY%

REM --- First-time setup --------------------------------------
if not exist ".venv" (
  echo First-time setup, please wait about a minute...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo Setup failed while creating the environment.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
echo Installing components...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo.
echo Starting the dashboard. Your browser will open in a moment.
echo Leave THIS window open while you use it. Close it to stop.
echo.
python -m src.arb.webapp --open

echo.
echo The dashboard has stopped.
pause
