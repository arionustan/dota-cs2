-- On a CS2 player shown in Dota.
-- * never dies from Dota damage by itself: the damage is sent to CS2, CS2 decides
-- * collides with units like a hero, so it can be blocked and hit

modifier_cs_proxy = class({})

function modifier_cs_proxy:IsHidden() return true end
function modifier_cs_proxy:IsPurgable() return false end
function modifier_cs_proxy:RemoveOnDeath() return true end

function modifier_cs_proxy:CheckState()
    return {
        [MODIFIER_STATE_PROVIDES_VISION] = true,
    }
end

function modifier_cs_proxy:DeclareFunctions()
    return {
        MODIFIER_PROPERTY_MIN_HEALTH,
        MODIFIER_EVENT_ON_TAKEDAMAGE,
        MODIFIER_EVENT_ON_ATTACK,
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

-- fires for every attack in the game (global modifier event): ranged ones fly into CS2 as real Dota projectiles
function modifier_cs_proxy:OnAttack(params)
    if not IsServer() then return end
    if GameRules.DotaCS and GameRules.DotaCS.BridgeOnAttack then
        GameRules.DotaCS:BridgeOnAttack(params.attacker, params.target)
    end
end
