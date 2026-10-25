// DotaCS: what a Dota hero has and a CS player didn't. Levels and experience, gold for last hits,
// respawn timer and buyback, teleport to towers, salve and wards, Aegis and Tormentor shard,
// outposts and watchers, wisdom runes, the Radiant fountain shooting back, water splashes,
// map bounds, chat between the games and K/D in both scoreboards.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Cvars;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private class CsHero
    {
        public int Level = 1, Xp, Kills, Deaths, Salves, Wards;
        public bool Shard;
        public float RespawnAt, AegisUntil, BuybackReady, TpReady, NextIncome;
        public Vector? DeathPos;
        public bool Holding, AegisRevive;
        // channels
        public string? TpLane; public Vector? TpTarget; public float TpStart; public Vector? TpFrom;
        public float SalveUntil, SalveNext; public int SalveLastHp;
        public Vector? SafePos; public float SafeNext, WaterNext;
        public int CaptureSpot = -1; public float CaptureStart;
    }

    private readonly Dictionary<int, CsHero> _csHero = new();
    private CsHero Hero(int slot) { if (!_csHero.TryGetValue(slot, out var h)) _csHero[slot] = h = new CsHero(); return h; }

    // Dota experience table (total XP needed for each level)
    private static readonly int[] XpTable =
    {
        0, 240, 640, 1160, 1760, 2440, 3200, 4000, 4900, 5900, 7000, 8200, 9500, 10900, 12400,
        14000, 15700, 17500, 19400, 21400, 23600, 26000, 28600, 31400, 34400,
    };
    private const int GoldToMoney = 3;            // 1 Dota gold = $3 in CS
    private const int IncomePerSecond = 4;        // passive income, like Dota's passive gold
    private const float TpChannel = 3f, TpCooldown = 60f; private const int TpCost = 300;
    private const int SalveCost = 330, WardCost = 150, MaxWards = 2;
    private const float BuybackCooldown = 300f;
    private const float CaptureTime = 3f, CaptureRadius = 230f;
    private static readonly Vector RadiantFountain = new(-7456, -6938, 393);
    private const float RadiantFountainRadius = 1200f;
    private const float WaterZ = 95f;            // below this height you are in the river
    private const float MapEdge = 8700f;

    private static readonly Vector[] SecretShops = { new(4886, -1208, 124), new(-5080, 1948, 123) };
    private const float ShopRadius = 600f;

    // outposts and watchers (lanterns) of the 7.41 map
    private static readonly (string Name, Vector Pos)[] CaptureSpots =
    {
        ("Аутпост", new(-4096, -448, 256)), ("Аутпост", new(3392, -448, 256)),
        ("Фонарь", new(7918, -1524, 21)), ("Фонарь", new(-6464, 6656, 151)), ("Фонарь", new(2718, -657, 256)),
        ("Фонарь", new(-3484, 34, 256)), ("Фонарь", new(1032, -4260, 256)), ("Фонарь", new(6528, -6592, 138)),
        ("Фонарь", new(768, -7648, 128)), ("Фонарь", new(-671, 7130, 128)), ("Фонарь", new(-1527, 3926, 256)),
        ("Фонарь", new(-7808, 1056, 17)),
    };
    private readonly Dictionary<int, float> _captured = new();

    private static int LevelFor(int xp) { var l = 1; while (l < XpTable.Length && xp >= XpTable[l]) l++; return l; }
    private static int MaxHpFor(CsHero h) => 100 + (h.Level - 1) * 15 + (h.Shard ? 50 : 0);
    private float LevelDmg(int slot) { var h = Hero(slot); return (1f + (h.Level - 1) * 0.04f) * (h.Shard ? 1.15f : 1f); }
    private static float RespawnTime(int level) => Math.Min(4f + level * 2f, 60f);
    private static int BuybackCost(int level) => 600 + level * 120;
    private bool IsHolding(int slot) => _csHero.TryGetValue(slot, out var h) && h.Holding;

    private void RegisterProgress()
    {
        AddCommand("css_tp", "teleport to a tower: top / mid / bot / base", (p, i) => { if (p != null) StartTp(p, i.ArgCount > 1 ? i.GetArg(1) : "mid"); });
        AddCommand("css_3p", "third person", (p, _) => p?.PrintToChat($" {ChatColors.Gold}Третье лицо:{ChatColors.Default} нажми F6 (ещё раз F6 вернёт первое лицо)"));
        AddCommand("css_bb", "buyback", (p, _) => { if (p != null) Buyback(p); });
        AddCommand("css_salve", "use a healing salve", (p, _) => { if (p != null) UseSalve(p); });
        AddCommand("css_ward", "place an observer ward", (p, _) => { if (p != null) PlaceWard(p); });
        AddCommand("css_buy", "buy salve / ward", (p, i) => { if (p != null) BuyItem(p, i.ArgCount > 1 ? i.GetArg(1) : ""); });
        AddCommand("css_inv", "level and items", (p, _) => { if (p != null) ShowInv(p); });
        AddCommand("css_money", "test: +$16000", (p, _) =>
        {
            if (p == null) return;
            if (ConVar.Find("sv_cheats")?.GetPrimitiveValue<bool>() != true) { p.PrintToChat(" Только с sv_cheats 1"); return; }
            AddMoney(p, 16000);
        });
        AddCommand("css_gun", "buy a gun for either team: ak47 / awp / m4 / deagle", (p, i) => { if (p != null) BuyGun(p, i.ArgCount > 1 ? i.GetArg(1) : "ak47"); });
        AddCommandListener("say", OnSay);
        AddCommandListener("say_team", OnSay);
        RegisterEventHandler<EventPlayerDeath>(OnHumanDeath);
        AddTimer(1f, ProgressSecond, CounterStrikeSharp.API.Modules.Timers.TimerFlags.REPEAT);
    }

    // CS "buy" refuses guns of the other team (a CT cannot buy an AK), so F1-F5 go through here
    private static readonly Dictionary<string, (string Item, int Price, bool Primary)> Guns = new()
    {
        ["ak47"] = ("weapon_ak47", 2700, true), ["awp"] = ("weapon_awp", 4750, true),
        ["m4"] = ("weapon_m4a1_silencer", 2900, true), ["deagle"] = ("weapon_deagle", 700, false),
    };
    private static readonly string[] Primaries = { "weapon_ak47", "weapon_awp", "weapon_m4a1_silencer", "weapon_m4a1", "weapon_famas", "weapon_galilar", "weapon_ssg08", "weapon_mp9", "weapon_mac10", "weapon_nova" };
    private static readonly string[] Pistols = { "weapon_deagle", "weapon_usp_silencer", "weapon_hkp2000", "weapon_glock", "weapon_p250", "weapon_fiveseven", "weapon_tec9" };

    private void BuyGun(CCSPlayerController p, string name)
    {
        var pawn = p.PlayerPawn.Value;
        if (!p.PawnIsAlive || pawn?.AbsOrigin == null || !Guns.TryGetValue(name.ToLowerInvariant(), out var g)) return;
        if (!AtShop(pawn.AbsOrigin)) { p.PrintToCenter("Закупка только на фонтане Тьмы или в секретной лавке"); return; }
        var m = p.InGameMoneyServices;
        if (m == null || m.Account < g.Price) { p.PrintToCenter($"Не хватает денег: нужно ${g.Price}"); return; }
        foreach (var w in g.Primary ? Primaries : Pistols) p.RemoveItemByDesignerName(w);
        p.GiveNamedItem(g.Item);
        if (g.Primary && pawn.ArmorValue < 100) { p.GiveNamedItem("item_assaultsuit"); }
        AddMoney(p, -g.Price);
    }

    // ------------------------------------------------------------ money, xp, levels
    private void AddMoney(CCSPlayerController p, int amount)
    {
        var m = p.InGameMoneyServices;
        if (m == null) return;
        m.Account = Math.Clamp(m.Account + amount, 0, 60000);
        Utilities.SetStateChanged(p, "CCSPlayerController", "m_pInGameMoneyServices");
    }

    private bool Spend(CCSPlayerController p, int amount, string what)
    {
        var m = p.InGameMoneyServices;
        if (m == null || m.Account < amount) { p.PrintToChat($" {ChatColors.Red}Не хватает денег:{ChatColors.Default} {what} стоит ${amount}"); return false; }
        AddMoney(p, -amount);
        return true;
    }

    private void AddXp(CCSPlayerController p, int xp)
    {
        var h = Hero(p.Slot);
        h.Xp += xp;
        var lvl = LevelFor(h.Xp);
        if (lvl <= h.Level) return;
        var oldMax = MaxHpFor(h);
        h.Level = lvl;
        var pawn = p.PlayerPawn.Value;
        if (pawn != null && pawn.IsValid && p.PawnIsAlive && !h.Holding)
        {
            ApplyMaxHp(pawn, h);
            pawn.Health = Math.Min(MaxHpFor(h), pawn.Health + (MaxHpFor(h) - oldMax));
            Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
            if (pawn.AbsOrigin != null) PlayDotaSound("Rune.Arcane", new Vector(pawn.AbsOrigin.X, pawn.AbsOrigin.Y, pawn.AbsOrigin.Z + 40));
        }
        p.PrintToCenterHtml($"<font color='#ffd040' class='fontSize-xl'>УРОВЕНЬ {lvl}</font><br><font color='#a0ffa0'>{MaxHpFor(h)} HP, урон +{(int)Math.Round((LevelDmg(p.Slot) - 1) * 100)}%</font>", 3);
        Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} получил {ChatColors.Gold}{lvl} уровень");
    }

    private static void ApplyMaxHp(CCSPlayerPawn pawn, CsHero h)
    {
        var max = MaxHpFor(h);
        if (pawn.MaxHealth == max) return;
        pawn.MaxHealth = max;
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iMaxHealth");
    }

    private static int MaxHp(CCSPlayerPawn pawn) => Math.Max(pawn.MaxHealth, 100);

    // E R slot gold xp unit : a CS player got the last hit on something in Dota
    private void OnReward(string[] e)
    {
        var p = PlayerBySlot((int)F(e[2]));
        if (p == null || !p.IsValid) return;
        var gold = (int)F(e[3]); var xp = (int)F(e[4]);
        AddMoney(p, gold * GoldToMoney);
        AddXp(p, xp);
        p.PrintToChat($" {ChatColors.Gold}+${gold * GoldToMoney}{ChatColors.Default} и {ChatColors.Green}+{xp} опыта{ChatColors.Default} ({Pretty(e.Length > 5 ? e[5] : "крип")})");
    }

    private void OnAegis(string[] e)
    {
        var p = PlayerBySlot((int)F(e[2]));
        if (p == null || !p.IsValid) return;
        Hero(p.Slot).AegisUntil = Server.CurrentTime + 300f;
        Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} убил Рошана и взял {ChatColors.Gold}Аегис{ChatColors.Default} (лишняя жизнь на 5 минут)");
        p.PrintToCenterHtml("<font color='#ffd040' class='fontSize-xl'>АЕГИС</font><br>Следующая смерть не считается", 4);
    }

    private void OnShard(string[] e)
    {
        var p = PlayerBySlot((int)F(e[2]));
        if (p == null || !p.IsValid) return;
        var h = Hero(p.Slot);
        if (h.Shard) { AddMoney(p, 1500); p.PrintToChat(" Тормент: шард уже есть, вместо него +$1500"); return; }
        h.Shard = true;
        var pawn = p.PlayerPawn.Value;
        if (pawn != null && pawn.IsValid) { ApplyMaxHp(pawn, h); pawn.Health += 50; Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth"); }
        Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} убил Тормента: {ChatColors.Gold}+50 HP и +15% урона навсегда");
    }

    // ------------------------------------------------------------ death, respawn timer, buyback, aegis
    private HookResult OnHumanDeath(EventPlayerDeath ev, GameEventInfo info)
    {
        var p = ev.Userid;
        if (p == null || !p.IsValid || p.IsBot) return HookResult.Continue;
        var h = Hero(p.Slot);
        var now = Server.CurrentTime;
        h.TpLane = null; h.SalveUntil = 0;
        var o = p.PlayerPawn.Value?.AbsOrigin;
        h.DeathPos = o != null ? new Vector(o.X, o.Y, o.Z) : null;
        if (now < h.AegisUntil)
        {
            h.AegisUntil = 0; h.AegisRevive = true;
            h.RespawnAt = now + 3f;
            Announce($" {ChatColors.Gold}Аегис{ChatColors.Default} спас {ChatColors.Blue}{p.PlayerName}");
            return HookResult.Continue;
        }
        h.AegisRevive = false;
        h.Deaths++;
        h.RespawnAt = now + RespawnTime(h.Level);
        return HookResult.Continue;
    }

    // called from OnPlayerSpawn: keeps a player out of the game until his respawn time
    private bool ProgressOnSpawn(CCSPlayerController p, CCSPlayerPawn pawn)
    {
        var h = Hero(p.Slot);
        ApplyMaxHp(pawn, h);
        pawn.Health = MaxHpFor(h);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
        if (Server.CurrentTime >= h.RespawnAt) { h.Holding = false; return false; }
        h.Holding = true;
        pawn.TakesDamage = false;
        pawn.Teleport(new Vector(DireFountain.X - 400, DireFountain.Y - 400, DireFountain.Z + 2600), new QAngle(60, 225, 0), new Vector(0, 0, 0));
        SetFrozen(pawn, true);
        return true;
    }

    private void Release(CCSPlayerController p, bool atDeath)
    {
        var h = Hero(p.Slot);
        h.Holding = false;
        var pawn = p.PlayerPawn.Value;
        if (pawn == null || !pawn.IsValid || !p.PawnIsAlive) return;
        pawn.TakesDamage = true;
        SetFrozen(pawn, false);
        var spot = atDeath && h.DeathPos != null ? h.DeathPos : DireSpawns[_spawnIndex++ % DireSpawns.Length];
        pawn.Teleport(new Vector(spot.X, spot.Y, spot.Z + 10), new QAngle(0, 225, 0), new Vector(0, 0, 0));
        pawn.Health = MaxHpFor(h);
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
        PlayStinger("respawn");
    }

    private void Buyback(CCSPlayerController p)
    {
        var h = Hero(p.Slot);
        var now = Server.CurrentTime;
        if (!h.Holding) { p.PrintToChat(" Байбек работает только пока ждёшь возрождения"); return; }
        if (now < h.BuybackReady) { p.PrintToChat($" Байбек перезаряжается: ещё {Math.Ceiling(h.BuybackReady - now)} с"); return; }
        if (!Spend(p, BuybackCost(h.Level), "Байбек")) return;
        h.BuybackReady = now + BuybackCooldown;
        h.RespawnAt = now;
        Release(p, false);
        Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} сделал {ChatColors.Gold}байбек");
    }

    // ------------------------------------------------------------ teleport to towers
    private Vector? TpTargetFor(string lane)
    {
        lane = lane.ToLowerInvariant();
        if (lane is "base" or "fountain" or "база") return new Vector(DireSpawns[0].X, DireSpawns[0].Y, DireSpawns[0].Z);
        if (lane is "top" or "верх") lane = "top"; else if (lane is "bot" or "низ") lane = "bot"; else lane = "mid";
        for (var tier = 1; tier <= 3; tier++)
        {
            var b = _buildings.FirstOrDefault(x => x.Alive && x.Name == $"badguys_tower{tier}_{lane}");
            if (b == null) continue;
            // stand a bit behind the tower, towards the Dire base
            var dx = DireFountain.X - b.X; var dy = DireFountain.Y - b.Y; var len = MathF.Max(MathF.Sqrt(dx * dx + dy * dy), 1);
            return new Vector(b.X + dx / len * 260, b.Y + dy / len * 260, b.Z + 20);
        }
        var t4 = _buildings.FirstOrDefault(x => x.Alive && x.Name.StartsWith("badguys_tower4"));
        return t4 != null ? new Vector(t4.X + 200, t4.Y + 200, t4.Z + 20) : new Vector(DireSpawns[0].X, DireSpawns[0].Y, DireSpawns[0].Z);
    }

    private void StartTp(CCSPlayerController p, string lane)
    {
        var h = Hero(p.Slot);
        var pawn = p.PlayerPawn.Value;
        var now = Server.CurrentTime;
        if (pawn == null || !p.PawnIsAlive || h.Holding || pawn.AbsOrigin == null) return;
        if (now < h.TpReady) { p.PrintToChat($" Телепорт перезаряжается: ещё {Math.Ceiling(h.TpReady - now)} с"); return; }
        var target = TpTargetFor(lane);
        if (target == null) return;
        if (!Spend(p, TpCost, "Телепорт")) return;
        h.TpLane = lane; h.TpTarget = target; h.TpStart = now;
        h.TpFrom = new Vector(pawn.AbsOrigin.X, pawn.AbsOrigin.Y, pawn.AbsOrigin.Z);
        PlayDotaSound("Rune.Haste", new Vector(pawn.AbsOrigin.X, pawn.AbsOrigin.Y, pawn.AbsOrigin.Z + 40));
    }

    // ------------------------------------------------------------ items: salve, ward
    private bool AtShop(Vector pos) =>
        Dist2(pos, DireFountain) < FountainRadius * FountainRadius || SecretShops.Any(s => Dist2(pos, s) < ShopRadius * ShopRadius);

    private void BuyItem(CCSPlayerController p, string what)
    {
        var pos = p.PlayerPawn.Value?.AbsOrigin;
        if (pos == null) return;
        if (!AtShop(pos)) { p.PrintToChat(" Покупать можно на фонтане или в секретной лавке"); return; }
        var h = Hero(p.Slot);
        switch (what.ToLowerInvariant())
        {
            case "salve": case "хилка":
                if (!Spend(p, SalveCost, "Хилка")) return;
                h.Salves++; break;
            case "ward": case "вард":
                if (h.Wards >= MaxWards) { p.PrintToChat($" Больше {MaxWards} вардов не унести"); return; }
                if (!Spend(p, WardCost, "Вард")) return;
                h.Wards++; break;
            default:
                p.PrintToChat($" Купить: {ChatColors.Green}!buy salve{ChatColors.Default} (${SalveCost}) или {ChatColors.Green}!buy ward{ChatColors.Default} (${WardCost})"); return;
        }
        PlayDotaSound("Rune.Bounty", new Vector(pos.X, pos.Y, pos.Z + 40));
        ShowInv(p);
    }

    private void UseSalve(CCSPlayerController p)
    {
        var h = Hero(p.Slot);
        var pawn = p.PlayerPawn.Value;
        if (pawn == null || !p.PawnIsAlive || h.Holding) return;
        if (h.Salves == 0)
        {
            if (pawn.AbsOrigin != null && AtShop(pawn.AbsOrigin)) BuyItem(p, "salve");
            if (h.Salves == 0) { p.PrintToChat(" Хилок нет. Купи на фонтане или в секретной лавке: !buy salve"); return; }
        }
        if (pawn.Health >= MaxHp(pawn)) { p.PrintToChat(" Здоровье и так полное"); return; }
        h.Salves--;
        h.SalveUntil = Server.CurrentTime + 8f; h.SalveNext = 0; h.SalveLastHp = pawn.Health;
        if (pawn.AbsOrigin != null) PlayDotaSound("Lotus.Heal", new Vector(pawn.AbsOrigin.X, pawn.AbsOrigin.Y, pawn.AbsOrigin.Z + 40));
        p.PrintToCenterHtml("<font color='#60ff80'>Хилка: лечит 8 секунд, урон её сбивает</font>", 2);
    }

    private void PlaceWard(CCSPlayerController p)
    {
        var h = Hero(p.Slot);
        var pawn = p.PlayerPawn.Value;
        var o = pawn?.AbsOrigin;
        if (pawn == null || o == null || !p.PawnIsAlive || h.Holding) return;
        if (h.Wards == 0)
        {
            if (AtShop(o)) BuyItem(p, "ward");
            if (h.Wards == 0) { p.PrintToChat(" Вардов нет. Купи на фонтане или в секретной лавке: !buy ward"); return; }
        }
        h.Wards--;
        _hits.Enqueue(string.Format(Inv, "G ward {0:F0} {1:F0} {2:F0} {3}", o.X, o.Y, o.Z, p.Slot));
        SpawnWardMarker(new Vector(o.X, o.Y, o.Z));
        p.PrintToChat($" {ChatColors.Green}Вард поставлен:{ChatColors.Default} 6 минут обзора в радиусе 1600 (герои рядом будут видны)");
    }

    private void SpawnWardMarker(Vector at)
    {
        try
        {
            var t = Utilities.CreateEntityByName<CPointWorldText>("point_worldtext");
            if (t == null) return;
            t.MessageText = "ВАРД"; t.Enabled = true; t.Fullbright = true;
            t.FontSize = 50; t.WorldUnitsPerPx = 0.2f;
            t.Color = System.Drawing.Color.FromArgb(255, 255, 220, 80);
            t.JustifyHorizontal = PointWorldTextJustifyHorizontal_t.POINT_WORLD_TEXT_JUSTIFY_HORIZONTAL_CENTER;
            t.ReorientMode = PointWorldTextReorientMode_t.POINT_WORLD_TEXT_REORIENT_AROUND_UP;
            t.DispatchSpawn();
            t.Teleport(new Vector(at.X, at.Y, at.Z + 70), null, null);
            var l = Utilities.CreateEntityByName<COmniLight>("light_omni2");
            if (l != null)
            {
                l.Color = System.Drawing.Color.FromArgb(255, 255, 220, 80); l.Brightness = 3f; l.Range = 200f; l.CastShadows = 0; l.Enabled = true;
                l.DispatchSpawn(); l.Teleport(new Vector(at.X, at.Y, at.Z + 40), null, null);
            }
            AddTimer(360f, () => { if (t.IsValid) t.Remove(); if (l != null && l.IsValid) l.Remove(); });
        }
        catch (Exception e) { Logger.LogWarning("DotaCS ward: {Error}", e.Message); }
    }

    private void ShowInv(CCSPlayerController p)
    {
        var h = Hero(p.Slot);
        var next = h.Level < XpTable.Length ? $"{h.Xp}/{XpTable[h.Level]}" : "макс";
        var now = Server.CurrentTime;
        p.PrintToChat($" {ChatColors.Gold}Уровень {h.Level}{ChatColors.Default} (опыт {next}), убийств {h.Kills}, смертей {h.Deaths}");
        p.PrintToChat($" Хилки: {ChatColors.Green}{h.Salves}{ChatColors.Default} (клавиша 7), варды: {ChatColors.Green}{h.Wards}{ChatColors.Default} (клавиша 8)" +
                      (now < h.AegisUntil ? $", {ChatColors.Gold}Аегис {Math.Ceiling(h.AegisUntil - now)} с" : "") + (h.Shard ? ", шард Тормента" : ""));
    }

    // ------------------------------------------------------------ chat between the games
    private HookResult OnSay(CCSPlayerController? p, CommandInfo info)
    {
        if (p == null || !p.IsValid || p.IsBot) return HookResult.Continue;
        var text = info.ArgString.Trim().Trim('"').Trim();
        if (text.Length == 0 || text[0] == '!' || text[0] == '/') return HookResult.Continue;
        text = text.Replace('\n', ' ').Replace('\r', ' ');
        if (text.Length > 120) text = text[..120];
        _hits.Enqueue($"M {Safe(p.PlayerName)} {text}");
        return HookResult.Continue;
    }

    private void OnDotaChat(string[] e)
    {
        if (e.Length < 4) return;
        Announce($" {ChatColors.Red}[Дота] {e[2].Replace('_', ' ')}:{ChatColors.Default} {string.Join(' ', e.Skip(3))}");
    }

    // ------------------------------------------------------------ every tick
    private void UpdateProgress()
    {
        var now = Server.CurrentTime;
        foreach (var p in Utilities.GetPlayers())
        {
            if (p == null || !p.IsValid || p.IsBot || !p.PawnIsAlive) continue;
            var pawn = p.PlayerPawn.Value;
            var o = pawn?.AbsOrigin;
            if (pawn == null || o == null) continue;
            var h = Hero(p.Slot);

            if (h.Holding)
            {
                if (now >= h.RespawnAt) { Release(p, h.AegisRevive); h.AegisRevive = false; continue; }
                if ((int)(now * 4) != (int)((now - Interval) * 4))
                    p.PrintToCenterHtml($"<font color='#ff6060' class='fontSize-l'>Возрождение через {Math.Ceiling(h.RespawnAt - now)} с</font><br>" +
                        $"Байбек: <font color='#ffd040'>!bb</font> или F11 (${BuybackCost(h.Level)})" +
                        (now < h.BuybackReady ? $", перезарядка {Math.Ceiling(h.BuybackReady - now)} с" : ""), 1);
                continue;
            }
            ApplyMaxHp(pawn, h);

            // teleport channel: 3 s standing still
            if (h.TpLane != null && h.TpTarget != null && h.TpFrom != null)
            {
                if (Dist2(o, h.TpFrom) > 60 * 60) { h.TpLane = null; p.PrintToCenterHtml("<font color='#ff6060'>Телепорт сбит: ты сдвинулся</font>", 2); }
                else if (now - h.TpStart >= TpChannel)
                {
                    pawn.Teleport(h.TpTarget, null, new Vector(0, 0, 0));
                    PlayDotaSound("Rune.Haste", new Vector(h.TpTarget.X, h.TpTarget.Y, h.TpTarget.Z + 40));
                    h.TpLane = null; h.TpReady = now + TpCooldown;
                }
                else if ((int)(now * 4) != (int)((now - Interval) * 4))
                    p.PrintToCenterHtml($"<font color='#60c0ff'>Телепорт: {h.TpLane}</font> {Bar((now - h.TpStart) / TpChannel)}", 1);
            }

            // salve: heals 40% max HP over 8 s, damage cancels it
            if (now < h.SalveUntil && now >= h.SalveNext)
            {
                if (pawn.Health < h.SalveLastHp) { h.SalveUntil = 0; p.PrintToCenterHtml("<font color='#ff6060'>Хилку сбили уроном</font>", 2); }
                else
                {
                    h.SalveNext = now + 0.5f;
                    pawn.Health = Math.Min(MaxHp(pawn), pawn.Health + Math.Max(1, (int)(MaxHp(pawn) * 0.4f / 16)));
                    Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
                    h.SalveLastHp = pawn.Health;
                }
            }

            // the Radiant fountain shoots CS players hard
            if (Dist2(o, RadiantFountain) < RadiantFountainRadius * RadiantFountainRadius && (int)(now * 4) != (int)((now - Interval) * 4))
            {
                DrawTracer(new Vector(RadiantFountain.X, RadiantFountain.Y, RadiantFountain.Z + 250), pawn);
                if (pawn.Health <= 35) { pawn.CommitSuicide(false, true); Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} сгорел у фонтана Света"); continue; }
                pawn.Health -= 35; Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
            }

            // outposts and watchers: stand 3 s next to one to take it for the CS team
            var spot = -1;
            for (var i = 0; i < CaptureSpots.Length; i++)
                if (Dist2(o, CaptureSpots[i].Pos) < CaptureRadius * CaptureRadius) { spot = i; break; }
            if (spot < 0 || (_captured.TryGetValue(spot, out var ct) && now < ct)) h.CaptureSpot = -1;
            else if (h.CaptureSpot != spot) { h.CaptureSpot = spot; h.CaptureStart = now; }
            else if (now - h.CaptureStart >= CaptureTime)
            {
                var c = CaptureSpots[spot];
                _hits.Enqueue(string.Format(Inv, "G capture {0:F0} {1:F0} {2:F0} {3}", c.Pos.X, c.Pos.Y, c.Pos.Z, p.Slot));
                _captured[spot] = now + 120f;
                h.CaptureSpot = -1;
                AddXp(p, c.Name == "Аутпост" ? 150 : 50);
                Announce($" {ChatColors.Blue}{p.PlayerName}{ChatColors.Default} захватил: {c.Name} (обзор для КС)");
            }
            else if ((int)(now * 4) != (int)((now - Interval) * 4))
                p.PrintToCenterHtml($"Захват: {CaptureSpots[spot].Name} {Bar((now - h.CaptureStart) / CaptureTime)}", 1);

            // map bounds: never fall out of the map
            var onGround = (pawn.Flags & 1) != 0;
            if (o.Z < -900 || Math.Abs(o.X) > MapEdge || Math.Abs(o.Y) > MapEdge)
            {
                var back = h.SafePos ?? DireSpawns[0];
                pawn.Teleport(back, null, new Vector(0, 0, 0));
                p.PrintToCenter("Край карты");
            }
            else if (onGround && now >= h.SafeNext) { h.SafeNext = now + 1f; h.SafePos = new Vector(o.X, o.Y, o.Z + 10); }

            // river: splashes when you walk in the water
            var v = pawn.AbsVelocity;
            if (onGround && o.Z < WaterZ && v != null && v.X * v.X + v.Y * v.Y > 90 * 90 && now >= h.WaterNext)
            {
                h.WaterNext = now + 0.33f;
                pawn.EmitSound("Player.Wade");
            }
        }
    }

    private static string Bar(float t)
    {
        var n = (int)Math.Clamp(t * 10, 0, 10);
        return "<font color='#60ff80'>" + new string('|', n * 2) + "</font><font color='#555555'>" + new string('|', (10 - n) * 2) + "</font>";
    }

    // ------------------------------------------------------------ every second: income, scoreboard
    private void ProgressSecond()
    {
        try
        {
            foreach (var p in Utilities.GetPlayers())
            {
                if (p == null || !p.IsValid) continue;
                if (!p.IsBot)
                {
                    var h = Hero(p.Slot);
                    if (p.PawnIsAlive && !h.Holding) AddMoney(p, IncomePerSecond);
                    SetScore(p, h.Kills, h.Deaths, 0, h.Level);
                }
                else
                {
                    var heroId = _heroBot.FirstOrDefault(kv => kv.Value == p.Slot).Key;
                    if (heroId != null && _heroes.TryGetValue(heroId, out var hs)) SetScore(p, hs.Kills, hs.Deaths, hs.Assists, hs.Level);
                }
            }
            Diag("progress second");
        }
        catch (Exception e) { Logger.LogWarning("DotaCS progress: {Error}", e.Message); }
    }

    private static void SetScore(CCSPlayerController p, int k, int d, int a, int lvl)
    {
        var tag = $"[ур.{lvl}]";
        if (p.Clan != tag) { p.Clan = tag; Utilities.SetStateChanged(p, "CCSPlayerController", "m_szClan"); }
        var st = p.ActionTrackingServices?.MatchStats;
        if (st != null && (st.Kills != k || st.Deaths != d || st.Assists != a))
        {
            st.Kills = k; st.Deaths = d; st.Assists = a;
            Utilities.SetStateChanged(p, "CCSPlayerController", "m_pActionTrackingServices");
        }
        if (p.Score != k * 2 + a) { p.Score = k * 2 + a; Utilities.SetStateChanged(p, "CCSPlayerController", "m_iScore"); }
    }

    private void CountCsKill(string killer)
    {
        foreach (var p in Utilities.GetPlayers())
            if (p != null && p.IsValid && !p.IsBot && Safe(p.PlayerName) == killer) { Hero(p.Slot).Kills++; return; }
    }
}
