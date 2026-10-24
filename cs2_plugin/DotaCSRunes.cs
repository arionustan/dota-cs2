// DotaCS: Dota runes and lotus pools in CS2. Runes spawn on the real Dota rune spots; touching one
// gives a CS player its effect (shown on screen with a timer). Lotus pools grow lotuses that heal.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private record RuneKind(string Id, string Name, string Model, string Sound, float Duration, System.Drawing.Color Color, string Html);

    private static readonly RuneKind[] PowerRunes =
    {
        new("haste", "Ускорение", "rune_haste01", "Rune.Haste", 22f, System.Drawing.Color.FromArgb(255, 255, 60, 40), "#ff5040"),
        new("dd", "Двойной урон", "rune_doubledamage01", "Rune.DD", 45f, System.Drawing.Color.FromArgb(255, 60, 120, 255), "#4080ff"),
        new("regen", "Регенерация", "rune_regeneration01", "Rune.Regen", 20f, System.Drawing.Color.FromArgb(255, 60, 255, 80), "#40ff60"),
        new("invis", "Невидимость в Доте", "rune_invisibility01", "Rune.Invis", 45f, System.Drawing.Color.FromArgb(255, 180, 120, 255), "#b080ff"),
        new("arcane", "Чародейство: все гранаты", "rune_arcane", "Rune.Arcane", 0f, System.Drawing.Color.FromArgb(255, 255, 80, 255), "#ff60ff"),
        new("shield", "Щит: +50 HP и броня", "rune_shield01", "Rune.Regen", 0f, System.Drawing.Color.FromArgb(255, 255, 210, 80), "#ffd050"),
    };
    private static readonly RuneKind BountyRune = new("bounty", "Богатство: +500$", "rune_goldxp", "Rune.Bounty", 0f, System.Drawing.Color.FromArgb(255, 255, 190, 40), "#ffc030");
    private static readonly RuneKind WaterRune = new("water", "Вода: +40 HP", "rune_water", "Rune.Water", 0f, System.Drawing.Color.FromArgb(255, 60, 180, 255), "#40b0ff");

    // Dota 7.41 rune spots (dota_item_rune_spawner_*)
    private static readonly RuneKind WisdomRune = new("wisdom", "Мудрость: +900 опыта", "rune_goldxp", "Rune.Arcane", 0f, System.Drawing.Color.FromArgb(255, 170, 90, 255), "#b070ff");

    // Dota 7.41 rune spots (dota_item_rune_spawner_*) and wisdom shrines (npc_dota_xp_fountain). Type: p power, b bounty, w wisdom
    private static readonly (float X, float Y, float Z, char Type)[] RuneSpots =
    {
        (-1640f, 1112f, 41f, 'p'), (1180f, -1216f, 57f, 'p'),
        (-996f, 4431f, 169f, 'b'), (595f, -4660f, 169f, 'b'),
        (-8088f, 768f, 39f, 'w'), (8167f, -1142f, 38f, 'w'),
    };
    private const float WisdomRuneEvery = 420f;   // Dota: every 7 minutes
    private const float PowerRuneEvery = 90f, BountyRuneEvery = 120f, RuneTouch = 85f;

    private class RuneProp { public RuneKind Kind = null!; public CDynamicProp? Prop; public COmniLight? Light; public CPointWorldText? Label; }
    private readonly Dictionary<int, RuneProp> _runes = new();
    private readonly Dictionary<int, float> _runeNext = new();
    private readonly Dictionary<(int Slot, string Id), float> _runeUntil = new();
    private float _runeHudNext;
    private static readonly Random Rng = new();

    private static string FxModel(string n) => $"models/dota_fx/{n}/{n}.vmdl";

    private static void PrecacheRunes(ResourceManifest m)
    {
        foreach (var r in PowerRunes) m.AddResource(FxModel(r.Model));
        m.AddResource(FxModel(BountyRune.Model)); m.AddResource(FxModel(WaterRune.Model));
        m.AddResource(FxModel("fountain_of_life_update")); m.AddResource(FxModel("fountain_of_life_consumable"));
    }

    private bool RuneActive(int slot, string id) => _runeUntil.TryGetValue((slot, id), out var t) && Server.CurrentTime < t;

    // double damage rune: CS damage to Dota counts twice
    private float DmgMult(int slot) => (RuneActive(slot, "dd") ? 2f : 1f) * LevelDmg(slot);

    private void UpdateRunes()
    {
        var now = Server.CurrentTime;
        var humans = Utilities.GetPlayers().Where(p => p.IsValid && !p.IsBot && p.PawnIsAlive && p.PlayerPawn.Value != null && !IsHolding(p.Slot)).ToList();

        for (var i = 0; i < RuneSpots.Length; i++)
        {
            var s = RuneSpots[i];
            if (!_runes.ContainsKey(i))
            {
                if (!_runeNext.TryGetValue(i, out var at)) _runeNext[i] = at = now + (s.Type == 'w' ? WisdomRuneEvery : 5f);
                if (now >= at) SpawnRune(i, s.Type == 'p' ? (Rng.Next(8) == 0 ? WaterRune : PowerRunes[Rng.Next(PowerRunes.Length)]) : s.Type == 'w' ? WisdomRune : BountyRune);
                continue;
            }
            foreach (var p in humans)
            {
                var o = p.PlayerPawn.Value!.AbsOrigin;
                if (o == null || Dist2(s.X, s.Y, o) > RuneTouch * RuneTouch || Math.Abs(o.Z - s.Z) > 100) continue;
                PickRune(p, i);
                break;
            }
        }

        // effects that last
        foreach (var p in humans)
        {
            var pawn = p.PlayerPawn.Value!;
            if (RuneActive(p.Slot, "haste") && pawn.VelocityModifier < 1.45f)
            {
                pawn.VelocityModifier = 1.45f;
                Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_flVelocityModifier");
            }
            if (RuneActive(p.Slot, "regen") && pawn.Health < MaxHp(pawn) && (int)(now * 4) != (int)((now - Interval) * 4))
            {
                pawn.Health = Math.Min(MaxHp(pawn), pawn.Health + Math.Max(3, MaxHp(pawn) * 3 / 100));
                Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
            }
        }

        // on-screen timer for runes that last
        if (now >= _runeHudNext)
        {
            _runeHudNext = now + 0.5f;
            foreach (var p in humans)
            {
                var parts = new List<string>();
                foreach (var r in PowerRunes)
                    if (r.Duration > 0 && _runeUntil.TryGetValue((p.Slot, r.Id), out var t) && t > now)
                        parts.Add($"<font color='{r.Html}'>{r.Name}: {Math.Ceiling(t - now)} с</font>");
                if (parts.Count > 0) p.PrintToCenterHtml(string.Join("<br>", parts), 1);
            }
        }
        UpdateLotus(humans);
    }

    private void SpawnRune(int i, RuneKind kind)
    {
        var s = RuneSpots[i];
        var r = new RuneProp { Kind = kind };
        try
        {
            var prop = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
            if (prop != null)
            {
                prop.Collision.SolidType = SolidType_t.SOLID_NONE;
                prop.DispatchSpawn();
                prop.SetModel(FxModel(kind.Model));
                SetPropScale(prop, 1.6f);   // a bit bigger than in Dota, easy to spot from a CS player's height
                prop.Teleport(new Vector(s.X, s.Y, s.Z + 30), new QAngle(0, Rng.Next(360), 0), null);
                prop.AcceptInput("SetAnimation", null, null, "idle");
                prop.AcceptInput("SetDefaultAnimation", null, null, "idle");
                prop.Glow.GlowColorOverride = kind.Color;
                prop.Glow.GlowRange = 3000; prop.Glow.GlowRangeMin = 0; prop.Glow.GlowTeam = -1; prop.Glow.GlowType = 3;
                Utilities.SetStateChanged(prop, "CBaseModelEntity", "m_Glow");
                r.Prop = prop;
            }
            var l = Utilities.CreateEntityByName<COmniLight>("light_omni2");
            if (l != null)
            {
                l.Color = kind.Color; l.Brightness = 6f; l.Range = 420f; l.CastShadows = 0; l.Enabled = true;
                l.DispatchSpawn();
                l.Teleport(new Vector(s.X, s.Y, s.Z + 60), null, null);
                r.Light = l;
            }
        }
        catch (Exception e) { Logger.LogWarning("DotaCS rune: {Error}", e.Message); }
        try
        {
            var t = Utilities.CreateEntityByName<CPointWorldText>("point_worldtext");
            if (t != null)
            {
                t.MessageText = "РУНА: " + kind.Name;
                t.Enabled = true; t.Fullbright = true;
                t.FontSize = 60; t.WorldUnitsPerPx = 0.22f;
                t.Color = kind.Color;
                t.JustifyHorizontal = PointWorldTextJustifyHorizontal_t.POINT_WORLD_TEXT_JUSTIFY_HORIZONTAL_CENTER;
                t.JustifyVertical = PointWorldTextJustifyVertical_t.POINT_WORLD_TEXT_JUSTIFY_VERTICAL_CENTER;
                t.ReorientMode = PointWorldTextReorientMode_t.POINT_WORLD_TEXT_REORIENT_AROUND_UP;
                t.DispatchSpawn();
                t.Teleport(new Vector(s.X, s.Y, s.Z + 110), null, null);
                r.Label = t;
            }
        }
        catch (Exception e) { Logger.LogWarning("DotaCS rune: {Error}", e.Message); }
        _runes[i] = r;
        if (s.Type != 'b') Announce($" {ChatColors.Gold}Появилась руна:{ChatColors.Default} {kind.Name}");
    }

    private void PickRune(CCSPlayerController p, int i)
    {
        var r = _runes[i];
        _runes.Remove(i);
        if (r.Prop != null && r.Prop.IsValid) r.Prop.Remove();
        if (r.Light != null && r.Light.IsValid) r.Light.Remove();
        if (r.Label != null && r.Label.IsValid) r.Label.Remove();
        var s = RuneSpots[i];
        _runeNext[i] = Server.CurrentTime + (s.Type == 'p' ? PowerRuneEvery : s.Type == 'w' ? WisdomRuneEvery : BountyRuneEvery);
        var pawn = p.PlayerPawn.Value!;
        var k = r.Kind;
        PlayDotaSound(k.Sound, new Vector(s.X, s.Y, s.Z + 40));

        switch (k.Id)
        {
            case "bounty":
                var money = p.InGameMoneyServices;
                if (money != null) { money.Account += 500; Utilities.SetStateChanged(p, "CCSPlayerController", "m_pInGameMoneyServices"); }
                break;
            case "wisdom":
                AddXp(p, 900);
                break;
            case "water":
                pawn.Health = Math.Min(MaxHp(pawn), pawn.Health + 40); Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
                break;
            case "shield":
                pawn.Health = Math.Max(pawn.Health, MaxHp(pawn)) + 50; Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
                pawn.ArmorValue = 100; Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_ArmorValue");
                break;
            case "arcane":
                foreach (var g in new[] { "weapon_hegrenade", "weapon_flashbang", "weapon_smokegrenade", "weapon_molotov" }) p.GiveNamedItem(g);
                break;
            case "invis":
                var o = pawn.AbsOrigin!;
                _hits.Enqueue(string.Format(Inv, "G invis {0:F0} {1:F0} {2:F0} {3}", o.X, o.Y, o.Z, p.Slot));
                break;
        }
        if (k.Duration > 0) _runeUntil[(p.Slot, k.Id)] = Server.CurrentTime + k.Duration;
        p.PrintToCenterHtml($"<font color='{k.Html}' class='fontSize-l'>РУНА: {k.Name}</font>", 3);
        Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} взял руну: {k.Name}");
    }

    // ------------------------------------------------------------ lotus pools
    private static readonly (float X, float Y, float Z)[] LotusPools = { (-7548f, 4209f, 98f), (7504f, -4404f, 101f) };
    private const int LotusMax = 3;
    private const float LotusGrow = 60f, LotusTouch = 150f;
    private readonly int[] _lotusCount = new int[2];
    private readonly float[] _lotusNext = new float[2];
    private readonly CDynamicProp?[] _poolProp = new CDynamicProp?[2];
    private readonly List<CDynamicProp>[] _lotusProps = { new(), new() };

    private void UpdateLotus(List<CCSPlayerController> humans)
    {
        var now = Server.CurrentTime;
        for (var i = 0; i < LotusPools.Length; i++)
        {
            var pool = LotusPools[i];
            if (_poolProp[i] == null || !_poolProp[i]!.IsValid)
            {
                try
                {
                    var prop = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
                    if (prop == null) continue;
                    prop.Collision.SolidType = SolidType_t.SOLID_NONE;
                    prop.DispatchSpawn();
                    prop.SetModel(FxModel("fountain_of_life_update"));
                    prop.Teleport(new Vector(pool.X, pool.Y, pool.Z), new QAngle(0, 0, 0), null);
                    prop.AcceptInput("SetAnimation", null, null, "idle");
                    prop.AcceptInput("SetDefaultAnimation", null, null, "idle");
                    _poolProp[i] = prop;
                    _lotusNext[i] = now + LotusGrow;
                    _lotusCount[i] = 1;
                    SyncLotusProps(i);
                }
                catch { continue; }
            }
            if (_lotusCount[i] < LotusMax && now >= _lotusNext[i])
            {
                _lotusCount[i]++; _lotusNext[i] = now + LotusGrow;
                SyncLotusProps(i);
            }
            if (_lotusCount[i] == 0) continue;
            foreach (var p in humans)
            {
                var pawn = p.PlayerPawn.Value!;
                var o = pawn.AbsOrigin;
                if (o == null || Dist2(pool.X, pool.Y, o) > LotusTouch * LotusTouch || pawn.Health >= MaxHp(pawn)) continue;
                _lotusCount[i]--; if (_lotusCount[i] == LotusMax - 1) _lotusNext[i] = now + LotusGrow;
                SyncLotusProps(i);
                pawn.Health = MaxHp(pawn); Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
                PlayDotaSound("Lotus.Heal", new Vector(pool.X, pool.Y, pool.Z + 40));
                p.PrintToCenterHtml("<font color='#ff9ad0' class='fontSize-l'>Лотос: здоровье восстановлено</font>", 3);
                break;
            }
        }
    }

    // flowers sit on the pool, one per lotus that has grown
    private void SyncLotusProps(int i)
    {
        var pool = LotusPools[i];
        var list = _lotusProps[i];
        while (list.Count > _lotusCount[i]) { var x = list[^1]; list.RemoveAt(list.Count - 1); if (x.IsValid) x.Remove(); }
        while (list.Count < _lotusCount[i])
        {
            try
            {
                var k = list.Count;
                var a = k * 2.1f;
                var prop = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
                if (prop == null) return;
                prop.Collision.SolidType = SolidType_t.SOLID_NONE;
                prop.DispatchSpawn();
                prop.SetModel(FxModel("fountain_of_life_consumable"));
                prop.Teleport(new Vector(pool.X + MathF.Cos(a) * 55, pool.Y + MathF.Sin(a) * 55, pool.Z + 8), new QAngle(0, k * 120, 0), null);
                prop.AcceptInput("SetAnimation", null, null, "idle");
                prop.AcceptInput("SetDefaultAnimation", null, null, "idle");
                prop.Glow.GlowColorOverride = System.Drawing.Color.FromArgb(255, 255, 140, 200);
                prop.Glow.GlowRange = 700; prop.Glow.GlowRangeMin = 0; prop.Glow.GlowTeam = -1; prop.Glow.GlowType = 3;
                Utilities.SetStateChanged(prop, "CBaseModelEntity", "m_Glow");
                list.Add(prop);
            }
            catch { return; }
        }
    }
}
