@echo off
title DotaWC3 LAN launcher
rem DotaWC3 over LAN: the bridge hosts a WC3 LAN game, no disk stutter. Close Dota 2, WC3 and old bridges first.
set "DOTA=C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta"
set "WC3=C:\Games\Warcraft III"
set "HERE=%~dp0"
set "BMC=%DOTA%\game\dota_addons\dotacs\models\wc3\blademaster\blademaster.vmdl_c"

if exist "%BMC%" goto compiled
echo [0/3] Compiling the Blademaster model for Dota, first time only...
"%DOTA%\game\bin\win64\resourcecompiler.exe" -i "%DOTA%\content\dota_addons\dotacs\models\wc3\blademaster\blademaster.vmdl" > "%HERE%compile_bm_log.txt" 2>&1
:compiled

echo [1/3] Starting the LAN bridge...
start "DotaWC3 LAN bridge" /D "%HERE%" cmd /k "chcp 65001 >nul & python bridge_lan.py"
timeout /t 2 /nobreak >nul

echo [2/3] Starting Dota 2 with the DotaCS custom game, pick Pudge...
start "" "%DOTA%\game\bin\win64\dota2.exe" -addon dotacs -tools -steam -novid +dota_launch_custom_game dotacs dota

echo [3/3] Starting Warcraft III...
start "" /D "%WC3%" "%WC3%\Warcraft III.exe" -window

echo.
echo In Warcraft III: Local Area Network, join the game "DotaWC3". It starts by itself.
pause
