-- DotaCS: all weapons and gear
-- Edit numbers here to balance the game.
--
-- cat:         shop column
-- price:       in dollars
-- damage:      per bullet (per pellet for shotguns)
-- pellets:     shotguns only, bullets per shot
-- rate:        seconds between shots (smaller = faster)
-- mag:         bullets in magazine
-- reload:      seconds
-- range:       Dota units
-- spread:      base spread in degrees
-- recoil:      extra degrees per shot while holding fire
-- move_spread: extra degrees while running
-- auto:        true = hold to fire, false = one shot per click

CS_CATEGORIES = { "pistols", "smg", "heavy", "rifles", "snipers", "grenades", "gear" }

CS_CATEGORY_NAMES = {
    pistols = "Пистолеты",
    smg     = "ПП",
    heavy   = "Тяжёлое",
    rifles  = "Винтовки",
    snipers = "Снайперки",
    grenades = "Гранаты",
    gear    = "Снаряжение",
}

CS_WEAPONS = {
    -- Pistols
    glock    = { cat = "pistols", name = "Glock-18",       price = 200,  damage = 30,  rate = 0.15,  mag = 20,  reload = 2.2, range = 900,  spread = 2,   recoil = 0.8, move_spread = 4,  auto = false },
    usp      = { cat = "pistols", name = "USP-S",          price = 200,  damage = 35,  rate = 0.17,  mag = 12,  reload = 2.2, range = 950,  spread = 1.5, recoil = 0.8, move_spread = 4,  auto = false },
    p2000    = { cat = "pistols", name = "P2000",          price = 200,  damage = 35,  rate = 0.17,  mag = 13,  reload = 2.2, range = 950,  spread = 1.5, recoil = 0.8, move_spread = 4,  auto = false },
    p250     = { cat = "pistols", name = "P250",           price = 300,  damage = 38,  rate = 0.15,  mag = 13,  reload = 2.2, range = 900,  spread = 2,   recoil = 1,   move_spread = 4,  auto = false },
    dualies  = { cat = "pistols", name = "Dual Berettas",  price = 300,  damage = 38,  rate = 0.12,  mag = 30,  reload = 3.8, range = 850,  spread = 2.5, recoil = 0.8, move_spread = 4,  auto = false },
    fiveseven= { cat = "pistols", name = "Five-SeveN",     price = 500,  damage = 32,  rate = 0.15,  mag = 20,  reload = 2.2, range = 950,  spread = 1.5, recoil = 0.8, move_spread = 4,  auto = false },
    tec9     = { cat = "pistols", name = "Tec-9",          price = 500,  damage = 33,  rate = 0.12,  mag = 18,  reload = 2.5, range = 850,  spread = 2.5, recoil = 1,   move_spread = 3,  auto = false },
    cz75     = { cat = "pistols", name = "CZ75-Auto",      price = 500,  damage = 31,  rate = 0.1,   mag = 12,  reload = 2.7, range = 850,  spread = 2.5, recoil = 1,   move_spread = 4,  auto = true  },
    deagle   = { cat = "pistols", name = "Desert Eagle",   price = 700,  damage = 53,  rate = 0.225, mag = 7,   reload = 2.2, range = 1000, spread = 1,   recoil = 2,   move_spread = 8,  auto = false },
    r8       = { cat = "pistols", name = "R8 Revolver",    price = 600,  damage = 86,  rate = 0.5,   mag = 8,   reload = 2.3, range = 1000, spread = 1,   recoil = 2,   move_spread = 8,  auto = false },

    -- SMGs
    mac10    = { cat = "smg", name = "MAC-10",    price = 1050, damage = 29, rate = 0.075, mag = 30, reload = 2.6, range = 850, spread = 3,   recoil = 0.6, move_spread = 2, auto = true },
    mp9      = { cat = "smg", name = "MP9",       price = 1250, damage = 26, rate = 0.07,  mag = 30, reload = 2.1, range = 850, spread = 3,   recoil = 0.6, move_spread = 2, auto = true },
    mp7      = { cat = "smg", name = "MP7",       price = 1500, damage = 29, rate = 0.08,  mag = 30, reload = 3.1, range = 900, spread = 2.5, recoil = 0.6, move_spread = 2, auto = true },
    mp5sd    = { cat = "smg", name = "MP5-SD",    price = 1500, damage = 27, rate = 0.08,  mag = 30, reload = 3.0, range = 900, spread = 2.5, recoil = 0.5, move_spread = 2, auto = true },
    ump45    = { cat = "smg", name = "UMP-45",    price = 1200, damage = 35, rate = 0.09,  mag = 25, reload = 3.5, range = 900, spread = 2.5, recoil = 0.7, move_spread = 2, auto = true },
    p90      = { cat = "smg", name = "P90",       price = 2350, damage = 26, rate = 0.07,  mag = 50, reload = 3.3, range = 900, spread = 3,   recoil = 0.5, move_spread = 2, auto = true },
    bizon    = { cat = "smg", name = "PP-Bizon",  price = 1400, damage = 27, rate = 0.08,  mag = 64, reload = 2.4, range = 850, spread = 3,   recoil = 0.5, move_spread = 2, auto = true },

    -- Heavy
    nova     = { cat = "heavy", name = "Nova",       price = 1050, damage = 26, pellets = 9, rate = 0.88,  mag = 8,   reload = 4.0, range = 550,  spread = 8, recoil = 0,   move_spread = 2,  auto = false },
    xm1014   = { cat = "heavy", name = "XM1014",     price = 2000, damage = 20, pellets = 6, rate = 0.35,  mag = 7,   reload = 4.0, range = 550,  spread = 8, recoil = 0,   move_spread = 2,  auto = true  },
    sawedoff = { cat = "heavy", name = "Sawed-Off",  price = 1100, damage = 32, pellets = 8, rate = 0.85,  mag = 7,   reload = 4.0, range = 450,  spread = 10,recoil = 0,   move_spread = 2,  auto = false },
    mag7     = { cat = "heavy", name = "MAG-7",      price = 1300, damage = 30, pellets = 8, rate = 0.85,  mag = 5,   reload = 2.5, range = 500,  spread = 7, recoil = 0,   move_spread = 2,  auto = false },
    m249     = { cat = "heavy", name = "M249",       price = 5200, damage = 32, rate = 0.08,  mag = 100, reload = 5.7, range = 1100, spread = 3, recoil = 0.8, move_spread = 10, auto = true  },
    negev    = { cat = "heavy", name = "Negev",      price = 1700, damage = 35, rate = 0.075, mag = 150, reload = 5.7, range = 1100, spread = 4, recoil = 0.6, move_spread = 10, auto = true  },

    -- Rifles
    famas    = { cat = "rifles", name = "FAMAS",     price = 2050, damage = 30, rate = 0.09, mag = 25, reload = 3.3, range = 1150, spread = 1.5, recoil = 1,   move_spread = 7, auto = true },
    galil    = { cat = "rifles", name = "Galil AR",  price = 1800, damage = 30, rate = 0.09, mag = 35, reload = 3.0, range = 1150, spread = 1.5, recoil = 1,   move_spread = 7, auto = true },
    m4a4     = { cat = "rifles", name = "M4A4",      price = 3100, damage = 33, rate = 0.09, mag = 30, reload = 3.1, range = 1200, spread = 1,   recoil = 1,   move_spread = 8, auto = true },
    m4a1s    = { cat = "rifles", name = "M4A1-S",    price = 2900, damage = 38, rate = 0.1,  mag = 20, reload = 3.1, range = 1200, spread = 0.8, recoil = 0.9, move_spread = 8, auto = true },
    ak47     = { cat = "rifles", name = "AK-47",     price = 2700, damage = 36, rate = 0.1,  mag = 30, reload = 2.5, range = 1200, spread = 1,   recoil = 1.2, move_spread = 8, auto = true },
    aug      = { cat = "rifles", name = "AUG",       price = 3300, damage = 28, rate = 0.09, mag = 30, reload = 3.8, range = 1300, spread = 0.7, recoil = 0.9, move_spread = 8, auto = true },
    sg553    = { cat = "rifles", name = "SG 553",    price = 3000, damage = 30, rate = 0.11, mag = 30, reload = 2.8, range = 1300, spread = 0.7, recoil = 1,   move_spread = 8, auto = true },

    -- Snipers
    ssg08    = { cat = "snipers", name = "SSG 08",   price = 1700, damage = 264, rate = 1.25, mag = 10, reload = 3.7, range = 1900, spread = 0.3, recoil = 0, move_spread = 6,  auto = false },
    awp      = { cat = "snipers", name = "AWP",      price = 4750, damage = 345, rate = 1.5,  mag = 5,  reload = 3.7, range = 2000, spread = 0.3, recoil = 0, move_spread = 15, auto = false },
    g3sg1    = { cat = "snipers", name = "G3SG1",    price = 5000, damage = 80,  rate = 0.25, mag = 20, reload = 4.7, range = 1800, spread = 0.8, recoil = 0.5, move_spread = 12, auto = false },
    scar20   = { cat = "snipers", name = "SCAR-20",  price = 5000, damage = 80,  rate = 0.25, mag = 20, reload = 3.1, range = 1800, spread = 0.8, recoil = 0.5, move_spread = 12, auto = false },
}

-- Knife: always in slot 3, melee, no ammo
CS_WEAPONS.knife = { cat = "knife", name = "Нож", price = 0, damage = 40, rate = 0.4,
                     range = 150, spread = 0, recoil = 0, move_spread = 0, auto = true, melee = true }

-- Zeus x27: one shot, short range, kills a CS player. Slot 3 together with the knife.
CS_WEAPONS.zeus = { cat = "gear", name = "Zeus x27", price = 200, damage = 500, rate = 1, mag = 1,
                    reload = 0, range = 200, spread = 0, recoil = 0, move_spread = 0, auto = false, taser = true }

-- Grenades (slot 4). max = how many of this type you can carry, CS_GRENADE_TOTAL = all types together
CS_GRENADE_TOTAL = 4
CS_GRENADE_RANGE = 1000   -- max throw distance
CS_GRENADE_SPEED = 900    -- flight speed
CS_GRENADES = {
    he      = { cat = "grenades", name = "HE граната",   price = 300, max = 1, radius = 350, damage = 392 },   -- x4 (was 98)
    flash   = { cat = "grenades", name = "Флешка",       price = 200, max = 2, radius = 650, blind = 3.5 },
    smoke   = { cat = "grenades", name = "Дымовая",      price = 300, max = 1, radius = 300, duration = 18 },
    molotov = { cat = "grenades", name = "Молотов",      price = 400, max = 1, radius = 250, duration = 7, dps = 160 },   -- x4 (was 40)
    decoy   = { cat = "grenades", name = "Ложная",       price = 50,  max = 1, duration = 15 },
}
CS_GRENADE_ORDER = { "he", "flash", "smoke", "molotov", "decoy" }
for _, g in pairs(CS_GRENADES) do
    g.grenade = true
    g.speed = 245
    g.rate = 0.8
    g.spread = 0
    g.recoil = 0
    g.move_spread = 0
    g.auto = false
end

CS_GEAR = {
    kevlar = { cat = "gear", name = "Кевлар",        price = 650,  armor = 35 },
    helmet = { cat = "gear", name = "Кевлар + шлем", price = 1000, armor = 50 },
    hp     = { cat = "gear", name = "+100 макс. HP", price = 1000, hp = 100 },
}

-- order of items inside each shop column
CS_SHOP_ORDER = {
    pistols  = { "glock", "usp", "p2000", "p250", "dualies", "fiveseven", "tec9", "cz75", "deagle", "r8" },
    smg      = { "mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon" },
    heavy    = { "nova", "xm1014", "sawedoff", "mag7", "m249", "negev" },
    rifles   = { "famas", "galil", "m4a4", "m4a1s", "ak47", "aug", "sg553" },
    snipers  = { "ssg08", "awp", "g3sg1", "scar20" },
    grenades = { "he", "flash", "smoke", "molotov", "decoy" },
    gear     = { "kevlar", "helmet", "hp", "zeus" },
}

-- Movement speed in CS units (like in CS2). Knife = 250.
-- Final Dota speed = CS speed * CS_SPEED_SCALE, so the knife gives 430.
CS_SPEED_SCALE = 430 / 250

local CS_SPEED = {
    knife = 250, zeus = 245,
    glock = 240, usp = 240, p2000 = 240, p250 = 240, dualies = 240, fiveseven = 240,
    tec9 = 240, cz75 = 240, deagle = 230, r8 = 220,
    mac10 = 240, mp9 = 240, mp7 = 220, mp5sd = 235, ump45 = 230, p90 = 230, bizon = 240,
    nova = 220, xm1014 = 215, sawedoff = 210, mag7 = 225, m249 = 195, negev = 150,
    famas = 220, galil = 215, m4a4 = 225, m4a1s = 225, ak47 = 215, aug = 220, sg553 = 210,
    ssg08 = 230, awp = 200, g3sg1 = 215, scar20 = 215,
}
for id, speed in pairs(CS_SPEED) do
    if CS_WEAPONS[id] then CS_WEAPONS[id].speed = speed end
end

function CS_GetItem(id)
    return CS_WEAPONS[id] or CS_GRENADES[id] or CS_GEAR[id]
end

-- which slot a weapon goes into
function CS_WeaponSlot(id)
    local w = CS_WEAPONS[id]
    if not w then return nil end
    if w.cat == "knife" then return "knife" end
    if w.taser then return "taser" end
    if w.cat == "pistols" then return "secondary" end
    return "primary"
end
