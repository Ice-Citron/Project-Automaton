@echo off
set /p IP="Enter new Vast IP: "
set /p PORT="Enter new Vast port: "
scp -r -P %PORT% C:\Users\USER\VastAI-Backup\workspace root@%IP%:/
echo Restore complete!
pause