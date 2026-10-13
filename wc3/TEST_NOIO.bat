@echo off
rem Opens the DotaWC3 test map without the file exchange, to check for lag
set "WC3=C:\Games\Warcraft III"
start "" /D "%WC3%" "%WC3%\Warcraft III.exe" -window -loadfile "Maps\DotaWC3_NoIO.w3x"
