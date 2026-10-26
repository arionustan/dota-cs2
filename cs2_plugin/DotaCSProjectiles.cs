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
        PortedFx.Clear(); AbilityFx.Clear();
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
                // ability|particle|mode (tools/dota_fx_port.py)
                foreach (var line in Directory.GetFiles(dir, "dota_abilities*.txt").SelectMany(File.ReadAllLines))
                {
                    var q = line.Trim().Split('|');
                    if (q.Length < 3) continue;
                    foreach (var a in q[0].Split(','))
                    {
                        if (!AbilityFx.TryGetValue(a, out var l)) AbilityFx[a] = l = new();
                        l.Add((q[1], q[2]));
                    }
                }
                break;
            }
        }
        catch { }
    }

    private static bool HasDotaFx(string p) => PortedFx.Contains(p);
    private static readonly Dictionary<string, List<(string Fx, string Mode)>> AbilityFx = new();

    // E AB ability cx cy cz tx ty tz target radius speed kind: the real Dota effect of a spell, placed like Dota places it
    private void OnDotaAbility(string[] e)
    {
        if (e.Length < 13) return;
        var caster = new Vector(F(e[3]), F(e[4]), F(e[5]));
        var point = new Vector(F(e[6]), F(e[7]), F(e[8]));
        var tgt = e[9]; var radius = F(e[10]); var speed = F(e[11]);
        var unitTarget = tgt != "-";
        var played = false;
        if (AbilityFx.TryGetValue(e[2], out var list))
            foreach (var (fx, mode) in list)
            {
                if (!HasDotaFx(fx)) continue;
                var tpos = unitTarget ? ProjTargetPos(tgt) ?? point : point;
                Proj? p = null;
                var dx = point.X - caster.X; var dy = point.Y - caster.Y;
                var len = (float)Math.Sqrt(dx * dx + dy * dy);
                switch (mode)
                {
                    case "caster": p = SpawnDotaFx(fx, caster, caster, -1, null); break;
                    case "point": p = SpawnDotaFx(fx, point, point, -1, null); break;
                    case "vel":
                        // linear projectile (Dragon Slave, Powershot...): CP1 is its velocity
                        var sp = speed > 0 ? speed : 1100f;
                        var v = len > 1 ? new Vector(dx / len * sp, dy / len * sp, 0) : new Vector(sp, 0, 0);
                        p = SpawnDotaFx(fx, new Vector(caster.X, caster.Y, caster.Z + 60), null, 1, v);
                        if (p != null) { p.Arrived = true; p.RemoveAt = Server.CurrentTime + Math.Clamp(1600f / sp + 1.5f, 1.5f, 5f); }
                        break;
                    case "track":
                        // homing spell projectile (Storm Bolt, Paralyzing Cask...): flies to the target like an attack
                        p = SpawnDotaFx(fx, new Vector(caster.X, caster.Y, caster.Z + 90), tpos, 2, new Vector(speed > 0 ? speed : 1000f, 0, 0));
                        if (p != null) { p.Target = unitTarget ? tgt : ""; p.Speed = speed > 0 ? speed : 1000f; p.LastTarget = tpos; _projs.Add(p); }
                        continue;
                    case "radius":
                        var r = radius > 0 ? radius : 300f;
                        p = SpawnDotaFx(fx, unitTarget || len > 1 ? tpos : caster, null, 1, new Vector(r, r, r));
                        break;
                    default:
                        // pos: a unit target gets CP0 on the caster and CP1 on the target (beams, Laguna, Finger); a point spell plays at the point
                        p = unitTarget ? SpawnDotaFx(fx, new Vector(caster.X, caster.Y, caster.Z + 80), tpos, -1, null)
                                       : SpawnDotaFx(fx, len > 1 ? point : caster, len > 1 ? point : caster, -1, null);
                        if (p != null && unitTarget) p.Target = tgt;
                        break;
                }
                if (p == null) continue;
                played = true;
                if (!p.Arrived) { p.Arrived = true; p.RemoveAt = Server.CurrentTime + 5f; }
                _projs.Add(p);
            }
        if (!played) PlaySpellFx(e[12], unitTarget ? ProjTargetPos(tgt) ?? point : point);
    }

    // Dota's stun stars over stunned heroes, the level-up burst when a hero levels up
    private readonly Dictionary<string, Proj> _stunFx = new();
    private readonly Dictionary<string, int> _heroLevelSeen = new();
    private void UpdateHeroFx()
    {
        foreach (var id in _stunFx.Keys.ToList())
            if (!_heroes.TryGetValue(id, out var h0) || !h0.Alive || h0.Act != "stun" || !h0.Visible)
            {
                var sp = _stunFx[id];
                if (sp.Fx.IsValid) sp.Fx.Remove();
                if (sp.Helper != null && sp.Helper.IsValid) sp.Helper.Remove();
                _stunFx.Remove(id);
            }
        foreach (var h in _heroes.Values)
        {
            var head = new Vector(h.X, h.Y, HeroFeetZ(h) + HeroCyl(h).Top + 10);
            if (h.Alive && h.Visible && h.Act == "stun" && AbilityFx.TryGetValue("@stun", out var st) && HasDotaFx(st[0].Fx))
            {
                if (!_stunFx.TryGetValue(h.Id, out var p) || !p.Fx.IsValid)
                {
                    var np = SpawnDotaFx(st[0].Fx, head, head, -1, null);
                    if (np != null) _stunFx[h.Id] = np;
                }
                else p.Fx.Teleport(head, null, null);
            }
            if (_heroLevelSeen.TryGetValue(h.Id, out var lv) && h.Level > lv && h.Visible && AbilityFx.TryGetValue("@levelup", out var lu) && HasDotaFx(lu[0].Fx))
            {
                var p = SpawnDotaFx(lu[0].Fx, new Vector(h.X, h.Y, HeroFeetZ(h)), new Vector(h.X, h.Y, HeroFeetZ(h)), -1, null);
                if (p != null) { p.Arrived = true; p.RemoveAt = Server.CurrentTime + 4f; _projs.Add(p); }
            }
            _heroLevelSeen[h.Id] = h.Level;
        }
    }

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

    private Proj? SpawnDotaFx(string effect, Vector at, Vector? cp1, float cp2x) =>
        SpawnDotaFx(effect, at, cp1, cp2x > 0 ? 2 : -1, cp2x > 0 ? new Vector(cp2x, 0, 0) : null);

    // CP0 = at; CP1 = a helper entity at cp1 (moved later for moving targets); dataCp = one more control point given as a value
    private Proj? SpawnDotaFx(string effect, Vector at, Vector? cp1, int dataCp, Vector? dataVal)
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
            if (dataCp >= 0 && dataVal != null) { fx.DataCP = dataCp; fx.DataCPValue.X = dataVal.X; fx.DataCPValue.Y = dataVal.Y; fx.DataCPValue.Z = dataVal.Z; }
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
