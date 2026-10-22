@echo off
cd /d "%~dp0"
set PY=py -3
where py >nul 2>nul || set PY=python
%PY% -c "import PySide6" 2>nul || (echo Falta o PySide6: corre primeiro instalar.bat & pause & exit /b 1)
set PYW=pyw -3
where pyw >nul 2>nul || set PYW=pythonw
start "" %PYW% run.py %*
