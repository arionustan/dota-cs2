-- Smoke grenade: 15 s of invisibility that nothing can reveal or dispel (no dust, gem, sentry, purge).

modifier_cs_smoke_invis = class({})

function modifier_cs_smoke_invis:IsHidden() return false end
function modifier_cs_smoke_invis:IsDebuff() return false end
function modifier_cs_smoke_invis:IsPurgable() return false end
function modifier_cs_smoke_invis:IsPurgeException() return false end
function modifier_cs_smoke_invis:RemoveOnDeath() return true end
function modifier_cs_smoke_invis:GetTexture() return "riki_smoke_screen" end

function modifier_cs_smoke_invis:CheckState()
    return {
        [MODIFIER_STATE_INVISIBLE] = true,
        [MODIFIER_STATE_TRUESIGHT_IMMUNE] = true,
        [MODIFIER_STATE_NO_UNIT_COLLISION] = true,
    }
end

function modifier_cs_smoke_invis:GetPriority() return MODIFIER_PRIORITY_SUPER_ULTRA end

function modifier_cs_smoke_invis:DeclareFunctions()
    return { MODIFIER_PROPERTY_INVISIBILITY_LEVEL }
end

function modifier_cs_smoke_invis:GetModifierInvisibilityLevel()
    return 1
end
