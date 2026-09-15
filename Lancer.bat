@echo off
REM Lance pv-dashboard en mode DEBUG avec console visible.
REM Utilise le Python Launcher officiel Windows (py.exe).
REM Pour un lancement silencieux, utilisez Lancer.vbs.

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERREUR : Python Launcher ^(py.exe^) introuvable.
    echo Installez Python 3 depuis python.org en cochant
    echo "Install launcher for all users".
    echo.
    pause
    exit /b 1
)

py run.py
echo.
echo Application fermee. Appuyez sur une touche pour quitter.
pause >nul
