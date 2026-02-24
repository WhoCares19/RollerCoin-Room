@echo off
setlocal

REM === Set Python script to run (change this if needed) ===
set PYFILE=assets/main.py

REM === Set global icon path (shared for ALL apps) ===
set ICONPATH=C:\Users\VvV\Desktop\python code\IconGolbalSaveLocation\RCICON.ico

REM === Change working directory to the folder where this .bat is ===
cd /d "%~dp0"

if not exist "%PYFILE%" (
    echo ERROR: "%PYFILE%" not found
    pause
    exit /b 1
)

:run
echo Starting app...
"C:\Users\VvV\AppData\Local\Programs\Python\Python312\python.exe" "%PYFILE%" "%ICONPATH%"

:loop
set /p action=Type "restart" to run again, "clear" to clear screen, "cls" to clear screen, or "exit" to quit: 

if /i "%action%"=="restart" goto run
if /i "%action%"=="clear" (
    cls
    goto loop
)
if /i "%action%"=="cls" (
    cls
    goto loop
)
if /i "%action%"=="exit" exit

goto loop
