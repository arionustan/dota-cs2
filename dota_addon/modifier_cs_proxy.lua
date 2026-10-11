-- On a CS2 player shown in Dota.
-- * never dies from Dota damage by itself: the damage is sent to CS2, CS2 decides
-- * always visible to the enemy team, so Dota players can target it

modifier_cs_proxy = class({})

function modifier_cs_proxy:IsHidden() return true end
function modifier_cs_proxy:IsPurgable() return false end
function modifier_cs_proxy:RemoveOnDeath() return true end

function modifier_cs_proxy:CheckState()
    return {
        [MODIFIER_STATE_PROVIDES_VISION] = true,
        [MODIFIER_STATE_NO_UNIT_COLLISION] = true,
    }
end

function modifier_cs_proxy:DeclareFunctions()
    return {
        MODIFIER_PROPERTY_MIN_HEALTH,
        MODIFIER_EVENT_ON_TAKEDAMAGE,
    }
end

function modifier_cs_proxy:GetMinHealth()
    if self.allowDeath then return 0 end
    return 1
end

function modifier_cs_proxy:OnTakeDamage(params)
    if not IsServer() then return end
    if params.unit ~= self:GetParent() then return end
    if GameRules.DotaCS and GameRules.DotaCS.OnProxyDamaged then
        GameRules.DotaCS:OnProxyDamaged(self:GetParent(), params.attacker, params.damage)
    end
end
