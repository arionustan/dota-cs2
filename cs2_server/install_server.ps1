# DotaCS: installs a separate CS2 dedicated server with Metamod, CounterStrikeSharp
# and the DotaCS bridge plugin. Your normal CS2 is not touched.
#
# Run from this folder:
#   powershell -ExecutionPolicy Bypass -File install_server.ps1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster

$Root      = "C:\cs2server"
$SteamCmd  = Join-Path $Root "steamcmd"
$Server    = Join-Path $Root "cs2"
$Csgo      = Join-Path $Server "game\csgo"
$Here      = $PSScriptRoot

function Step($text) { Write-Host ""; Write-Host "=== $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Fail($text) { Write-Host "    ОШИБКА: $text" -ForegroundColor Red; Read-Host "Нажми Enter чтобы выйти"; exit 1 }

# ---------------------------------------------------------------- disk space
Step "Проверяю место на диске C:"
$freeGb = [math]::Round((Get-PSDrive C).Free / 1GB)
$alreadyDownloaded = Test-Path (Join-Path $Server "game\bin\win64\cs2.exe")
if (-not $alreadyDownloaded -and $freeGb -lt 80) { Fail "на диске C: свободно $freeGb ГБ, нужно хотя бы 80 ГБ" }
if ($freeGb -lt 2) { Fail "на диске C: почти нет места ($freeGb ГБ)" }
Ok "свободно $freeGb ГБ"
New-Item -ItemType Directory -Force -Path $Root, $SteamCmd, $Server | Out-Null

# ---------------------------------------------------------------- SteamCMD
Step "1/6 SteamCMD (официальная утилита Valve для серверов)"
$steamExe = Join-Path $SteamCmd "steamcmd.exe"
if (-not (Test-Path $steamExe)) {
    $zip = Join-Path $Root "steamcmd.zip"
    Invoke-WebRequest "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $SteamCmd -Force
    Remove-Item $zip
}
Ok "готово"

# ---------------------------------------------------------------- CS2 server
Step "2/6 Сервер CS2 (около 75 ГБ, если ещё не скачан; это долго, окно не закрывай)"
$serverExe = Join-Path $Server "game\bin\win64\cs2.exe"
for ($try = 1; $try -le 3 -and -not (Test-Path $serverExe); $try++) {
    & $steamExe +force_install_dir $Server +login anonymous +app_update 730 validate +quit
    if (Test-Path $serverExe) { break }
    Write-Host "    SteamCMD не докачал, пробую ещё раз ($try/3)..." -ForegroundColor Yellow
}
if (-not (Test-Path $serverExe)) { Fail "сервер не скачался. Запусти скрипт ещё раз, он продолжит с места остановки" }
Ok "сервер в $Server"

# ---------------------------------------------------------------- Metamod
Step "3/6 Metamod:Source"
$mmDir = Join-Path $Csgo "addons\metamod"
if (-not (Test-Path $mmDir)) {
    $url = $null
    try {
        # Metamod 2.x for CS2 is published on GitHub; take the newest Windows build
        $releases = Invoke-RestMethod "https://api.github.com/repos/alliedmodders/metamod-source/releases?per_page=30" -Headers @{ "User-Agent" = "DotaCS" }
        foreach ($r in $releases) {
            $a = $r.assets | Where-Object { $_.name -like "mmsource-2.*-windows.zip" } | Select-Object -First 1
            if ($a) { $url = $a.browser_download_url; break }
        }
    } catch {}
    if (-not $url) {
        # known good build (2.0 build 1473)
        $url = "https://github.com/alliedmodders/metamod-source/releases/download/2.0.0.1473/mmsource-2.0.0-git1473-windows.zip"
    }
    try {
        $zip = Join-Path $Root "metamod.zip"
        Invoke-WebRequest $url -OutFile $zip
        Expand-Archive $zip -DestinationPath $Csgo -Force
        Remove-Item $zip
        Ok ("скачан " + [System.IO.Path]::GetFileName($url))
    } catch {
        Fail "не получилось скачать Metamod: $url"
    }
}
Ok "готово"

# ---------------------------------------------------------------- gameinfo.gi
Step "4/6 Подключаю Metamod в gameinfo.gi"
$gi = Join-Path $Csgo "gameinfo.gi"
$text = Get-Content $gi -Raw
if ($text -notmatch "csgo/addons/metamod") {
    $text = $text -replace "(?m)^([ \t]*)(Game_LowViolence\s+csgo_lv[^\r\n]*)", "`$1`$2`r`n`$1Game`tcsgo/addons/metamod"
    if ($text -notmatch "csgo/addons/metamod") { Fail "не нашёл строку Game_LowViolence в gameinfo.gi" }
    Set-Content $gi $text -NoNewline
}
Ok "готово (это только копия сервера, твоя КС2 не изменена)"

# ---------------------------------------------------------------- CounterStrikeSharp
Step "5/6 CounterStrikeSharp"
$cssDir = Join-Path $Csgo "addons\counterstrikesharp"
if (-not (Test-Path $cssDir)) {
    $release = Invoke-RestMethod "https://api.github.com/repos/roflmuffin/CounterStrikeSharp/releases/latest" -Headers @{ "User-Agent" = "DotaCS" }
    $asset = $release.assets | Where-Object { $_.name -like "counterstrikesharp-with-runtime-windows-*.zip" } | Select-Object -First 1
    if (-not $asset) { Fail "не нашёл сборку CounterStrikeSharp для Windows в последнем релизе" }
    $zip = Join-Path $Root "css.zip"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip -DestinationPath $Csgo -Force
    Remove-Item $zip
    Ok "версия $($release.tag_name)"
}
# Visual C++ runtime, CounterStrikeSharp needs it on Windows
$vc = Join-Path $Root "vc_redist.x64.exe"
if (-not (Test-Path $vc)) {
    Invoke-WebRequest "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vc
    Start-Process $vc -ArgumentList "/install", "/quiet", "/norestart" -Wait
}
Ok "готово"

# ---------------------------------------------------------------- plugin
Step "6/6 Собираю плагин DotaCS"
$hasSdk = $false
try { $hasSdk = (& dotnet --list-sdks 2>$null) -match "^10\." } catch {}
if (-not $hasSdk) {
    Write-Host "    Ставлю .NET 10 SDK (нужен один раз, чтобы собрать плагин)..."
    winget install --id Microsoft.DotNet.SDK.10 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}
$proj = Join-Path $Here "DotaCSBridge"
$out  = Join-Path $cssDir "plugins\DotaCSBridge"
& dotnet build $proj -c Release -o $out
if (-not (Test-Path (Join-Path $out "DotaCSBridge.dll"))) { Fail "плагин не собрался, скинь Claude текст из этого окна" }
Ok "плагин в $out"

Step "Всё установлено!"
Write-Host "Запускай сервер файлом start_server.bat в этой же папке."
Read-Host "Нажми Enter чтобы закрыть"
