-- Jump: the model goes up and down in an arc while the modifier lasts.

modifier_cs_jump = class({})

local JUMP_HEIGHT = 70

function modifier_cs_jump:IsHidden() return true end
function modifier_cs_jump:IsPurgable() return false end
function modifier_cs_jump:RemoveOnDeath() return true end

function modifier_cs_jump:DeclareFunctions()
    return { MODIFIER_PROPERTY_VISUAL_Z_DELTA }
end

function modifier_cs_jump:GetVisualZDelta()
    local duration = self:GetDuration()
    if duration <= 0 then return 0 end
    local t = math.min(1, self:GetElapsedTime() / duration)
    return 4 * JUMP_HEIGHT * t * (1 - t)
end
