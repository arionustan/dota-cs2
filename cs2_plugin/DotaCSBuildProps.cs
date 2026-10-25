// DotaCS: Dota buildings as props in CS2 (they fall when destroyed in Dota), Pudge particles from Dota, hook throw. Generated in part.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    // model, x, y, z, yaw, scale, Dota building x, y
    private static readonly (string Model, float X, float Y, float Z, float Yaw, float Scale, float Bx, float By)[] BuildingProps =
    {
        ("radiant_tower002", -3952f, -6112f, 256f, 0.0f, 1.00f, -3952f, -6112f),
        ("radiant_tower002", -4640f, -4144f, 256f, 45.0f, 1.00f, -4640f, -4144f),
        ("radiant_tower002", -6592f, -3408f, 256f, 90.0f, 1.00f, -6592f, -3408f),
        ("radiant_tower002", -360f, -6256f, 128f, 0.0f, 1.00f, -360f, -6256f),
        ("radiant_tower002", 4860f, -6379f, 128f, 30.0f, 1.00f, 4860f, -6379f),
        ("radiant_tower002", -3190f, -2926f, 128f, 45.0f, 1.00f, -3190f, -2926f),
        ("radiant_tower002", -6501f, -872f, 128f, 90.0f, 1.00f, -6501f, -872f),
        ("radiant_tower002", -6336f, 1856f, 128f, 90.0f, 1.00f, -6336f, 1856f),
        ("radiant_tower002", -5712f, -4864f, 256f, 45.0f, 1.00f, -5712f, -4864f),
        ("radiant_melee_barracks001", -4672f, -4552f, 256f, 135.0f, 1.00f, -4672f, -4552f),
        ("radiant_ranged_barracks001", -5060f, -4199f, 256f, 315.0f, 1.00f, -5060f, -4199f),
        ("radiant_melee_barracks001", -4280f, -6360f, 256f, 90.0f, 1.00f, -4280f, -6360f),
        ("radiant_ranged_barracks001", -4279f, -5853f, 256f, 270.0f, 1.00f, -4279f, -5853f),
        ("radiant_melee_barracks001", -6336f, -3758f, 256f, 180.0f, 1.00f, -6336f, -3758f),
        ("radiant_ranged_barracks001", -6844f, -3759f, 256f, 0.0f, 1.00f, -6844f, -3759f),
        ("dire_barracks_melee001", 6592f, 3392f, 256f, 0.0f, 1.00f, 6592f, 3392f),
        ("dire_barracks_ranged001", 6064f, 3376f, 256f, 180.0f, 1.00f, 6064f, 3376f),
        ("dire_barracks_ranged001", 4336f, 4183f, 256f, 135.0f, 1.00f, 4336f, 4183f),
        ("dire_barracks_melee001", 4702f, 3824f, 256f, 315.0f, 1.00f, 4702f, 3824f),
        ("dire_barracks_melee001", 3898f, 5496f, 256f, 270.0f, 1.00f, 3898f, 5496f),
        ("dire_barracks_ranged001", 3894f, 6025f, 256f, 90.0f, 1.00f, 3894f, 6025f),
        ("dire_ancient_base001", 5528f, 5000f, 248f, 45.0f, 1.00f, 5528f, 5000f),
        ("radiant_ancient001", -5920f, -5352f, 240f, 345.0f, 1.00f, -5920f, -5352f),
        ("dire_tower002", 4944f, 4776f, 256f, 43.0f, 1.00f, 4944f, 4776f),
        ("dire_tower002", -128f, 6016f, 128f, 0.0f, 1.00f, -128f, 6016f),
        ("dire_tower002", -5275f, 6036f, 128f, 30.0f, 1.00f, -5275f, 6036f),
        ("dire_tower002", 2496f, 2112f, 128f, 45.0f, 1.00f, 2496f, 2112f),
        ("dire_tower002", 524f, 652f, 128f, 45.0f, 1.00f, 524f, 652f),
        ("dire_tower002", 6400f, 384f, 128f, 90.0f, 1.00f, 6400f, 384f),
        ("dire_tower002", 6336f, 3032f, 256f, 90.0f, 1.00f, 6336f, 3032f),
        ("dire_tower002", 3552f, 5776f, 256f, 0.0f, 1.00f, 3552f, 5776f),
        ("dire_tower002", 4272f, 3759f, 256f, 45.0f, 1.00f, 4272f, 3759f),
        ("dire_tower002", 5280f, 4432f, 256f, 42.0f, 1.00f, 5280f, 4432f),
        ("radiant_tower002", -5392f, -5192f, 256f, 45.0f, 1.00f, -5392f, -5192f),
        ("radiant_tower002", -1544f, -1408f, 128f, 45.0f, 1.00f, -1544f, -1408f),
        ("radiant_statue001", -6590f, -4207f, 240f, 302.0f, 1.00f, -6590f, -4207f),
        ("radiant_statue001", -5838f, -4292f, 240f, 221.0f, 1.00f, -5838f, -4292f),
        ("radiant_statue001", -4752f, -6080f, 240f, 304.0f, 1.00f, -4752f, -6080f),
        ("radiant_statue001", -5312f, -4800f, 240f, 303.0f, 1.00f, -5312f, -4800f),
        ("radiant_statue001", -4782f, -5268f, 240f, 232.0f, 1.00f, -4782f, -5268f),
        ("dire_column001", 6326f, 3798f, 256f, 245.0f, 1.00f, 6326f, 3798f),
        ("dire_column001", 5521f, 3949f, 256f, 294.0f, 1.00f, 5521f, 3949f),
        ("dire_column001", 4894f, 4370f, 264f, 46.0f, 1.00f, 4894f, 4370f),
        ("dire_column001", 4481f, 4989f, 256f, 121.0f, 1.00f, 4481f, 4989f),
        ("dire_column001", 4411f, 5753f, 256f, 65.0f, 1.00f, 4411f, 5753f),
        ("dire_tower002", 6269f, -2240f, 128f, 90.0f, 1.00f, 6269f, -2240f),
        ("dire_column001", 5286f, 3374f, 271f, 125.0f, 1.00f, 5286f, 3374f),
        ("dire_column001", 3784f, 4718f, 271f, 86.0f, 1.00f, 3784f, 4718f),
        ("radiant_statue001", -5598f, -3711f, 280f, 302.0f, 1.00f, -5598f, -3711f),
        ("radiant_statue001", -4265f, -5162f, 256f, 313.0f, 1.00f, -4265f, -5162f),
    };
    private readonly CDynamicProp?[] _bldProps = new CDynamicProp?[50];
    private readonly bool[] _bldDead = new bool[50];

    private static string BldPath(string n) => $"models/dota_bld/{n}/{n}.vmdl";

    private static void PrecacheBuildingsAndFx(ResourceManifest m)
    {
        foreach (var n in BuildingProps.Select(b => b.Model).Distinct()) m.AddResource(BldPath(n));
        m.AddResource(FxRot); m.AddResource(FxDismember); m.AddResource(FxHookImpact); m.AddResource(FxBuildingDeath);
    }

    private void UpdateBuildingProps()
    {
        for (var i = 0; i < BuildingProps.Length; i++)
        {
            var b = BuildingProps[i];
            // alive or dead in Dota? (no data from Dota yet = keep it standing)
            var dead = false;
            foreach (var d in _buildings)
            {
                var dx = d.X - b.Bx; var dy = d.Y - b.By;
                if (dx * dx + dy * dy < 120 * 120) { dead = !d.Alive; break; }
            }
            if (dead && !_bldDead[i])
            {
                _bldDead[i] = true;
                if (_bldProps[i] != null && _bldProps[i]!.IsValid) _bldProps[i]!.Remove();
                _bldProps[i] = null;
                var at = new Vector(b.X, b.Y, b.Z + 60);
                StartFx(FxBuildingDeath, at, 4f);
                PlayDotaSound(b.Model.StartsWith("dire") ? "Building_DireTower.Destruction" : "Building_RadiantTower.Destruction", at);
                continue;
            }
            if (!dead) _bldDead[i] = false;
            if (!dead && (_bldProps[i] == null || !_bldProps[i]!.IsValid))
                try { _bldProps[i] = SpawnStatic(BldPath(b.Model), b.X, b.Y, b.Z, b.Yaw, b.Scale, true, null); } catch { }
        }
    }

    // ------------------------------------------------------------ Dota particles
    private const string FxRot = "particles/units/heroes/hero_pudge/pudge_rot.vpcf";
    private const string FxDismember = "particles/units/heroes/hero_pudge/pudge_dismember.vpcf";
    private const string FxHookImpact = "particles/units/heroes/hero_pudge/pudge_meathook_impact.vpcf";
    private const string FxBuildingDeath = "particles/explosions_fx/explosion_c4_500.vpcf";

    // spell effects of Dota heroes, made of CS2's own particles (E FX kind x y z)
    private static readonly Dictionary<string, string[]> SpellFx = new()
    {
        ["fire"] = new[] { "particles/inferno_fx/explosion_molotov_air.vpcf" },
        ["boom"] = new[] { "particles/explosions_fx/explosion_c4_500.vpcf" },
        ["lightning"] = new[] { "particles/environment/de_train/train_lightning.vpcf", "particles/generic_fx/fx_electric_arc_spark.vpcf" },
        ["blink"] = new[] { "particles/generic_fx/fx_electricspark_glow_large.vpcf" },
        ["he"] = new[] { "particles/entity/env_explosion/explosion_hegrenade_a.vpcf" },
    };

    private static void PrecacheSpellFx(ResourceManifest m)
    {
        foreach (var list in SpellFx.Values) foreach (var f in list) m.AddResource(f);
    }

    private void PlaySpellFx(string kind, Vector at)
    {
        if (!SpellFx.TryGetValue(kind, out var list)) return;
        foreach (var f in list) StartFx(f, at, 4f);
        Diag("spell fx " + kind);
    }

    private CParticleSystem? StartFx(string effect, Vector at, float seconds, float cp1 = 0f)
    {
        try
        {
            var fx = Utilities.CreateEntityByName<CParticleSystem>("info_particle_system");
            if (fx == null) return null;
            fx.EffectName = effect;
            fx.StartActive = true;
            if (cp1 > 0) { fx.DataCP = 1; fx.DataCPValue.X = cp1; fx.DataCPValue.Y = cp1; fx.DataCPValue.Z = cp1; }
            fx.DispatchSpawn();
            fx.Teleport(at, null, null);
            fx.AcceptInput("Start");
            if (seconds > 0) AddTimer(seconds, () => { if (fx.IsValid) fx.Remove(); });
            return fx;
        }
        catch { return null; }
    }

    // ------------------------------------------------------------ Pudge's hook flying out and back (E HK heroId x y z dirx diry)
    private readonly List<(Vector From, float Dx, float Dy, float Start)> _hookThrows = new();
    private const float HookSpeed = 1450f, HookRange = 1300f;

    private void StartHookThrow(float x, float y, float z, float dx, float dy)
    {
        var len = (float)Math.Sqrt(dx * dx + dy * dy);
        if (len < 0.01f) return;
        _hookThrows.Add((new Vector(x, y, z + 60), dx / len, dy / len, Server.CurrentTime));
    }

    private void UpdateHookThrows()
    {
        var now = Server.CurrentTime;
        for (var i = _hookThrows.Count - 1; i >= 0; i--)
        {
            var h = _hookThrows[i];
            var t = now - h.Start;
            var outT = HookRange / HookSpeed;
            var dist = t < outT ? t * HookSpeed : HookRange - (t - outT) * HookSpeed;
            var slot = 1000 + i;
            if (dist <= 0) { RemoveChain(slot); _hookThrows.RemoveAt(i); continue; }
            DrawChain(slot, h.From, new Vector(h.From.X + h.Dx * dist, h.From.Y + h.Dy * dist, h.From.Z));
        }
    }
}
