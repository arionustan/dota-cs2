-- Hidden ability on CS players. Only used so grenades can fly as Dota projectiles.
-- The real logic lives in cs_grenades.lua.

cs_grenade = class({})

function cs_grenade:OnProjectileHit_ExtraData(target, location, data)
    if GameRules.DotaCS and data and data.gid then
        GameRules.DotaCS:OnGrenadeLanded(tonumber(data.gid))
    end
    return true
end
