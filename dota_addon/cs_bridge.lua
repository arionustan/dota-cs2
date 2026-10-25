-- DotaCS bridge, Dota side.
--
-- 20 times a second Dota sends to the bridge on this PC:
--   H heroId x y z fx fy hp maxhp alive name   every Dota hero (in CS2 coordinates)
--   C T slot x y     a CS player was pushed/hooked in Dota: move him in CS2
--   C S slot sec     a CS player is stunned/rooted in Dota: freeze him in CS2
--   C K slot dmg killer   a CS player took damage in Dota: damage him in CS2
--   C H slot heroId  a CS player is being pulled by a meat hook: draw the chain in CS2
--   E K hero killer weapon   a CS player killed a Dota hero (score + kill message in CS2)
-- and gets back:
--   P slot x y z fx fy isBot hp name           every alive CS2 player
--   D heroId damage attackerSlot weapon        a CS2 player shot a Dota hero
--
-- CS2 players are "npc_cs_proxy" units on the enemy team. Their position and HP come
-- from CS2, except while a Dota effect (stun, hook, push) controls them.

CS_BRIDGE_URL = "http://127.0.0.1:3000/dota"
CS_BRIDGE_TICK = 0.05

-- CS2 coordinates -> Dota coordinates: dota = cs * SCALE + OFFSET
CS_BRIDGE_SCALE = 1.0 -- CS2 runs on the real Dota map, 1:1
CS_BRIDGE_SEND_Z = true
CS_BRIDGE_OFFSET = Vector(0, 0, 0)

-- balance: a CS player has 100 HP, a Dota hero 600-3000, so bullets hit harder and spells softer
CS_BRIDGE_DAMAGE_TO_DOTA = 1.5   -- CS bullet damage -> Dota hero damage
CS_BRIDGE_DAMAGE_TO_CS = 0.35    -- Dota damage -> CS player damage
CS_BRIDGE_MAX_HIT_TO_CS = 60     -- one Dota hit never takes more than this from a CS player
CS_BRIDGE_KILL_CREDIT_TIME = 1.5 -- a CS player who dies this soon after a Dota hit counts as a Dota kill

local function ToDota(x, y)
    return Vector(x, y, 0) * CS_BRIDGE_SCALE + CS_BRIDGE_OFFSET
end

local function ToCS(pos)
    local v = (pos - CS_BRIDGE_OFFSET) * (1 / CS_BRIDGE_SCALE)
    return v.x, v.y
end

------------------------------------------------------------
-- Start / stop
------------------------------------------------------------
-- start automatically when the game loads (quiet until it connects)
function CDotaCS:BridgeAutoStart()
    GameRules:GetGameModeEntity():SetContextThink("cs_bridge_auto", function()
        if not self.bridge then self:BridgeToggle(0, true) end
        return nil
    end, 3)
    -- custom games don't always spawn Roshan and the Tormentors: make sure they exist
    GameRules:GetGameModeEntity():SetContextThink("cs_bosses", function()
        if GameRules:State_Get() < DOTA_GAMERULES_STATE_GAME_IN_PROGRESS then return 2 end
        self:BridgeEnsureBoss("npc_dota_roshan", Vector(2831, -2740, 64))
        self:BridgeEnsureBoss("npc_dota_miniboss", Vector(-7680, 6336, 128))
        self:BridgeEnsureBoss("npc_dota_miniboss", Vector(7616, -6464, 128))
        return 30
    end, 5)
end

-- spawn a boss at pos unless one of that kind is already alive near it (Roshan anywhere)
function CDotaCS:BridgeEnsureBoss(name, pos)
    local radius = (name == "npc_dota_roshan") and 30000 or 1500
    for _, u in ipairs(FindUnitsInRadius(DOTA_TEAM_NEUTRALS, pos, nil, radius, DOTA_UNIT_TARGET_TEAM_BOTH,
        DOTA_UNIT_TARGET_ALL, DOTA_UNIT_TARGET_FLAG_INVULNERABLE + DOTA_UNIT_TARGET_FLAG_DEAD, FIND_ANY_ORDER, false)) do
        if u:GetUnitName() == name then
            -- seen alive: from now on a dead boss waits for its respawn time
            self.bossSeen = self.bossSeen or {}
            self.bossSeen[name .. math.floor(pos.x)] = true
            return
        end
    end
    self.bossRespawn = self.bossRespawn or {}
    local key = name .. math.floor(pos.x)
    local now = GameRules:GetGameTime()
    if not self.bossRespawn[key] then self.bossRespawn[key] = now + (self.bossSeen and self.bossSeen[key] and 660 or 0) end
    if now < self.bossRespawn[key] then return end
    self.bossRespawn[key] = nil
    self.bossSeen = self.bossSeen or {}
    self.bossSeen[key] = true
    pcall(CreateUnitByName, name, pos, true, nil, nil, DOTA_TEAM_NEUTRALS)
end

-- CS player's level, K/D and HP in Dota: name label and how much he is worth when killed
function CDotaCS:BridgeProxyStats(unit, name, lvl, kills, deaths, maxhp)
    local label = string.format("%s  ур.%d  %d/%d", name:gsub("_", " "), lvl, kills, deaths)
    if unit.csLabel ~= label then
        unit.csLabel = label
        if not name:find("^WC3_") then unit:SetCustomHealthLabel(label, 110, 170, 255) end
    end
    if maxhp and maxhp > 0 and unit:GetMaxHealth() ~= maxhp then
        unit:SetBaseMaxHealth(maxhp); unit:SetMaxHealth(maxhp)
    end
    if unit.csLevel ~= lvl then
        unit.csLevel = lvl
        unit:SetDeathXP(100 + lvl * 40)
        unit:SetMinimumGoldBounty(200 + lvl * 20); unit:SetMaximumGoldBounty(200 + lvl * 20)
    end
end

-- Dota chat -> CS chat (E M name text)
function CDotaCS:BridgeChat(pid, text)
    if not self.bridge or not text or text == "" or text:sub(1, 1) == "-" then return end
    local name = (PlayerResource:GetPlayerName(pid) or "dota"):gsub("%s", "_")
    if name == "" then name = "dota" end
    table.insert(self.bridge.outbox, "E M " .. name .. " " .. text:gsub("[\r\n]", " "))
end

function CDotaCS:BridgeToggle(pid, auto)
    if self.bridge then
        self.bridge.running = false
        for _, unit in pairs(self.bridge.proxies or {}) do
            if unit and not unit:IsNull() then UTIL_Remove(unit) end
        end
        self.bridge = nil
        self:Msg("Мост выключен")
        return
    end

    if not CreateHTTPRequestScriptVM then
        if not auto then
            self:Msg("ОШИБКА: в этой версии Доты скрипты не могут делать HTTP-запросы")
        end
        return
    end

    self.bridge = {
        pid = pid, running = true, busy = false, ok = 0, fail = 0, auto = auto,
        proxies = {},   -- [slot] = unit
        outbox = {},    -- C lines waiting to be sent
        waitingMsg = false,
    }
    if not auto then
        self:Msg("Мост: подключаюсь к " .. CS_BRIDGE_URL)
    end

    local bridge = self.bridge
    self:BridgeListenSounds()
    GameRules:GetGameModeEntity():SetContextThink("cs_bridge", function()
        if not bridge.running then return nil end
        self:BridgeTick(bridge)
        -- while the bridge isn't answering, check only once a second
        if bridge.ok == 0 or bridge.lastFailed then return 1.0 end
        return CS_BRIDGE_TICK
    end, 0)
end

-- "Тест моста" button in settings
function CDotaCS:OnBridgeButton(data)
    self:BridgeToggle(data.PlayerID)
end

------------------------------------------------------------
-- Sending
------------------------------------------------------------
function CDotaCS:BridgeHeroLines()
    local lines = {}
    for _, hero in pairs(HeroList:GetAllHeroes()) do
        local pid = hero:GetPlayerOwnerID()
        if hero:IsRealHero() and not hero:IsIllusion() and not (pid and self.csPlayers[pid]) then
            local x, y = ToCS(hero:GetAbsOrigin())
            local z = CS_BRIDGE_SEND_Z and hero:GetAbsOrigin().z or 0
            local f = hero:GetForwardVector()
            local name = hero:GetUnitName():gsub("npc_dota_hero_", "")
            -- what the hero is doing right now, so CS2 plays the matching animation
            local act = "-"
            local ab = hero:GetCurrentActiveAbility()
            if ab and not ab:IsNull() then
                local an = ab:GetAbilityName()
                act = (an == "pudge_meat_hook") and "hook" or (an == "pudge_dismember") and "ult"
                    or (ab:GetAbilityType() == DOTA_ABILITY_TYPE_ULTIMATE) and "ult" or "cast"
            elseif hero:IsStunned() then
                act = "stun"
            elseif hero:IsAttacking() then
                act = "attack"
            end
            -- visible effects on the hero (Rot cloud...)
            local fx = hero:HasModifier("modifier_pudge_rot") and "rot" or "-"
            table.insert(lines, string.format("H %d %.1f %.1f %.1f %.3f %.3f %d %d %d %s %s %s %d %d %d %d %d",
                hero:entindex(), x, y, z, f.x, f.y,
                hero:GetHealth(), hero:GetMaxHealth(), hero:IsAlive() and 1 or 0, name, act, fx,
                self:BridgeVisibleToCS(hero) and 1 or 0,
                hero:GetKills(), hero:GetDeaths(), hero:GetAssists(), hero:GetLevel()))
        end
    end
    return lines
end

-- fog of war: can the CS team (enemies of the Dota player) see this unit right now?
function CDotaCS:BridgeVisibleToCS(unit)
    local bridge = self.bridge
    if not bridge then return true end
    local csTeam = self:BridgeEnemyTeam(bridge)
    if unit:GetTeamNumber() == csTeam then return true end
    if unit:IsInvisible() and not unit:HasModifier("modifier_truesight") then return false end
    return IsLocationVisible(csTeam, unit:GetAbsOrigin())
end

function CDotaCS:BridgeTick(bridge)
    if bridge.busy then return end

    local lines = self:BridgeHeroLines()
    for _, l in ipairs(self:BridgeUnitLines(bridge)) do table.insert(lines, l) end
    table.insert(lines, GameRules:IsDaytime() and "N 0" or "N 1")   -- day/night for CS2
    bridge.buildTick = ((bridge.buildTick or 0) + 1) % 10
    if bridge.buildTick == 0 then
        for _, l in ipairs(self:BridgeBuildingLines()) do table.insert(lines, l) end
    end
    bridge.soundCount = 0
    for _, c in ipairs(bridge.outbox) do table.insert(lines, c) end
    local sentOutbox = #bridge.outbox

    local ok, req = pcall(CreateHTTPRequestScriptVM, "POST", CS_BRIDGE_URL)
    if not ok or not req then
        self:Msg("ОШИБКА: не удалось создать запрос: " .. tostring(req))
        bridge.running = false
        return
    end

    req:SetHTTPRequestRawPostBody("text/plain", #lines > 0 and table.concat(lines, "\n") or "none")
    bridge.busy = true
    req:Send(function(result)
        bridge.busy = false
        if not bridge.running then return end
        if result and result.StatusCode == 200 then
            -- commands reached the bridge, drop them from the outbox
            for _ = 1, sentOutbox do table.remove(bridge.outbox, 1) end
        end
        self:BridgeResult(bridge, result)
    end)
end

------------------------------------------------------------
-- Receiving
------------------------------------------------------------
function CDotaCS:BridgeResult(bridge, result)
    local code = result and result.StatusCode or 0
    if code ~= 200 then
        bridge.fail = bridge.fail + 1
        bridge.lastFailed = true
        if not bridge.auto and (bridge.fail == 1 or bridge.fail % 40 == 0) then
            self:Msg("Мост не отвечает (код " .. tostring(code) .. "). Запущен ли bridge.py?")
        end
        return
    end

    bridge.lastFailed = false
    bridge.ok = bridge.ok + 1
    if bridge.ok == 1 then
        self:Msg("Мост подключен! Дота общается с компьютером.")
    end

    local seen = {}
    local count = 0
    for line in (result.Body or ""):gmatch("[^\r\n]+") do
        local kind = line:sub(1, 2)
        if kind == "P " then
            local slot, x, y, z, fx, fy, bot, hp, name = line:match(
                "^P (%d+) (%-?[%d%.]+) (%-?[%d%.]+) (%-?[%d%.]+) (%-?[%d%.]+) (%-?[%d%.]+) (%d) (%-?%d+) ?(%S*)")
            if slot then
                count = count + 1
                seen[slot] = true
                self:BridgeUpdateProxy(bridge, slot, tonumber(x), tonumber(y), tonumber(fx), tonumber(fy), tonumber(hp), name)
                -- level, kills, deaths, max HP of the CS player (newer plugin)
                local lvl, k, d, mhp = line:match(" (%d+) (%d+) (%d+) (%d+)$")
                local unit = bridge.proxies[slot]
                if lvl and unit and not unit:IsNull() and name and name ~= "" then
                    self:BridgeProxyStats(unit, name, tonumber(lvl), tonumber(k), tonumber(d), tonumber(mhp))
                end
            end
        elseif kind == "M " then
            -- CS chat -> Dota chat
            local who, text = line:match("^M (%S+) (.+)$")
            if who then GameRules:SendCustomMessage("<font color='#5ab4ff'>[КС] " .. who:gsub("_", " ") .. ":</font> " .. text, 0, 0) end
        elseif kind == "T " then
            -- a CS grenade went off: knock down trees around it
            local x, y, z, r = line:match("^T (%-?[%d%.]+) (%-?[%d%.]+) (%-?[%d%.]+) (%d+)")
            if x then GridNav:DestroyTreesAroundPoint(ToDota(tonumber(x), tonumber(y)), tonumber(r), true) end
        elseif kind == "G " then
            local gk, gx, gy, gz, gslot = line:match("^G (%a+) (%-?[%d%.]+) (%-?[%d%.]+) (%-?[%d%.]+) (%-?%d+)")
            if gk then self:BridgeGrenade(bridge, gk, tonumber(gx), tonumber(gy), tonumber(gz), gslot) end
        elseif kind == "D " then
            local heroId, dmg, attackerSlot, weapon = line:match("^D (%d+) (%-?[%d%.]+) (%d+) ?(%S*)")
            if heroId then
                self:BridgeHeroHit(bridge, tonumber(heroId), tonumber(dmg), attackerSlot, weapon)
            end
        end
    end

    -- CS players that died or left
    for slot, unit in pairs(bridge.proxies) do
        if not seen[slot] then
            self:BridgeRemoveProxy(bridge, slot, unit)
        end
    end

    if count == 0 then
        if not bridge.waitingMsg then
            bridge.waitingMsg = true
            self:Msg("Мост работает, жду игроков из КС2 или Warcraft III.")
        end
    else
        bridge.waitingMsg = false
    end
end

------------------------------------------------------------
-- CS players in Dota
------------------------------------------------------------
function CDotaCS:BridgeEnemyTeam(bridge)
    local hero = PlayerResource:GetSelectedHeroEntity(bridge.pid)
    local team = hero and hero:GetTeamNumber() or DOTA_TEAM_GOODGUYS
    return (team == DOTA_TEAM_GOODGUYS) and DOTA_TEAM_BADGUYS or DOTA_TEAM_GOODGUYS
end

function CDotaCS:BridgeUpdateProxy(bridge, slot, x, y, fx, fy, hp, name)
    local unit = bridge.proxies[slot]
    local target = ToDota(x, y)

    if not unit or unit:IsNull() then
        -- a hero coming from Warcraft III gets its WC3 model, CS2 players stay "npc_cs_proxy"
        local unitName = (name and name:find("^WC3_")) and "npc_wc3_blademaster" or "npc_cs_proxy"
        unit = CreateUnitByName(unitName, target, true, nil, nil, self:BridgeEnemyTeam(bridge))
        if not unit then return end
        unit.csSlot = slot
        unit:SetIdleAcquire(false)
        unit:AddNewModifier(unit, nil, "modifier_cs_proxy", {})
        bridge.proxies[slot] = unit
        if unitName == "npc_wc3_blademaster" then
            self:Msg("Мастер клинка из Warcraft III появился в Доте. Его можно бить скиллами!")
        else
            self:Msg("Ксник из КС2 появился в Доте. Его можно бить скиллами!")
        end
    end

    if name and name ~= "" and unit.csName ~= name then
        unit.csName = name
        if not name:find("^WC3_") then unit:SetCustomHealthLabel(name, 110, 170, 255) end
    end

    -- HP comes from CS2
    if hp and hp > unit:GetMaxHealth() then
        unit:SetBaseMaxHealth(hp); unit:SetMaxHealth(hp)
    end
    if hp and hp > 0 then
        unit:SetHealth(math.min(hp, unit:GetMaxHealth()))
    end

    -- while a Dota effect controls the unit, Dota is in charge of its position
    local stunned = unit:IsStunned() or unit:IsRooted()
    local pushed = unit:IsCurrentlyHorizontalMotionControlled() or unit:IsCurrentlyVerticalMotionControlled()

    if stunned then
        self:BridgeCommand(bridge, string.format("C S %s 0.25", slot))
    end

    -- slows (rot, frost...): scale the CS player's speed the same way
    local base = unit:GetBaseMoveSpeed()
    local mult = (base and base > 0) and math.min(unit:GetIdealSpeed() / base, 1) or 1
    if mult < 0.97 or unit.csSlowed then
        self:BridgeCommand(bridge, string.format("C V %s %.2f", slot, mult))
        unit.csSlowed = mult < 0.97
    end

    if pushed then
        -- Pudge's hook: draw the chain in CS2 too
        local hook = unit:FindModifierByName("modifier_pudge_meat_hook")
        local caster = hook and hook:GetCaster()
        if caster and not caster:IsNull() then
            if not unit.csHooked then self:BridgeSound("Hero_Pudge.AttackHookImpact", unit:GetAbsOrigin()) end
            unit.csHooked = true
            self:BridgeCommand(bridge, string.format("C H %s %d", slot, caster:entindex()))
        end
        local cx, cy = ToCS(unit:GetAbsOrigin())
        local cz = GetGroundPosition(unit:GetAbsOrigin(), unit).z
        if not hook then unit.csHooked = nil end
        self:BridgeCommand(bridge, string.format("C T %s %.1f %.1f %.1f", slot, cx, cy, cz))
        return
    end

    -- CS2 sends a position ~10 times a second; the unit glides towards it every frame (see BridgeSmooth)
    local goal = GetGroundPosition(target, unit)
    local now = GameRules:GetGameTime()
    if unit.csGoal then
        local dt = now - (unit.csGoalTime or now)
        local step = goal - unit.csGoal
        step.z = 0
        if dt > 0.02 then
            local v = step / dt
            if v:Length2D() > 600 then v = Vector(0, 0, 0) end       -- respawn / teleport
            unit.csVel = (unit.csVel or Vector(0, 0, 0)) * 0.4 + v * 0.6
        end
    end
    unit.csGoal = goal
    unit.csGoalTime = now
    local dir = Vector(fx, fy, 0)
    if dir:Length2D() > 0.1 then unit.csFace = dir:Normalized() end
    if not unit.csSmoothing then
        unit.csSmoothing = true
        unit:SetAbsOrigin(goal)
        unit:SetContextThink("cs_smooth", function() return self:BridgeSmooth(unit) end, 0)
    end
end

-- every frame: move the CS player towards where CS2 says he is (with a little prediction),
-- so he walks smoothly instead of jumping 10 times a second
function CDotaCS:BridgeSmooth(unit)
    if not unit or unit:IsNull() then return nil end
    local DT = 0.03
    if not unit.csGoal or unit:IsCurrentlyHorizontalMotionControlled() or unit:IsCurrentlyVerticalMotionControlled() then
        return DT
    end
    local now = GameRules:GetGameTime()
    local age = now - (unit.csGoalTime or now)
    local vel = unit.csVel or Vector(0, 0, 0)
    if age > 0.3 then vel = Vector(0, 0, 0) end                    -- no news: he stopped
    local pred = unit.csGoal + vel * math.min(age, 0.15)
    local cur = unit:GetAbsOrigin()
    local d = pred - cur
    d.z = 0
    local pos
    if d:Length2D() > 450 then
        pos = pred
    else
        pos = cur + d * math.min(1, DT * 12)
    end
    unit:SetAbsOrigin(GetGroundPosition(pos, unit))
    -- turn smoothly
    if unit.csFace then
        local f = unit:GetForwardVector()
        local nf = f + (unit.csFace - f) * 0.35
        nf.z = 0
        if nf:Length2D() > 0.01 then
            nf = nf:Normalized()
            unit:SetForwardVector(nf)
            -- Dota turns a unit back to its own "ideal" facing; FaceTowards moves that ideal facing too
            unit:FaceTowards(unit:GetAbsOrigin() + unit.csFace * 200)
        end
    end
    -- run animation with hysteresis, playback speed follows the real speed
    local speed = vel:Length2D()
    if speed > 60 and not unit.csRun then
        unit:StartGestureWithPlaybackRate(ACT_DOTA_RUN, math.max(0.6, math.min(speed / 300, 1.6)))
        unit.csRun = true
    elseif speed < 20 and unit.csRun then
        unit:RemoveGesture(ACT_DOTA_RUN)
        unit.csRun = false
    end
    return DT
end

-- queue a command for CS2; only the newest freeze/teleport per player is kept, damage always adds up
function CDotaCS:BridgeCommand(bridge, line)
    local kind, slot = line:match("^C (%a) (%d+)")
    if kind and kind ~= "K" then
        for i, c in ipairs(bridge.outbox) do
            local k2, s2 = c:match("^C (%a) (%d+)")
            if k2 == kind and s2 == slot then
                bridge.outbox[i] = line
                return
            end
        end
    end
    table.insert(bridge.outbox, line)
end

-- a Dota hero or creep damaged a CS player
function CDotaCS:OnProxyDamaged(unit, attacker, damage)
    local bridge = self.bridge
    if not bridge or not unit.csSlot or damage <= 0 then return end
    unit.lastHitBy = attacker
    unit.lastHitTime = GameRules:GetGameTime()
    -- towers, fountain, creeps, Roshan: show the shot in CS2
    if attacker and not attacker:IsNull() and attacker.IsHero and not attacker:IsHero() then
        local p = attacker:GetAbsOrigin()
        local ax, ay = ToCS(p)
        self:BridgeCommand(bridge, string.format("C R %s %.0f %.0f %.0f", unit.csSlot, ax, ay, p.z))
    end
    local dmg = math.min(damage * CS_BRIDGE_DAMAGE_TO_CS, CS_BRIDGE_MAX_HIT_TO_CS)
    local who = "dota"
    if attacker and not attacker:IsNull() and attacker.GetUnitName then
        who = attacker:GetUnitName():gsub("npc_dota_hero_", ""):gsub("npc_dota_", "")
    end
    self:BridgeCommand(bridge, string.format("C K %s %.0f %s", unit.csSlot, math.max(dmg, 1), who))
end

function CDotaCS:BridgeRemoveProxy(bridge, slot, unit)
    bridge.proxies[slot] = nil
    if not unit or unit:IsNull() then return end

    local recent = unit.lastHitTime and (GameRules:GetGameTime() - unit.lastHitTime) < CS_BRIDGE_KILL_CREDIT_TIME
    local killer = unit.lastHitBy
    if recent and killer and not killer:IsNull() and unit:IsAlive() then
        -- died in CS2 right after a Dota hit: a real Dota kill (gold, kill feed)
        local mod = unit:FindModifierByName("modifier_cs_proxy")
        if mod then mod.allowDeath = true end
        unit:Kill(nil, killer)
    elseif unit:IsAlive() then
        -- died in CS2 for another reason: play the death animation, no bounty
        local mod = unit:FindModifierByName("modifier_cs_proxy")
        if mod then mod.allowDeath = true end
        unit:ForceKill(false)
    else
        UTIL_Remove(unit)
    end
end

------------------------------------------------------------
-- CS2 grenades in Dota: HE and molotov (x4 damage), flash blinds heroes, smoke = 15 s invisibility
------------------------------------------------------------
function CDotaCS:BridgeGrenade(bridge, kind, x, y, z, slot)
    local owner = bridge.proxies[slot]
    if not owner or owner:IsNull() then
        -- thrower not in Dota (dead or not spawned yet): use any CS player, effects still happen
        for _, p in pairs(bridge.proxies) do if p and not p:IsNull() then owner = p break end end
    end
    if not owner then return end
    local pos = GetGroundPosition(ToDota(x, y), nil)
    local team = owner:GetTeamNumber()
    if kind == "he" then
        self:GrenadeHE(owner, -1, pos, CS_GRENADES.he, true)
    elseif kind == "flash" then
        self:GrenadeFlash(owner, pos, CS_GRENADES.flash)
    elseif kind == "fire" then
        local g = CS_GRENADES.molotov
        local thinker = CreateModifierThinker(owner, nil, "modifier_cs_grenade_thinker", { duration = g.duration + 1 }, pos, team, false)
        self:GrenadeMolotov(owner, -1, thinker, pos, g, true)
    elseif kind == "invis" then
        -- invisibility rune picked up in CS2: invisible in Dota for 45 s (sentry/dust still reveal), shooting breaks it
        if owner == bridge.proxies[slot] then owner:AddNewModifier(owner, nil, "modifier_cs_smoked", { duration = 45 }) end
    elseif kind == "ward" then
        -- observer ward bought in CS2: real Dota vision for the CS team (fog of war opens in CS2 too)
        local ok, ward = pcall(CreateUnitByName, "npc_dota_observer_wards", pos, false, owner, owner, team)
        if ok and ward then
            ward:AddNewModifier(owner, nil, "modifier_kill", { duration = 360 })
            pcall(function() ward:AddNewModifier(owner, nil, "modifier_item_buff_ward", { duration = 360 }) end)
            EmitSoundOnLocationWithCaster(pos, "DOTA_Item.ObserverWard.Activate", owner)
        end
    elseif kind == "capture" then
        -- CS player captured an outpost or a watcher: it now gives vision to the CS team
        for _, e in ipairs(Entities:FindAllInSphere(pos, 450)) do
            local cls = e.GetClassname and e:GetClassname() or ""
            if (cls:find("watch_tower") or cls:find("lantern")) and e.SetTeam and e:GetTeamNumber() ~= team then
                e:SetTeam(team)
                self:Msg("Ксник захватил " .. (cls:find("lantern") and "фонарь" or "аутпост") .. "!")
            end
        end
    elseif kind == "smoke" then
        local g = CS_GRENADES.smoke
        local thinker = CreateModifierThinker(owner, nil, "modifier_cs_grenade_thinker", { duration = g.duration + 1 }, pos, team, false)
        self:GrenadeSmoke(owner, thinker, pos, g)
        if owner.csSlot then owner:AddNewModifier(owner, nil, "modifier_cs_smoke_invis", { duration = CS_SMOKE_INVIS_TIME }) end
    end
end

------------------------------------------------------------
-- CS players shooting Dota heroes
------------------------------------------------------------
function CDotaCS:BridgeHeroHit(bridge, heroId, damage, attackerSlot, weapon)
    local hero = EntIndexToHScript(heroId)
    if not hero or hero:IsNull() or not hero:IsAlive() then return end

    local attacker = bridge.proxies[attackerSlot]
    if not attacker or attacker:IsNull() then attacker = hero end -- unknown shooter: still apply damage
    -- a CS player can't hurt his own side (Dire creeps, towers...)
    if attacker ~= hero and attacker:GetTeamNumber() == hero:GetTeamNumber() then return end
    -- grenade damage comes with the G lines (bigger, area), not from the invisible hitbox bot
    local w = weapon or ""
    if w:find("hegrenade") or w:find("inferno") or w:find("molotov") or w:find("incgrenade") then return end
    if attacker ~= hero and weapon == "blademaster" then
        attacker:StartGesture(ACT_DOTA_ATTACK)
        EmitSoundOn("Hero_Juggernaut.Attack", hero)
    elseif attacker ~= hero then
        if attacker:HasModifier("modifier_cs_smoked") then attacker:RemoveModifierByName("modifier_cs_smoked") end
        -- a CS player shoots: aim at the hero, play the shooting animation and a rifle shot (not every bullet)
        local now = GameRules:GetGameTime()
        if not attacker.csLastShot or now - attacker.csLastShot > 0.25 then
            attacker.csLastShot = now
            local d = hero:GetAbsOrigin() - attacker:GetAbsOrigin(); d.z = 0
            if d:Length2D() > 1 then attacker.csFace = d:Normalized() end
            attacker:RemoveGesture(ACT_DOTA_ATTACK)
            attacker:StartGestureWithPlaybackRate(ACT_DOTA_ATTACK, 2)
            EmitSoundOn("Hero_Sniper.attack", attacker)
            local fx = ParticleManager:CreateParticle(CS_TRACER, PATTACH_CUSTOMORIGIN, attacker)
            ParticleManager:SetParticleControl(fx, 0, attacker:GetAbsOrigin() + Vector(0, 0, 90))
            ParticleManager:SetParticleControl(fx, 1, hero:GetAbsOrigin() + Vector(0, 0, 90))
            ParticleManager:ReleaseParticleIndex(fx)
        end
    end

    local weaponName = (weapon or ""):gsub("^weapon_", "")
    local wasAlive = hero:IsAlive()
    local bountyGold = hero.GetGoldBounty and hero:GetGoldBounty() or 0
    local bountyXp = hero.GetDeathXP and hero:GetDeathXP() or 0
    self:DealDamage(attacker, -1, hero, damage * CS_BRIDGE_DAMAGE_TO_DOTA, weaponName)
    if wasAlive and not hero:IsAlive() and attacker ~= hero and attacker.csSlot then
        -- last hit by a CS player: gold and experience go to him in CS2 (E R slot gold xp unit)
        local uname = hero:GetUnitName():gsub("npc_dota_hero_", ""):gsub("npc_dota_", "")
        if hero:IsRealHero() then
            bountyGold = 150 + hero:GetLevel() * 15
            bountyXp = 100 + hero:GetLevel() * 30
        end
        table.insert(bridge.outbox, string.format("E R %s %d %d %s", attacker.csSlot, bountyGold, bountyXp, uname))
        if uname == "roshan" then
            table.insert(bridge.outbox, string.format("E AEGIS %s", attacker.csSlot))
            self:Msg("Ксник убил Рошана и забрал Аегис!")
            local p = hero:GetAbsOrigin()
            hero:SetContextThink("cs_aegis_cleanup", function()
                for _, drop in ipairs(Entities:FindAllByClassnameWithin("dota_item_drop", p, 600)) do
                    local item = drop:GetContainedItem()
                    if item and item:GetAbilityName() == "item_aegis" then UTIL_Remove(item); UTIL_Remove(drop) end
                end
            end, 0.5)
        elseif uname:find("miniboss") then
            table.insert(bridge.outbox, string.format("E SHARD %s", attacker.csSlot))
            self:Msg("Ксник убил Тормента!")
        end
    end
    if wasAlive and not hero:IsAlive() and hero:IsRealHero() then
        -- killed by a CS player: tell CS2 (score + message)
        local heroName = hero:GetUnitName():gsub("npc_dota_hero_", "")
        local killer = (attacker ~= hero and attacker.csName) or ("player" .. tostring(attackerSlot))
        table.insert(bridge.outbox, string.format("E K %s %s %s", heroName, killer, weaponName ~= "" and weaponName or "gun"))
    end
end

------------------------------------------------------------
-- Creeps, neutrals and Roshan near CS players (U lines)
------------------------------------------------------------
CS_BRIDGE_UNIT_RANGE = 3000
CS_BRIDGE_MAX_UNITS = 60

function CDotaCS:BridgeUnitLines(bridge)
    local lines, seen = {}, {}
    for _, proxy in pairs(bridge.proxies) do
        if proxy and not proxy:IsNull() then
            local found = FindUnitsInRadius(DOTA_TEAM_GOODGUYS, proxy:GetAbsOrigin(), nil, CS_BRIDGE_UNIT_RANGE,
                DOTA_UNIT_TARGET_TEAM_BOTH, DOTA_UNIT_TARGET_BASIC,
                DOTA_UNIT_TARGET_FLAG_INVULNERABLE + DOTA_UNIT_TARGET_FLAG_DEAD + DOTA_UNIT_TARGET_FLAG_MAGIC_IMMUNE_ENEMIES,
                FIND_CLOSEST, false)
            for _, u in ipairs(found) do
                local id = u:entindex()
                if not seen[id] and not u.csSlot and #lines < CS_BRIDGE_MAX_UNITS and self:BridgeVisibleToCS(u) then
                    seen[id] = true
                    local model = (u:GetModelName() or ""):match("([^/]+)%.vmdl$")
                    if model then
                        local pos = u:GetAbsOrigin()
                        local x, y = ToCS(pos)
                        local f = u:GetForwardVector()
                        table.insert(lines, string.format("U %d %.1f %.1f %.1f %.3f %.3f %d %d %d %s %s",
                            id, x, y, pos.z, f.x, f.y, u:GetHealth(), u:GetMaxHealth(), u:IsAlive() and 1 or 0,
                            model, u:IsAttacking() and "attack" or "-"))
                    end
                end
            end
        end
    end
    return lines
end

------------------------------------------------------------
-- Dota sounds near CS players (E S event x y z)
------------------------------------------------------------
CS_BRIDGE_SOUND_RANGE = 2500
CS_BRIDGE_MAX_SOUNDS = 12   -- per tick

local ATTACK_SOUNDS = {
    { "creep_goodguys_melee", "Creep_Good_Melee.Attack" }, { "creep_goodguys_flagbearer", "Creep_Good_Melee.Attack" },
    { "creep_goodguys_ranged", "Creep_Good_Range.Attack" }, { "goodguys_siege", "Creep_Good_Engine.Attack" },
    { "creep_badguys_melee", "Creep_Bad_Melee.Attack" }, { "creep_badguys_flagbearer", "Creep_Bad_Melee.Attack" },
    { "creep_badguys_ranged", "Creep_Bad_Range.Attack" }, { "badguys_siege", "Creep_Bad_Engine.Attack" },
    { "tower", "Tower.HeroImpact" }, { "fountain", "Tower.HeroImpact" },
    { "roshan", "Roshan.Attack" }, { "hero_pudge", "Hero_Pudge.Attack" },
}
local DEATH_SOUNDS = {
    { "kobold", "n_creep_kobolds.Death" }, { "troll", "n_creep_trollCommon.Death" }, { "satyr", "n_creep_SatyrCommon.Death" },
    { "prowler", "n_creep_SatyrCommon.Death" }, { "gnoll", "n_creep_gnoll.Death" }, { "ogre", "n_creep_ogres.Death" },
    { "harpy", "n_creep_harpy.Death" }, { "centaur", "n_creep_centaurKhan.Death" }, { "wolf", "n_creep_Worg.Death" },
    { "golem", "n_creep_golemRock.Death" }, { "black_dragon", "n_creep_blackdragon.Death" },
    { "black_drake", "n_creep_blackdrake.Death" }, { "furbolg", "n_creep_furbolgUrsa.Death" },
    { "wildkin", "n_creep_Wildkin.Death" }, { "thunder_lizard", "n_creep_Thunderlizard_Big.Death" },
    { "fel_beast", "n_creep_fellbeast.Death" }, { "ghost", "n_creep_ghost.Death" },
    { "jungle_stalker", "n_creep_junglestalkerCommon.Death" }, { "roshan", "Roshan.Death" },
    { "goodguys_tower", "Building_RadiantTower.Destruction" }, { "badguys_tower", "Building_DireTower.Destruction" },
    { "hero_pudge", "Hero_Pudge.Death" },
}
local ABILITY_SOUNDS = {
    pudge_meat_hook = "Hero_Pudge.AttackHookExtend",
    pudge_rot = "Hero_Pudge.Rot",
    pudge_dismember = "Hero_Pudge.Dismember",
    pudge_eject = "Hero_Pudge.Eject",
}

local function Lookup(list, name)
    for _, e in ipairs(list) do
        if name:find(e[1], 1, true) then return e[2] end
    end
end

function CDotaCS:BridgeSound(event, pos)
    local bridge = self.bridge
    if not bridge or not event or not pos then return end
    if (bridge.soundCount or 0) >= CS_BRIDGE_MAX_SOUNDS then return end
    local near = false
    for _, u in pairs(bridge.proxies) do
        if u and not u:IsNull() and (u:GetAbsOrigin() - pos):Length2D() < CS_BRIDGE_SOUND_RANGE then near = true break end
    end
    if not near then return end
    bridge.soundCount = (bridge.soundCount or 0) + 1
    local x, y = ToCS(pos)
    table.insert(bridge.outbox, string.format("E S %s %.0f %.0f %.0f", event, x, y, pos.z))
end

-- a visible effect in CS2 for Dota spells (E FX kind x y z): fire, lightning, explosion, blink
local SPELL_FX = {
    { "lina_", "fire" }, { "phoenix_", "fire" }, { "ember_", "fire" }, { "jakiro_macropyre", "fire" },
    { "zuus_", "lightning" }, { "leshrac_", "lightning" }, { "razor_", "lightning" }, { "disruptor_", "lightning" },
    { "blink", "blink" }, { "time_walk", "blink" }, { "phantom_strike", "blink" }, { "pounce", "blink" }, { "shadow_dance", "blink" },
    { "earthshaker_", "boom" }, { "sven_storm_bolt", "boom" }, { "sven_gods_strength", "boom" }, { "nevermore_requiem", "boom" },
    { "nevermore_shadowraze", "fire" }, { "invoker_sun_strike", "fire" }, { "invoker_chaos_meteor", "fire" },
    { "lion_finger_of_death", "lightning" }, { "lion_impale", "boom" }, { "faceless_void_chronosphere", "blink" },
    { "antimage_mana_void", "he" }, { "crystal_maiden_crystal_nova", "he" }, { "queenofpain_sonic_wave", "he" },
    { "legion_commander_duel", "boom" }, { "axe_culling_blade", "boom" }, { "windrunner_powershot", "blink" },
    { "dragon_knight_breathe_fire", "fire" }, { "huskar_", "fire" }, { "ogre_magi_fireblast", "boom" }, { "ogre_magi_ignite", "fire" },
    { "tidehunter_ravage", "boom" }, { "kunkka_torrent", "he" }, { "kunkka_ghostship", "boom" }, { "necrolyte_reapers_scythe", "boom" },
    { "skeleton_king_hellfire_blast", "fire" }, { "mirana_starfall", "lightning" }, { "riki_blink_strike", "blink" },
    { "bloodseeker_rupture", "he" }, { "shadow_shaman_ether_shock", "lightning" }, { "witch_doctor_paralyzing_cask", "he" },
    { "ursa_earthshock", "boom" }, { "bristleback_quill_spray", "he" }, { "viper_viper_strike", "he" },
}

function CDotaCS:BridgeSpellFx(abilityName, caster)
    local kind
    for _, e in ipairs(SPELL_FX) do
        if abilityName:find(e[1], 1, true) then kind = e[2] break end
    end
    if not kind then return end
    local pos = caster:GetAbsOrigin()
    local cur = caster:GetCursorPosition()
    if cur and cur:Length2D() > 1 and (cur - pos):Length2D() < 2500 then pos = cur end
    local bridge = self.bridge
    if not bridge then return end
    local near = false
    for _, u in pairs(bridge.proxies) do
        if u and not u:IsNull() and (u:GetAbsOrigin() - pos):Length2D() < CS_BRIDGE_SOUND_RANGE then near = true break end
    end
    if not near then return end
    local x, y = ToCS(pos)
    table.insert(bridge.outbox, string.format("E FX %s %.0f %.0f %.0f", kind, x, y, GetGroundPosition(pos, nil).z))
end

function CDotaCS:BridgeListenSounds()
    if self.bridgeSoundsOn then return end
    self.bridgeSoundsOn = true
    local lastAttack = {}

    ListenToGameEvent("entity_hurt", function(ev)
        if not self.bridge then return end
        if ev.entindex_inflictor and ev.entindex_inflictor ~= 0 then return end -- spells are handled below
        local attacker = ev.entindex_attacker and EntIndexToHScript(ev.entindex_attacker)
        if not attacker or attacker:IsNull() or not attacker.GetUnitName then return end
        local now = GameRules:GetGameTime()
        if lastAttack[attacker] and now - lastAttack[attacker] < 0.3 then return end
        lastAttack[attacker] = now
        local name = attacker:GetUnitName()
        local snd = Lookup(ATTACK_SOUNDS, name)
        if not snd and CS_HERO_SOUNDS then snd = CS_HERO_SOUNDS.attack[name] end
        if not snd and name:find("neutral", 1, true) then
            snd = attacker:IsRangedAttacker() and "n_creep_Ranged.Attack" or "n_creep_Melee.Attack"
        end
        if snd then self:BridgeSound(snd, attacker:GetAbsOrigin()) end
    end, nil)

    -- trees cut in Dota disappear in CS2 too
    ListenToGameEvent("tree_cut", function(ev)
        if not self.bridge then return end
        local x, y = ToCS(Vector(ev.tree_x or 0, ev.tree_y or 0, 0))
        table.insert(self.bridge.outbox, string.format("E T %.0f %.0f", x, y))
    end, nil)

    ListenToGameEvent("entity_killed", function(ev)
        if not self.bridge then return end
        local unit = ev.entindex_killed and EntIndexToHScript(ev.entindex_killed)
        if not unit or unit:IsNull() or not unit.GetUnitName then return end
        local snd = Lookup(DEATH_SOUNDS, unit:GetUnitName())
        if not snd and CS_HERO_SOUNDS then snd = CS_HERO_SOUNDS.death[unit:GetUnitName()] end
        if snd then self:BridgeSound(snd, unit:GetAbsOrigin()) end
    end, nil)

    ListenToGameEvent("dota_player_used_ability", function(ev)
        if not self.bridge then return end
        local snd = ABILITY_SOUNDS[ev.abilityname or ""] or (CS_HERO_SOUNDS and CS_HERO_SOUNDS.ability[ev.abilityname or ""])
        local caster = ev.caster_entindex and EntIndexToHScript(ev.caster_entindex)
        -- Pudge's hook: show it flying in CS2 too
        if ev.abilityname == "pudge_meat_hook" and caster and not caster:IsNull() then
            local o = caster:GetAbsOrigin()
            local dir = caster:GetCursorPosition() - o
            if dir:Length2D() < 1 then dir = caster:GetForwardVector() end
            local x, y = ToCS(o)
            table.insert(self.bridge.outbox, string.format("E HK %d %.0f %.0f %.0f %.3f %.3f", caster:entindex(), x, y, o.z, dir.x, dir.y))
        end
        if snd and caster and not caster:IsNull() then self:BridgeSound(snd, caster:GetAbsOrigin()) end
        if caster and not caster:IsNull() then self:BridgeSpellFx(ev.abilityname or "", caster) end
    end, nil)
end

------------------------------------------------------------
-- Buildings (B lines): CS players can shoot towers, barracks and the Ancient
------------------------------------------------------------
function CDotaCS:BridgeBuildingLines()
    local lines = {}
    local found = FindUnitsInRadius(DOTA_TEAM_GOODGUYS, Vector(0, 0, 0), nil, FIND_UNITS_EVERYWHERE,
        DOTA_UNIT_TARGET_TEAM_BOTH, DOTA_UNIT_TARGET_BUILDING,
        DOTA_UNIT_TARGET_FLAG_INVULNERABLE + DOTA_UNIT_TARGET_FLAG_DEAD, FIND_ANY_ORDER, false)
    for _, b in ipairs(found) do
        local pos = b:GetAbsOrigin()
        local x, y = ToCS(pos)
        local name = b:GetUnitName():gsub("npc_dota_", "")
        local invuln = b:IsInvulnerable() and 1 or 0
        table.insert(lines, string.format("B %d %.0f %.0f %.0f %d %d %d %d %s",
            b:entindex(), x, y, pos.z, b:GetHealth(), b:GetMaxHealth(), b:IsAlive() and 1 or 0, invuln, name))
    end
    return lines
end
