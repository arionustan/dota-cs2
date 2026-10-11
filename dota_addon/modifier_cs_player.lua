-- CS player modifier:
-- * max HP is exactly targetHP (100 at start, up to 1000 with upgrades),
--   it can go both below and above the Dota hero's own HP
-- * normal Dota attack is disabled (CS players shoot with the mouse)
-- * fast turning

modifier_cs_player = class({})

-- stack count = HP bonus + OFFSET (stack counts can't safely be negative)
local OFFSET = 100000

function modifier_cs_player:IsHidden() return false end
function modifier_cs_player:IsPurgable() return false end
function modifier_cs_player:RemoveOnDeath() return false end
function modifier_cs_player:GetTexture() return "sniper_take_aim" end

function modifier_cs_player:OnCreated(kv)
    if not IsServer() then return end
    self.targetHP = 100
    self:SetStackCount(OFFSET)
    self:StartIntervalThink(0.25)
    self:OnIntervalThink()
end

-- called from game mode when HP is upgraded or on respawn
function modifier_cs_player:SetTargetHP(hp)
    self.targetHP = hp
    self:OnIntervalThink()
end

function modifier_cs_player:OnIntervalThink()
    local hero = self:GetParent()
    local bonus = self:GetStackCount() - OFFSET
    local base = hero:GetMaxHealth() - bonus      -- HP without our modifier
    local newBonus = self.targetHP - base
    if newBonus ~= bonus then
        self:SetStackCount(newBonus + OFFSET)
        hero:CalculateStatBonus(true)
    end
end

function modifier_cs_player:CheckState()
    return { [MODIFIER_STATE_DISARMED] = true }
end

function modifier_cs_player:DeclareFunctions()
    return {
        MODIFIER_PROPERTY_HEALTH_BONUS,
        MODIFIER_PROPERTY_TURN_RATE_OVERRIDE,
    }
end

function modifier_cs_player:GetModifierHealthBonus()
    local stack = self:GetStackCount()
    if stack == 0 then return 0 end -- not synced yet
    return stack - OFFSET
end

function modifier_cs_player:GetModifierTurnRate_Override()
    return 3.0
end
