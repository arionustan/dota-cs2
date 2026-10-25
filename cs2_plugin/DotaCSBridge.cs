// DotaCS bridge plugin for a CS2 server (CounterStrikeSharp).
//
// Every 0.05s:
//   sends   P slot x y z fx fy isBot hp          for every alive human CS player
//           D heroId damage attackerSlot weapon  when a CS player shot a Dota hero bot
//   gets    H heroId x y z fx fy hp maxhp alive name   Dota heroes -> moved CS bots
//           C T slot x y     teleport a CS player (hook, push)
//           C S slot sec     freeze a CS player (stun, root)
//           C K slot dmg [killer]   damage a CS player (killer = Dota hero name, for the kill message)
//           C H slot heroId  draw the meat hook chain from the hero to the CS player
//           E K hero killer weapon  a CS player killed a Dota hero (score + message)
//
// Dota heroes are CS bots on the T side that stand still (bot_stop 1) and are
// teleported every tick to where the hero is in Dota. They never die in CS:
// their health is reset every tick, the real HP lives in Dota.

using System.Collections.Concurrent;
using System.Globalization;
using System.Text;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Timers;
using CounterStrikeSharp.API.Modules.Utils;
using CounterStrikeSharp.API.Modules.UserMessages;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge : BasePlugin
{
    public override string ModuleName => "DotaCS Bridge";
    public override string ModuleVersion => "0.15.0";

    private const string BridgeUrl = "http://127.0.0.1:3000/cs";
    private const float Interval = 0.05f;
    private const int BotHealth = 1000;
    private const float FloorZ = 64f;                                // fallback floor height
    private const string PudgeModel = "models/dota_pudge/pudge.vmdl";
    private readonly Dictionary<string, CDynamicProp> _heroProp = new(); // heroId -> Pudge model following the bot
    private readonly Dictionary<string, string> _heroAnim = new();       // heroId -> current animation
    private readonly Dictionary<string, Vector> _heroLastPos = new();
    private readonly Dictionary<string, float> _heroMoveTime = new();
    private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    private static readonly HttpClient Http = new(new HttpClientHandler { UseProxy = false })
    {
        Timeout = TimeSpan.FromSeconds(1)
    };

    private record HeroState(string Id, float X, float Y, float Z, float Fx, float Fy, int Hp, int MaxHp, bool Alive, string Name, string Act, string Effect, bool Visible = true,
        int Kills = 0, int Deaths = 0, int Assists = 0, int Level = 1);

    // filled by the HTTP thread, used on the game thread
    private readonly ConcurrentQueue<string> _incoming = new();
    private readonly ConcurrentQueue<string> _hits = new();

    private Dictionary<string, HeroState> _heroes = new();
    private readonly Dictionary<string, int> _heroBot = new();      // heroId -> bot slot
    private readonly Dictionary<int, float> _frozenUntil = new();   // CS player slot -> time
    private float _lastBotAdd;

    private int _inFlight;
    private int _sendFails;
    private int _readFails;
    private bool _connected;

    public override void Load(bool hotReload)
    {
        Logger.LogInformation("DotaCS bridge plugin {Version} loaded, sending to {Url}", ModuleVersion, BridgeUrl);
        RegisterEventHandler<EventPlayerHurt>(OnPlayerHurt);
        RegisterEventHandler<EventPlayerSpawn>(OnPlayerSpawn);
        RegisterEventHandler<EventBulletImpact>(OnBulletImpact);
        RegisterEventHandler<EventHegrenadeDetonate>(OnHeDetonate);
        RegisterEventHandler<EventFlashbangDetonate>((ev, _) => { SendGrenade("flash", ev.X, ev.Y, ev.Z, ev.Userid); return HookResult.Continue; });
        RegisterEventHandler<EventSmokegrenadeDetonate>((ev, _) => { SendGrenade("smoke", ev.X, ev.Y, ev.Z, ev.Userid); return HookResult.Continue; });
        RegisterEventHandler<EventMolotovDetonate>((ev, _) => { SendGrenade("fire", ev.X, ev.Y, ev.Z, ev.Userid); return HookResult.Continue; });
        AddCommand("css_faq", "DotaCS commands", (p, _) => { if (p != null) Faq(p); });
        RegisterProgress();
        RegisterEventHandler<EventPlayerDeath>((ev, _) => { if (ev.Userid != null && ev.Userid.IsValid && !ev.Userid.IsBot) PlayStinger("killed"); return HookResult.Continue; });
        AddCommandListener("buy", OnBuy);
        AddCommandListener("autobuy", OnBuy);
        AddCommandListener("rebuy", OnBuy);
        RegisterListener<Listeners.OnMapStart>(_ => SetupServer());
        RegisterListener<Listeners.OnServerPrecacheResources>(m => { m.AddResource(PudgeModel); PrecacheExtra(m); PrecacheHeroes(m); });
        AddTimer(Interval, Tick, TimerFlags.REPEAT);
        AddTimer(30f, SetupServer, TimerFlags.REPEAT);   // keep the settings even if a config resets them
        SetupServer();
        StartRelay();
    }

    public override void Unload(bool hotReload) => StopRelay();

    private void SetupServer()
    {
        // bots only exist as Dota heroes: they stand still and don't shoot
        Server.ExecuteCommand("bot_quota_mode normal");
        Server.ExecuteCommand("bot_stop 1");
        Server.ExecuteCommand("bot_join_after_player 0");
        // test server: never kick idle players, endless warmup, instant respawn
        Server.ExecuteCommand("mp_autokick 0");
        Server.ExecuteCommand("mp_warmup_pausetimer 1");
        Server.ExecuteCommand("mp_ignore_round_win_conditions 1");
        Server.ExecuteCommand("mp_respawn_on_death_ct 1");
        Server.ExecuteCommand("mp_respawn_on_death_t 1");
        // buying works anywhere for the engine, the plugin only allows it at the Dire fountain
        Server.ExecuteCommand("mp_buy_anywhere 1");
        Server.ExecuteCommand("mp_buytime 999999");
        Server.ExecuteCommand("sv_hibernate_when_empty 0");
        // test mode: cheats on (noclip, god...). Remove before giving the game to the streamer
        Server.ExecuteCommand("sv_cheats 1");
        // test mode extras: endless ammo, lots of money, more grenades, no freeze time
        Server.ExecuteCommand("sv_infinite_ammo 1");
        Server.ExecuteCommand("mp_maxmoney 60000");
        Server.ExecuteCommand("mp_startmoney 2000");   // real economy: money comes from last hits, kills and passive income (!money for tests)
        Server.ExecuteCommand("ammo_grenade_limit_total 6");
        Server.ExecuteCommand("mp_freezetime 0");
        Server.ExecuteCommand("mp_roundtime 60");
    }

    // ------------------------------------------------------------ CS player shot a hero bot
    private HookResult OnPlayerHurt(EventPlayerHurt ev, GameEventInfo info)
    {
        try
        {
            var victim = ev.Userid;
            var attacker = ev.Attacker;
            if (victim == null || attacker == null || !victim.IsValid || !attacker.IsValid) return HookResult.Continue;
            if (!victim.IsBot || attacker.IsBot) return HookResult.Continue;

            var heroId = _heroBot.FirstOrDefault(kv => kv.Value == victim.Slot).Key;
            if (heroId == null) return HookResult.Continue;

            _hits.Enqueue(string.Format(Inv, "D {0} {1} {2} {3}", heroId, ev.DmgHealth * DmgMult(attacker.Slot), attacker.Slot, ev.Weapon));
        }
        catch (Exception e)
        {
            Logger.LogWarning("DotaCS hurt handler: {Error}", e.Message);
        }
        return HookResult.Continue;
    }

    // ------------------------------------------------------------ main loop (game thread)
    private void Tick()
    {
        try
        {
            ApplyIncoming(); Diag("ApplyIncoming");
            SyncBots(); Diag("SyncBots");
            SyncUnits(); Diag("SyncUnits");
            UpdateTrees(); Diag("UpdateTrees");
            UpdateBuildingProps(); Diag("UpdateBuildingProps");
            UpdateHookThrows(); Diag("UpdateHookThrows");
            UpdateAmbient(); Diag("UpdateAmbient");
            UpdateFreezes(); Diag("UpdateFreezes");
            UpdateHooks(); Diag("UpdateHooks");
            UpdateCsPlayers(); Diag("UpdateCsPlayers");
            UpdateTracers(); Diag("UpdateTracers");
            UpdateHpBars(); Diag("UpdateHpBars");
            UpdateRunes(); Diag("UpdateRunes");
            UpdateProgress(); Diag("UpdateProgress");
        }
        catch (Exception e)
        {
            _readFails++;
            if (_readFails == 1 || _readFails % 400 == 0)
                Logger.LogWarning("DotaCS tick error ({Count}x): {Error}", _readFails, e.Message);
        }

        if (Volatile.Read(ref _inFlight) != 0) return;

        string body;
        try
        {
            body = BuildBody();
        }
        catch (Exception e)
        {
            _readFails++;
            if (_readFails == 1 || _readFails % 400 == 0)
                Logger.LogWarning("DotaCS could not read players ({Count}x): {Error}", _readFails, e.Message);
            return;
        }

        if (_relayOn) { RelayExchangeCs(body); return; }

        Interlocked.Exchange(ref _inFlight, 1);
        _ = Task.Run(async () =>
        {
            try
            {
                using var content = new StringContent(body, Encoding.UTF8, "text/plain");
                using var response = await Http.PostAsync(BridgeUrl, content);
                var text = await response.Content.ReadAsStringAsync();
                _incoming.Enqueue(text);
                if (!_connected)
                {
                    _connected = true;
                    Logger.LogInformation("DotaCS connected to the bridge (HTTP {Code})", (int)response.StatusCode);
                }
            }
            catch (Exception e)
            {
                _connected = false;
                _sendFails++;
                if (_sendFails == 1 || _sendFails % 200 == 0)
                    Logger.LogWarning("DotaCS bridge not reachable ({Count}x), is bridge.py running? {Error}", _sendFails, e.Message);
            }
            finally
            {
                Interlocked.Exchange(ref _inFlight, 0);
            }
        });
    }

    private string BuildBody()
    {
        var sb = new StringBuilder();
        foreach (var player in Utilities.GetPlayers())
        {
            if (player == null || !player.IsValid || player.IsBot || !player.PawnIsAlive || IsHolding(player.Slot)) continue;
            var pawn = player.PlayerPawn.Value;
            if (pawn == null || !pawn.IsValid) continue;
            var pos = pawn.AbsOrigin;
            if (pos == null) continue;

            double yaw = pawn.EyeAngles.Y * Math.PI / 180.0;
            var ch = Hero(player.Slot);
            sb.AppendLine(string.Format(Inv, "P {0} {1:F1} {2:F1} {3:F1} {4:F3} {5:F3} 0 {6} {7} {8} {9} {10} {11}",
                player.Slot, pos.X, pos.Y, pos.Z, Math.Cos(yaw), Math.Sin(yaw), pawn.Health, Safe(player.PlayerName),
                ch.Level, ch.Kills, ch.Deaths, MaxHp(pawn)));
        }
        while (_hits.TryDequeue(out var hit)) sb.AppendLine(hit);
        return sb.Length > 0 ? sb.ToString() : "none";
    }

    // ------------------------------------------------------------ answers from the bridge
    private void ApplyIncoming()
    {
        string? latest = null;
        var commands = new List<string>();
        while (_incoming.TryDequeue(out var text))
        {
            latest = text;
            foreach (var line in text.Split('\n'))
                if (line.StartsWith("C ") || line.StartsWith("E ")) commands.Add(line.Trim());
        }
        if (latest == null) return;

        var heroes = new Dictionary<string, HeroState>();
        foreach (var raw in latest.Split('\n'))
        {
            var p = raw.Trim().Split(' ');
            // H heroId x y z fx fy hp maxhp alive name
            if (p.Length < 11 || p[0] != "H") continue;
            heroes[p[1]] = new HeroState(p[1], F(p[2]), F(p[3]), F(p[4]), F(p[5]), F(p[6]),
                (int)F(p[7]), (int)F(p[8]), p[9] == "1", p[10], p.Length > 11 ? p[11] : "-", p.Length > 12 ? p[12] : "-", p.Length <= 13 || p[13] != "0",
                p.Length > 17 ? (int)F(p[14]) : 0, p.Length > 17 ? (int)F(p[15]) : 0, p.Length > 17 ? (int)F(p[16]) : 0, p.Length > 17 ? (int)F(p[17]) : 1);
        }
        _heroes = heroes;
        foreach (var raw in latest.Split('\n'))
            if (raw.StartsWith("N ")) SetNight(raw.Trim() == "N 1");
        ParseUnits(latest);
        ParseBuildings(latest);

        foreach (var cmd in commands)
        {
            var parts = cmd.Split(' ');
            if (parts[0] == "E") ApplyEvent(parts); else ApplyCommand(parts);
        }
    }

    private void ApplyCommand(string[] c)
    {
        if (c.Length < 4) return;
        var player = PlayerBySlot((int)F(c[2]));
        var pawn = player?.PlayerPawn.Value;
        if (player == null || pawn == null || !pawn.IsValid || !player.PawnIsAlive) return;

        switch (c[1])
        {
            case "T" when c.Length >= 5:
                var z = pawn.AbsOrigin?.Z ?? 0;
                pawn.Teleport(new Vector(F(c[3]), F(c[4]), c.Length > 5 ? F(c[5]) + 8 : z + 2), null, new Vector(0, 0, 0));
                break;

            case "S":
                var until = Server.CurrentTime + F(c[3]);
                if (!_frozenUntil.TryGetValue(player.Slot, out var old) || old < until)
                    _frozenUntil[player.Slot] = until;
                SetFrozen(pawn, true);
                break;

            case "V" when c.Length >= 4:
                // Dota slow (rot, frost...): keep the CS player's speed scaled while Dota says so
                pawn.VelocityModifier = Math.Clamp(F(c[3]), 0.1f, 1f);
                Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_flVelocityModifier");
                break;

            case "R" when c.Length >= 6:
                // a tower / fountain / creep shot at this CS player: draw a short tracer
                DrawTracer(new Vector(F(c[3]), F(c[4]), F(c[5]) + 120), pawn);
                break;

            case "H" when c.Length >= 4:
                DrawHook(c[3], pawn);
                break;

            case "K":
                var dmg = (int)Math.Ceiling(F(c[3]));
                if (dmg <= 0) break;
                if (pawn.Health - dmg <= 0)
                {
                    var killer = c.Length > 4 ? Pretty(c[4]) : "Дота";
                    pawn.CommitSuicide(false, true);
                    _dotaScore++;
                    Announce($" {ChatColors.Red}{killer}{ChatColors.Default} убил {ChatColors.Blue}{player.PlayerName}{ChatColors.Default} из Доты");
                    player.PrintToCenterHtml($"<font color='#ff4040'>Тебя убил {killer} из Доты</font>");
                    CheckWin();
                }
                else
                {
                    pawn.Health -= dmg;
                    Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
                }
                break;
        }
    }

    private void UpdateFreezes()
    {
        foreach (var slot in _frozenUntil.Keys.ToList())
        {
            if (Server.CurrentTime < _frozenUntil[slot]) continue;
            _frozenUntil.Remove(slot);
            var pawn = PlayerBySlot(slot)?.PlayerPawn.Value;
            if (pawn != null && pawn.IsValid) SetFrozen(pawn, false);
        }
    }

    private static void SetFrozen(CCSPlayerPawn pawn, bool frozen)
    {
        var type = frozen ? MoveType_t.MOVETYPE_NONE : MoveType_t.MOVETYPE_WALK;
        if (pawn.MoveType == type) return;
        pawn.MoveType = type;
        pawn.ActualMoveType = type;
        Utilities.SetStateChanged(pawn, "CBaseEntity", "m_MoveType");
        if (frozen) pawn.Teleport(null, null, new Vector(0, 0, 0));
    }

    // ------------------------------------------------------------ Dota heroes as CS bots
    private void SyncBots()
    {
        var bots = Utilities.GetPlayers().Where(p => p != null && p.IsValid && p.IsBot).ToList();
        var botBySlot = bots.ToDictionary(b => b.Slot);

        // forget heroes that are gone or whose bot left
        foreach (var id in _heroBot.Keys.ToList())
            if (!_heroes.ContainsKey(id) || !botBySlot.ContainsKey(_heroBot[id]))
                _heroBot.Remove(id);
        foreach (var id in _heroProp.Keys.ToList())
            if (!_heroes.ContainsKey(id)) RemoveProp(id);

        // give free bots to heroes without one
        var used = _heroBot.Values.ToHashSet();
        var free = new Queue<CCSPlayerController>(bots.Where(b => !used.Contains(b.Slot)));
        foreach (var hero in _heroes.Values)
        {
            if (_heroBot.ContainsKey(hero.Id)) continue;
            if (free.Count > 0) _heroBot[hero.Id] = free.Dequeue().Slot;
        }

        // need more bots? add one at a time
        var missing = _heroes.Count - _heroBot.Count;
        if (missing > 0 && Server.CurrentTime - _lastBotAdd > 1.0f)
        {
            _lastBotAdd = Server.CurrentTime;
            Server.ExecuteCommand("bot_add_t");
        }
        // too many bots? kick spare ones
        else if (free.Count > 0 && _heroes.Count > 0 && Server.CurrentTime - _lastBotAdd > 1.0f)
        {
            _lastBotAdd = Server.CurrentTime;
            var spare = free.Dequeue();
            Server.ExecuteCommand("kickid " + spare.UserId);
        }

        // move every hero bot to its hero
        foreach (var (heroId, slot) in _heroBot)
        {
            var bot = botBySlot[slot];
            var hero = _heroes[heroId];
            var pawn = bot.PlayerPawn.Value;

            var shownName = $"{hero.Name} {Math.Max(hero.Hp, 0)}/{hero.MaxHp}";
            if (bot.PlayerName != shownName)
            {
                bot.PlayerName = shownName;
                Utilities.SetStateChanged(bot, "CBasePlayerController", "m_iszPlayerName");
            }
            if (pawn == null || !pawn.IsValid) continue;
            if (!bot.PawnIsAlive) { bot.Respawn(); continue; }

            CDynamicProp? prop = null;
            if (UsePudgeModel) { HideBot(bot, pawn, hero.Name == "pudge" || !HeroModelNames.Contains(hero.Name) ? PudgeHitboxScale : HeroHitboxScale); prop = PropFor(heroId, hero.Name); }
            var heroPos = new Vector(hero.X, hero.Y, hero.Z);
            var yaw = (float)(Math.Atan2(hero.Fy, hero.Fx) * 180.0 / Math.PI);

            if (hero.Alive && !hero.Visible)
            {
                // fog of war: the CS team has no vision of this hero in Dota, hide model and hitbox
                prop?.Teleport(new Vector(hero.X, hero.Y, hero.Z - 3000), null, null);
                pawn.Teleport(new Vector(hero.X, hero.Y, hero.Z - 3000), null, new Vector(0, 0, 0));
                continue;
            }
            if (!hero.Alive)
            {
                // dead in Dota: Pudge plays his death animation where he fell, the hitbox goes under the map
                SetAnim(heroId, prop, "death");
                pawn.Teleport(new Vector(hero.X, hero.Y, hero.Z - 3000), null, new Vector(0, 0, 0));
                continue;
            }

            // the bot is the hitbox, the Pudge model is what you see
            var z = hero.Z;
            if (Math.Abs(z) < 0.01f)
            {
                // Dota sends no heights (flat arena): keep the bot on the floor
                z = pawn.AbsOrigin?.Z ?? FloorZ;
                if (z < FloorZ - 100 || z > FloorZ + 400) z = FloorZ + 16;
            }
            pawn.Teleport(new Vector(hero.X, hero.Y, z + 4), new QAngle(0, yaw, 0), new Vector(0, 0, 0));
            if (prop != null)
            {
                prop.Teleport(new Vector(hero.X, hero.Y, z), new QAngle(0, yaw + PudgeYawOffset, 0), null);
                if (_heroLastPos.TryGetValue(heroId, out var last) &&
                    Math.Abs(hero.X - last.X) + Math.Abs(hero.Y - last.Y) > 1f)
                    _heroMoveTime[heroId] = Server.CurrentTime;
                var moving = _heroMoveTime.TryGetValue(heroId, out var mt) && Server.CurrentTime - mt < 0.25f;
                var isPudge = !_heroModelOf.TryGetValue(heroId, out var hm) || hm == PudgeModel;
                var anim = hero.Act switch
                {
                    "hook" => isPudge ? "hook" : "cast",
                    "cast" => isPudge ? "hook" : "cast",
                    "ult" => "ult",
                    "stun" => "stun",
                    "attack" => "attack",
                    _ => moving ? "run" : "idle",
                };
                SetAnim(heroId, prop, anim);
                UpdateRot(heroId, hero, prop);
            }
            _heroLastPos[heroId] = heroPos;

            // never die in CS, Dota owns the HP
            if (pawn.Health != BotHealth)
            {
                pawn.Health = BotHealth;
                Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
            }
        }
    }

    // ------------------------------------------------------------ Pudge model
    private const float PudgeYawOffset = 0f;   // DMX models already face +X like CS
    private const bool UsePudgeModel = true;
    private const float PudgeScale = 0.95f;        // Pudge towers over CS players (was 0.55, the same as creeps)
    private const float PudgeHitboxScale = 3.1f;   // hitboxes follow the bigger model

    private void HideBot(CCSPlayerController bot, CCSPlayerPawn pawn, float hitboxScale)
    {
        if (pawn.Render.A != 0)
        {
            pawn.RenderMode = RenderMode_t.kRenderTransAlpha;
            pawn.Render = System.Drawing.Color.FromArgb(0, 255, 255, 255);
            Utilities.SetStateChanged(pawn, "CBaseModelEntity", "m_clrRender");
            bot.RemoveWeapons();
            // Pudge is ~133 units tall, a CS player ~72: scale the invisible bot so its hitboxes cover the model.
            try
            {
                var node = pawn.CBodyComponent?.SceneNode;
                if (node != null)
                {
                    node.GetSkeletonInstance().Scale = hitboxScale;
                    Utilities.SetStateChanged(pawn, "CBaseEntity", "m_CBodyComponent");
                }
            }
            catch (Exception e) { Logger.LogWarning("DotaCS: can't scale the bot: {Error}", e.Message); }
        }
    }

    // Dota heroes with their own model in CS2 (tools/hero_build.py); everyone else is shown as Pudge
    private static readonly string[] HeroModelNames =
        { "axe", "juggernaut", "sniper", "crystal_maiden", "lina", "phantom_assassin", "drow_ranger", "nevermore" };
    private const float HeroScale = 0.75f;
    private const float HeroHitboxScale = 2.4f;   // other heroes are smaller than Pudge
    private readonly Dictionary<string, string> _heroModelOf = new();

    private static string HeroModelPath(string n) => $"models/dota_heroes/{n}/{n}.vmdl";

    // only use a hero model if it really got compiled, so a failed compile never shows an error model
    private static bool ModelExists(string path)
    {
        try
        {
            var rel = path.Replace('/', Path.DirectorySeparatorChar) + "_c";
            foreach (var root in new[] { Path.Combine(Server.GameDirectory, "csgo"), Server.GameDirectory })
                if (File.Exists(Path.Combine(root, rel))) return true;
        }
        catch { }
        return false;
    }

    private static string ModelForHero(string name) =>
        HeroModelNames.Contains(name) && ModelExists(HeroModelPath(name)) ? HeroModelPath(name) : PudgeModel;

    private static void PrecacheHeroes(ResourceManifest m)
    {
        foreach (var n in HeroModelNames)
            if (ModelExists(HeroModelPath(n))) m.AddResource(HeroModelPath(n));
    }

    private CDynamicProp? PropFor(string heroId, string heroName)
    {
        if (_heroProp.TryGetValue(heroId, out var prop) && prop.IsValid) return prop;
        try
        {
            prop = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
            if (prop == null) return null;
            prop.Collision.SolidType = SolidType_t.SOLID_NONE;
            prop.DispatchSpawn();
            var model = ModelForHero(heroName);
            _heroModelOf[heroId] = model;
            prop.SetModel(model);
            SetPropScale(prop, model == PudgeModel ? PudgeScale : HeroScale);
            Diag("hero model " + heroName + " -> " + model);
            _heroProp[heroId] = prop;
            _heroAnim.Remove(heroId);
            return prop;
        }
        catch (Exception e)
        {
            Logger.LogWarning("DotaCS: can't create the Pudge model: {Error}", e.Message);
            return null;
        }
    }

    private void SetAnim(string heroId, CDynamicProp? prop, string anim)
    {
        if (prop == null || !prop.IsValid) return;
        if (_heroAnim.TryGetValue(heroId, out var cur) && cur == anim) return;
        _heroAnim[heroId] = anim;
        prop.AcceptInput("SetAnimation", null, null, anim);
        prop.AcceptInput("SetDefaultAnimation", null, null, anim == "death" ? "death" : anim);
        if (anim == "ult" && prop.AbsOrigin != null && (!_heroModelOf.TryGetValue(heroId, out var m) || m == PudgeModel)) StartFx(FxDismember, new Vector(prop.AbsOrigin.X, prop.AbsOrigin.Y, prop.AbsOrigin.Z + 60), 3.5f);
    }

    private void RemoveProp(string heroId)
    {
        if (_heroProp.TryGetValue(heroId, out var prop) && prop.IsValid) prop.Remove();
        _heroProp.Remove(heroId);
        _heroModelOf.Remove(heroId);
        _heroAnim.Remove(heroId);
        _heroLastPos.Remove(heroId);
    }

    // ------------------------------------------------------------ score, messages, hook chain
    private const int WinScore = 10;   // first side to this many kills wins the match
    private int _csScore;
    private int _dotaScore;

    private void ApplyEvent(string[] e)
    {
        // E K hero killer weapon : a CS player killed a Dota hero
        if (e.Length >= 6 && e[1] == "R") { OnReward(e); return; }
        if (e.Length >= 3 && e[1] == "AEGIS") { OnAegis(e); return; }
        if (e.Length >= 3 && e[1] == "SHARD") { OnShard(e); return; }
        if (e.Length >= 4 && e[1] == "M") { OnDotaChat(e); return; }
        if (e.Length >= 4 && e[1] == "K")
        {
            _csScore++;
            CountCsKill(e[3]);
            var weapon = e.Length > 4 ? " (" + e[4] + ")" : "";
            Announce($" {ChatColors.Blue}{Pretty(e[3])}{ChatColors.Default} убил {ChatColors.Red}{Pretty(e[2])}{ChatColors.Default}{weapon}");
            foreach (var p in Utilities.GetPlayers())
                if (p != null && p.IsValid && !p.IsBot)
                    p.PrintToCenterHtml($"<font color='#40a0ff'>{Pretty(e[2])} убит!</font>");
            CheckWin();
        }
        // E HK heroId x y z dirx diry : Pudge threw his hook
        if (e.Length >= 8 && e[1] == "HK")
        {
            StartHookThrow(F(e[3]), F(e[4]), F(e[5]), F(e[6]), F(e[7]));
            return;
        }
        // E T x y : a tree was cut in Dota
        else if (e.Length >= 4 && e[1] == "T")
        {
            CutTree(F(e[2]), F(e[3]));
        }
        // E S event x y z : a Dota sound near a CS player
        else if (e.Length >= 6 && e[1] == "S")
        {
            PlayDotaSound(e[2], new Vector(F(e[3]), F(e[4]), F(e[5]) + 40));
        }
    }

    private void CheckWin()
    {
        Announce($" Счёт: {ChatColors.Blue}КС {_csScore}{ChatColors.Default} : {ChatColors.Red}{_dotaScore} Дота{ChatColors.Default}  (до {WinScore})");
        if (_csScore < WinScore && _dotaScore < WinScore) return;
        var cs = _csScore >= WinScore;
        PlayStinger(cs ? "dire_win" : "dire_lose");
        Announce(cs ? $" {ChatColors.Blue}КС ПОБЕДИЛИ!" : $" {ChatColors.Red}ДОТА ПОБЕДИЛА!");
        foreach (var p in Utilities.GetPlayers())
            if (p != null && p.IsValid && !p.IsBot)
                p.PrintToCenterHtml(cs ? "<font color='#40a0ff' class='fontSize-xl'>КС ПОБЕДИЛИ!</font>" : "<font color='#ff4040' class='fontSize-xl'>ДОТА ПОБЕДИЛА!</font>");
        _csScore = 0;
        _dotaScore = 0;
    }

    private static void Announce(string text) => Server.PrintToChatAll(text);

    private static string Pretty(string name)
    {
        name = name.Replace('_', ' ');
        return name.Length > 0 ? char.ToUpper(name[0]) + name.Substring(1) : name;
    }

    private static string Safe(string? name)
    {
        var n = (name ?? "player").Replace(' ', '_').Replace('\n', '_');
        return n.Length > 0 ? n : "player";
    }

    private readonly Dictionary<int, CBeam> _hookBeam = new();
    private readonly Dictionary<int, float> _hookUntil = new();

    // a brown "chain" beam from Pudge's hand to the hooked CS player, refreshed while the hook pulls
    private void DrawHook(string heroId, CCSPlayerPawn victim)
    {
        if (!_heroes.TryGetValue(heroId, out var hero)) return;
        var slot = victim.Controller.Value?.Index ?? 0;
        var start = new Vector(hero.X, hero.Y, hero.Z + 80);
        var vp = victim.AbsOrigin;
        if (vp == null) return;
        var end = new Vector(vp.X, vp.Y, vp.Z + 40);
        try
        {
            if (!_hookUntil.ContainsKey((int)slot)) { victim.EmitSound("Weapon_Knife.Hit"); StartFx(FxHookImpact, end, 2f); }
            DrawChain((int)slot, start, end);
            _hookUntil[(int)slot] = Server.CurrentTime + 0.2f;
        }
        catch (Exception e) { Logger.LogWarning("DotaCS hook chain: {Error}", e.Message); }
    }

    private void UpdateHooks()
    {
        foreach (var slot in _hookUntil.Keys.ToList())
        {
            if (Server.CurrentTime < _hookUntil[slot]) continue;
            _hookUntil.Remove(slot);
            RemoveChain(slot);
        }
    }

    // ------------------------------------------------------------ CS side of the Dota map: Dire spawn, fountain, shop, portals
    private static readonly Vector[] DireSpawns =
    {
        new(6836, 6554, 400), new(6902, 6420, 400), new(7036, 6312, 400), new(7166, 6209, 400), new(7316, 6084, 400),
    };
    private static readonly Vector DireFountain = new(7408, 6848, 377);
    private const float FountainRadius = 1100f;   // heal + shop range
    private const int FountainHealPerTick = 3;     // every 0.05 s -> 60 HP/s
    private static readonly Vector[] Portals = { new(-6458, 7599, 256), new(6426, -7314, 256) };
    private const float PortalRadius = 140f;
    private const float PortalTime = 6.0f;         // stand this long to teleport (Dota: 6 s channel)
    private readonly Dictionary<int, float> _portalSince = new();
    private readonly Dictionary<int, float> _portalCooldown = new();
    private int _spawnIndex;

    private HookResult OnPlayerSpawn(EventPlayerSpawn ev, GameEventInfo info)
    {
        var player = ev.Userid;
        if (player == null || !player.IsValid || player.IsBot) return HookResult.Continue;
        AddTimer(0.1f, () =>
        {
            var pawn = player.PlayerPawn.Value;
            if (!player.IsValid || pawn == null || !pawn.IsValid || !player.PawnIsAlive) return;
            if (ProgressOnSpawn(player, pawn)) return;
            var spot = DireSpawns[_spawnIndex++ % DireSpawns.Length];
            pawn.Teleport(spot, new QAngle(0, 225, 0), new Vector(0, 0, 0));
            if (_night) { SendNightFade(player, true, 0.1f); ApplyWorldNight(true); }
        });
        return HookResult.Continue;
    }

    // ------------------------------------------------------------ grenades go to Dota (G kind x y z slot)
    private void SendGrenade(string kind, float x, float y, float z, CCSPlayerController? who)
    {
        var slot = who != null && who.IsValid ? who.Slot : -1;
        _hits.Enqueue(string.Format(Inv, "G {0} {1:F0} {2:F0} {3:F0} {4}", kind, x, y, z, slot));
    }

    // ------------------------------------------------------------ !faq
    private void Faq(CCSPlayerController p)
    {
        string[] lines =
        {
            $" {ChatColors.Gold}DotaCS: команды и кнопки",
            $" {ChatColors.Green}F1{ChatColors.Default} AK  {ChatColors.Green}F2{ChatColors.Default} AWP  {ChatColors.Green}F3{ChatColors.Default} гранаты  {ChatColors.Green}F4{ChatColors.Default} дигл  {ChatColors.Green}F5{ChatColors.Default} M4",
            $" {ChatColors.Green}F6{ChatColors.Default} третье лицо вкл/выкл  {ChatColors.Green}V{ChatColors.Default} полёт  {ChatColors.Green}K{ChatColors.Default} переподключиться",
            $" {ChatColors.Green}H{ChatColors.Default} спрятать худ  {ChatColors.Green}J{ChatColors.Default} спрятать оружие  {ChatColors.Green}O{ChatColors.Default} чистый экран для записи",
            $" Гранаты бьют и по Доте: {ChatColors.Red}HE и молотов x4 урона{ChatColors.Default}, флешка ослепляет героев, дым даёт невидимость в Доте на 15 сек",
            $" Руны на местах рун Доты: подойди и коснись. Лотосы у пулов лотоса лечат до 100 HP",
            $" Портал: постой 2 сек в портале. Закупка только на фонтане Тьмы",
            $" {ChatColors.Green}F7/F8/F9/F10{ChatColors.Default} телепорт верх/мид/низ/база ($300, 3 сек)  {ChatColors.Green}F11{ChatColors.Default} байбек",
            $" {ChatColors.Green}7{ChatColors.Default} хилка  {ChatColors.Green}8{ChatColors.Default} вард  {ChatColors.Green}9{ChatColors.Default} уровень и вещи. Покупка: !buy salve / !buy ward на фонтане или в секретной лавке",
            $" Деньги и опыт за добивание крипов и героев, уровень даёт HP и урон. Рошан даёт Аегис, Тормент шард, стой 3 сек у аутпоста или фонаря чтобы захватить",
            $" Чат: {ChatColors.Green}!faq{ChatColors.Default} это меню, {ChatColors.Green}!3p{ChatColors.Default} третье лицо, обычный чат видят и в Доте",
        };
        foreach (var l in lines) p.PrintToChat(l);
    }

    // ------------------------------------------------------------ day / night from Dota
    private bool _night;

    private void SetNight(bool night)
    {
        if (night == _night) return;
        _night = night;
        foreach (var p in Utilities.GetPlayers())
            if (p.IsValid && !p.IsBot) SendNightFade(p, night, 3f);
        ApplyWorldNight(night);
        Announce(night ? $" {ChatColors.Blue}В Доте наступила ночь{ChatColors.Default}, видно хуже"
                       : $" {ChatColors.Gold}В Доте наступил день{ChatColors.Default}");
    }

    // logs each stage once, so if the server ever dies the log shows the last thing that worked
    private readonly HashSet<string> _diag = new();
    private void Diag(string stage) { if (_diag.Add(stage)) Logger.LogInformation("DotaCS stage ok: {Stage}", stage); }

    // real night: dims the sun (light_environment) and the sky (env_sky); both are server entities in dotacs_arena
    private float _sunBright = -1, _skyBright = -1, _skyIntensity = -1;
    private System.Drawing.Color _sunColor, _skyTint;

    private void ApplyWorldNight(bool night)
    {
        try
        {
            Diag("night start " + night);
            foreach (var sky in Utilities.FindAllEntitiesByDesignerName<CEnvSky>("env_sky"))
            {
                if (_skyBright < 0) { _skyBright = sky.BrightnessScale; _skyTint = sky.TintColor; }
                sky.BrightnessScale = night ? _skyBright * 0.12f : _skyBright;
                sky.TintColor = night ? System.Drawing.Color.FromArgb(255, 70, 90, 160) : _skyTint;
                Utilities.SetStateChanged(sky, "CEnvSky", "m_flBrightnessScale");
                Utilities.SetStateChanged(sky, "CEnvSky", "m_vTintColor");
            }
            Diag("night sky " + night);
        }
        catch (Exception e) { Logger.LogWarning("DotaCS: world night failed: {Error}", e.Message); }
    }

    // a dark blue screen tint that stays until day (UM_Fade: duration and hold in 1/512 s)
    private void SendNightFade(CCSPlayerController player, bool night, float seconds)
    {
        try
        {
            var msg = UserMessage.FromId(106);
            msg.SetInt("duration", (int)(seconds * 512));
            msg.SetInt("hold_time", night ? 0 : 0);
            msg.SetInt("flags", night ? (0x2 | 0x8) : (0x1 | 0x10));   // out+stayout / in+purge
            uint r = 8, g = 12, b = 40, a = night ? 150u : 0u;
            msg.SetUInt("color", r | (g << 8) | (b << 16) | (a << 24));
            var rf = new RecipientFilter { player };
            msg.Send(rf);
        }
        catch (Exception e) { Logger.LogWarning("DotaCS: night fade failed: {Error}", e.Message); }
    }

    private HookResult OnBuy(CCSPlayerController? player, CommandInfo info)
    {
        if (player == null || !player.IsValid || player.IsBot) return HookResult.Continue;
        var pos = player.PlayerPawn.Value?.AbsOrigin;
        if (pos != null && AtShop(pos)) return HookResult.Continue;
        player.PrintToCenter("Закупка только на фонтане Тьмы или в секретной лавке");
        return HookResult.Handled;
    }

    private void UpdateCsPlayers()
    {
        foreach (var player in Utilities.GetPlayers())
        {
            if (player == null || !player.IsValid || player.IsBot || !player.PawnIsAlive) continue;
            var pawn = player.PlayerPawn.Value;
            var pos = pawn?.AbsOrigin;
            if (pawn == null || pos == null) continue;

            // fountain heals
            if (IsHolding(player.Slot)) continue;
            if (Dist2(pos, DireFountain) < FountainRadius * FountainRadius && pawn.Health < MaxHp(pawn))
            {
                pawn.Health = Math.Min(MaxHp(pawn), pawn.Health + Math.Max(FountainHealPerTick, MaxHp(pawn) * 3 / 100));
                Utilities.SetStateChanged(pawn, "CBaseEntity", "m_iHealth");
            }

            // twin gates: stand on one for 2 s -> appear at the other
            var slot = player.Slot;
            var now = Server.CurrentTime;
            int at = -1;
            for (int i = 0; i < Portals.Length; i++)
                if (Dist2(pos, Portals[i]) < PortalRadius * PortalRadius) at = i;
            if (at < 0 || (_portalCooldown.TryGetValue(slot, out var cd) && now < cd)) { _portalSince.Remove(slot); continue; }
            if (!_portalSince.TryGetValue(slot, out var since)) { _portalSince[slot] = now; continue; }
            if (now - since < PortalTime)
            {
                if ((int)(now * 4) != (int)((now - Interval) * 4)) player.PrintToCenterHtml($"<font color='#c080ff'>Врата: стой на месте</font> {Bar((now - since) / PortalTime)}", 1);
                continue;
            }
            var dest = Portals[1 - at];
            var dir = new Vector(-dest.X, -dest.Y, 0);                 // step out towards the map centre
            var len = (float)Math.Sqrt(dir.X * dir.X + dir.Y * dir.Y);
            pawn.Teleport(new Vector(dest.X + dir.X / len * 220, dest.Y + dir.Y / len * 220, dest.Z + 40), null, new Vector(0, 0, 0));
            pawn.EmitSound("Player.Teleport");
            _portalSince.Remove(slot);
            _portalCooldown[slot] = now + 3f;
        }
    }

    private static float Dist2(Vector a, Vector b) => (a.X - b.X) * (a.X - b.X) + (a.Y - b.Y) * (a.Y - b.Y);

    private readonly List<(CBeam beam, float until)> _tracers = new();

    private void DrawTracer(Vector from, CCSPlayerPawn victim)
    {
        var vp = victim.AbsOrigin;
        if (vp == null) return;
        try
        {
            var beam = Utilities.CreateEntityByName<CBeam>("beam")!;
            beam.Render = System.Drawing.Color.FromArgb(255, 255, 200, 80);
            beam.Width = 2f; beam.EndWidth = 1f;
            beam.DispatchSpawn();
            beam.Teleport(from, new QAngle(0, 0, 0), new Vector(0, 0, 0));
            beam.EndPos.X = vp.X; beam.EndPos.Y = vp.Y; beam.EndPos.Z = vp.Z + 40;
            Utilities.SetStateChanged(beam, "CBeam", "m_vecEndPos");
            _tracers.Add((beam, Server.CurrentTime + 0.15f));
        }
        catch (Exception e) { Logger.LogWarning("DotaCS tracer: {Error}", e.Message); }
    }

    private void UpdateTracers()
    {
        for (int i = _tracers.Count - 1; i >= 0; i--)
        {
            if (Server.CurrentTime < _tracers[i].until) continue;
            if (_tracers[i].beam.IsValid) _tracers[i].beam.Remove();
            _tracers.RemoveAt(i);
        }
    }

    // ------------------------------------------------------------ helpers
    private static CCSPlayerController? PlayerBySlot(int slot)
    {
        foreach (var p in Utilities.GetPlayers())
            if (p != null && p.IsValid && p.Slot == slot) return p;
        return null;
    }

    private static float F(string s) =>
        float.TryParse(s, NumberStyles.Float, Inv, out var v) ? v : 0f;
}
