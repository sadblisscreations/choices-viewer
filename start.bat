@echo off
REM Activate virtual environment
call "C:\Users\owain\Locker\choices_viewer\venv\Scripts\activate.bat"

REM Change to working directory
cd /d "C:\Users\owain\Locker"

REM Run the program
python -m choices_viewer

REM Keep window open if there is an error
pause