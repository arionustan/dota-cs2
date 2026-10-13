@echo off
title DotaWC3 launcher
rem DotaWC3: Dota 2 x Warcraft III. Close Dota 2, WC3 and the CS2 server first.
set "DOTA=C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta"
set "WC3=C:\Games\Warcraft III"
set "HERE=%~dp0"

if not exist "%DOTA%\game\dota_addons\dotacs\models\wc3\blademaster\blademaster.vmdl_c" (
  echo [0/3] Compiling the Blademaster model for Dota, first time only...
  "%DOTA%\game\bin\win64\resourcecompiler.exe" -i "%DOTA%\content\dota_addons\dotacs\models\wc3\blademaster\blademaster.vmdl" > "%HERE%compile_bm_log.txt" 2>&1
  echo Log: %HERE%compile_bm_log.txt
)

echo [1/3] Starting the bridge...
start "DotaWC3 bridge" /D "%HERE%" cmd /k "chcp 65001 >nul & python bridge_wc3.py"
timeout /t 2 /nobreak >nul

echo [2/3] Starting Dota 2 with the DotaCS custom game, pick Pudge...
start "" "%DOTA%\game\bin\win64\dota2.exe" -addon dotacs -tools -steam -novid +dota_launch_custom_game dotacs dota

echo [3/3] Starting Warcraft III with the test map...
start "" /D "%WC3%" "%WC3%\Warcraft III.exe" -window -loadfile "Maps\DotaWC3_Test.w3x"

echo Done. You can close this window.
pause
