@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title LMU Overlays - publicar versao

rem ---- 1. encontrar o Git (instalado, ou o que vem com o GitHub Desktop) ----------------
set "GIT="
where git >nul 2>nul && set "GIT=git"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT (
  for /d %%d in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
    if exist "%%d\resources\app\git\cmd\git.exe" set "GIT=%%d\resources\app\git\cmd\git.exe"
  )
)
if not defined GIT (
  echo O Git nao esta instalado. Vou instalar agora ^(precisa de internet^)...
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
)
if not defined GIT (
  echo.
  echo Nao consegui instalar o Git sozinho. Instala-o em https://git-scm.com/download/win
  echo ^(Next, Next, ... Finish^) e volta a abrir este ficheiro.
  goto erro
)
echo Git: !GIT!

rem ---- 2. primeira vez: ligar esta pasta ao teu repositorio do GitHub ------------------
"!GIT!" rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo.
  echo Esta pasta ainda nao esta ligada ao GitHub.
  echo Cria primeiro um repositorio PUBLICO e VAZIO em github.com ^(+ ^> New repository^).
  set /p REPO=Endereco do repositorio ^(ex.: https://github.com/silvaleo00/lmu-overlays^):
  if "!REPO!"=="" goto erro
  "!GIT!" init -b main
  "!GIT!" remote add origin "!REPO!"
)
"!GIT!" remote get-url origin >nul 2>nul
if errorlevel 1 (
  set /p REPO=Endereco do repositorio no GitHub:
  if "!REPO!"=="" goto erro
  "!GIT!" remote add origin "!REPO!"
)
"!GIT!" config user.name >nul 2>nul || "!GIT!" config user.name "LMU Overlays"
"!GIT!" config user.email >nul 2>nul || "!GIT!" config user.email "lmu-overlays@users.noreply.github.com"

rem ---- 3. versao nova ------------------------------------------------------------------
for /f "tokens=2 delims==" %%a in ('findstr /b "VERSION" lmuov\version.py') do set CUR=%%a
set CUR=!CUR: =!
set CUR=!CUR:"=!
echo.
echo Versao atual: !CUR!
set /p NEW=Numero da nova versao (ex.: 1.2.0):
if "!NEW!"=="" goto erro
set /p MSG=O que mudou (uma linha):
if "!MSG!"=="" set MSG=Versao !NEW!

echo.
echo A correr os testes ...
set PY=py -3
where py >nul 2>nul || set PY=python
if exist ".build-venv\Scripts\python.exe" set PY=".build-venv\Scripts\python.exe"
%PY% tests\test_core.py
if errorlevel 1 (
  echo.
  echo Os testes falharam ^(ou o Python nao esta instalado^). Se for so o Python, corre antes o instalar.bat.
  goto erro
)

powershell -NoProfile -Command "(Get-Content 'lmuov\version.py') -replace '^VERSION = .*', 'VERSION = \"!NEW!\"' | Set-Content 'lmuov\version.py' -Encoding utf8"
"!GIT!" add -A
"!GIT!" commit -m "v!NEW!: !MSG!"
echo.
echo A enviar para o GitHub ^(na primeira vez abre o browser para entrares na tua conta^) ...
"!GIT!" pull --rebase origin main
"!GIT!" push -u origin main
if errorlevel 1 goto erro

echo.
echo ============================================================
echo  Enviado. O GitHub esta a compilar a v!NEW! (uns 5 minutos):
echo  separador Actions do teu repositorio. Quando acabar, as apps
echo  dos teus amigos mostram o botao "Atualizar para !NEW!".
echo ============================================================
pause
exit /b 0

:erro
echo.
echo Nao foi publicado. Ve as mensagens acima.
pause
exit /b 1
