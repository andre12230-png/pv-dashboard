@echo off
rem ==========================================================================
rem  Construit pv-dashboard.exe (dossier dist\pv-dashboard\).
rem  Double-cliquez ce fichier apres avoir ferme l'application.
rem
rem  Le programme lit ses donnees (config.yaml, Releves-pv.csv, backups\,
rem  pv-dashboard.ico) DEUX crans plus haut, c'est-a-dire dans ce dossier-ci.
rem  Elles ne sont donc jamais touchees par une reconstruction, qui efface et
rem  recree entierement dist\pv-dashboard\.
rem ==========================================================================

cd /d "%~dp0"

rem --------------------------------------------------------------------------
rem  "py" et non "python" : ce sont DEUX installations differentes sur ce PC.
rem  C'est "py" qui lance l'application et les tests ; en construisant avec
rem  lui, l'exe embarque exactement les bibliotheques que les tests ont
rem  verifiees.
rem --------------------------------------------------------------------------
if not defined PYTHON set "PYTHON=py"

"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller est absent : installation...
    "%PYTHON%" -m pip install --quiet pyinstaller
    if errorlevel 1 (
        echo ERREUR : impossible d'installer PyInstaller.
        pause
        exit /b 1
    )
)

echo Construction de pv-dashboard.exe ...
echo.

rem --------------------------------------------------------------------------
rem  --windowed        : pas de console noire derriere l'application.
rem  --onedir          : demarrage rapide. En --onefile, les ~300 Mo de
rem                      PySide6 + matplotlib + pandas seraient decompresses
rem                      a CHAQUE lancement.
rem  run.py            : le lanceur avec ecran d'attente, pas app_desktop.py.
rem  --exclude-module  : tkinter et PyQt ne servent pas (matplotlib tourne en
rem                      QtAgg, voir gui_widgets.py) mais seraient embarques
rem                      parce que presents sur le PC.
rem --------------------------------------------------------------------------
"%PYTHON%" -m PyInstaller --noconfirm --onedir --windowed ^
  --name "pv-dashboard" ^
  --icon "pv-dashboard.ico" ^
  --exclude-module tkinter ^
  --exclude-module PyQt5 ^
  --exclude-module PyQt6 ^
  --exclude-module pytest ^
  run.py

echo.
if exist "dist\pv-dashboard\pv-dashboard.exe" (
    echo Termine : dist\pv-dashboard\pv-dashboard.exe
    echo.
    echo Pour l'utiliser au quotidien, faites un raccourci vers ce fichier.
    echo NE LE DEPLACEZ PAS ailleurs : il ne trouverait plus vos donnees.
) else (
    echo ECHEC : lisez les messages ci-dessus.
)
echo.
pause
