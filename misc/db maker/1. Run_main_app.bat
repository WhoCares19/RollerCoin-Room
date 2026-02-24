@echo off
cd /d "C:\Users\VvV\Desktop\python code\RC ROOM\ImagesApp"

:run
echo Starting app...
"C:\Users\VvV\AppData\Local\Programs\Python\Python312\python.exe" main.py

:loop
set /p action=Type "restart" to run again, "clear" to clear screen, or "exit" to quit: 

if /i "%action%"=="restart" goto run
if /i "%action%"=="cls" (
    cls
    goto loop
)
if /i "%action%"=="exit" exit

goto loop
