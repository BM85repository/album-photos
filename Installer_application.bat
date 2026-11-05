@echo off
rem Album Photos - installe l'application (bibliotheques, raccourcis Bureau et menu Demarrer)
cd /d "%~dp0"
if not exist "installer_app.py" goto zip
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto sanspython
%PY% installer_app.py
if errorlevel 9009 goto sanspython
echo.
pause
exit /b

:sanspython
echo.
echo Python est introuvable sur ce PC.
echo 1. Installez-le depuis https://www.python.org/downloads/
echo    en cochant la case "Add python.exe to PATH" sur le premier ecran.
echo 2. Redemarrez le PC, puis relancez ce fichier.
start "" https://www.python.org/downloads/
echo.
pause
exit /b

:zip
echo.
echo Les fichiers de l'outil sont introuvables a cote de ce .bat.
echo Le ZIP n'a sans doute pas ete decompresse : clic droit sur le ZIP, "Extraire tout...",
echo puis lancez le .bat depuis le dossier extrait.
echo.
pause
