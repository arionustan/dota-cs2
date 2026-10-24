-- Flashbang on Dota heroes: attacks miss and vision drops to almost nothing while blinded.
-- (The white screen is drawn by the UI for every blinded player.)

modifier_cs_blind = class({})

function modifier_cs_blind:IsHidden() return false end
function modifier_cs_blind:IsDebuff() return true end
function modifier_cs_blind:IsPurgable() return false end
function modifier_cs_blind:GetTexture() return "keeper_of_the_light_blinding_light" end

function modifier_cs_blind:DeclareFunctions()
    return {
        MODIFIER_PROPERTY_MISS_PERCENTAGE,
        MODIFIER_PROPERTY_FIXED_DAY_VISION,
        MODIFIER_PROPERTY_FIXED_NIGHT_VISION,
    }
end

-- a blinded hero sees almost nothing around him either
function modifier_cs_blind:GetFixedDayVision() return 100 end
function modifier_cs_blind:GetFixedNightVision() return 100 end

function modifier_cs_blind:GetModifierMiss_Percentage()
    return 100
end
