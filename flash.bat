@echo off
REM flash.bat - installe les dependances, verifie le firmware et flashe le Model:Cycles (Windows).
REM Double-clique ce fichier, ou en ligne de commande :
REM    flash.bat                   auto-detecte le .syx, installe, verifie, flashe
REM    flash.bat mon.syx           flashe ce fichier precis
REM    flash.bat --verify mon.syx  verifie seulement (rien envoye)
REM
REM /!\ Le flash se fait par l'entree MIDI IN de l'appareil (jack TRS 3,5 mm) : interface a sortie
REM     TRS + cable jack stereo, ou interface DIN + adaptateur fourni. Jamais par l'USB.
REM     Lis RECOVERY.md avant. Tu flashes a tes risques (garantie ; brick possible mais recuperable par le MIDI IN).
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV=.venv"
set "VERIFY_ONLY=0"
set "SYX="

REM ---- 1. arguments ----------------------------------------------------------
for %%a in (%*) do (
  if /I "%%~a"=="--verify" (set "VERIFY_ONLY=1") else (
    echo %%~a| findstr /I /E ".syx" >nul && set "SYX=%%~a"
  )
)

REM auto-detection : priorite au *_mod.syx le plus recent, sinon model-cycles_OS*.syx
if "%SYX%"=="" (
  for /f "delims=" %%f in ('dir /b /o-d *_mod.syx 2^>nul') do (set "SYX=%%f" & goto :gotsyx)
  for /f "delims=" %%f in ('dir /b /o-d model-cycles_OS*.syx 2^>nul') do (set "SYX=%%f" & goto :gotsyx)
)
:gotsyx
if "%SYX%"=="" (
  echo [31mAucun fichier .syx trouve.[0m
  echo Construis d'abord un firmware modifie :
  echo    python tools\build.py -i model-cycles_OS1.13.syx -t 6ch-multiout
  echo ...ou pose ton .syx ici et relance :  flash.bat mon.syx
  pause & exit /b 1
)
if not exist "%SYX%" ( echo [31mFichier introuvable : %SYX%[0m & pause & exit /b 1 )
echo.
echo Fichier cible : %SYX%

REM ---- 2. Python 3 -----------------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if "%PY%"=="" ( where python >nul 2>&1 && set "PY=python" )
if "%PY%"=="" (
  echo [31mPython 3 est introuvable.[0m
  echo Installe-le depuis https://www.python.org/downloads/  ^(coche "Add Python to PATH"^)
  echo ...ou via le Microsoft Store : "Python 3".
  pause & exit /b 1
)
echo Python : & %PY% --version

REM ---- 3. venv + dependances (mido + python-rtmidi) --------------------------
if not exist "%VENV%\Scripts\python.exe" (
  echo.
  echo Creation de l'environnement Python ^(.venv^)...
  %PY% -m venv "%VENV%" || ( echo [31mEchec de la creation du venv.[0m & pause & exit /b 1 )
)
set "VPY=%VENV%\Scripts\python.exe"
echo.
echo Installation des dependances ^(mido, python-rtmidi^)...
"%VPY%" -m pip install --quiet --upgrade pip >nul 2>&1
"%VPY%" -m pip install --quiet mido python-rtmidi
if errorlevel 1 (
  echo [31mEchec de l'installation de python-rtmidi.[0m
  echo Installe "Microsoft C++ Build Tools" si demande, puis relance :
  echo    https://visualstudio.microsoft.com/visual-cpp-build-tools/
  pause & exit /b 1
)

REM ---- 4. verification du fichier -------------------------------------------
echo.
echo Verification du fichier...
"%VPY%" tools\flash.py "%SYX%" --verify
if errorlevel 1 ( pause & exit /b 1 )
if "%VERIFY_ONLY%"=="1" (
  echo.
  echo Verification seule demandee. Rien n'a ete envoye.
  pause & exit /b 0
)

REM ---- 5. rappel de branchement + flash -------------------------------------
echo.
echo ----------------------------------------------------------------------------
echo  AVANT DE CONTINUER
echo  1. Relie la sortie MIDI de ton interface au MIDI IN du Model:Cycles (jack TRS) :
echo     cable jack stereo si l'interface a une sortie TRS, sinon DIN + adaptateur fourni.
echo  2. Sauvegarde tes projets (Elektron Transfer) - le flash peut les affecter.
echo  3. Passe l'appareil en mode reception :
echo         eteindre -^> maintenir [FUNC] -^> allumer -^> [TRIG 4] (OS UPGRADE)
echo     L'ecran doit afficher "READY TO RECEIVE".
echo  4. Garde ton .syx OFFICIEL sous la main : c'est ta recuperation (meme procedure).
echo ----------------------------------------------------------------------------
echo.
echo Lancement du flasher (il te fera choisir le port et confirmer)...
"%VPY%" tools\flash.py "%SYX%" --send
pause
