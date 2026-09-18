@echo off
title WeatherGPT
cd /d "%~dp0"

if exist ".\venv\Scripts\python.exe" (
    echo Starting WeatherGPT with existing virtual environment...
    ".\venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
) else (
    echo Virtual environment not found. Using system Python...
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
)
pause
