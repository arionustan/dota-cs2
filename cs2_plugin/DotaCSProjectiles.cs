// DotaCS: real Dota particles in CS2. The compiled Dota particles (vpcf_c) and their textures are copied into
// the addon (tools/dota_particles.py). A Dota attack projectile is created at the attacker (control point 0),
// flies by itself to control point 1 (a helper entity we move onto the target every frame) with the speed in
// control point 2, and on arrival its "end cap" plays the Dota impact, exactly like in Dota.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private class Proj
    {
        public CParticleSystem Fx = null!;
        public CBaseEntity? Helper;
        public string Target = "";
        public Vector Pos = new(0, 0, 0);
        public Vector LastTarget = new(0, 0, 0);
        public float Speed, Born, RemoveAt;
        public bool Arrived;
    }
    private readonly List<Proj> _projs = new();
    private readonly Dictionary<int, float> _projHitSlot = new();   // CS player slot -> time a Dota projectile reached him
    private static readonly HashSet<string> PortedFx = new();

    // every ported particle that is on disk gets precached (only the roots in particles/dota_ported.txt)
    private static void PrecacheDotaFx(ResourceManifest m)
    {
        try
        {
            foreach (var root in new[] { Path.Combine(Server.GameDirectory, "csgo"), Server.GameDirectory })
            {
                var dir = Path.Combine(root, "particles");
                var lists = Directory.Exists(dir) ? Directory.GetFiles(dir, "dota_ported*.txt") : Array.Empty<string>();
                if (lists.Length == 0) continue;
                foreach (var line in lists.SelectMany(File.ReadAllLines))
                {
                    var p = line.Trim();
                    if (p.Length == 0 || !File.Exists(Path.Combine(root, p.Replace('/', Path.DirectorySeparatorChar) + "_c"))) continue;
                    PortedFx.Add(p); m.AddResource(p);
                }
                break;
            }
        }
        catch { }
    }

    private static bool HasDotaFx(string p) => PortedFx.Contains(p);

    // where a Dota target is right now (chest height): p<slot> = CS player, e<entindex> = hero / unit / building
    private Vector? ProjTargetPos(string t)
    {
        if (t.StartsWith("p") && int.TryParse(t[1..], out var slot))
        {
            var pl = PlayerBySlot(slot);
            var o = pl?.PlayerPawn.Value?.AbsOrigin;
            return o == null ? null : new Vector(o.X, o.Y, o.Z + 45);
        }
        var id = t.Length > 1 ? t[1..] : t;
        if (_heroes.TryGetValue(id, out var h)) { var c = HeroCyl(h); return new Vector(h.X, h.Y, HeroFeetZ(h) + (c.Z0 + c.Top) * 0.55f); }
        if (_units.TryGetValue(id, out var u)) { var hh = UnitHitbox.TryGetValue(u.Model, out var hb) ? hb.H : 90f; return new Vector(u.X, u.Y, u.Z + hh * 0.55f); }
        foreach (var b in _buildings) if (b.Id == id) return new Vector(b.X, b.Y, b.Z + 150);
        return null;
    }

    // E PJ particle x y z target speed
    private void OnDotaProjectile(string[] e)
    {
        if (e.Length < 8 || !HasDotaFx(e[2])) return;
        var tgt = ProjTargetPos(e[6]);
        if (tgt == null) return;
        var from = new Vector(F(e[3]), F(e[4]), F(e[5]));
        var speed = Math.Max(F(e[7]), 300f);
        var p = SpawnDotaFx(e[2], from, tgt, speed);
        if (p == null) return;
        p.Target = e[6]; p.Speed = speed;
        _projs.Add(p);
    }

    private Proj? SpawnDotaFx(string effect, Vector at, Vector? cp1, float cp2x)
    {
        try
        {
            CBaseEntity? helper = null;
            if (cp1 != null)
            {
                helper = Utilities.CreateEntityByName<CBaseEntity>("info_particle_target");
                if (helper != null) { helper.DispatchSpawn(); helper.Teleport(cp1, null, null); }
            }
            var fx = Utilities.CreateEntityByName<CParticleSystem>("info_particle_system");
            if (fx == null) return null;
            fx.EffectName = effect;
            fx.StartActive = true;
            if (helper != null) fx.ControlPointEnts[1].Raw = helper.EntityHandle.Raw;
            if (cp2x > 0) { fx.DataCP = 2; fx.DataCPValue.X = cp2x; fx.DataCPValue.Y = 0; fx.DataCPValue.Z = 0; }
            fx.DispatchSpawn();
            fx.Teleport(at, null, null);
            fx.AcceptInput("Start");
            Diag("dota fx " + effect);
            return new Proj { Fx = fx, Helper = helper, Pos = new Vector(at.X, at.Y, at.Z), LastTarget = cp1 ?? at, Born = Server.CurrentTime };
        }
        catch (Exception ex) { Logger.LogWarning("DotaCS dota fx {Fx}: {Error}", effect, ex.Message); return null; }
    }

    // every server frame: keep the target helper on the target, fly our own copy to know when it lands
    private void ProjFrame()
    {
        if (_projs.Count == 0) return;
        var now = Server.CurrentTime;
        var dt = Server.FrameTime > 0 ? Server.FrameTime : 1f / 64f;
        for (var i = _projs.Count - 1; i >= 0; i--)
        {
            var p = _projs[i];
            if (p.Arrived)
            {
                if (now < p.RemoveAt) continue;
                if (p.Fx.IsValid) p.Fx.Remove();
                if (p.Helper != null && p.Helper.IsValid) p.Helper.Remove();
                _projs.RemoveAt(i);
                continue;
            }
            var t = ProjTargetPos(p.Target) ?? p.LastTarget;
            p.LastTarget = t;
            if (p.Helper != null && p.Helper.IsValid) p.Helper.Teleport(t, null, null);
            float dx = t.X - p.Pos.X, dy = t.Y - p.Pos.Y, dz = t.Z - p.Pos.Z;
            var d = (float)Math.Sqrt(dx * dx + dy * dy + dz * dz);
            var step = p.Speed * dt;
            if (d <= step + 8f || now - p.Born > 6f || !p.Fx.IsValid)
            {
                p.Arrived = true; p.RemoveAt = now + 2.5f;
                if (p.Fx.IsValid) { p.Fx.Teleport(t, null, null); p.Fx.AcceptInput("StopPlayEndCap"); }
                if (p.Target.StartsWith("p") && int.TryParse(p.Target[1..], out var slot)) _projHitSlot[slot] = now;
                continue;
            }
            p.Pos = new Vector(p.Pos.X + dx / d * step, p.Pos.Y + dy / d * step, p.Pos.Z + dz / d * step);
        }
    }

    // E PFX particle x y z [cp1x cp1y cp1z]: a Dota spell effect at a point (control point 1 = second point if given)
    private void OnDotaSpellFx(string[] e)
    {
        if (e.Length < 6 || !HasDotaFx(e[2])) return;
        var at = new Vector(F(e[3]), F(e[4]), F(e[5]));
        var cp1 = e.Length >= 9 ? new Vector(F(e[6]), F(e[7]), F(e[8])) : at;
        var p = SpawnDotaFx(e[2], at, cp1, 0);
        if (p == null) return;
        p.Arrived = true; p.RemoveAt = Server.CurrentTime + 6f;
        _projs.Add(p);
    }

    // test: !pfx tower | creep | lina | lsa | bolt  (plays a ported Dota effect in front of you)
    private void PfxTest(CCSPlayerController p, string what)
    {
        var pawn = p.PlayerPawn.Value;
        if (pawn?.AbsOrigin == null) return;
        var o = pawn.AbsOrigin;
        var yaw = pawn.EyeAngles.Y * Math.PI / 180;
        var ahead = new Vector(o.X + (float)Math.Cos(yaw) * 700, o.Y + (float)Math.Sin(yaw) * 700, o.Z);
        var near = new Vector(o.X + (float)Math.Cos(yaw) * 250, o.Y + (float)Math.Sin(yaw) * 250, o.Z);
        string? proj = what switch
        {
            "tower" => "particles/base_attacks/ranged_tower_good.vpcf",
            "tower2" => "particles/base_attacks/ranged_tower_bad.vpcf",
            "creep" => "particles/base_attacks/ranged_goodguy.vpcf",
            "lina" => "particles/units/heroes/hero_lina/lina_base_attack.vpcf",
            _ => null,
        };
        if (proj != null)
        {
            if (!HasDotaFx(proj)) { p.PrintToChat(" Эффект не найден (запусти START_ALL): " + proj); return; }
            var pr = SpawnDotaFx(proj, new Vector(ahead.X, ahead.Y, ahead.Z + 150), new Vector(o.X, o.Y, o.Z + 45), 900);
            if (pr != null) { pr.Target = "p" + p.Slot; pr.Speed = 900; _projs.Add(pr); }
            return;
        }
        var spell = what switch
        {
            "lsa" => "particles/units/heroes/hero_lina/lina_spell_light_strike_array.vpcf",
            "bolt" => "particles/units/heroes/hero_zuus/zuus_lightning_bolt.vpcf",
            _ => "",
        };
        if (spell == "") { p.PrintToChat(" !pfx tower / tower2 / creep / lina / lsa / bolt"); return; }
        OnDotaSpellFx(new[] { "E", "PFX", spell, near.X.ToString(Inv), near.Y.ToString(Inv), near.Z.ToString(Inv) });
    }
}
