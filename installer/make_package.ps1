# DotaCS: builds the package for the streamer from YOUR working install.
# Result: C:\DotaCS_package\DotaCS.zip (send it via Google Drive / Yandex Disk).
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
function Step($t) { Write-Host ""; Write-Host "=== $t" -ForegroundColor Cyan }
function Fail($t) { Write-Host "ОШИБКА: $t" -ForegroundColor Red; Read-Host "Enter"; exit 1 }

$Steam = "C:\Program Files (x86)\Steam\steamapps\common"
$CsAddon = "$Steam\Counter-Strike Global Offensive\game\csgo_addons\dotacs_arena"
$CsMap = "$Steam\Counter-Strike Global Offensive\game\csgo\maps\dotacs_arena.vpk"
$CsCfg = "$Steam\Counter-Strike Global Offensive\game\csgo\cfg\dotacs_binds.cfg"
$DotaGame = "$Steam\dota 2 beta\game\dota_addons\dotacs"
$DotaContent = "$Steam\dota 2 beta\content\dota_addons\dotacs"
$SrvAddons = "C:\cs2server\cs2\game\csgo\addons"
$Here = $PSScriptRoot

$Desk = "C:\DotaCS_package"   # not the Desktop: OneDrive would start uploading gigabytes
New-Item -ItemType Directory -Force $Desk | Out-Null
$Out = Join-Path $Desk "DotaCS"
$F = Join-Path $Out "files"
$Stage = Join-Path $Desk "_stage"

foreach ($p in $CsAddon, $CsMap, $DotaGame, $SrvAddons) { if (-not (Test-Path $p)) { Fail "нет $p" } }
if (-not (Test-Path "$SrvAddons\counterstrikesharp\plugins\DotaCSBridge\DotaCSBridge.dll")) { Fail "нет плагина DotaCSBridge.dll" }

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force $F, "$F\server_cfg", "$F\client_cfg", $Stage | Out-Null

Step "1/5 Скрипты"
Copy-Item "$Here\files\dotacs.ps1" $F
Copy-Item "$Here\1_INSTALL.bat", "$Here\2_PLAY.bat", "$Here\UNINSTALL.bat", "$Here\README_RU.txt" $Out
Copy-Item "$Here\files\server_cfg\*" "$F\server_cfg"
Copy-Item $CsCfg "$F\client_cfg"

Step "2/5 Мод Dota 2"
tar -a -cf "$F\dota_game.zip" --exclude "tools_*" -C $DotaGame .
New-Item -ItemType Directory -Force "$Stage\dc" | Out-Null
Copy-Item "$DotaGame\addoninfo.txt" "$Stage\dc" -ErrorAction SilentlyContinue
if (Test-Path "$DotaContent\panorama") { robocopy "$DotaContent\panorama" "$Stage\dc\panorama" /S /NFL /NDL /NJH /NJS /NP | Out-Null }
tar -a -cf "$F\dota_content.zip" -C "$Stage\dc" .

Step "3/5 Модели, звуки, частицы CS2 (несколько минут)"
$A = "$Stage\cs"
foreach ($d in "models", "materials", "panorama", "sounds", "soundevents", "particles") {
    if (Test-Path "$CsAddon\$d") { robocopy "$CsAddon\$d" "$A\$d" *_c /S /NFL /NDL /NJH /NJS /NP | Out-Null }
}
robocopy "$CsAddon\resource\overviews" "$A\resource\overviews" *.txt /NFL /NDL /NJH /NJS /NP | Out-Null
tar -a -cf "$F\cs_assets.zip" -C $A .
if ($LASTEXITCODE -ne 0) { Fail "не получилось упаковать модели" }
Copy-Item $CsMap "$F\dotacs_arena.vpk"

Step "4/5 Metamod, CounterStrikeSharp и плагин"
tar -a -cf "$F\server_addons.zip" --exclude "*/logs/*" -C (Split-Path $SrvAddons) addons
if ($LASTEXITCODE -ne 0) { Fail "не получилось упаковать addons" }

Step "5/5 Общий архив"
Remove-Item $Stage -Recurse -Force
$Zip = Join-Path $Desk "DotaCS.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
tar -a -cf $Zip -C $Desk DotaCS
$gb = [math]::Round((Get-Item $Zip).Length / 1GB, 2)
Write-Host ""
Write-Host "Готово: $Zip ($gb GB)" -ForegroundColor Green
Write-Host "Папка $Out тоже осталась, из неё можно проверить установку у себя."
Read-Host "Enter"
