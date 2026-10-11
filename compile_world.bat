@echo off
title DotaCS: compile world model
set "RC=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe"
set "CONT=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\dotacs_arena"
echo Compiling world_all.vmdl, this takes a few minutes...
"%RC%" -i "%CONT%\models\dota_map\world_all.vmdl" > "%~dp0compile_world_log.txt" 2>&1
echo Exit code %errorlevel% >> "%~dp0compile_world_log.txt"
echo Done. Log: %~dp0compile_world_log.txt
pause
