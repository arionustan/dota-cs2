-- DotaCS: weapons on the ground
-- * on death a CS player drops the primary (or the pistol if no primary)
-- * G drops the gun in your hands
-- * walk over a gun to pick it up if that slot is empty, E swaps it with yours
-- * Dota heroes can't pick these up

CS_DROP_LIFETIME = 60     -- seconds before a gun on the ground disappears
CS_PICKUP_RADIUS = 90     -- auto pickup when walking over
CS_SWAP_RADIUS = 150      -- E to swap

function CDotaCS:DropWeapon(pid, slot, pos)
    local p = self.csPlayers[pid]
    if not p then return end
    local id = p.weapons[slot]
    if not id or slot == "knife" then return end

    local item = CreateItem("item_cs_weapon", nil, nil)
    if not item then return end
    item.csWeapon = id
    item.csAmmo = p.ammo[slot]

    local dropPos = pos + RandomVector(RandomFloat(20, 60))
    local container = CreateItemOnPositionSync(dropPos, item)
    if container then
        self.drops[container] = { item = item, time = GameRules:GetGameTime() }
    end

    p.weapons[slot] = nil
    p.ammo[slot] = 0
    p.noPickupUntil = GameRules:GetGameTime() + 1 -- don't pick it right back up

    if p.slot == slot then
        self:SwitchSlot(pid, self:BestSlot(p))
    end
    self:SendHud(pid)
end

-- G key
function CDotaCS:OnDropKey(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    local hero = PlayerResource:GetSelectedHeroEntity(pid)
    if not p or not hero or not hero:IsAlive() then return end
    if p.slot ~= "primary" and p.slot ~= "secondary" then return end
    self:DropWeapon(pid, p.slot, hero:GetAbsOrigin() + hero:GetForwardVector() * 80)
end

function CDotaCS:TakeDrop(pid, container)
    local drop = self.drops[container]
    if not drop then return end
    local p = self.csPlayers[pid]
    local id = drop.item.csWeapon
    local slot = CS_WeaponSlot(id)
    local w = CS_WEAPONS[id]

    p.weapons[slot] = id
    p.ammo[slot] = drop.item.csAmmo or (w and w.mag) or 0

    self.drops[container] = nil
    UTIL_Remove(drop.item)
    UTIL_Remove(container)

    self:SwitchSlot(pid, slot)
end

-- E key: swap your gun with the nearest one on the ground
function CDotaCS:OnUseKey(data)
    local pid = data.PlayerID
    local p = self.csPlayers[pid]
    local hero = PlayerResource:GetSelectedHeroEntity(pid)
    if not p or not hero or not hero:IsAlive() then return end

    local pos = hero:GetAbsOrigin()
    local best, bestDist = nil, CS_SWAP_RADIUS
    for container, _ in pairs(self.drops) do
        if not container:IsNull() then
            local d = (container:GetAbsOrigin() - pos):Length2D()
            if d < bestDist then
                best, bestDist = container, d
            end
        end
    end
    if not best then return end

    local slot = CS_WeaponSlot(self.drops[best].item.csWeapon)
    if p.weapons[slot] then
        self:DropWeapon(pid, slot, pos)
    end
    self:TakeDrop(pid, best)
end

-- called every tick: auto pickup and cleanup
function CDotaCS:DropsTick(now)
    for container, drop in pairs(self.drops) do
        if container:IsNull() or drop.item:IsNull() then
            self.drops[container] = nil
        elseif now - drop.time > CS_DROP_LIFETIME then
            self.drops[container] = nil
            UTIL_Remove(drop.item)
            UTIL_Remove(container)
        end
    end

    for pid, p in pairs(self.csPlayers) do
        local hero = PlayerResource:GetSelectedHeroEntity(pid)
        if hero and hero:IsAlive() and now >= (p.noPickupUntil or 0) then
            local pos = hero:GetAbsOrigin()
            for container, drop in pairs(self.drops) do
                local slot = CS_WeaponSlot(drop.item.csWeapon)
                if not p.weapons[slot]
                    and (container:GetAbsOrigin() - pos):Length2D() < CS_PICKUP_RADIUS then
                    self:TakeDrop(pid, container)
                    break
                end
            end
        end
    end
end

-- true if this order targets one of our guns on the ground
function CDotaCS:IsDropOrder(event)
    local target = event.entindex_target and EntIndexToHScript(event.entindex_target)
    if not target then return false end
    if self.drops[target] then return true end
    if target.GetContainedItem then
        local item = target:GetContainedItem()
        return item and item:GetAbilityName() == "item_cs_weapon"
    end
    return false
end
