@echo off
cd /d "%~dp0"
set PY=py -3
where py >nul 2>nul || set PY=python
echo A instalar o PySide6...
%PY% -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
  echo.
  echo Falhou. Confirma que o Python esta instalado e com "Add python.exe to PATH" marcado.
) else (
  echo.
  echo Pronto. Usa iniciar.bat ^(jogo^) ou demo.bat ^(dados simulados^).
)
pause
