-- Invisible point on the ground where a grenade lands (and where smoke/fire lives).
-- Dota removes the point by itself when this modifier ends.

modifier_cs_grenade_thinker = class({})

function modifier_cs_grenade_thinker:IsHidden() return true end
function modifier_cs_grenade_thinker:IsPurgable() return false end
