@echo off
rem Construit dist\Valorisation.exe (application autonome, un seul fichier).
rem Option : construire_exe.bat <dossier de sortie>   (par defaut : dist)
rem Prérequis : pip install -r requirements.txt pyinstaller
rem Les fichiers intermédiaires vont dans %TEMP% (chemins courts : le dossier du projet est profond).
setlocal
cd /d "%~dp0"
set "TRAVAIL=%TEMP%\valorisation_build"
set "SORTIE=%~dp0dist"
if not "%~1"=="" set "SORTIE=%~1"

python -m PyInstaller --noconfirm --clean --onefile --windowed --name Valorisation ^
  --icon "%~dp0valorisation\ressources\valorisation.ico" ^
  --workpath "%TRAVAIL%" --specpath "%TRAVAIL%" --distpath "%SORTIE%" ^
  --paths "%~dp0." ^
  --add-data "%~dp0valorisation\correspondances\*.yaml;valorisation\correspondances" ^
  --add-data "%~dp0valorisation\ressources\valorisation.ico;valorisation\ressources" ^
  --collect-all curl_cffi ^
  --hidden-import xlrd ^
  --exclude-module matplotlib --exclude-module scipy --exclude-module statsmodels --exclude-module arch ^
  --exclude-module IPython --exclude-module pytest --exclude-module PyQt5 --exclude-module PySide6 ^
  "%~dp0Valorisation.pyw"

if errorlevel 1 (
  echo.
  echo Echec de la construction.
  exit /b 1
)
echo.
echo Application construite : %SORTIE%\Valorisation.exe
endlocal
