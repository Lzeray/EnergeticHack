@echo off
setlocal enabledelayedexpansion

echo === EnergeticHack: setup (Windows) ===
echo.

set PYVER=
for %%v in (3.12 3.11 3.13) do (
    if not defined PYVER (
        py -%%v --version >nul 2>&1
        if not errorlevel 1 (
            set PYVER=%%v
        )
    )
)

if not defined PYVER (
    echo [X] Не найден подходящий Python (3.11 / 3.12 / 3.13) через py-launcher.
    echo.
    echo     Скачай и установи Python 3.12:
    echo     https://www.python.org/downloads/release/python-3120/
    echo     При установке ОБЯЗАТЕЛЬНО поставь галочку "Add python.exe to PATH".
    echo.
    echo     Потом запусти этот файл ещё раз.
    pause
    exit /b 1
)

echo [OK] Использую Python %PYVER% ^(py -%PYVER%^)
echo.

py -%PYVER% -m venv .venv
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip -q
pip install -r requirements.txt

echo.
echo === Готово ===
echo Дальше в этом же окне:
echo   python -m scripts.run_demo --period daily
echo   uvicorn app.main:app --host 0.0.0.0 --port 8899
echo.
echo В следующий раз перед запуском активируй окружение:
echo   .venv\Scripts\activate.bat
pause
