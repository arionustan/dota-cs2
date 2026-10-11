@echo off
title DotaCS: update CS2 server
echo Updating the CS2 server to the same version as your CS2...
"C:\cs2server\steamcmd\steamcmd.exe" +force_install_dir "C:\cs2server\cs2" +login anonymous +app_update 730 +quit
echo Re-adding Metamod to gameinfo.gi (an update can remove it)...
powershell -ExecutionPolicy Bypass -Command "$gi='C:\cs2server\cs2\game\csgo\gameinfo.gi'; $t=Get-Content $gi -Raw; if ($t -notmatch 'csgo/addons/metamod') { $t=$t -replace '(?m)^([ \t]*)(Game_LowViolence\s+csgo_lv[^\r\n]*)', \"`$1`$2`r`n`$1Game`tcsgo/addons/metamod\"; Set-Content $gi $t -NoNewline; 'Metamod line added' } else { 'Metamod line already there' }"
type "C:\cs2server\cs2\game\csgo\steam.inf"
echo.
echo Done.
pause
