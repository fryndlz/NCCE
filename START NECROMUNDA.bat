@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Krakaumunda Story Engine

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo.
  echo ============================================================
  echo  KRAKAUMUNDA STORY ENGINE - STARTUP ERROR
  echo ============================================================
  echo.
  echo Python 3 was not found on this PC.
  echo.
  echo Install Python 3 from https://www.python.org/downloads/windows/
  echo During installation, enable "Add python.exe to PATH".
  echo Then double-click START NECROMUNDA.bat again.
  echo.
  pause
  exit /b 1
)

%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 goto :python_error

if not exist "data" mkdir "data"
if not exist "data\chronicle.db" (
  echo Creating the campaign database for the first run...
  %PYTHON_CMD% src\seed.py data\chronicle.db
  if errorlevel 1 goto :seed_error
)

echo.
echo ============================================================
echo  KRAKAUMUNDA STORY ENGINE
 echo ============================================================
echo.
echo Starting at http://127.0.0.1:8765
echo Keep this window open while using the app.
echo Press Ctrl+C here to stop it.
echo.

start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'"
%PYTHON_CMD% src\server.py
if errorlevel 1 goto :server_error
exit /b 0

:python_error
echo.
echo Python was found, but Python 3 could not be started.
echo Command attempted: %PYTHON_CMD%
echo.
pause
exit /b 1

:seed_error
echo.
echo ============================================================
echo  DATABASE INITIALIZATION FAILED
 echo ============================================================
echo The app could not create its initial campaign database.
echo The error from Python is shown above.
echo.
pause
exit /b 1

:server_error
echo.
echo ============================================================
echo  SERVER FAILED TO START
 echo ============================================================
echo The error from Python is shown above.
echo.
echo A common cause is another copy already running on port 8765.
echo Try opening http://127.0.0.1:8765 in your browser first.
echo.
pause
exit /b 1
