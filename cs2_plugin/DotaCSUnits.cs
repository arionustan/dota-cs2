// DotaCS: Dota creeps, neutrals and Roshan in CS2, Dota sounds, Pudge's chain, hero glow.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    // models converted from Dota (models/dota_units/<name>/<name>.vmdl)
    private static readonly HashSet<string> UnitModels = new()
    {
        "creep_bad_flagbearer","creep_bad_melee","creep_bad_siege","creep_good_siege","ice_giant01","lane_dire_ranged",
        "n_creep_ancient_frog","n_creep_ancient_frog_mage","n_creep_beast","n_creep_black_dragon","n_creep_black_drake",
        "n_creep_centaur_lrg","n_creep_centaur_med","n_creep_forest_troll_berserker","n_creep_forest_troll_high_priest",
        "n_creep_froglet","n_creep_froglet_mage","n_creep_furbolg_disrupter","n_creep_gargoyle","n_creep_ghost_a","n_creep_ghost_b",
        "n_creep_gnoll","n_creep_golem_b","n_creep_harpy_a","n_creep_harpy_b","n_creep_kobold_a","n_creep_kobold_b","n_creep_kobold_c",
        "n_creep_ogre_lrg","n_creep_ogre_med","n_creep_satyr_a","n_creep_satyr_b","n_creep_satyr_c","n_creep_satyr_spawn_a",
        "n_creep_satyr_spawn_b","n_creep_tadpole_c","n_creep_tadpole_ranged_v2","n_creep_tadpole_v2","n_creep_thunder_lizard_big",
        "n_creep_thunder_lizard_small","n_creep_trio_model","n_creep_troll_dark_a","n_creep_troll_dark_b","n_creep_vulture_a",
        "n_creep_vulture_b","n_creep_worg_large","n_creep_worg_small","neutral_creep_golem_a","pine_cone","radiant_flagbearer",
        "radiant_melee","radiant_ranged","roshan",
    };
    private const string ChainModel = "models/dota_units/chainlink/chainlink.vmdl";
    private const string SoundEvents = "soundevents/dotacs.vsndevts";
    private const int MaxUnits = 60;

    private static string UnitModelPath(string name) => $"models/dota_units/{name}/{name}.vmdl";

    private static void PrecacheExtra(ResourceManifest m)
    {
        m.AddResource(ChainModel);
        m.AddResource(SoundEvents);
        PrecacheWildlife(m);
        PrecacheTrees(m);
        PrecacheBuildingsAndFx(m);
        foreach (var n in UnitModels) m.AddResource(UnitModelPath(n));
        foreach (var b in BloodFx) m.AddResource(b);
        PrecacheRunes(m);
    }

    // ------------------------------------------------------------ units (U lines)
    private record UnitState(string Id, float X, float Y, float Z, float Fx, float Fy, int Hp, int MaxHp, bool Alive, string Model, string Act);
    private Dictionary<string, UnitState> _units = new();
    private readonly Dictionary<string, CDynamicProp> _unitProp = new();
    private readonly Dictionary<string, string> _unitAnim = new();
    private readonly Dictionary<string, Vector> _unitLastPos = new();
    private readonly Dictionary<string, float> _unitMoveTime = new();

    private void ParseUnits(string text)
    {
        var units = new Dictionary<string, UnitState>();
        foreach (var raw in text.Split('\n'))
        {
            var p = raw.Trim().Split(' ');
            // U id x y z fx fy hp maxhp alive model act
            if (p.Length < 12 || p[0] != "U") continue;
            var model = p[10].Replace("_mega", "");
            if (!UnitModels.Contains(model)) continue;
            units[p[1]] = new UnitState(p[1], F(p[2]), F(p[3]), F(p[4]), F(p[5]), F(p[6]), (int)F(p[7]), (int)F(p[8]), p[9] == "1", model, p[11]);
            if (units.Count >= MaxUnits) break;
        }
        _units = units;
    }

    private void SyncUnits()
    {
        foreach (var id in _unitProp.Keys.ToList())
            if (!_units.ContainsKey(id)) RemoveUnit(id);

        foreach (var u in _units.Values)
        {
            if (!_unitProp.TryGetValue(u.Id, out var prop) || !prop.IsValid)
            {
                try
                {
                    prop = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
                    if (prop == null) continue;
                    prop.Collision.SolidType = SolidType_t.SOLID_NONE;
                    prop.DispatchSpawn();
                    prop.SetModel(UnitModelPath(u.Model));
                    SetPropScale(prop, ModelScale);
                    _unitProp[u.Id] = prop;
                    _unitAnim.Remove(u.Id);
                }
                catch (Exception e) { Logger.LogWarning("DotaCS unit model {Model}: {Error}", u.Model, e.Message); continue; }
            }

            var yaw = (float)(Math.Atan2(u.Fy, u.Fx) * 180.0 / Math.PI);
            prop.Teleport(new Vector(u.X, u.Y, u.Z), new QAngle(0, yaw + PudgeYawOffset, 0), null);

            if (_unitLastPos.TryGetValue(u.Id, out var last) && Math.Abs(u.X - last.X) + Math.Abs(u.Y - last.Y) > 1f)
                _unitMoveTime[u.Id] = Server.CurrentTime;
            _unitLastPos[u.Id] = new Vector(u.X, u.Y, u.Z);
            var moving = _unitMoveTime.TryGetValue(u.Id, out var mt) && Server.CurrentTime - mt < 0.25f;
            var anim = !u.Alive ? "death" : u.Act == "attack" ? "attack" : moving ? "run" : "idle";

            if (_unitAnim.TryGetValue(u.Id, out var cur) && cur == anim) continue;
            _unitAnim[u.Id] = anim;
            prop.AcceptInput("SetAnimation", null, null, anim);
            prop.AcceptInput("SetDefaultAnimation", null, null, anim);
        }
    }

    private void RemoveUnit(string id)
    {
        if (_unitProp.TryGetValue(id, out var prop) && prop.IsValid) prop.Remove();
        _unitProp.Remove(id);
        _unitAnim.Remove(id);
        _unitLastPos.Remove(id);
        _unitMoveTime.Remove(id);
    }

    // ------------------------------------------------------------ Dota sounds (E S event x y z)
    private readonly List<CDynamicProp> _emitters = new();
    private int _emitterNext;

    private void PlayDotaSound(string ev, Vector pos)
    {
        try
        {
            CDynamicProp? e = null;
            if (_emitters.Count < 8)
            {
                e = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
                if (e == null) return;
                e.Collision.SolidType = SolidType_t.SOLID_NONE;
                e.RenderMode = RenderMode_t.kRenderNone;
                e.DispatchSpawn();
                e.SetModel(ChainModel);
                _emitters.Add(e);
            }
            else
            {
                e = _emitters[_emitterNext++ % _emitters.Count];
                if (!e.IsValid) { _emitters.Remove(e); return; }
            }
            e.Teleport(pos, null, null);
            e.EmitSound("dota." + ev);
        }
        catch (Exception ex) { Logger.LogWarning("DotaCS sound {Event}: {Error}", ev, ex.Message); }
    }

    // ------------------------------------------------------------ Pudge's chain (real links instead of a beam)
    private readonly Dictionary<int, List<CDynamicProp>> _chainLinks = new();
    private const float LinkStep = 7f;

    private void DrawChain(int slot, Vector start, Vector end)
    {
        if (!_chainLinks.TryGetValue(slot, out var links)) _chainLinks[slot] = links = new List<CDynamicProp>();
        var dx = end.X - start.X; var dy = end.Y - start.Y; var dz = end.Z - start.Z;
        var dist = (float)Math.Sqrt(dx * dx + dy * dy + dz * dz);
        var count = Math.Clamp((int)(dist / LinkStep), 1, 200);
        var yaw = (float)(Math.Atan2(dy, dx) * 180.0 / Math.PI);
        var pitch = dist > 0.1f ? (float)(-Math.Asin(dz / dist) * 180.0 / Math.PI) : 0f;

        while (links.Count < count)
        {
            var l = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
            if (l == null) break;
            l.Collision.SolidType = SolidType_t.SOLID_NONE;
            l.DispatchSpawn();
            l.SetModel(ChainModel);
            links.Add(l);
        }
        while (links.Count > count)
        {
            var l = links[^1];
            if (l.IsValid) l.Remove();
            links.RemoveAt(links.Count - 1);
        }
        for (var i = 0; i < links.Count; i++)
        {
            var t = (i + 0.5f) / links.Count;
            var p = new Vector(start.X + dx * t, start.Y + dy * t, start.Z + dz * t);
            if (links[i].IsValid) links[i].Teleport(p, new QAngle(pitch, yaw, i % 2 == 0 ? 0 : 90), null);
        }
    }

    private void RemoveChain(int slot)
    {
        if (!_chainLinks.TryGetValue(slot, out var links)) return;
        foreach (var l in links) if (l.IsValid) l.Remove();
        _chainLinks.Remove(slot);
    }

    // Dota models are imported 1:1 (animations break if the mesh alone is scaled), the entity is scaled instead
    private const float ModelScale = 0.55f;   // Pudge about 1.8x a CS player, same as his hitbox

    private static void SetPropScale(CDynamicProp prop, float scale)
    {
        try
        {
            var node = prop.CBodyComponent?.SceneNode;
            if (node == null) return;
            node.GetSkeletonInstance().Scale = scale;
            Utilities.SetStateChanged(prop, "CBaseEntity", "m_CBodyComponent");
        }
        catch { }
    }

    // ------------------------------------------------------------ red outline on Dota heroes
    private const int GlowRange = 700;

    private static void SetGlow(CDynamicProp prop, System.Drawing.Color color)
    {
        try
        {
            if (prop.Glow.GlowColorOverride == color) return;
            prop.Glow.GlowColorOverride = color;
            prop.Glow.GlowRange = GlowRange;   // CS players see the outline only when close
            prop.Glow.GlowRangeMin = 0;
            prop.Glow.GlowTeam = -1;
            prop.Glow.GlowType = 3;
            Utilities.SetStateChanged(prop, "CBaseModelEntity", "m_Glow");
        }
        catch { }
    }

    // ------------------------------------------------------------ Rot: a smoke cloud around Pudge while it is on
    private readonly Dictionary<string, CParticleSystem> _rotFx = new();
    private const string RotParticle = "particles/burning_fx/gas_canister_idle_radius.vpcf";

    private void UpdateRot(string heroId, HeroState hero, CDynamicProp? prop)
    {
        try
        {
            var on = hero.Alive && hero.Effect == "rot";
            _rotFx.TryGetValue(heroId, out var fx);
            if (!on)
            {
                if (fx != null && fx.IsValid) fx.Remove();
                _rotFx.Remove(heroId);
                if (prop != null) SetGlow(prop, System.Drawing.Color.FromArgb(255, 150, 35, 35));
                return;
            }
            if (prop != null) SetGlow(prop, System.Drawing.Color.FromArgb(255, 70, 140, 40));
            if (fx == null || !fx.IsValid)
            {
                fx = StartFx(FxRot, new Vector(hero.X, hero.Y, hero.Z + 10), 0f, 250f);
                if (fx == null) return;
                _rotFx[heroId] = fx;
            }
            fx.Teleport(new Vector(hero.X, hero.Y, hero.Z + 10), null, null);
        }
        catch { }
    }
}
