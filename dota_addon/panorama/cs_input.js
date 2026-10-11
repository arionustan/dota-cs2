"use strict";

// DotaCS client: controls, HUD, buy menu, crosshair, kill feed, flashbang, settings.
// CS controls turn on only after the server says this player is a CS player,
// so Dota players keep their normal controls. Kill feed and flashbang work for everyone.

$.Msg("[DotaCS] cs_input.js loaded");

(function () {
    var enabled = false;
    var firing = false;
    var shopOpen = false;
    var settingsOpen = false;
    var money = 0;
    var shopTiles = [];
    var moveKeys = { W: false, A: false, S: false, D: false };
    var hud = {};

    // ---------------- settings (reset when the game restarts) ----------------
    var DEFAULTS = {
        chColor: "#4cff4c",
        chLength: 8,
        chGap: 4,
        chThickness: 2,
        chDot: false,
        chOutline: true,
        chDynamic: true,
        wheelJump: true,
        killFeed: true,
        hideDotaHud: true,
    };
    var settings = JSON.parse(JSON.stringify(DEFAULTS));
    var CH_COLORS = ["#4cff4c", "#ffff00", "#00ffff", "#4c8cff", "#ff4cff", "#ff3b3b", "#ffffff"];

    // ---------------- helpers ----------------
    function send(name, data) {
        GameEvents.SendCustomGameEventToServer(name, data || {});
    }

    // Panorama turns Lua arrays into objects with "1", "2"... keys
    function toArray(obj) {
        if (!obj) return [];
        if (Array.isArray(obj)) return obj;
        var keys = Object.keys(obj).sort(function (a, b) { return Number(a) - Number(b); });
        return keys.map(function (k) { return obj[k]; });
    }

    // true while the player is typing in the Dota chat
    var dotaHudRoot = null;
    function chatActive() {
        try {
            if (!dotaHudRoot) {
                var p = $.GetContextPanel();
                while (p.GetParent()) p = p.GetParent();
                dotaHudRoot = p;
            }
            var input = dotaHudRoot.FindChildTraverse("ChatInput");
            return !!(input && input.BHasKeyFocus());
        } catch (e) {
            return false;
        }
    }

    function bindKey(key, name, onDown, onUp) {
        var down = onDown;
        onDown = function () { if (!chatActive()) down(); };
        Game.AddCommand("+" + name, onDown, "", 0);
        Game.AddCommand("-" + name, onUp || function () {}, "", 0);
        Game.CreateCustomKeyBind(key, "+" + name);
    }

    function cursorWorld() {
        return GameUI.GetScreenWorldPosition(GameUI.GetCursorPosition());
    }

    function myHero() {
        return Players.GetPlayerHeroEntityIndex(Players.GetLocalPlayer());
    }

    // screen pixels -> panorama units (panorama is laid out for 1080p height)
    function toPanorama(px) {
        return px * 1080 / Game.GetScreenHeight();
    }

    function menuOpen() {
        return shopOpen || settingsOpen;
    }

    // ---------------- WASD ----------------
    function bindMove(key) {
        bindKey(key, "CSMove_" + key,
            function () { moveKeys[key] = true; send("cs_key", { key: key, down: 1 }); },
            function () { moveKeys[key] = false; send("cs_key", { key: key, down: 0 }); });
    }

    // ---------------- shooting ----------------
    function sendFire(down) {
        var data = { down: down };
        var pos = cursorWorld();
        if (pos) {
            data.x = pos[0];
            data.y = pos[1];
            data.z = pos[2];
        }
        send("cs_fire", data);
    }

    function fireLoop() {
        if (!firing) return;
        if (!GameUI.IsMouseDown(0) || menuOpen()) {
            firing = false;
            sendFire(0);
            return;
        }
        sendFire(1);
        $.Schedule(0.05, fireLoop);
    }

    GameUI.SetMouseCallback(function (eventName, arg) {
        if (!enabled || menuOpen()) return false;

        // mouse wheel = jump (bunnyhop like in CS)
        if (eventName === "wheeled") {
            if (settings.wheelJump) {
                send("cs_jump");
                return true;
            }
            return false;
        }

        if (arg !== 0) return false;
        if (eventName === "pressed" || eventName === "doublepressed") {
            firing = true;
            sendFire(1);
            $.Schedule(0.05, fireLoop);
            return true;
        }
        return false;
    });

    // ---------------- buy menu ----------------
    function buildShop(catalog) {
        var columnsPanel = $("#CSShopColumns");
        columnsPanel.RemoveAndDeleteChildren();
        shopTiles = [];

        toArray(catalog.columns).forEach(function (col, ci) {
            var column = $.CreatePanel("Panel", columnsPanel, "CSCol" + ci);
            column.AddClass("CSColumn");

            var title = $.CreatePanel("Label", column, "");
            title.AddClass("CSColumnTitle");
            title.text = col.title;

            toArray(col.items).forEach(function (item) {
                var tile = $.CreatePanel("Panel", column, "CSItem_" + item.id);
                tile.AddClass("CSItem");

                var name = $.CreatePanel("Label", tile, "");
                name.AddClass("CSItemName");
                name.text = item.name;

                var price = $.CreatePanel("Label", tile, "");
                price.AddClass("CSItemPrice");
                price.text = "$" + item.price;

                tile.SetPanelEvent("onactivate", function () {
                    send("cs_buy", { item: item.id });
                });

                shopTiles.push({ panel: tile, price: item.price });
            });
        });
        refreshShop();
    }

    function refreshShop() {
        shopTiles.forEach(function (t) {
            t.panel.SetHasClass("TooExpensive", t.price > money);
        });
        $("#CSShopMoney").text = "$" + money;
    }

    function toggleShop() {
        if (settingsOpen) toggleSettings();
        shopOpen = !shopOpen;
        $("#CSShop").visible = shopOpen;
        $("#CSShopMsg").text = "";
        refreshShop();
    }

    GameEvents.Subscribe("cs_shop_msg", function (data) {
        $("#CSShopMsg").text = data.text;
    });

    // ---------------- HUD from server ----------------
    GameEvents.Subscribe("cs_hud", function (data) {
        hud = data;
        money = data.money;
        $("#CSHud").visible = true;
        $("#CSMoney").text = "$" + data.money;
        $("#CSWeapon").text = data.weapon;

        if (data.noammo) {
            $("#CSAmmo").text = "";
            $("#CSAmmoMag").text = "";
        } else if (data.reloading) {
            $("#CSAmmo").text = "...";
            $("#CSAmmoMag").text = "перезарядка";
        } else {
            $("#CSAmmo").text = String(data.ammo);
            $("#CSAmmoMag").text = "/ " + data.mag;
        }
        $("#CSAmmo").SetHasClass("Low", !data.noammo && data.mag > 0 && data.ammo <= data.mag * 0.2);

        var s1 = $("#CSSlot1"), s2 = $("#CSSlot2"), s3 = $("#CSSlot3"), s4 = $("#CSSlot4");
        s1.text = data.primary ? "1  " + data.primary : "";
        s2.text = data.secondary ? "2  " + data.secondary : "";
        s3.text = "3  Нож" + (data.taser ? "  /  " + data.taser : "");
        s4.text = data.grenades ? "4  " + data.grenades : "";
        s1.SetHasClass("Active", data.slot === "primary");
        s2.SetHasClass("Active", data.slot === "secondary");
        s3.SetHasClass("Active", data.slot === "knife" || data.slot === "taser");
        s4.SetHasClass("Active", data.slot === "grenade");

        $("#CSArmor").text = String(data.armor || 0);
        $("#CSArmorRow").visible = (data.armor || 0) > 0;

        var prompt = $("#CSPrompt");
        prompt.text = data.nearDrop ? "E  поднять " + data.nearDrop : "";
        prompt.SetHasClass("Visible", !!data.nearDrop);

        if (shopOpen) refreshShop();
    });

    // HP, death timer and crosshair are updated every frame
    function frame() {
        if (enabled) {
            var hero = myHero();
            if (hero !== -1) {
                var hp = Entities.GetHealth(hero);
                var maxHp = Entities.GetMaxHealth(hero);
                $("#CSHealth").text = String(Math.max(0, hp));
                $("#CSHealth").SetHasClass("Low", hp <= maxHp * 0.25);
                $("#CSHealthFill").style.width = (maxHp > 0 ? Math.floor(100 * hp / maxHp) : 0) + "%";

                var dead = !Entities.IsAlive(hero);
                var deadLabel = $("#CSDead");
                deadLabel.SetHasClass("Visible", dead);
                if (dead) {
                    var t = 0;
                    try { t = Players.GetRespawnSeconds(Players.GetLocalPlayer()); } catch (e) {}
                    deadLabel.text = t > 0 ? "Возрождение через " + Math.ceil(t) : "Ты погиб";
                }
            }
            updateCrosshair();
        }
        $.Schedule(0, frame);
    }

    // ---------------- crosshair ----------------
    var chState = { gap: -999 };

    function layoutCrosshair(holder, gap) {
        var len = settings.chLength;
        var th = settings.chThickness;
        var c = 50; // center of the 100x100 holder

        function place(id, x, y, w, h) {
            var p = holder.FindChildTraverse(id);
            if (!p) return;
            p.style.width = w + "px";
            p.style.height = h + "px";
            p.style.position = x + "px " + y + "px 0px";
            p.style.backgroundColor = settings.chColor;
            p.SetHasClass("Outline", settings.chOutline);
        }

        place("CHTop", c - th / 2, c - gap - len, th, len);
        place("CHBottom", c - th / 2, c + gap, th, len);
        place("CHLeft", c - gap - len, c - th / 2, len, th);
        place("CHRight", c + gap, c - th / 2, len, th);
        place("CHDot", c - th / 2, c - th / 2, th, th);
        var dot = holder.FindChildTraverse("CHDot");
        if (dot) dot.visible = settings.chDot;
    }

    function updateCrosshair() {
        var ch = $("#CSCrosshair");
        var show = enabled && !menuOpen();
        ch.SetHasClass("Visible", show);
        if (!show) return;

        var cur = GameUI.GetCursorPosition();
        ch.style.position = (toPanorama(cur[0]) - 50) + "px " + (toPanorama(cur[1]) - 50) + "px 0px";

        var gap = settings.chGap;
        if (settings.chDynamic) {
            var moving = moveKeys.W || moveKeys.A || moveKeys.S || moveKeys.D;
            if (moving) gap += 6;
            if (GameUI.IsMouseDown(0)) gap += 5;
        }
        if (gap !== chState.gap) {
            chState.gap = gap;
            layoutCrosshair(ch, gap);
        }
    }

    function refreshCrosshair() {
        chState.gap = -999;
        // preview in settings
        var holder = $("#CSPreviewHolder");
        if (holder.GetChildCount() === 0) {
            ["CHTop", "CHBottom", "CHLeft", "CHRight", "CHDot"].forEach(function (id) {
                var p = $.CreatePanel("Panel", holder, id);
                p.AddClass("CHLine");
                p.hittest = false;
            });
        }
        layoutCrosshair(holder, settings.chGap);
    }

    // ---------------- kill feed ----------------
    function unitLabel(name, unit) {
        if (name) return name;
        if (!unit) return "?";
        if (unit === "cs") return "Ксник";
        return $.Localize("#" + unit);
    }

    GameEvents.Subscribe("cs_killfeed", function (data) {
        if (!settings.killFeed) return;
        var feed = $("#CSKillFeed");
        var row = $.CreatePanel("Panel", feed, "");
        row.AddClass("CSKill");

        var myName = Players.GetPlayerName(Players.GetLocalPlayer());
        if (data.killer === myName || data.victim === myName) row.AddClass("Mine");

        var teamClass = function (team) { return team === 2 ? "Radiant" : "Dire"; };

        if (data.killer || data.killerUnit) {
            var k = $.CreatePanel("Label", row, "");
            k.AddClass("CSKillName");
            k.AddClass(teamClass(data.killerTeam));
            k.text = unitLabel(data.killer, data.killerUnit);
        }

        var w = $.CreatePanel("Label", row, "");
        w.AddClass("CSKillWeapon");
        w.text = data.weapon ? "[" + data.weapon + "]" : "✕";

        var v = $.CreatePanel("Label", row, "");
        v.AddClass("CSKillName");
        v.AddClass(teamClass(data.victimTeam));
        v.text = unitLabel(data.victim, data.victimUnit);

        // keep only the last 5
        while (feed.GetChildCount() > 5) {
            feed.GetChild(0).DeleteAsync(0);
        }
        $.Schedule(6, function () { if (row.IsValid()) row.AddClass("Fade"); });
        $.Schedule(6.6, function () { if (row.IsValid()) row.DeleteAsync(0); });
    });

    // ---------------- flashbang ----------------
    GameEvents.Subscribe("cs_flash", function (data) {
        var flash = $("#CSFlash");
        var hold = Math.max(0.2, data.duration * 0.5);
        var fade = Math.max(0.3, data.duration * 0.5);
        flash.style.transitionDuration = "0s";
        flash.style.opacity = "1";
        $.Schedule(hold, function () {
            flash.style.transitionProperty = "opacity";
            flash.style.transitionDuration = fade + "s";
            flash.style.opacity = "0";
        });
    });

    // ---------------- settings menu ----------------
    function addRow(parent, label) {
        var row = $.CreatePanel("Panel", parent, "");
        row.AddClass("CSOptionRow");
        var l = $.CreatePanel("Label", row, "");
        l.AddClass("CSOptionLabel");
        l.text = label;
        var controls = $.CreatePanel("Panel", row, "");
        controls.AddClass("CSOptionControls");
        return controls;
    }

    function addButton(parent, text, onClick) {
        var b = $.CreatePanel("Button", parent, "");
        b.AddClass("CSSmallButton");
        var l = $.CreatePanel("Label", b, "");
        l.text = text;
        b.SetPanelEvent("onactivate", onClick);
        return b;
    }

    function addStepper(parent, label, key, min, max, step) {
        var controls = addRow(parent, label);
        var value;
        addButton(controls, "−", function () {
            settings[key] = Math.max(min, Math.round((settings[key] - step) * 10) / 10);
            value.text = String(settings[key]);
            applySettings();
        });
        value = $.CreatePanel("Label", controls, "");
        value.AddClass("CSOptionValue");
        value.text = String(settings[key]);
        addButton(controls, "+", function () {
            settings[key] = Math.min(max, Math.round((settings[key] + step) * 10) / 10);
            value.text = String(settings[key]);
            applySettings();
        });
    }

    function addToggle(parent, label, key) {
        var controls = addRow(parent, label);
        var on, off;
        function paint() {
            on.SetHasClass("Active", settings[key]);
            off.SetHasClass("Active", !settings[key]);
        }
        on = addButton(controls, "ВКЛ", function () { settings[key] = true; paint(); applySettings(); });
        off = addButton(controls, "ВЫКЛ", function () { settings[key] = false; paint(); applySettings(); });
        paint();
    }

    function addColors(parent, label, key) {
        var controls = addRow(parent, label);
        var swatches = [];
        CH_COLORS.forEach(function (color) {
            var s = $.CreatePanel("Button", controls, "");
            s.AddClass("CSSwatch");
            s.style.backgroundColor = color;
            s.SetPanelEvent("onactivate", function () {
                settings[key] = color;
                swatches.forEach(function (x) { x.p.SetHasClass("Active", x.c === color); });
                applySettings();
            });
            swatches.push({ p: s, c: color });
        });
        swatches.forEach(function (x) { x.p.SetHasClass("Active", x.c === settings[key]); });
    }

    function buildSettings() {
        var ch = $("#CSCrosshairOptions");
        ch.RemoveAndDeleteChildren();
        addColors(ch, "Цвет", "chColor");
        addStepper(ch, "Длина", "chLength", 1, 30, 1);
        addStepper(ch, "Зазор", "chGap", -5, 20, 1);
        addStepper(ch, "Толщина", "chThickness", 1, 8, 0.5);
        addToggle(ch, "Точка в центре", "chDot");
        addToggle(ch, "Обводка", "chOutline");
        addToggle(ch, "Расходится при стрельбе и беге", "chDynamic");

        var game = $("#CSPageGame");
        game.RemoveAndDeleteChildren();
        addToggle(game, "Прыжок на колёсико мыши", "wheelJump");
        addToggle(game, "Лента убийств", "killFeed");
        addToggle(game, "Скрыть интерфейс Доты", "hideDotaHud");
        var bridgeRow = addRow(game, "Тест моста с КС2 (нужен запущенный bridge.py)");
        addButton(bridgeRow, "ВКЛ / ВЫКЛ", function () { send("cs_bridge_toggle"); });

        $("#CSKeysText").text =
            "<b>WASD</b>  движение<br>" +
            "<b>ЛКМ</b>  стрелять / бросить гранату<br>" +
            "<b>R</b>  перезарядка<br>" +
            "<b>Пробел / колёсико</b>  прыжок (жми сразу после приземления для баннихопа)<br>" +
            "<b>1 / 2 / 3 / 4</b>  основное / пистолет / нож и Zeus / гранаты<br>" +
            "<b>Q</b>  предыдущее оружие<br>" +
            "<b>G</b>  выбросить оружие<br>" +
            "<b>E</b>  поднять оружие с земли<br>" +
            "<b>B</b>  меню закупки (только у фонтана)<br>" +
            "<b>O</b>  настройки";

        refreshCrosshair();
    }

    function showTab(name) {
        ["Crosshair", "Game", "Keys"].forEach(function (t) {
            $("#CSPage" + t).visible = (t === name);
            $("#CSTab" + t).SetHasClass("Active", t === name);
        });
    }

    function toggleSettings() {
        if (shopOpen) toggleShop();
        settingsOpen = !settingsOpen;
        $("#CSSettings").visible = settingsOpen;
    }

    function setDotaHud(visible) {
        var elements = [
            "DOTA_DEFAULT_UI_ACTION_PANEL",
            "DOTA_DEFAULT_UI_INVENTORY_SHOP",
            "DOTA_DEFAULT_UI_INVENTORY_ITEMS",
            "DOTA_DEFAULT_UI_INVENTORY_QUICKBUY",
            "DOTA_DEFAULT_UI_INVENTORY_COURIER",
            "DOTA_DEFAULT_UI_INVENTORY_PROTECT",
            "DOTA_DEFAULT_UI_INVENTORY_GOLD",
            "DOTA_DEFAULT_UI_SHOP_SUGGESTEDITEMS",
            "DOTA_DEFAULT_UI_QUICK_STATS",
        ];
        elements.forEach(function (name) {
            try {
                var id = DotaDefaultUIElement_t[name];
                if (id !== undefined) GameUI.SetDefaultUIEnabled(id, visible);
            } catch (e) {}
        });
    }

    function applySettings() {
        refreshCrosshair();
        if (enabled) setDotaHud(!settings.hideDotaHud);
        if (!settings.killFeed) $("#CSKillFeed").RemoveAndDeleteChildren();
    }

    $("#CSTabCrosshair").SetPanelEvent("onactivate", function () { showTab("Crosshair"); });
    $("#CSTabGame").SetPanelEvent("onactivate", function () { showTab("Game"); });
    $("#CSTabKeys").SetPanelEvent("onactivate", function () { showTab("Keys"); });
    $("#CSSettingsButton").SetPanelEvent("onactivate", toggleSettings);
    $("#CSSettingsReset").SetPanelEvent("onactivate", function () {
        settings = JSON.parse(JSON.stringify(DEFAULTS));
        buildSettings();
        applySettings();
    });

    // ---------------- enable CS controls ----------------
    GameEvents.Subscribe("cs_enable", function (catalog) {
        buildShop(catalog);
        if (enabled) return;
        enabled = true;

        ["W", "A", "S", "D"].forEach(bindMove);
        bindKey("R", "CSReload", function () { send("cs_reload"); });
        bindKey("1", "CSSlot1", function () { send("cs_slot", { slot: "1" }); });
        bindKey("2", "CSSlot2", function () { send("cs_slot", { slot: "2" }); });
        bindKey("3", "CSSlot3", function () { send("cs_slot", { slot: "3" }); });
        bindKey("4", "CSSlot4", function () { send("cs_slot", { slot: "4" }); });
        bindKey("Q", "CSSlotLast", function () { send("cs_slot", { slot: "last" }); });
        bindKey("G", "CSDrop", function () { send("cs_drop"); });
        bindKey("E", "CSUse", function () { send("cs_use"); });
        bindKey("SPACE", "CSJump", function () { send("cs_jump"); });
        bindKey("B", "CSShop", toggleShop);

        applySettings();
        $.Msg("[DotaCS] CS controls enabled");
    });

    $("#CSShop").visible = false;
    $("#CSSettings").visible = false;
    $("#CSHud").visible = false;
    showTab("Crosshair");
    bindKey("O", "CSSettings", toggleSettings);

    buildSettings();
    frame();
})();
