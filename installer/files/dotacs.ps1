# DotaCS: install / play / uninstall for Dota 2 x CS2.
# Called by 1_INSTALL.bat, 2_PLAY.bat and UNINSTALL.bat next to the "files" folder.
param([ValidateSet("install", "play", "uninstall")][string]$Mode = "play")

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Files = $PSScriptRoot
$Root = Split-Path $Files -Parent
$StateFile = Join-Path $Files "state.txt"

function Step($t) { Write-Host ""; Write-Host "=== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "    $t" -ForegroundColor Green }
function Warn($t) { Write-Host "    $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host ""; Write-Host "ОШИБКА: $t" -ForegroundColor Red; Read-Host "Нажми Enter чтобы закрыть"; exit 1 }

Add-Type @"
using System; using System.Runtime.InteropServices;
public static class DotaCSLink {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool CreateHardLink(string newName, string existing, IntPtr sa);
}
"@

# ------------------------------------------------------------------ Steam and the games
function Find-Game($folder) {
    $steam = $null
    try { $steam = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction Stop).SteamPath } catch {}
    if (-not $steam) { $steam = "C:\Program Files (x86)\Steam" }
    $steam = $steam -replace "/", "\"
    $libs = @($steam)
    $vdf = Join-Path $steam "steamapps\libraryfolders.vdf"
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $libs += ($m.Groups[1].Value -replace "\\\\", "\")
        }
    }
    foreach ($l in ($libs | Select-Object -Unique)) {
        $p = Join-Path $l "steamapps\common\$folder"
        if (Test-Path (Join-Path $p "game")) { return @{ Path = $p; Lib = $l } }
    }
    return $null
}

function Load-State {
    $s = @{}
    if (Test-Path $StateFile) {
        foreach ($line in Get-Content $StateFile -Encoding UTF8) {
            $i = $line.IndexOf("=")
            if ($i -gt 0) { $s[$line.Substring(0, $i)] = $line.Substring($i + 1) }
        }
    }
    return $s
}

function Save-State($s) {
    ($s.Keys | ForEach-Object { "$_=$($s[$_])" }) | Set-Content $StateFile -Encoding UTF8
}

# ------------------------------------------------------------------ the CS2 server copy
# The server is a second copy of your own CS2 made of hard links: it takes almost no disk space and
# downloads nothing. Only the server copy gets Metamod, your normal CS2 is not changed.
$CopyNotLink = @("csgo\gameinfo.gi", "csgo\gameinfo_branchspecific.gi", "csgo\steam.inf")

function Build-ServerCopy($cs, $server) {
    $srcGame = Join-Path $cs "game"
    $dstGame = Join-Path $server "game"
    $keep = Join-Path $server "_addons_keep"
    $addons = Join-Path $dstGame "csgo\addons"
    if (Test-Path $addons) {
        if (Test-Path $keep) { Remove-Item $keep -Recurse -Force }
        Move-Item $addons $keep
    }
    if (Test-Path $dstGame) { Remove-Item $dstGame -Recurse -Force }   # removes only the links, not your CS2 files
    New-Item -ItemType Directory -Force $dstGame | Out-Null

    $n = 0; $copied = 0
    $prefix = $srcGame.TrimEnd("\").Length + 1
    foreach ($f in [System.IO.Directory]::EnumerateFiles($srcGame, "*", [System.IO.SearchOption]::AllDirectories)) {
        $rel = $f.Substring($prefix)
        if ($rel.StartsWith("csgo\addons\", "OrdinalIgnoreCase")) { continue }
        $dst = Join-Path $dstGame $rel
        $dir = [System.IO.Path]::GetDirectoryName($dst)
        if (-not [System.IO.Directory]::Exists($dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
        $copy = ($CopyNotLink -contains $rel) -or $rel.StartsWith("csgo\cfg\", "OrdinalIgnoreCase")
        if ($copy -or -not [DotaCSLink]::CreateHardLink($dst, $f, [IntPtr]::Zero)) {
            [System.IO.File]::Copy($f, $dst, $true); $copied++
        }
        $n++
        if ($n % 2000 -eq 0) { Write-Host "    $n файлов..." }
    }
    if ($copied -gt 500) { Warn "жёсткие ссылки не сработали, файлы скопированы ($copied шт.)" }

    if (Test-Path $keep) { Move-Item $keep $addons }

    # Metamod line in the server copy's gameinfo.gi
    $gi = Join-Path $dstGame "csgo\gameinfo.gi"
    $text = Get-Content $gi -Raw
    if ($text -notmatch "csgo/addons/metamod") {
        $text = $text -replace "(?m)^([ \t]*)(Game_LowViolence\s+csgo_lv[^\r\n]*)", "`$1`$2`r`n`$1Game`tcsgo/addons/metamod"
        if ($text -notmatch "csgo/addons/metamod") { Fail "не нашёл строку Game_LowViolence в gameinfo.gi" }
        Set-Content $gi $text -NoNewline
    }
    # server settings
    Copy-Item (Join-Path $Files "server_cfg\*") (Join-Path $dstGame "csgo\cfg") -Force
    Ok "копия сервера готова ($n файлов)"
}

function Server-IsCurrent($cs, $server) {
    $a = Join-Path $cs "game\csgo\steam.inf"
    $b = Join-Path $server "game\csgo\steam.inf"
    if (-not (Test-Path $b)) { return $false }
    return (Get-Content $a -Raw) -eq (Get-Content $b -Raw)
}

# ------------------------------------------------------------------ install
function Install {
    Write-Host "DotaCS: установка Dota 2 x CS2" -ForegroundColor Cyan
    foreach ($p in "cs2", "dota2") {
        if (Get-Process $p -ErrorAction SilentlyContinue) { Fail "закрой Dota 2 и CS2 перед установкой" }
    }

    Step "1/6 Ищу Dota 2 и CS2"
    $dota = Find-Game "dota 2 beta"
    $cs = Find-Game "Counter-Strike Global Offensive"
    if (-not $dota) { Fail "не нашёл Dota 2. Установи её в Steam" }
    if (-not $cs) { Fail "не нашёл Counter-Strike 2. Установи его в Steam" }
    Ok "Dota 2: $($dota.Path)"
    Ok "CS2:    $($cs.Path)"
    $csgo = Join-Path $cs.Path "game\csgo"
    $server = Join-Path $cs.Lib "DotaCS_server"

    Step "2/6 Мод для Dota 2"
    $dg = Join-Path $dota.Path "game\dota_addons\dotacs"
    $dc = Join-Path $dota.Path "content\dota_addons\dotacs"
    New-Item -ItemType Directory -Force $dg, $dc | Out-Null
    tar -xf (Join-Path $Files "dota_game.zip") -C $dg
    if ($LASTEXITCODE -ne 0) { Fail "не распаковался dota_game.zip" }
    tar -xf (Join-Path $Files "dota_content.zip") -C $dc
    Ok "готово"

    Step "3/6 Модели, звуки и карта для CS2 (несколько минут)"
    $list = tar -tf (Join-Path $Files "cs_assets.zip")
    tar -xf (Join-Path $Files "cs_assets.zip") -C $csgo
    if ($LASTEXITCODE -ne 0) { Fail "не распаковался cs_assets.zip (мало места на диске?)" }
    $list | Where-Object { $_ -and -not $_.EndsWith("/") } | ForEach-Object { "game\csgo\" + ($_ -replace "/", "\") } |
        Set-Content (Join-Path $Files "installed_files.txt") -Encoding UTF8
    Copy-Item (Join-Path $Files "dotacs_arena.vpk") (Join-Path $csgo "maps\dotacs_arena.vpk") -Force
    Copy-Item (Join-Path $Files "client_cfg\*") (Join-Path $csgo "cfg") -Force
    Ok "готово"

    Step "4/6 Visual C++ (нужен серверу)"
    $vcOk = $false
    foreach ($k in "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64") {
        try { if ((Get-ItemProperty $k -ErrorAction Stop).Installed -eq 1) { $vcOk = $true } } catch {}
    }
    if (-not $vcOk) {
        $vc = Join-Path $env:TEMP "vc_redist.x64.exe"
        try {
            Invoke-WebRequest "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vc
            Write-Host "    Если Windows спросит разрешение, нажми Да"
            Start-Process $vc -ArgumentList "/install", "/quiet", "/norestart" -Wait
        } catch { Warn "не скачался Visual C++, поставь его вручную: https://aka.ms/vs/17/release/vc_redist.x64.exe" }
    }
    Ok "готово"

    Step "5/6 Сервер CS2 (копия твоей CS2 без скачивания, 1-3 минуты)"
    New-Item -ItemType Directory -Force $server | Out-Null
    Build-ServerCopy $cs.Path $server
    $addons = Join-Path $server "game\csgo"
    tar -xf (Join-Path $Files "server_addons.zip") -C $addons
    if ($LASTEXITCODE -ne 0) { Fail "не распаковался server_addons.zip" }
    Ok "Metamod, CounterStrikeSharp и плагин DotaCS на месте"

    Step "6/6 Ярлык на рабочем столе"
    try {
        $desk = [Environment]::GetFolderPath("Desktop")
        $sh = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desk "DotaCS.lnk"))
        $sh.TargetPath = Join-Path $Root "2_PLAY.bat"
        $sh.WorkingDirectory = $Root
        $sh.IconLocation = (Join-Path $dota.Path "game\bin\win64\dota2.exe") + ",0"
        $sh.Save()
        Ok "ярлык DotaCS создан"
    } catch { Warn "ярлык не создался, запускай 2_PLAY.bat" }

    Save-State @{ Dota = $dota.Path; CS = $cs.Path; Server = $server }

    Step "Всё установлено!"
    Write-Host ""
    Write-Host "Важно: в Steam нужен бесплатный DLC 'Dota 2 Workshop Tools':" -ForegroundColor Yellow
    Write-Host "  Steam -> Библиотека -> Dota 2 -> правой кнопкой -> Свойства -> DLC -> поставь галочку."
    Write-Host ""
    Write-Host "Запуск: ярлык DotaCS на рабочем столе или 2_PLAY.bat"
    Read-Host "Нажми Enter чтобы закрыть"
}

# ------------------------------------------------------------------ play
function Play {
    $s = Load-State
    if (-not $s.CS -or -not (Test-Path $s.Server)) { Fail "сначала запусти 1_INSTALL.bat" }
    foreach ($p in "cs2", "dota2") {
        if (Get-Process $p -ErrorAction SilentlyContinue) {
            Warn "Dota 2 или CS2 уже запущены. Закрой их и нажми Enter"
            Read-Host | Out-Null
            break
        }
    }

    if (-not (Server-IsCurrent $s.CS $s.Server)) {
        Step "CS2 обновилась, обновляю копию сервера (1-3 минуты)"
        Build-ServerCopy $s.CS $s.Server
    }

    Step "1/3 Запускаю сервер CS2"
    $exe = Join-Path $s.Server "game\bin\win64\cs2.exe"
    Start-Process $exe -WindowStyle Minimized -ArgumentList @(
        "-dedicated", "-insecure", "-console", "-port", "27030", "+sv_lan", "1", "+map", "dotacs_arena",
        "+game_type", "0", "+game_mode", "1", "+mp_autokick", "0", "+mp_warmup_pausetimer", "1",
        "+sv_hibernate_when_empty", "0", "+bot_quota", "0")
    Write-Host "    Если Windows спросит про брандмауэр, нажми Разрешить"
    Write-Host "    Жду загрузки карты (обычно 30-90 секунд)..."
    $ready = $false
    for ($i = 0; $i -lt 180 -and -not $ready; $i++) {
        Start-Sleep 1
        try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", 3000); $c.Close(); $ready = $true } catch {}
    }
    if ($ready) { Ok "сервер готов" } else { Warn "сервер долго грузится, запускаю игры всё равно" }

    Step "2/3 Запускаю Dota 2 с режимом DotaCS"
    Start-Process (Join-Path $s.Dota "game\bin\win64\dota2.exe") -ArgumentList @(
        "-addon", "dotacs", "-tools", "-steam", "-novid", "+dota_launch_custom_game", "dotacs", "dota")

    Step "3/3 Запускаю CS2 и захожу на сервер"
    Start-Sleep 5
    Start-Process (Join-Path $s.CS "game\bin\win64\cs2.exe") -ArgumentList @(
        "-steam", "-insecure", "-novid", "+exec", "dotacs_binds", "+connect", "127.0.0.1:27030")

    Write-Host ""
    Ok "Готово. Это окно можно закрыть."
    Write-Host "Если КС не зашла на сервер: открой консоль (~) и введи  connect 127.0.0.1:27030"
    Start-Sleep 8
}

# ------------------------------------------------------------------ uninstall
function Uninstall {
    $s = Load-State
    if (-not $s.CS) { Fail "DotaCS не установлен" }
    foreach ($p in "cs2", "dota2") {
        if (Get-Process $p -ErrorAction SilentlyContinue) { Fail "закрой Dota 2 и CS2" }
    }
    Step "Удаляю DotaCS"
    if (Test-Path $s.Server) { Remove-Item $s.Server -Recurse -Force; Ok "сервер удалён" }
    $list = Join-Path $Files "installed_files.txt"
    if (Test-Path $list) {
        foreach ($rel in Get-Content $list -Encoding UTF8) {
            $p = Join-Path $s.CS $rel
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
    }
    foreach ($p in "game\csgo\maps\dotacs_arena.vpk", "game\csgo\cfg\dotacs_binds.cfg") {
        $f = Join-Path $s.CS $p; if (Test-Path $f) { Remove-Item $f -Force }
    }
    Ok "файлы из CS2 удалены"
    foreach ($p in "game\dota_addons\dotacs", "content\dota_addons\dotacs") {
        $f = Join-Path $s.Dota $p; if (Test-Path $f) { Remove-Item $f -Recurse -Force }
    }
    Ok "мод из Dota 2 удалён"
    $lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "DotaCS.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
    Remove-Item $StateFile -Force
    Write-Host "Готово. Steam -> CS2 -> Свойства -> Установленные файлы -> Проверить целостность, если хочешь всё вернуть 1 в 1."
    Read-Host "Нажми Enter чтобы закрыть"
}

try {
    switch ($Mode) { "install" { Install } "play" { Play } "uninstall" { Uninstall } }
} catch {
    Fail ("$($_.Exception.Message)`n" + $_.InvocationInfo.PositionMessage)
}
