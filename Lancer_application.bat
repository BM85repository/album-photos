@echo off
rem Album Photos - ouvre l'application (sans fenetre noire)
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 album_photos_app.pyw & exit /b)
where pythonw >nul 2>nul && (start "" pythonw album_photos_app.pyw & exit /b)
echo Python est introuvable : lancez d'abord Installer_application.bat.
pause
