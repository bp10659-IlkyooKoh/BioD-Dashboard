@echo off
chcp 65001 > nul
title BioD Dashboard Launcher

cd /d "%~dp0"

echo ============================================
echo BioD Dashboard Launcher
echo ============================================
echo Current folder:
echo %cd%
echo.

if not exist app.py (
    echo [ERROR] app.py was not found in this folder.
    pause
    exit /b
)

set "PYTHON_EXE=C:\Users\bp10659\AppData\Local\miniconda3\envs\work\python.exe"

echo Python path:
echo %PYTHON_EXE%
echo.

"%PYTHON_EXE%" --version

if errorlevel 1 (
    echo.
    echo [ERROR] Python executable path is not valid.
    echo Please check PYTHON_EXE in this bat file.
    pause
    exit /b
)

echo.
echo Checking Streamlit...
"%PYTHON_EXE%" -m streamlit --version

if errorlevel 1 (
    echo.
    echo [ERROR] Streamlit was not found in this Python environment.
    echo Install it from Jupyter with:
    echo.
    echo import sys
    echo !"{PYTHON_EXE}" -m pip install streamlit plotly openpyxl
    echo.
    pause
    exit /b
)

echo.
echo Starting BioD Dashboard...
echo If browser does not open, visit:
echo http://localhost:8501
echo.

"%PYTHON_EXE%" -m streamlit run app.py

pause