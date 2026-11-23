@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python "Tools\trending\build_board.py" --open
) else (
  py -3.13 "Tools\trending\build_board.py" --open
)
if errorlevel 1 pause
