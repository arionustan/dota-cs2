# DotaCS: builds the package for the streamer from YOUR working install.
# Result: folder C:\DotaCS_package\DotaCS (upload the whole folder to Google Drive).
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
function Step($t) { Write-Host ""; Write-Host "=== $t" -ForegroundColor Cyan }
function Fail($t) { Write-Host "ОШИБКА: $t" -ForegroundColor Red; Read-Host "Enter"; exit 1 }

$Steam = "C:\Program Files (x86)\Steam\steamapps\common"
$CsAddon = "$Steam\Counter-Strike Global Offensive\game\csgo_addons\dotacs_arena"
$CsMap = "$Steam\Counter-Strike Global Offensive\game\csgo\maps\dotacs_arena.vpk"
$CsCfg = "$Steam\Counter-Strike Global Offensive\game\csgo\cfg\dotacs_binds.cfg"
$DotaGame = "$Steam\dota 2 beta\game\dota_addons\dotacs"
$DotaContent = "$Steam\dota 2 beta\content\dota_addons\dotacs"
$SrvCsgo = "C:\cs2server\cs2\game\csgo"
$Here = $PSScriptRoot
$Base = "C:\DotaCS_package"   # not the Desktop: OneDrive would start uploading gigabytes
$Out = Join-Path $Base "DotaCS"
$F = Join-Path $Out "files"

# sources: list of @(sourceRoot, prefixInZip, filterScript); a file that can't be read stops the script
function Make-Zip($zipPath, $sources) {
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, "Create")
    $n = 0
    try {
        foreach ($s in $sources) {
            $root = $s[0].TrimEnd("\"); $prefix = $s[1]; $filter = $s[2]
            if (-not (Test-Path $root)) { continue }
            foreach ($f in [System.IO.Directory]::EnumerateFiles($root, "*", [System.IO.SearchOption]::AllDirectories)) {
                $rel = $f.Substring($root.Length + 1)
                if ($filter -and -not (& $filter $rel)) { continue }
                $entry = ($prefix + $rel) -replace "\\", "/"
                try {
                    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f, $entry, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
                } catch { $zip.Dispose(); Fail "не смог прочитать $f (закрой Dota 2, CS2 и сервер). $($_.Exception.Message)" }
                $n++
                if ($n % 1000 -eq 0) { Write-Host "    $n файлов..." }
            }
        }
    } finally { $zip.Dispose() }
    $mb = [math]::Round((Get-Item $zipPath).Length / 1MB)
    Write-Host "    $([System.IO.Path]::GetFileName($zipPath)): $n файлов, $mb МБ" -ForegroundColor Green
}

foreach ($p in $CsAddon, $CsMap, $DotaGame, $SrvCsgo) { if (-not (Test-Path $p)) { Fail "нет $p" } }
if (-not (Test-Path "$SrvCsgo\addons\counterstrikesharp\plugins\DotaCSBridge\DotaCSBridge.dll")) { Fail "нет плагина DotaCSBridge.dll" }
foreach ($p in "cs2", "dota2") { if (Get-Process $p -ErrorAction SilentlyContinue) { Fail "закрой Dota 2, CS2 и окно сервера" } }

if (Test-Path $Base) { Remove-Item $Base -Recurse -Force }
New-Item -ItemType Directory -Force $F, "$F\server_cfg", "$F\client_cfg" | Out-Null

Step "1/5 Скрипты"
Copy-Item "$Here\files\dotacs.ps1" $F
Copy-Item "$Here\1_INSTALL.bat", "$Here\2_PLAY.bat", "$Here\UNINSTALL.bat", "$Here\README_RU.txt" $Out
Copy-Item "$Here\files\server_cfg\*" "$F\server_cfg"
Copy-Item $CsCfg "$F\client_cfg"

Step "2/5 Мод Dota 2"
Make-Zip "$F\dota_game.zip" @(, @($DotaGame, "", { param($r) -not $r.StartsWith("tools_") }))
Make-Zip "$F\dota_content.zip" @(, @("$DotaContent\panorama", "panorama\", $null))

Step "3/5 Модели, звуки, частицы CS2 (несколько минут)"
$isC = { param($r) $r.EndsWith("_c") }
$src = @()
foreach ($d in "models", "materials", "panorama", "sounds", "soundevents", "particles") { $src += , @("$CsAddon\$d", "$d\", $isC) }
$src += , @("$CsAddon\resource\overviews", "resource\overviews\", $null)
Make-Zip "$F\cs_assets.zip" $src

Step "4/5 Карта"
Copy-Item $CsMap "$F\dotacs_arena.vpk"
Write-Host "    dotacs_arena.vpk: $([math]::Round((Get-Item "$F\dotacs_arena.vpk").Length / 1MB)) МБ" -ForegroundColor Green

Step "5/5 Metamod, CounterStrikeSharp и плагин"
Make-Zip "$F\server_addons.zip" @(, @("$SrvCsgo\addons", "addons\", { param($r) $r -notmatch "\\logs\\" }))

Write-Host ""
Write-Host "Готово. Загрузи на Google Диск всю папку $Out" -ForegroundColor Green
Write-Host "В папке files должно быть 6 файлов: dotacs.ps1, dota_game.zip, dota_content.zip, cs_assets.zip, dotacs_arena.vpk, server_addons.zip"
Read-Host "Enter"
