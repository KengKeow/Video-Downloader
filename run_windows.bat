@echo off
cd /d "%~dp0"
echo Installing/updating video utility dependency...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Python or installation unavailable. Make sure Python 3.10+ is installed.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8765"
py server.py
pause
