@echo off
setlocal
cd /d "%~dp0"
title LMU Overlays - criar .exe

set PY=py -3
where py >nul 2>nul || set PY=python
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Precisas do Python instalado NESTE PC para criar o .exe ^(os teus amigos nao^).
  echo Instala de https://www.python.org/downloads/ e marca "Add python.exe to PATH".
  goto erro
)

echo [1/4] A preparar um ambiente limpo em .build-venv ...
if not exist ".build-venv\Scripts\python.exe" (
  %PY% -m venv .build-venv
  if errorlevel 1 goto erro
)
set VPY=.build-venv\Scripts\python.exe
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install --upgrade pyside6-essentials pyinstaller
if errorlevel 1 goto erro

echo.
echo [2/4] A correr os testes ...
"%VPY%" tests\test_core.py
if errorlevel 1 goto erro

echo.
echo [3/4] A gerar o executavel (demora 1-2 minutos) ...
"%VPY%" -m PyInstaller --noconfirm --clean lmu_overlays.spec
if errorlevel 1 goto erro
copy /y "LEIA-ME_amigos.txt" "dist\LMU Overlays\LEIA-ME.txt" >nul

echo.
echo [4/4] A criar o zip para partilhar ...
if exist "dist\LMU_Overlays_Windows.zip" del /q "dist\LMU_Overlays_Windows.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\LMU Overlays' -DestinationPath 'dist\LMU_Overlays_Windows.zip' -Force"
if errorlevel 1 goto erro

echo.
echo ============================================================
echo  Pronto:  dist\LMU_Overlays_Windows.zip
echo  Envia esse zip aos teus amigos. Nao precisam de Python.
echo ============================================================
explorer "dist"
pause
exit /b 0

:erro
echo.
echo Algo falhou. Ve as mensagens acima (ou manda-mas).
pause
exit /b 1
