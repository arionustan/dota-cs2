-- Standing inside a smoke cloud: enemies outside can't see you.

modifier_cs_smoked = class({})

function modifier_cs_smoked:IsHidden() return false end
function modifier_cs_smoked:IsPurgable() return false end
function modifier_cs_smoked:GetTexture() return "riki_smoke_screen" end

function modifier_cs_smoked:CheckState()
    return { [MODIFIER_STATE_INVISIBLE] = true }
end

function modifier_cs_smoked:DeclareFunctions()
    return { MODIFIER_PROPERTY_INVISIBILITY_LEVEL }
end

function modifier_cs_smoked:GetModifierInvisibilityLevel()
    return 1
end
