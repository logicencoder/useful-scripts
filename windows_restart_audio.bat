@echo off
echo Stopping Windows Audio services...
net stop "Windows Audio Endpoint Builder" /y
net stop "Windows Audio"

echo Waiting 2 seconds...
timeout /t 2 >nul

echo Starting Windows Audio services...
net start "Windows Audio Endpoint Builder"
net start "Windows Audio"

echo Done.
pause
