@echo off
setlocal
set APP_STARTED=0

REM === Set Python script to run (change this if needed) ===
set PYFILE=room_main.py

REM === Set global icon path (shared for ALL apps) ===
set ICONPATH=C:\Users\VvV\Desktop\python code\IconGolbalSaveLocation\RCICON.ico

REM === Change working directory to the folder where this .bat is ===
cd /d "%~dp0"

:display_header
cls
echo.
echo                               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo                               ~~~~ This cmd starts RollerCoin Room Application ~~~~
echo                               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

echo  restart - restarts the app
echo  cls or clear - deletes the text

echo.
if "%APP_STARTED%"=="1" goto loop

:run
set APP_STARTED=1
echo Starting app...
"C:\Users\VvV\AppData\Local\Programs\Python\Python312\python.exe" "%PYFILE%" "%ICONPATH%"

:loop
set /p action=Type "restart" to run again, "clear" to clear screen, "cls" to clear screen, or "exit" to quit: 

if /i "%action%"=="restart" goto run
if /i "%action%"=="clear" goto display_header
if /i "%action%"=="cls" goto display_header
if /i "%action%"=="exit" exit

goto loop