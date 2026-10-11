-- Flashbang on Dota heroes: attacks miss while blinded.
-- (The white screen is drawn by the UI for every blinded player.)

modifier_cs_blind = class({})

function modifier_cs_blind:IsHidden() return false end
function modifier_cs_blind:IsDebuff() return true end
function modifier_cs_blind:IsPurgable() return true end
function modifier_cs_blind:GetTexture() return "keeper_of_the_light_blinding_light" end

function modifier_cs_blind:DeclareFunctions()
    return { MODIFIER_PROPERTY_MISS_PERCENTAGE }
end

function modifier_cs_blind:GetModifierMiss_Percentage()
    return 100
end
