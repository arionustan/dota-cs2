// DotaCS: hitboxes of Dota heroes in CS2. A hero is a cylinder measured from its model at the CS scale
// (tools/hero_hitbox.py), tested against the shot line like creeps. The CS bot of the hero only keeps the
// scoreboard row and stays under the map, so its scaled-up skeleton can no longer catch bullets in the wrong place.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    // radius, bottom, top (CS units above the hero's feet)
    private static readonly Dictionary<string, (float R, float Z0, float Top)> HeroHitbox = new()
    {
        ["axe"] = (32f, 0f, 125f),
        ["juggernaut"] = (24f, 0f, 125f),
        ["sniper"] = (29f, 0f, 88f),
        ["crystal_maiden"] = (36f, 0f, 124f),
        ["lina"] = (30f, 0f, 143f),
        ["phantom_assassin"] = (27f, 0f, 132f),
        ["nevermore"] = (28f, 0f, 121f),
        ["drow_ranger"] = (18f, 0f, 109f),
        ["earthshaker"] = (44f, 0f, 124f),
        ["zuus"] = (21f, 0f, 102f),
        ["lion"] = (46f, 0f, 135f),
        ["invoker"] = (41f, 0f, 172f),
        ["slark"] = (33f, 0f, 90f),
        ["windrunner"] = (24f, 0f, 111f),
        ["sven"] = (29f, 0f, 127f),
        ["legion_commander"] = (27f, 0f, 117f),
        ["faceless_void"] = (37f, 0f, 124f),
        ["antimage"] = (23f, 0f, 132f),
        ["queenofpain"] = (31f, 0f, 124f),
        ["mirana"] = (44f, 0f, 136f),
        ["riki"] = (25f, 0f, 88f),
        ["bloodseeker"] = (23f, 0f, 111f),
        ["viper"] = (45f, 40f, 185f),
        ["witch_doctor"] = (46f, 0f, 175f),
        ["kunkka"] = (27f, 0f, 126f),
        ["skeleton_king"] = (31f, 0f, 142f),
        ["dragon_knight"] = (30f, 0f, 138f),
        ["tidehunter"] = (68f, 0f, 149f),
        ["ursa"] = (55f, 0f, 138f),
        ["bristleback"] = (41f, 0f, 120f),
        ["ogre_magi"] = (44f, 0f, 137f),
        ["huskar"] = (46f, 0f, 131f),
        ["necrolyte"] = (32f, 0f, 125f),
        ["shadow_shaman"] = (36f, 0f, 99f),
        ["troll_warlord"] = (26f, 0f, 149f),
        ["pudge"] = (51f, 0f, 156f),
    };
    private const float HeadshotPart = 0.2f, HeadshotMult = 2.5f;

    private (float R, float Z0, float Top) HeroCyl(HeroState h)
    {
        var name = _heroModelOf.TryGetValue(h.Id, out var m) && m != PudgeModel ? h.Name : "pudge";
        return HeroHitbox.TryGetValue(name, out var c) ? c : HeroHitbox["pudge"];
    }

    private static float HeroFeetZ(HeroState h) => Math.Abs(h.Z) < 0.01f ? FloorZ : h.Z;

    // the shot line from (sx,sy,sz) to (x,y,z): nearest hero hit, its t along the line and if it was the head
    private HeroState? HitHero(float sx, float sy, float sz, float dx, float dy, float dz, float maxT, out float bestT, out bool head, out Vector at)
    {
        HeroState? best = null; bestT = maxT; head = false; at = new Vector(0, 0, 0);
        var dxy = dx * dx + dy * dy;
        if (dxy < 1f) return null;
        foreach (var h in _heroes.Values)
        {
            if (!h.Alive || !h.Visible) continue;
            var c = HeroCyl(h);
            var r = c.R * 1.2f + 6f;                        // a little forgiving: the model moves between Dota updates
            var t = Math.Clamp(((h.X - sx) * dx + (h.Y - sy) * dy) / dxy, 0f, maxT);
            float px = sx + dx * t, py = sy + dy * t, pz = sz + dz * t;
            var ddx = px - h.X; var ddy = py - h.Y;
            var feet = HeroFeetZ(h);
            if (ddx * ddx + ddy * ddy > r * r || pz < feet + c.Z0 - 8 || pz > feet + c.Top + 8) continue;
            if (t >= bestT) continue;
            bestT = t; best = h; at = new Vector(px, py, pz);
            head = pz > feet + c.Top - (c.Top - c.Z0) * HeadshotPart;
        }
        return best;
    }

    private (float X, float Y, float Z) EyeOf(CCSPlayerPawn pawn)
    {
        var o = pawn.AbsOrigin!;
        float off = 64f;
        try { off = pawn.ViewOffset.Z; if (off < 10f) off = 64f; } catch { }
        return (o.X, o.Y, o.Z + off);
    }

    // knife: no bullet impact, so stab along the view direction
    private HookResult OnWeaponFireKnife(EventWeaponFire ev, GameEventInfo info)
    {
        try
        {
            var p = ev.Userid;
            if (p == null || !p.IsValid || p.IsBot || !ev.Weapon.Contains("knife")) return HookResult.Continue;
            var pawn = p.PlayerPawn.Value;
            if (pawn?.AbsOrigin == null) return HookResult.Continue;
            var (sx, sy, sz) = EyeOf(pawn);
            var a = pawn.EyeAngles;
            double yaw = a.Y * Math.PI / 180, pitch = a.X * Math.PI / 180;
            float dx = (float)(Math.Cos(pitch) * Math.Cos(yaw)) * 90, dy = (float)(Math.Cos(pitch) * Math.Sin(yaw)) * 90, dz = (float)(-Math.Sin(pitch)) * 90;
            TryHitUnit(p, sx + dx, sy + dy, sz + dz, 40f, "weapon_knife");
        }
        catch { }
        return HookResult.Continue;
    }
}
