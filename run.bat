@echo off
setlocal

REM --- Configuration ---
set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt
set MAIN_SCRIPT=main.py
set PYTHON_CMD=python

REM --- Check for Python ---
echo Checking for Python...
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not found in your PATH.
    echo Please install Python 3 from python.org and ensure it's added to your PATH.
    pause
    exit /b 1
)

REM --- Virtual Environment Setup ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ---------------------------------------------------
    echo  First-time setup: Creating virtual environment...
    echo ---------------------------------------------------
    %PYTHON_CMD% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo Error: Failed to create the virtual environment.
        pause
        exit /b 1
    )

    echo.
    echo ---------------------------------------------------
    echo  Installing required packages...
    echo ---------------------------------------------------
    call "%VENV_DIR%\Scripts\activate.bat"
    pip install -r %REQUIREMENTS_FILE%
    if %errorlevel% neq 0 (
        echo Error: Failed to install packages from %REQUIREMENTS_FILE%.
        pause
        exit /b 1
    )
    echo.
    echo ---------------------------------------------------
    echo  Setup complete!
    echo ---------------------------------------------------
    echo.
)

REM --- Run the Application ---
echo Starting the Minecraft Server GUI...
call "%VENV_DIR%\Scripts\activate.bat"
%PYTHON_CMD% %MAIN_SCRIPT%

echo.
echo Application closed.
pause
endlocal
