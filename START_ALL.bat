@echo off
title DotaCS launcher
rem DotaCS: starts everything for the bridge test.
rem Close Dota 2 and CS2 before running this.
set "ADDON=%~dp0"

set "CSA=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo_addons\dotacs_arena"
set "CSC=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo"
set "CSS=C:\cs2server\cs2\game\csgo"

set "CONT=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\dotacs_arena"
set "RC=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe"
set "PK=%CONT%\_pack"
if not exist "%CONT%\models\dota_units\_v4.txt" (
  echo Unpacking creep, neutral and Roshan models...
  if exist "%CONT%\models\dota_units" rmdir /s /q "%CONT%\models\dota_units"
  if exist "%CSA%\models\dota_units" rmdir /s /q "%CSA%\models\dota_units"
  mkdir "%CONT%\models\dota_units"
  echo v4> "%CONT%\models\dota_units\_v4.txt"
  for %%Z in ("%PK%\units*.zip") do tar -xf "%%~Z" -C "%CONT%\models\dota_units"
)
set "NEWSND="
if not exist "%CONT%\sounds\dotacs" mkdir "%CONT%\sounds\dotacs"
for %%Z in ("%PK%\sounds*.zip") do (
  if not exist "%CONT%\sounds\dotacs\_%%~nZ.txt" (
    echo Unpacking %%~nZ...
    tar -xf "%%~Z" -C "%CONT%\sounds\dotacs"
    echo 1> "%CONT%\sounds\dotacs\_%%~nZ.txt"
    set "NEWSND=1"
  )
)
echo [0/4] Compiling new DotaCS assets (radar, water, Pudge, sounds)...
for %%F in ("panorama\images\overheadmaps\dotacs_arena_radar_psd.vtex" "models\dota_map\water_generic_000.vmat" "models\dota_map\water_generic_000_slope.vmat" "models\dota_pudge\pudge.vmdl" "soundevents\dotacs.vsndevts") do (
  if exist "%CONT%\%%~F" "%RC%" -i "%CONT%\%%~F" >nul 2>&1
)
if defined NEWSND (
  "%RC%" -r -i "%CONT%\sounds\dotacs\*.wav" >nul 2>&1
  "%RC%" -r -i "%CONT%\sounds\dotacs\*.mp3" >nul 2>&1
  "%RC%" -i "%CONT%\soundevents\dotacs.vsndevts" >nul 2>&1
)
if not exist "%CONT%\models\dota_wild\_v1.txt" (
  echo Unpacking Dota wildlife...
  if not exist "%CONT%\models\dota_wild" mkdir "%CONT%\models\dota_wild"
  for %%Z in ("%PK%\wild*.zip") do tar -xf "%%~Z" -C "%CONT%\models\dota_wild"
  echo v1> "%CONT%\models\dota_wild\_v1.txt"
)
for /d %%U in ("%CONT%\models\dota_wild\*") do (
  if not exist "%CSA%\models\dota_wild\%%~nxU\%%~nxU.vmdl_c" "%RC%" -i "%%~U\%%~nxU.vmdl" >nul 2>&1
)
if not exist "%CSA%\models\dota_map\_fol1.txt" (
  echo Compiling moving foliage...
  for %%M in (tree_oak_leaves_00 tree_oak_leaves_05 tree_oak_leaves_blank tree_pine_frond_00 tree_bamboo_leaves_01 dire_tree007_moss dire_tree007c plants001 flowers_00 flowers_02 grass_clump_00a_brown grass_clump_tintable_02 universal_vines001 roots_radiant_leaves roots_outpost_leaves leaves_white000 fountain_of_life_plants_radiant lily_flower_00) do "%RC%" -i "%CONT%\models\dota_map\%%M.vmat" >nul 2>&1
  echo 1> "%CSA%\models\dota_map\_fol1.txt"
)
if not exist "%CONT%\models\dota_dyn\_v2.txt" (
  echo Unpacking trees, banners, cattails...
  if exist "%CONT%\models\dota_dyn" rmdir /s /q "%CONT%\models\dota_dyn"
  if exist "%CSA%\models\dota_dyn" rmdir /s /q "%CSA%\models\dota_dyn"
  mkdir "%CONT%\models\dota_dyn"
  for %%Z in ("%PK%\dyn*.zip") do tar -xf "%%~Z" -C "%CONT%\models\dota_dyn"
  echo Compiling trees, banners, cattails, takes a few minutes...
  for /r "%CONT%\models\dota_dyn" %%F in (*.vmdl) do "%RC%" -i "%%F" >nul 2>&1
  echo 1> "%CONT%\models\dota_dyn\_v2.txt"
)
if not exist "%CONT%\models\dota_bld\_v1.txt" (
  echo Unpacking towers and barracks...
  if exist "%CONT%\models\dota_bld" rmdir /s /q "%CONT%\models\dota_bld"
  if exist "%CSA%\models\dota_bld" rmdir /s /q "%CSA%\models\dota_bld"
  mkdir "%CONT%\models\dota_bld"
  for %%Z in ("%PK%\bld*.zip") do tar -xf "%%~Z" -C "%CONT%\models\dota_bld"
  echo Compiling towers and barracks, takes a few minutes...
  for /r "%CONT%\models\dota_bld" %%F in (*.vmdl) do "%RC%" -i "%%F" >nul 2>&1
  echo 1> "%CONT%\models\dota_bld\_v1.txt"
)
if not exist "%CONT%\particles\_v1.txt" (
  echo Unpacking Dota particles...
  if not exist "%CONT%\particles" mkdir "%CONT%\particles"
  for %%Z in ("%PK%\pfx*.zip") do tar -xf "%%~Z" -C "%CONT%"
  for /r "%CONT%\particles" %%F in (*.vpcf) do "%RC%" -i "%%F" >nul 2>&1
  echo 1> "%CONT%\particles\_v1.txt"
)
echo Compiling creep models (first time takes a few minutes)...
for /d %%U in ("%CONT%\models\dota_units\*") do (
  if not exist "%CSA%\models\dota_units\%%~nxU\%%~nxU.vmdl_c" "%RC%" -i "%%~U\%%~nxU.vmdl" >nul 2>&1
)
echo [0/4] Copying the Dota map and the Pudge model into CS2 (client and server)...
for %%D in ("%CSC%" "%CSS%") do (
  robocopy "%CSA%\models" "%%~D\models" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\materials" "%%~D\materials" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\panorama" "%%~D\panorama" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\sounds" "%%~D\sounds" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\soundevents" "%%~D\soundevents" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\particles" "%%~D\particles" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\resource" "%%~D\resource" *.txt /S /XO /NFL /NDL /NJH /NJS /NP >nul
)

python "%ADDON%maptools\patch_map.py"

echo [1/4] Starting the bridge...
start "DotaCS bridge" /D "%ADDON%bridge" cmd /k "chcp 65001 >nul & python bridge.py"
timeout /t 2 /nobreak >nul

echo [2/4] Starting the CS2 server...
start "DotaCS CS2 server" /D "%ADDON%cs2server" "%ADDON%cs2server\start_server.bat"

echo Waiting 45 seconds for the server to load...
timeout /t 45

echo [3/4] Starting Dota 2 tools with the DotaCS custom game...
start "" "C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\bin\win64\dota2.exe" -addon dotacs -tools -steam -novid +dota_launch_custom_game dotacs dota

echo [4/4] Starting CS2 and joining your server...
rem -insecure is needed so CS2 accepts the custom map (turn it off before normal matchmaking)
start "" "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\cs2.exe" -steam -insecure -novid +exec dotacs_binds +connect 127.0.0.1:27030

echo.
echo Done. You can close this window.
pause
