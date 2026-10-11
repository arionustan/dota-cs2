-- DotaCS: Dota 2 x CS custom game
--
-- Files:
--   cs_weapons.lua   all weapons, grenades, prices, speeds (balance here)
--   cs_grenades.lua  HE, flash, smoke, molotov, decoy
--   cs_drops.lua     guns on the ground
--   cs_pick.lua      game modes and "CS or Dota" choice
--   modifiers/       HP, armor, speed, jump, blind, smoke

-- Dota runs this file in its own scope, but required files run in the global one.
-- Put the class and all settings in the global scope so every file sees them.
if _G.CDotaCS == nil then
    _G.CDotaCS = class({})
end
CDotaCS = _G.CDotaCS

require("cs_weapons")
require("cs_grenades")
require("cs_drops")
require("cs_pick")
require("cs_bridge")

LinkLuaModifier("modifier_cs_player", "modifiers/modifier_cs_player", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_armor", "modifiers/modifier_cs_armor", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_speed", "modifiers/modifier_cs_speed", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_jump", "modifiers/modifier_cs_jump", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_grenade_thinker", "modifiers/modifier_cs_grenade_thinker", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_blind", "modifiers/modifier_cs_blind", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_smoked", "modifiers/modifier_cs_smoked", LUA_MODIFIER_MOTION_NONE)
LinkLuaModifier("modifier_cs_proxy", "modifiers/modifier_cs_proxy", LUA_MODIFIER_MOTION_NONE)

-- CS settings
_G.CS_START_MONEY = 800
_G.CS_TEST_NO_CREEPS = false -- lane creeps and neutrals spawn (set true to test without them)
_G.CS_REWARD_CREEP = 150
_G.CS_REWARD_HERO = 300
_G.CS_START_HP = 100
_G.CS_MAX_HP = 1000
_G.CS_START_PISTOL = "glock"
_G.CS_BASE_HERO = "npc_dota_hero_sniper"
_G.CS_TICK = 0.03
_G.CS_MOVE_LOOKAHEAD = 200
_G.CS_TRACER = "particles/units/heroes/hero_zuus/zuus_arc_lightning.vpcf" -- placeholder
_G.CS_SHOT_SOUND = "Hero_Sniper.attack"                                  -- placeholder
_G.CS_ZEUS_SOUND = "Hero_Zuus.ArcLightning.Target"

-- Jump and bunnyhop
_G.CS_JUMP_TIME = 0.6     -- seconds in the air
_G.CS_BHOP_WINDOW = 0.2   -- jump again within this time after landing to keep speed
_G.CS_BHOP_STEP = 0.08    -- +8% speed for each chained jump
_G.CS_BHOP_MAX = 8        -- max chained jumps (+64%)
_G.CS_HELMET_UPGRADE_PRICE = 350 -- helmet when you already have kevlar, like in CS

function Precache(context)
    PrecacheUnitByNameSync(CS_BASE_HERO, context)
    PrecacheUnitByNameSync("npc_cs_proxy", context)
    PrecacheResource("particle", CS_TRACER, context)
    PrecacheResource("soundfile", "soundevents/game_sounds_heroes/game_sounds_sniper.vsndevts", context)
    PrecacheResource("soundfile", "soundevents/game_sounds_heroes/game_sounds_zuus.vsndevts", context)
    CS_PrecacheGrenades(context)
end

function Activate()
    GameRules.DotaCS = CDotaCS()
    GameRules.DotaCS:Init()
end

function CDotaCS:Init()
    print("[DotaCS] Loaded!")

    self.csPlayers = {}
    self.grenades = {}
    self.smokes = {}
    self.fires = {}
    self.drops = {}
    self.lastHit = {}

    GameRules:SetHeroSelectionTime(40)
    GameRules:SetStrategyTime(10)
    GameRules:SetPreGameTime(30)

    -- test mode: no lane creeps and no neutrals, so nothing pushes the throne during tests
    if CS_TEST_NO_CREEPS then
        pcall(function() GameRules:SetCreepSpawningEnabled(false) end)
        SendToServerConsole("dota_creeps_no_spawning 1")
        SendToServerConsole("dota_neutral_spawn_interval 9999")
        pcall(function()
            local mode = GameRules:GetGameModeEntity()
            mode:SetNeutralStashEnabled(false)
        end)
    end

    ListenToGameEvent("player_chat", Dynamic_Wrap(CDotaCS, "OnPlayerChat"), self)
    ListenToGameEvent("entity_killed", Dynamic_Wrap(CDotaCS, "OnEntityKilled"), self)
    ListenToGameEvent("npc_spawned", Dynamic_Wrap(CDotaCS, "OnNPCSpawned"), self)

    local events = {
        cs_key = "OnKey", cs_fire = "OnFire", cs_reload = "OnReloadKey", cs_slot = "OnSlotKey",
        cs_buy = "OnBuy", cs_jump = "OnJump", cs_drop = "OnDropKey", cs_use = "OnUseKey",
        cs_bridge_toggle = "OnBridgeButton",
    }
    for name, method in pairs(events) do
        CustomGameEventManager:RegisterListener(name, function(_, d) self[method](self, d) end)
    end

    self:InitPick()
    self:BridgeAutoStart()

    local mode = GameRules:GetGameModeEntity()
    mode:SetExecuteOrderFilter(Dynamic_Wrap(CDotaCS, "OrderFilter"), self)
    mode:SetThink("Think", self, "cs_think", CS_TICK)
end

------------------------------------------------------------
-- Chat commands (for testing)
------------------------------------------------------------
function CDotaCS:OnPlayerChat(keys)
    local text = string.lower(keys.text or "")
    local pid = keys.playerid

    if text == "-cs" then
        self:MakeCSPlayer(pid)
    elseif text == "-bridge" then
        self:BridgeToggle(pid)
    elseif text == "-money" and GameRules:IsCheatMode() then
        self:AddMoney(pid, 10000)
    end
end

------------------------------------------------------------
-- Create CS player
------------------------------------------------------------
function CDotaCS:MakeCSPlayer(pid)
    if self.csPlayers[pid] then return end
    self.firstSpawnDone[pid] = true

    local hero = PlayerResource:ReplaceHeroWith(pid, CS_BASE_HERO, 0, 0)
    if not hero then
        self:Msg("Error: could not create CS player.")
        return
    end

    for i = hero:GetAbilityCount() - 1, 0, -1 do
        local ability = hero:GetAbilityByIndex(i)
        if ability then
            hero:RemoveAbilityByHandle(ability)
        end
    end
    hero:SetAbilityPoints(0)
    hero:SetIdleAcquire(false)

    local grenadeAbility = hero:AddAbility("cs_grenade")
    if grenadeAbility then grenadeAbility:SetLevel(1) end

    self.csPlayers[pid] = {
        money = CS_START_MONEY,
        maxHP = CS_START_HP,
        weapons = { primary = nil, secondary = nil, knife = "knife", taser = nil },
        ammo = { primary = 0, secondary = 0, knife = 0, taser = 0 },
        grenades = {},
        grenadeType = nil,
        slot = "secondary",
        lastSlot = "knife",
        reloadEnd = nil,
        nextShot = 0,
        recoil = 0,
        firing = false,
        shotQueued = false,
        aim = nil,
        keys = {},
        running = false,
        jumpEnd = nil,
        landTime = nil,
        bhop = 0,
        speed = 0,
        nearDrop = "",
    }

    hero:AddNewModifier(hero, nil, "modifier_cs_player", {})
    hero:AddNewModifier(hero, nil, "modifier_cs_speed", {})
    self:GiveWeapon(pid, CS_START_PISTOL)

    PlayerResource:SetCameraTarget(pid, hero)

    local player = PlayerResource:GetPlayer(pid)
    if player then
        CustomGameEventManager:Send_ServerToPlayer(player, "cs_enable", self:BuildCatalog())
    end

    self:SendHud(pid)
    self:BroadcastPickState()
end

-- Shop catalog for the UI
function CDotaCS:BuildCatalog()
    local columns = {}
    for i, cat in ipairs(CS_CATEGORIES) do
        local items = {}
        for j, id in ipairs(CS_SHOP_ORDER[cat]) do
            local item = CS_GetItem(id)
            items[j] = { id = id, name = item.name, price = item.price }
        end
        columns[i] = { title = CS_CATEGORY_NAMES[cat], items = items }
    end
    return { columns = columns }
end

------------------------------------------------------------
-- Weapons and slots
--   primary / secondary / knife / taser / grenade
------------------------------------------------------------
function CDotaCS:CurrentWeapon(p)
    if p.slot == "grenade" then
        return p.grenadeType, CS_GRENADES[p.grenadeType]
    end
    local id = p.weapons[p.slot]
    return id, CS_WEAPONS[id]
end

function CDotaCS:BestSlot(p)
    if p.weapons.primary then return "primary" end
    if p.weapons.secondary then return "secondary" end
    return "knife"
end

function CDotaCS:GiveWeapon(pid, weaponId)
    local p = self.csPlayers[pid]
    local w = CS_WEAPONS[weaponId]
    if not p or not w then return end

    local slot = CS_WeaponSlot(weaponId)
    p.weapons[slot] = weaponId
    p.ammo[slot] = w.mag or 0
    self:SwitchSlot(pid, slot)
end

function CDotaCS:SwitchSlot(pid, slot)
    local p = self.csPlayers[pid]
    if not p then return end
    if slot == "grenade" then
        if not p.grenadeType or (p.grenades[p.grenadeType] or 0) <= 0 then return end
    elseif not p.weapons[slot] then
        return
    end

    if p.slot ~= slot then p.lastSlot = p.slot end
    p.slot = slot
    p.reloadEnd = nil
    p.recoil = 0
    p.shotQueued = false
    p.nextShot = GameRules:GetGameTime() + 0.3 -- draw time
    self:SendHud(pid)
end

-- keys 1-4 and Q
function CDotaCS:OnSlotKey(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    if not p then return end
    local s = tostring(data.slot)

    if s == "1" then
        self:SwitchSlot(pid, "primary")
    elseif s == "2" then
        self:SwitchSlot(pid, "secondary")
    elseif s == "3" then
        -- 3 cycles knife <-> Zeus
        if p.slot == "knife" and p.weapons.taser then
            self:SwitchSlot(pid, "taser")
        else
            self:SwitchSlot(pid, "knife")
        end
    elseif s == "4" then
        self:CycleGrenade(pid)
    elseif s == "last" then
        local last = p.lastSlot
        if last == "grenade" and self:GrenadeCount(p) == 0 then last = nil end
        if last and (last == "grenade" or p.weapons[last]) then
            self:SwitchSlot(pid, last)
        end
    end
end

------------------------------------------------------------
-- Shop
------------------------------------------------------------
function CDotaCS:OnBuy(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    local hero = PlayerResource:GetSelectedHeroEntity(pid)
    local id = data.item
    local item = CS_GetItem(id)
    if not p or not hero or not item then return end

    if not hero:IsAlive() then
        return self:ShopMsg(pid, "Нельзя покупать мёртвым")
    end
    if not hero:IsInRangeOfShop(DOTA_SHOP_HOME, true) then
        return self:ShopMsg(pid, "Покупать можно только у фонтана")
    end

    local price = item.price
    local armorMod = hero:FindModifierByName("modifier_cs_armor")

    -- check what the player already has
    if CS_WEAPONS[id] then
        if p.weapons[CS_WeaponSlot(id)] == id then
            return self:ShopMsg(pid, "У тебя уже есть " .. item.name)
        end
    elseif CS_GRENADES[id] then
        local err = self:CanBuyGrenade(p, id)
        if err then return self:ShopMsg(pid, err) end
    elseif item.armor then
        local current = armorMod and armorMod:GetStackCount() or 0
        if current >= item.armor then
            return self:ShopMsg(pid, "Броня уже есть")
        end
        if id == "helmet" and current > 0 then
            price = CS_HELMET_UPGRADE_PRICE
        end
    elseif item.hp then
        if p.maxHP >= CS_MAX_HP then
            return self:ShopMsg(pid, "Уже максимум HP")
        end
    end

    if p.money < price then
        return self:ShopMsg(pid, "Не хватает денег")
    end

    -- give the item
    if CS_WEAPONS[id] then
        -- like in CS: buying a new gun drops the old one from that slot
        local slot = CS_WeaponSlot(id)
        if p.weapons[slot] and slot ~= "taser" then
            self:DropWeapon(pid, slot, hero:GetAbsOrigin())
        end
        self:GiveWeapon(pid, id)
    elseif CS_GRENADES[id] then
        self:GiveGrenade(pid, id)
    elseif item.armor then
        hero:AddNewModifier(hero, nil, "modifier_cs_armor", { armor = item.armor })
    elseif item.hp then
        p.maxHP = math.min(CS_MAX_HP, p.maxHP + item.hp)
        local mod = hero:FindModifierByName("modifier_cs_player")
        if mod then mod:SetTargetHP(p.maxHP) end
        hero:Heal(item.hp, nil)
    end

    p.money = p.money - price
    self:ShopMsg(pid, "Куплено: " .. item.name)
    self:SendHud(pid)
end

function CDotaCS:ShopMsg(pid, text)
    local player = PlayerResource:GetPlayer(pid)
    if player then
        CustomGameEventManager:Send_ServerToPlayer(player, "cs_shop_msg", { text = text })
    end
end

------------------------------------------------------------
-- Spawn / respawn
------------------------------------------------------------
function CDotaCS:OnNPCSpawned(keys)
    local unit = EntIndexToHScript(keys.entindex)
    if not unit then return end

    -- test mode: remove lane creeps and neutrals as soon as they spawn
    if CS_TEST_NO_CREEPS and not unit.csSlot and unit:GetUnitName() ~= "npc_cs_proxy"
        and (unit:IsCreep() or unit:IsNeutralUnitType()) and not unit:IsHero()
        and unit:GetPlayerOwnerID() == -1 then
        unit:SetContextThink("cs_nocreep", function()
            if not unit:IsNull() then UTIL_Remove(unit) end
            return nil
        end, 0.03)
        return
    end

    if not unit:IsRealHero() then return end

    self:CheckFirstSpawn(unit)

    local pid = unit:GetPlayerOwnerID()
    local p = self.csPlayers[pid]
    if not p or not p.diedOnce then return end

    -- respawn: knife + start pistol, armor and grenades are gone, bought HP stays
    p.weapons.primary = nil
    p.ammo.primary = 0
    p.weapons.secondary = nil
    p.weapons.taser = nil
    p.grenades = {}
    p.grenadeType = nil
    p.bhop = 0
    p.jumpEnd = nil
    p.landTime = nil
    p.slot = "knife"
    self:GiveWeapon(pid, CS_START_PISTOL)

    local mod = unit:FindModifierByName("modifier_cs_player")
    if mod then mod:SetTargetHP(p.maxHP) end

    PlayerResource:SetCameraTarget(pid, unit)
end

------------------------------------------------------------
-- Input from UI
------------------------------------------------------------
function CDotaCS:OnKey(data)
    local p = self.csPlayers[data.PlayerID]
    if not p then return end
    p.keys[data.key] = (data.down == 1)
end

function CDotaCS:OnFire(data)
    local p = self.csPlayers[data.PlayerID]
    if not p then return end

    if data.x then
        p.aim = Vector(data.x, data.y, data.z or 0)
    end

    if data.down == 1 then
        if not p.firing then
            p.shotQueued = true
        end
        p.firing = true
    elseif data.down == 0 then
        p.firing = false
    end
end

function CDotaCS:OnReloadKey(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    if p then self:StartReload(pid, p) end
end

------------------------------------------------------------
-- Jump and bunnyhop
------------------------------------------------------------
function CDotaCS:OnJump(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    local hero = PlayerResource:GetSelectedHeroEntity(pid)
    if not p or not hero or not hero:IsAlive() then return end
    if hero:IsStunned() or hero:IsRooted() then return end

    local now = GameRules:GetGameTime()
    if p.jumpEnd then return end -- already in the air

    -- jumped right after landing while moving: keep and add speed
    if p.landTime and (now - p.landTime) <= CS_BHOP_WINDOW and p.running then
        p.bhop = math.min(p.bhop + 1, CS_BHOP_MAX)
    else
        p.bhop = 0
    end

    p.jumpEnd = now + CS_JUMP_TIME
    p.landTime = nil
    hero:AddNewModifier(hero, nil, "modifier_cs_jump", { duration = CS_JUMP_TIME })
end

function CDotaCS:JumpTick(p, now)
    if p.jumpEnd and now >= p.jumpEnd then
        p.jumpEnd = nil
        p.landTime = now
    end

    -- stayed on the ground too long, or stopped moving: lose bhop speed
    if not p.jumpEnd and p.bhop > 0 then
        if not p.running or (p.landTime and now - p.landTime > CS_BHOP_WINDOW) then
            p.bhop = 0
        end
    end
end

function CDotaCS:UpdateSpeed(p, hero)
    local _, w = self:CurrentWeapon(p)
    local csSpeed = (w and w.speed) or 250
    local speed = math.floor(csSpeed * CS_SPEED_SCALE * (1 + p.bhop * CS_BHOP_STEP))
    if speed ~= p.speed then
        p.speed = speed
        local mod = hero:FindModifierByName("modifier_cs_speed")
        if mod then mod:SetStackCount(speed) end
    end
end

------------------------------------------------------------
-- Main loop
------------------------------------------------------------
function CDotaCS:Think()
    local now = GameRules:GetGameTime()
    for pid, p in pairs(self.csPlayers) do
        local hero = PlayerResource:GetSelectedHeroEntity(pid)
        if hero and hero:IsAlive() then
            self:MoveTick(p, hero)
            self:JumpTick(p, now)
            self:UpdateSpeed(p, hero)
            self:FireTick(pid, p, hero)
            self:NearDropTick(pid, p, hero)
        end
    end
    self:DropsTick(now)
    return CS_TICK
end

function CDotaCS:MoveTick(p, hero)
    local dx, dy = 0, 0
    if p.keys.W then dy = dy + 1 end
    if p.keys.S then dy = dy - 1 end
    if p.keys.D then dx = dx + 1 end
    if p.keys.A then dx = dx - 1 end

    if dx ~= 0 or dy ~= 0 then
        local dir = Vector(dx, dy, 0):Normalized()
        hero:MoveToPosition(hero:GetAbsOrigin() + dir * CS_MOVE_LOOKAHEAD)
        p.running = true
    elseif p.running then
        hero:Stop()
        p.running = false
    end
end

-- tell the UI which gun is close enough to pick up with E
function CDotaCS:NearDropTick(pid, p, hero)
    local pos = hero:GetAbsOrigin()
    local name = ""
    local bestDist = CS_SWAP_RADIUS
    for container, drop in pairs(self.drops) do
        if not container:IsNull() then
            local d = (container:GetAbsOrigin() - pos):Length2D()
            if d < bestDist then
                bestDist = d
                local w = CS_WEAPONS[drop.item.csWeapon]
                name = w and w.name or ""
            end
        end
    end
    if name ~= p.nearDrop then
        p.nearDrop = name
        self:SendHud(pid)
    end
end

function CDotaCS:FireTick(pid, p, hero)
    local _, w = self:CurrentWeapon(p)
    if not w then return end
    local now = GameRules:GetGameTime()

    if p.reloadEnd and now >= p.reloadEnd then
        p.reloadEnd = nil
        p.ammo[p.slot] = w.mag
        self:SendHud(pid)
    end

    if not p.firing then
        p.recoil = math.max(0, p.recoil - 0.3)
    end

    local wantShot = p.firing and (w.auto or p.shotQueued)
    if not wantShot then return end
    if p.reloadEnd then return end
    if now < p.nextShot then return end
    if hero:IsStunned() or hero:IsHexed() then return end

    p.shotQueued = false
    p.nextShot = now + w.rate

    if w.grenade then
        self:ThrowGrenade(pid, p, hero)
        return
    end

    if not w.melee then
        if p.ammo[p.slot] <= 0 then
            p.nextShot = now
            self:StartReload(pid, p)
            return
        end
        p.ammo[p.slot] = p.ammo[p.slot] - 1
    end

    self:Shoot(pid, p, hero, w)

    -- Zeus is gone after one shot
    if w.taser then
        p.weapons.taser = nil
        self:SwitchSlot(pid, "knife")
    end

    self:SendHud(pid)
end

function CDotaCS:StartReload(pid, p)
    local _, w = self:CurrentWeapon(p)
    if not w or w.melee or w.grenade or w.taser or p.reloadEnd then return end
    if p.ammo[p.slot] >= w.mag then return end
    p.reloadEnd = GameRules:GetGameTime() + w.reload
    self:SendHud(pid)
end

function CDotaCS:Shoot(pid, p, hero, w)
    local origin = hero:GetAbsOrigin()
    local aim = p.aim or (origin + hero:GetForwardVector() * 100)

    local baseDir = aim - origin
    baseDir.z = 0
    if baseDir:Length2D() < 1 then baseDir = hero:GetForwardVector() end
    baseDir = baseDir:Normalized()

    hero:SetForwardVector(baseDir)
    hero:StartGestureWithPlaybackRate(ACT_DOTA_ATTACK, 4)

    if w.melee then
        self:FireBullet(pid, hero, origin, baseDir, w, 90, false)
        return
    end

    local spread = w.spread + p.recoil * w.recoil
    if p.running then spread = spread + w.move_spread end
    if p.jumpEnd then spread = spread + w.move_spread * 2 end -- shooting in the air is bad, like in CS

    p.recoil = math.min(p.recoil + 1, 10)
    EmitSoundOn(w.taser and CS_ZEUS_SOUND or CS_SHOT_SOUND, hero)

    for _ = 1, (w.pellets or 1) do
        local angle = RandomFloat(-spread, spread)
        local dir = RotatePosition(Vector(0, 0, 0), QAngle(0, angle, 0), baseDir)
        self:FireBullet(pid, hero, origin, dir, w, 40, true)
    end
end

function CDotaCS:FireBullet(pid, hero, origin, dir, w, width, tracer)
    local endPos = origin + dir * w.range
    local units = FindUnitsInLine(
        hero:GetTeamNumber(), origin, endPos, nil, width,
        DOTA_UNIT_TARGET_TEAM_ENEMY,
        DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC + DOTA_UNIT_TARGET_BUILDING,
        DOTA_UNIT_TARGET_FLAG_NONE
    )

    local target, best = nil, math.huge
    for _, u in pairs(units) do
        local d = (u:GetAbsOrigin() - origin):Length2D()
        if d < best then
            best = d
            target = u
        end
    end

    if target then
        endPos = target:GetAbsOrigin()
        self:DealDamage(hero, pid, target, w.damage, w.name)
    end

    if tracer then
        local fx = ParticleManager:CreateParticle(CS_TRACER, PATTACH_CUSTOMORIGIN, hero)
        ParticleManager:SetParticleControl(fx, 0, origin + Vector(0, 0, 80))
        ParticleManager:SetParticleControl(fx, 1, endPos + Vector(0, 0, 80))
        ParticleManager:ReleaseParticleIndex(fx)
    end
end

-- all CS damage goes through here, so the kill feed knows the weapon
function CDotaCS:DealDamage(attacker, attackerPid, victim, damage, weaponName)
    self.lastHit[victim:entindex()] = { weapon = weaponName, time = GameRules:GetGameTime() }
    ApplyDamage({
        victim = victim,
        attacker = attacker,
        damage = damage,
        damage_type = DAMAGE_TYPE_PHYSICAL,
    })
end

------------------------------------------------------------
-- Order filter
------------------------------------------------------------
function CDotaCS:OrderFilter(event)
    local t = event.order_type

    -- nobody picks up CS guns with Dota clicks
    if t == DOTA_UNIT_ORDER_PICKUP_ITEM and self:IsDropOrder(event) then
        return false
    end

    local pid = event.issuer_player_id_const
    if pid and self.csPlayers[pid] then
        if t == DOTA_UNIT_ORDER_MOVE_TO_POSITION
            or t == DOTA_UNIT_ORDER_MOVE_TO_TARGET
            or t == DOTA_UNIT_ORDER_MOVE_TO_DIRECTION
            or t == DOTA_UNIT_ORDER_ATTACK_TARGET
            or t == DOTA_UNIT_ORDER_ATTACK_MOVE
            or t == DOTA_UNIT_ORDER_PURCHASE_ITEM
            or t == DOTA_UNIT_ORDER_PICKUP_ITEM then
            return false
        end
    end
    return true
end

------------------------------------------------------------
-- Money and HUD
------------------------------------------------------------
function CDotaCS:AddMoney(pid, amount)
    local p = self.csPlayers[pid]
    if not p then return end
    p.money = p.money + amount
    self:SendHud(pid)
end

function CDotaCS:SendHud(pid)
    local p = self.csPlayers[pid]
    local player = PlayerResource:GetPlayer(pid)
    if not p or not player then return end
    local _, w = self:CurrentWeapon(p)
    w = w or {}

    local function nameOf(id)
        local item = CS_GetItem(id)
        return item and item.name or ""
    end

    local grenades = {}
    for i, id in ipairs(CS_GRENADE_ORDER) do
        local n = p.grenades[id] or 0
        if n > 0 then
            table.insert(grenades, CS_GRENADES[id].name .. (n > 1 and (" x" .. n) or ""))
        end
    end

    local hero = PlayerResource:GetSelectedHeroEntity(pid)
    local armorMod = hero and hero:FindModifierByName("modifier_cs_armor")

    CustomGameEventManager:Send_ServerToPlayer(player, "cs_hud", {
        weapon = w.name or "",
        noammo = (w.melee or w.grenade) and 1 or 0,
        ammo = p.ammo[p.slot] or 0,
        mag = w.mag or 0,
        money = p.money,
        reloading = p.reloadEnd and 1 or 0,
        slot = p.slot,
        primary = nameOf(p.weapons.primary),
        secondary = nameOf(p.weapons.secondary),
        taser = nameOf(p.weapons.taser),
        grenades = table.concat(grenades, ", "),
        armor = armorMod and armorMod:GetStackCount() or 0,
        nearDrop = p.nearDrop or "",
    })
end

------------------------------------------------------------
-- Kills: money, death drop, kill feed
------------------------------------------------------------
function CDotaCS:OnEntityKilled(keys)
    local killed = EntIndexToHScript(keys.entindex_killed)
    if not killed then return end
    local attacker = keys.entindex_attacker and EntIndexToHScript(keys.entindex_attacker)

    if killed:IsRealHero() then
        local kpid = killed:GetPlayerOwnerID()
        local kp = self.csPlayers[kpid]
        if kp then
            -- drop the best gun, like in CS
            local dropSlot = kp.weapons.primary and "primary" or (kp.weapons.secondary and "secondary")
            if dropSlot then
                self:DropWeapon(kpid, dropSlot, killed:GetAbsOrigin())
            end
            kp.diedOnce = true
            kp.firing = false
            kp.keys = {}
            kp.bhop = 0
            kp.jumpEnd = nil
            kp.reloadEnd = nil
            self:SendHud(kpid)
        end
        self:SendKillFeed(killed, attacker)
    elseif killed.csSlot then
        -- a CS2 player (shown in Dota) was killed by a Dota hero
        self:SendKillFeed(killed, attacker)
    end

    if not attacker or not attacker.GetPlayerOwnerID then return end
    local pid = attacker:GetPlayerOwnerID()
    if pid == nil or pid < 0 or not self.csPlayers[pid] then return end
    if attacker:GetTeamNumber() == killed:GetTeamNumber() then return end

    if killed:IsRealHero() then
        self:AddMoney(pid, CS_REWARD_HERO)
    elseif killed:IsCreep() then
        self:AddMoney(pid, CS_REWARD_CREEP)
    end
end

function CDotaCS:SendKillFeed(killed, attacker)
    local function info(unit)
        if not unit or unit:IsNull() then return "", "", 0 end
        if unit.csSlot then
            return unit.csName or ("КС2 игрок " .. unit.csSlot), "cs", unit:GetTeamNumber()
        end
        local pid = unit.GetPlayerOwnerID and unit:GetPlayerOwnerID() or -1
        local name = (pid and pid >= 0) and PlayerResource:GetPlayerName(pid) or ""
        local unitName = unit:GetUnitName()
        if self.csPlayers[pid] then unitName = "cs" end
        return name, unitName, unit:GetTeamNumber()
    end

    local vName, vUnit, vTeam = info(killed)
    local kName, kUnit, kTeam = info(attacker)

    local weapon = ""
    local hit = self.lastHit[killed:entindex()]
    if hit and GameRules:GetGameTime() - hit.time < 0.5 then
        weapon = hit.weapon
    end

    CustomGameEventManager:Send_ServerToAllClients("cs_killfeed", {
        killer = kName, killerUnit = kUnit, killerTeam = kTeam,
        victim = vName, victimUnit = vUnit, victimTeam = vTeam,
        weapon = weapon,
    })
end

function CDotaCS:Msg(text)
    GameRules:SendCustomMessage("[DotaCS] " .. text, 0, 0)
end
