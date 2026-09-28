@echo off
setlocal

echo === EnergeticHack setup (Windows) ===
echo.

set PYVER=

py -3.12 --version >nul 2>&1
if errorlevel 1 goto try311
set PYVER=3.12
goto found

:try311
py -3.11 --version >nul 2>&1
if errorlevel 1 goto try313
set PYVER=3.11
goto found

:try313
py -3.13 --version >nul 2>&1
if errorlevel 1 goto notfound
set PYVER=3.13
goto found

:notfound
echo [X] No suitable Python found via the py-launcher (tried 3.12, 3.11, 3.13).
echo.
echo Download and install Python 3.12 from:
echo https://www.python.org/downloads/release/python-3120/
echo During install, check the box "Add python.exe to PATH".
echo Then run this script again.
pause
exit /b 1

:found
echo [OK] Using Python %PYVER%
echo.

py -%PYVER% -m venv .venv
if errorlevel 1 (
    echo [X] Failed to create the virtual environment.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [X] pip install failed - see the errors above.
    pause
    exit /b 1
)

echo.
echo === Done ===
echo Next, in this same window:
echo   python -m scripts.run_demo --period daily
echo   uvicorn app.main:app --host 0.0.0.0 --port 8899
echo.
echo Next time, before running the app, activate the environment:
echo   In cmd:        .venv\Scripts\activate.bat
echo   In PowerShell: .venv\Scripts\Activate.ps1
pause
