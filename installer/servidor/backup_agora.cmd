@echo off
rem Backup do banco do Cortex ERP. Executado diariamente pelo Agendador de Tarefas.
cd /d "%~dp0app"
"%~dp0python\python.exe" "%~dp0app\scripts\backup.py" --dest "%~dp0Backups" --keep 30 >> "%~dp0logs\backup.log" 2>&1
set RESULTADO=%errorlevel%
if /i "%~1"=="/silencioso" exit /b %RESULTADO%
if %RESULTADO%==0 (echo Backup concluido. Arquivos em "%~dp0Backups") else (echo Falha no backup. Veja "%~dp0logs\backup.log")
pause
