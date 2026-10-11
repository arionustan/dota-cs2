-- DotaCS: grenades (HE, flash, smoke, molotov, decoy)
-- A grenade flies as a Dota projectile to an invisible point on the ground,
-- then OnGrenadeLanded does the effect.

CS_FX = {
    projectile = "particles/units/heroes/hero_alchemist/alchemist_unstable_concoction_projectile.vpcf",
    he         = "particles/units/heroes/hero_lina/lina_spell_light_strike_array.vpcf",
    flash      = "particles/units/heroes/hero_keeper_of_the_light/keeper_of_the_light_blinding_light_aoe.vpcf",
    smoke      = "particles/units/heroes/hero_riki/riki_smokebomb.vpcf",
    fire       = "particles/units/heroes/hero_ember_spirit/ember_spirit_flameguard.vpcf",
}

CS_SND = {
    he      = "Hero_Techies.LandMine.Detonate",
    flash   = "Hero_KeeperOfTheLight.BlindingLight",
    smoke   = "Hero_Riki.Smoke_Screen",
    molotov = "Hero_EmberSpirit.FlameGuard.Cast",
    throw   = "Hero_Alchemist.UnstableConcoction.Throw",
}

CS_GRENADE_SOUNDFILES = {
    "soundevents/game_sounds_heroes/game_sounds_techies.vsndevts",
    "soundevents/game_sounds_heroes/game_sounds_keeper_of_the_light.vsndevts",
    "soundevents/game_sounds_heroes/game_sounds_riki.vsndevts",
    "soundevents/game_sounds_heroes/game_sounds_ember_spirit.vsndevts",
    "soundevents/game_sounds_heroes/game_sounds_alchemist.vsndevts",
}

function CS_PrecacheGrenades(context)
    for _, fx in pairs(CS_FX) do
        PrecacheResource("particle", fx, context)
    end
    for _, f in ipairs(CS_GRENADE_SOUNDFILES) do
        PrecacheResource("soundfile", f, context)
    end
end

------------------------------------------------------------
-- Buying and selecting grenades
------------------------------------------------------------
function CDotaCS:GrenadeCount(p)
    local total = 0
    for _, n in pairs(p.grenades) do total = total + n end
    return total
end

-- returns an error text, or nil if the player can buy it
function CDotaCS:CanBuyGrenade(p, id)
    local g = CS_GRENADES[id]
    if (p.grenades[id] or 0) >= g.max then
        return "Больше нельзя: " .. g.name
    end
    if self:GrenadeCount(p) >= CS_GRENADE_TOTAL then
        return "Максимум " .. CS_GRENADE_TOTAL .. " гранаты"
    end
    return nil
end

function CDotaCS:GiveGrenade(pid, id)
    local p = self.csPlayers[pid]
    p.grenades[id] = (p.grenades[id] or 0) + 1
    self:SendHud(pid)
end

-- key 4: take out a grenade, press again to cycle through the types you have
function CDotaCS:CycleGrenade(pid)
    local p = self.csPlayers[pid]
    if not p then return end

    local owned = {}
    for _, id in ipairs(CS_GRENADE_ORDER) do
        if (p.grenades[id] or 0) > 0 then table.insert(owned, id) end
    end
    if #owned == 0 then return end

    local nextId = owned[1]
    if p.slot == "grenade" then
        for i, id in ipairs(owned) do
            if id == p.grenadeType then
                nextId = owned[(i % #owned) + 1]
                break
            end
        end
    end

    p.grenadeType = nextId
    self:SwitchSlot(pid, "grenade")
end

------------------------------------------------------------
-- Throwing
------------------------------------------------------------
function CDotaCS:ThrowGrenade(pid, p, hero)
    local id = p.grenadeType
    local g = CS_GRENADES[id]
    if not g or (p.grenades[id] or 0) <= 0 then return end

    local origin = hero:GetAbsOrigin()
    local target = p.aim or (origin + hero:GetForwardVector() * 500)
    local dir = target - origin
    dir.z = 0
    local dist = math.min(dir:Length2D(), CS_GRENADE_RANGE)
    if dist < 50 then dist = 50 end
    if dir:Length2D() < 1 then dir = hero:GetForwardVector() end
    dir = dir:Normalized()
    local landPos = GetGroundPosition(origin + dir * dist, nil)

    p.grenades[id] = p.grenades[id] - 1
    hero:SetForwardVector(dir)
    hero:StartGestureWithPlaybackRate(ACT_DOTA_ATTACK, 2)
    EmitSoundOn(CS_SND.throw, hero)

    -- invisible point where it lands; lives a bit longer than the longest effect
    local life = dist / CS_GRENADE_SPEED + (g.duration or 0) + 2
    local thinker = CreateModifierThinker(hero, nil, "modifier_cs_grenade_thinker",
        { duration = life }, landPos, hero:GetTeamNumber(), false)

    self.grenadeId = (self.grenadeId or 0) + 1
    local gid = self.grenadeId
    self.grenades[gid] = { type = id, owner = hero, ownerPid = pid, thinker = thinker }

    local ability = hero:FindAbilityByName("cs_grenade")
    if ability then
        ProjectileManager:CreateTrackingProjectile({
            Target = thinker,
            Source = hero,
            Ability = ability,
            EffectName = CS_FX.projectile,
            iMoveSpeed = CS_GRENADE_SPEED,
            vSourceLoc = origin,
            bDodgeable = false,
            bProvidesVision = true,
            iVisionRadius = 150,
            iVisionTeamNumber = hero:GetTeamNumber(),
            ExtraData = { gid = gid },
        })
    else
        -- fallback: no projectile, land after the flight time
        thinker:SetContextThink("cs_land", function()
            self:OnGrenadeLanded(gid)
            return nil
        end, dist / CS_GRENADE_SPEED)
    end

    -- nothing left of this type: switch to the next grenade or a gun
    if p.grenades[id] <= 0 then
        if self:GrenadeCount(p) > 0 then
            self:CycleGrenade(pid)
        else
            self:SwitchSlot(pid, self:BestSlot(p))
        end
    end
    self:SendHud(pid)
end

------------------------------------------------------------
-- Effects
------------------------------------------------------------
function CDotaCS:OnGrenadeLanded(gid)
    local gr = self.grenades[gid]
    if not gr then return end
    self.grenades[gid] = nil

    local thinker = gr.thinker
    if not thinker or thinker:IsNull() then return end
    local pos = thinker:GetAbsOrigin()
    local g = CS_GRENADES[gr.type]
    local owner = gr.owner

    if gr.type == "he" then
        self:GrenadeHE(owner, gr.ownerPid, pos, g)
        UTIL_Remove(thinker)
    elseif gr.type == "flash" then
        self:GrenadeFlash(owner, pos, g)
        UTIL_Remove(thinker)
    elseif gr.type == "smoke" then
        self:GrenadeSmoke(owner, thinker, pos, g)
    elseif gr.type == "molotov" then
        self:GrenadeMolotov(owner, gr.ownerPid, thinker, pos, g)
    elseif gr.type == "decoy" then
        self:GrenadeDecoy(owner, thinker, pos, g)
    end
end

local function UnitsAround(pos, radius)
    return FindUnitsInRadius(DOTA_TEAM_NOTEAM, pos, nil, radius,
        DOTA_UNIT_TARGET_TEAM_BOTH,
        DOTA_UNIT_TARGET_HERO + DOTA_UNIT_TARGET_BASIC,
        DOTA_UNIT_TARGET_FLAG_MAGIC_IMMUNE_ENEMIES,
        FIND_ANY_ORDER, false)
end

-- HE: damage falls off with distance, hurts everyone like in CS (also yourself)
function CDotaCS:GrenadeHE(owner, ownerPid, pos, g)
    local fx = ParticleManager:CreateParticle(CS_FX.he, PATTACH_WORLDORIGIN, nil)
    ParticleManager:SetParticleControl(fx, 0, pos)
    ParticleManager:SetParticleControl(fx, 1, Vector(g.radius, 1, 1))
    ParticleManager:ReleaseParticleIndex(fx)
    EmitSoundOnLocationWithCaster(pos, CS_SND.he, owner)

    for _, u in pairs(UnitsAround(pos, g.radius)) do
        if u:IsAlive() and not u:IsBuilding() then
            local d = (u:GetAbsOrigin() - pos):Length2D()
            local dmg = g.damage * (1 - d / g.radius)
            if dmg > 1 and owner and not owner:IsNull() then
                self:DealDamage(owner, ownerPid, u, dmg, g.name)
            end
        end
    end
end

-- Flash: everyone close enough gets a white screen; Dota heroes also miss attacks
function CDotaCS:GrenadeFlash(owner, pos, g)
    local fx = ParticleManager:CreateParticle(CS_FX.flash, PATTACH_WORLDORIGIN, nil)
    ParticleManager:SetParticleControl(fx, 0, pos)
    ParticleManager:SetParticleControl(fx, 1, pos)
    ParticleManager:SetParticleControl(fx, 2, Vector(g.radius, 0, 0))
    ParticleManager:ReleaseParticleIndex(fx)
    EmitSoundOnLocationWithCaster(pos, CS_SND.flash, owner)

    local heroes = FindUnitsInRadius(DOTA_TEAM_NOTEAM, pos, nil, g.radius,
        DOTA_UNIT_TARGET_TEAM_BOTH, DOTA_UNIT_TARGET_HERO,
        DOTA_UNIT_TARGET_FLAG_MAGIC_IMMUNE_ENEMIES, FIND_ANY_ORDER, false)

    for _, h in pairs(heroes) do
        if h:IsRealHero() and h:IsAlive() then
            local d = (h:GetAbsOrigin() - pos):Length2D()
            local duration = 0.5 + g.blind * (1 - d / g.radius)
            local pid = h:GetPlayerOwnerID()
            local player = pid and pid >= 0 and PlayerResource:GetPlayer(pid)
            if player then
                CustomGameEventManager:Send_ServerToPlayer(player, "cs_flash", { duration = duration })
            end
            if not self.csPlayers[pid] then
                h:AddNewModifier(owner, nil, "modifier_cs_blind", { duration = duration })
            end
        end
    end
end

-- Smoke: big cloud, units inside are hidden from enemies outside; puts out molotov fire
function CDotaCS:GrenadeSmoke(owner, thinker, pos, g)
    local fx = ParticleManager:CreateParticle(CS_FX.smoke, PATTACH_WORLDORIGIN, nil)
    ParticleManager:SetParticleControl(fx, 0, pos)
    ParticleManager:SetParticleControl(fx, 1, Vector(g.radius, g.radius, g.radius))
    EmitSoundOnLocationWithCaster(pos, CS_SND.smoke, owner)

    self.smokes[thinker] = { pos = pos, radius = g.radius }

    -- put out fire that is under the smoke
    for fireThinker, fire in pairs(self.fires) do
        if (fire.pos - pos):Length2D() < g.radius + fire.radius then
            if not fireThinker:IsNull() then UTIL_Remove(fireThinker) end
            self.fires[fireThinker] = nil
            if fire.fx then
                ParticleManager:DestroyParticle(fire.fx, false)
                ParticleManager:ReleaseParticleIndex(fire.fx)
            end
        end
    end

    local endTime = GameRules:GetGameTime() + g.duration
    thinker:SetContextThink("cs_smoke", function()
        local now = GameRules:GetGameTime()
        if now >= endTime then
            ParticleManager:DestroyParticle(fx, false)
            ParticleManager:ReleaseParticleIndex(fx)
            self.smokes[thinker] = nil
            UTIL_Remove(thinker)
            return nil
        end
        for _, u in pairs(UnitsAround(pos, g.radius)) do
            u:AddNewModifier(u, nil, "modifier_cs_smoked", { duration = 0.3 })
        end
        return 0.2
    end, 0)
end

-- Molotov: fire on the ground that burns everyone standing in it
function CDotaCS:GrenadeMolotov(owner, ownerPid, thinker, pos, g)
    -- landed in smoke: goes out right away
    for _, smoke in pairs(self.smokes) do
        if (smoke.pos - pos):Length2D() < smoke.radius then
            UTIL_Remove(thinker)
            return
        end
    end

    local fx = ParticleManager:CreateParticle(CS_FX.fire, PATTACH_ABSORIGIN_FOLLOW, thinker)
    ParticleManager:SetParticleControl(fx, 0, pos)
    ParticleManager:SetParticleControl(fx, 2, Vector(g.radius, g.radius, g.radius))
    EmitSoundOnLocationWithCaster(pos, CS_SND.molotov, owner)

    self.fires[thinker] = { pos = pos, radius = g.radius, fx = fx }

    local tick = 0.25
    local endTime = GameRules:GetGameTime() + g.duration
    thinker:SetContextThink("cs_fire", function()
        if GameRules:GetGameTime() >= endTime then
            ParticleManager:DestroyParticle(fx, false)
            ParticleManager:ReleaseParticleIndex(fx)
            self.fires[thinker] = nil
            UTIL_Remove(thinker)
            return nil
        end
        for _, u in pairs(UnitsAround(pos, g.radius)) do
            if u:IsAlive() and not u:IsBuilding() and owner and not owner:IsNull() then
                self:DealDamage(owner, ownerPid, u, g.dps * tick, g.name)
            end
        end
        return tick
    end, 0)
end

-- Decoy: makes gunshot sounds so enemies think someone is there
function CDotaCS:GrenadeDecoy(owner, thinker, pos, g)
    local endTime = GameRules:GetGameTime() + g.duration
    thinker:SetContextThink("cs_decoy", function()
        if GameRules:GetGameTime() >= endTime then
            UTIL_Remove(thinker)
            return nil
        end
        local shots = RandomInt(1, 4)
        for i = 1, shots do
            EmitSoundOnLocationWithCaster(pos, CS_SHOT_SOUND, owner)
        end
        -- enemies see "shots" on the minimap, like on the CS radar
        if owner and not owner:IsNull() then
            local enemyTeam = (owner:GetTeamNumber() == DOTA_TEAM_GOODGUYS) and DOTA_TEAM_BADGUYS or DOTA_TEAM_GOODGUYS
            MinimapEvent(enemyTeam, owner, pos.x, pos.y, DOTA_MINIMAP_EVENT_ENEMY_TELEPORTING, 1)
        end
        return RandomFloat(0.4, 1.4)
    end, 0.5)
end
