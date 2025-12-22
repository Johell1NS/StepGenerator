@echo off
setlocal EnableDelayedExpansion
title StepMania Chart Generator - ArrowVortex Workflow
color 0F

:MENU
cls
echo.
echo ============================================================
echo   STEPMANIA CHART GENERATOR - ArrowVortex Workflow
echo ============================================================
echo.
echo   1. APRI IN ARROWVORTEX
echo      (Apre l'MP3 o l'.sm selezionato direttamente nel tool)
echo.
echo   2. RIGENERA GRAFICO (VELOCE)
echo      (Riprocessa un grafico esistente usando i dati salvati)
echo.
echo   3. MODIFICA DIFFICOLTA
echo      (Aumenta/Diminuisce difficolta +/- 20%% preservando Holds)
echo.
echo   4. SUPPORT ME
echo      (Support the project development)
echo.
echo   9. Esci
echo.
echo ============================================================
echo.

set /p choice="Seleziona opzione, o inserisci un URL YouTube: "

echo !choice! | findstr /C:"http" >nul
if !errorlevel!==0 goto YOUTUBE_DL

if "!choice!"=="1" goto OPEN_AV
if "!choice!"=="2" goto REGENERATE
if "!choice!"=="3" goto MOD_STEPS
if "!choice!"=="4" goto SUPPORT
if "!choice!"=="9" goto EXIT

echo.
echo Scelta non valida!
timeout /t 2 >nul
goto MENU

:OPEN_AV
cls
echo.
echo ============================================================
echo   1. APRI IN ARROWVORTEX
echo ============================================================
echo.
call venv\Scripts\activate.bat
python src\open_in_arrowvortex.py
pause
goto MENU

:REGENERATE
cls
echo.
echo ============================================================
echo   2. RIGENERA GRAFICO (VELOCE)
echo ============================================================
echo.
call venv\Scripts\activate.bat
python src\regenerate_menu.py
pause
goto MENU

:MOD_STEPS
cls
echo.
echo ============================================================
echo   3. MODIFICA DIFFICOLTA
echo ============================================================
echo.
call venv\Scripts\activate.bat
python src\modifica_steps.py
pause
goto MENU

:SUPPORT
cls
echo.
echo ============================================================
echo   4. SUPPORT ME
echo ============================================================
echo.
call venv\Scripts\activate.bat
python src\support_me.py
goto MENU

:YOUTUBE_DL
cls
echo.
echo ============================================================
echo   SCARICAMENTO DA YOUTUBE
echo ============================================================
echo.
call venv\Scripts\activate.bat
python src\audioYouTube.py "!choice!"
pause
goto MENU

:EXIT
exit
