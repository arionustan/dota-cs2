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
if not exist "%CONT%\models\dota_fx\_v1.txt" (
  echo Unpacking runes and lotus pools...
  if not exist "%CONT%\models\dota_fx" mkdir "%CONT%\models\dota_fx"
  for %%Z in ("%PK%\fx*.zip") do tar -xf "%%~Z" -C "%CONT%\models\dota_fx"
  echo Compiling runes and lotus pools...
  for /r "%CONT%\models\dota_fx" %%F in (*.vmdl) do "%RC%" -i "%%F" >nul 2>&1
  echo 1> "%CONT%\models\dota_fx\_v1.txt"
)
if not exist "%CONT%\particles\_v1.txt" (
  echo Unpacking Dota particles...
  if not exist "%CONT%\particles" mkdir "%CONT%\particles"
  for %%Z in ("%PK%\pfx*.zip") do tar -xf "%%~Z" -C "%CONT%"
  for /r "%CONT%\particles" %%F in (*.vpcf) do "%RC%" -i "%%F" >nul 2>&1
  echo 1> "%CONT%\particles\_v1.txt"
)
rem Creep and hero models were imported at 0.315 scale while their animations are full size, which squashed
rem heads and stretched limbs. Fix the source models once and compile them again (Pudge was already right).
if not exist "%CONT%\models\_scale1.txt" (
  echo Fixing creep and hero model scale, recompiling them takes a few minutes...
  powershell -NoProfile -Command "Get-ChildItem -Recurse -Filter *.vmdl -Path '%CONT%\models\dota_units','%CONT%\models\dota_heroes' | ForEach-Object { $t = [IO.File]::ReadAllText($_.FullName); if ($t.Contains('import_scale = 0.314961')) { [IO.File]::WriteAllText($_.FullName, $t.Replace('import_scale = 0.314961','import_scale = 1.0')) } }"
  if exist "%CSA%\models\dota_units" rmdir /s /q "%CSA%\models\dota_units"
  if exist "%CSA%\models\dota_heroes" rmdir /s /q "%CSA%\models\dota_heroes"
  echo 1> "%CONT%\models\_scale1.txt"
)
echo Compiling creep models (first time takes a few minutes)...
for /d %%U in ("%CONT%\models\dota_units\*") do (
  if not exist "%CSA%\models\dota_units\%%~nxU\%%~nxU.vmdl_c" "%RC%" -i "%%~U\%%~nxU.vmdl" >nul 2>&1
)
rem Map materials tinted with the colors the real Dota map gives them (cliffs, rocks, stairs...). Compiled once.
if not exist "%CSA%\models\dota_map\_tint1.txt" (
  echo Recoloring map rocks and cliffs...
  for %%M in (bad_shop001 bones_tintable_002 campfire_rocks001 cliff_wall001 cliff_wall002 cliff_wall003 crystal001_refract crystal_02 dire_chain001_tint dire_lava_tint_00 dire_river_statue flowers_00 flowers_02 good_base_wall001 good_shop001_items grass_clump_tintable_02 ground_rock001 liquid_pour_00 log002 mushrooms_wild_00 neutral_creep_camp001 petals_pink001 radiant_barracks_pool001 radiant_statue002 radiant_tower_base002 radiant_wall001 river_rocks001 roots_radiant roots_radiant_leaves secretshop_dire001 secretshop_radiant001 statue001 stone_wall001 stone_wall002 stone_wall003 stone_wall004 temple_stairs001 temple_stairs_blocks001 temple_stairs_blocks002 tile_stone_000_50 torch001 tree_gnarly001 urn001 urn002 urn002b waterfall_bridge_statue002_tintable web_fall_00 wood_fence001_tintable wood_walls001) do "%RC%" -i "%CONT%\models\dota_map\%%M.vmat" >nul 2>&1
  echo 1> "%CSA%\models\dota_map\_tint1.txt"
)
rem Real Dota particles (tools/dota_particles.py): compiled Dota effects, each dotafx*.zip is unpacked once into the addon.
for %%Z in ("%PK%\dotafx*.zip") do (
  if not exist "%CSA%\particles\_%%~nZ.txt" (
    echo Unpacking Dota effects %%~nZ...
    if not exist "%CSA%\particles" mkdir "%CSA%\particles"
    tar -xf "%%~Z" -C "%CSA%"
    echo 1> "%CSA%\particles\_%%~nZ.txt"
  )
)
rem Real Dota effects rebuilt from source (tools/dota_fx_port.py): each dotafxsrc*.zip is unpacked and compiled once.
set "NEWFX="
for %%Z in ("%PK%\dotafxsrc*.zip") do (
  if not exist "%CONT%\particles\_%%~nZ.txt" (
    echo Unpacking Dota effects %%~nZ...
    tar -xf "%%~Z" -C "%CONT%"
    echo 1> "%CONT%\particles\_%%~nZ.txt"
    set "NEWFX=1"
  )
)
if defined NEWFX (
  echo Compiling Dota effects, takes a few minutes...
  "%RC%" -f -r -i "%CONT%\materials\*.vtex" >> "%CONT%\particles\_fx_compile_log.txt" 2>&1
  "%RC%" -f -r -i "%CONT%\particles\*.vpcf" >> "%CONT%\particles\_fx_compile_log.txt" 2>&1
  if not exist "%CSA%\particles" mkdir "%CSA%\particles"
  copy /y "%CONT%\particles\dota_*.txt" "%CSA%\particles\" >nul
)
rem Dota heroes (tools/hero_build.py): every heroes*.zip is unpacked once, then each hero model compiles once.
rem Compile output goes to models\dota_heroes\_compile_log.txt so problems can be read later.
if not exist "%CONT%\models\dota_heroes" mkdir "%CONT%\models\dota_heroes"
for %%Z in ("%PK%\heroes*.zip") do (
  if not exist "%CONT%\models\dota_heroes\_%%~nZ.txt" (
    echo Unpacking %%~nZ...
    tar -xf "%%~Z" -C "%CONT%\models\dota_heroes"
    echo 1> "%CONT%\models\dota_heroes\_%%~nZ.txt"
  )
)
for /d %%U in ("%CONT%\models\dota_heroes\*") do (
  if not exist "%CSA%\models\dota_heroes\%%~nxU\%%~nxU.vmdl_c" (
    echo Compiling hero %%~nxU...
    "%RC%" -i "%%~U\%%~nxU.vmdl" >> "%CONT%\models\dota_heroes\_compile_log.txt" 2>&1
  )
)
echo [0/4] Copying the Dota map and the Pudge model into CS2 (client and server)...
for %%D in ("%CSC%" "%CSS%") do (
  robocopy "%CSA%\models" "%%~D\models" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\materials" "%%~D\materials" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\panorama" "%%~D\panorama" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\sounds" "%%~D\sounds" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\soundevents" "%%~D\soundevents" *_c /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\particles" "%%~D\particles" *_c *.txt /S /XO /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%CSA%\resource" "%%~D\resource" *.txt /S /XO /NFL /NDL /NJH /NJS /NP >nul
)

python "%ADDON%maptools\patch_map.py"

rem Keep the CS2 server copy on the same version as your CS2, otherwise CS2 says "client is out of date"
set "SRVWAIT=45"
set "CV="
set "SV="
for /f "tokens=2 delims==" %%A in ('findstr /b "PatchVersion=" "%CSC%\steam.inf"') do set "CV=%%A"
for /f "tokens=2 delims==" %%A in ('findstr /b "PatchVersion=" "%CSS%\steam.inf"') do set "SV=%%A"
if "%CV%"=="%SV%" goto server_version_ok
echo CS2 was updated: your CS2 %CV%, server %SV%. Updating the server, this can take a few minutes...
"C:\cs2server\steamcmd\steamcmd.exe" +force_install_dir "C:\cs2server\cs2" +login anonymous +app_update 730 +quit
powershell -ExecutionPolicy Bypass -Command "$gi='C:\cs2server\cs2\game\csgo\gameinfo.gi'; $t=Get-Content $gi -Raw; if ($t -notmatch 'csgo/addons/metamod') { $t=$t -replace '(?m)^([ \t]*)(Game_LowViolence\s+csgo_lv[^\r\n]*)', \"`$1`$2`r`n`$1Game`tcsgo/addons/metamod\"; Set-Content $gi $t -NoNewline; 'Metamod line added' }"
for /f "tokens=2 delims==" %%A in ('findstr /b "PatchVersion=" "%CSS%\steam.inf"') do set "SV=%%A"
echo Server is now %SV%, its first start after an update is slower
set "SRVWAIT=100"
:server_version_ok
echo [1/4] Starting the bridge...
start "DotaCS bridge" /D "%ADDON%bridge" cmd /k "chcp 65001 >nul & python bridge.py"
timeout /t 2 /nobreak >nul

echo [2/4] Starting the CS2 server...
start "DotaCS CS2 server" /D "%ADDON%cs2server" "%ADDON%cs2server\start_server.bat"

echo Waiting %SRVWAIT% seconds for the server to load...
timeout /t %SRVWAIT%

rem Dota side: the CS2 counter-terrorist model, compiled once (and again when the version file changes)
set "DRC=C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\bin\win64\resourcecompiler.exe"
if not exist "%ADDON%models\cs\cs_ct\_built_v1.txt" (
  echo Compiling the counter-terrorist model for Dota, first time only...
  "%DRC%" -i "%ADDON%models\cs\cs_ct\cs_ct.vmdl" > "%ADDON%models\cs\cs_ct\compile_log.txt" 2>&1
  echo 1> "%ADDON%models\cs\cs_ct\_built_v1.txt"
)
echo [3/4] Starting Dota 2 tools with the DotaCS custom game...
start "" "C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\bin\win64\dota2.exe" -addon dotacs -tools -steam -novid +dota_launch_custom_game dotacs dota

echo [4/4] Starting CS2 and joining your server...
rem -insecure is needed so CS2 accepts the custom map (turn it off before normal matchmaking)
start "" "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\cs2.exe" -steam -insecure -novid +exec dotacs_binds +connect 127.0.0.1:27030

echo.
echo Done. You can close this window.
pause
