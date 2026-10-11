-- Move speed for CS players. Stack count = speed (depends on weapon and bunnyhop).
-- Ignores Dota's 550 speed cap so bunnyhop can go faster.

modifier_cs_speed = class({})

function modifier_cs_speed:IsHidden() return true end
function modifier_cs_speed:IsPurgable() return false end
function modifier_cs_speed:RemoveOnDeath() return false end

function modifier_cs_speed:DeclareFunctions()
    return {
        MODIFIER_PROPERTY_MOVESPEED_BASE_OVERRIDE,
        MODIFIER_PROPERTY_IGNORE_MOVESPEED_LIMIT,
    }
end

function modifier_cs_speed:GetModifierMoveSpeedOverride()
    local s = self:GetStackCount()
    if s <= 0 then return nil end
    return s
end

function modifier_cs_speed:GetModifierIgnoreMovespeedLimit()
    return 1
end
