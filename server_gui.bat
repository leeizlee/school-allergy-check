@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 goto use_python
start "" pythonw.exe "%~dp0server_gui.py"
exit /b

:use_python
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process python -ArgumentList '\"%~dp0server_gui.py\"' -WorkingDirectory '\"%~dp0\"' -WindowStyle Hidden"
exit /b
