@echo off
cd /d "%~dp0"
title Unisci File

echo.
echo Verifica dipendenze...

py -3 -c "import customtkinter" 2>nul
if %errorlevel% neq 0 (
    echo Installo customtkinter...
    py -3 -m pip install customtkinter
)

py -3 -c "import tkinterdnd2" 2>nul
if %errorlevel% neq 0 (
    echo Installo tkinterdnd2...
    py -3 -m pip install tkinterdnd2
)

echo Avvio...
echo.

py -3 main.py
if %errorlevel%==0 goto end

echo.
echo Lo script e' uscito con un errore (vedi sopra).
pause
exit /b

:end
