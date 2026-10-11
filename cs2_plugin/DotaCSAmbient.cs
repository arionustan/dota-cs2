// DotaCS: Dota ambience (wind, river, waterfall, birds, bats, base hum) and Dota music in CS2.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    // looping ambience from Dota's "default_day" soundscape: event, position, length of the file (s)
    private static readonly (string Ev, Vector? Pos, float Len)[] AmbientLoops =
    {
        ("default_day_lp", null, 48.98f),
        ("radiant_spawn_loop_02", new Vector(-7350, -6825, 389), 35.33f),
        ("radiant_ancient_lp_01", new Vector(-5850, -5300, 261), 33.23f),
        ("dire_spawn_loop_01", new Vector(7250, 6750, 389), 30.67f),
        ("dire_ancient_lp_01", new Vector(5250, 4700, 261), 33.37f),
        ("waterfall_loop_01", new Vector(-9000, 2900, 150), 33.56f),
        ("river_med_lp_01", new Vector(-1750, 7600, 5), 30.72f),
        ("river_light_lp_03", new Vector(2500, 7100, 130), 30.74f),
        ("river_med_lp_01", new Vector(-1500, 5500, 5), 30.72f),
        ("river_light_lp_03", new Vector(-150, -3000, 130), 30.74f),
        ("river_med_lp_01", new Vector(1200, -5700, 5), 30.72f),
        ("river_med_lp_01", new Vector(1750, -8000, 5), 30.72f),
        ("river_light_lp_03", new Vector(-3000, -8000, 130), 30.74f),
        ("dire_pit_loop_01_l", new Vector(-3000, 2400, 20), 39.25f),
        ("dire_pit_loop_01_l", new Vector(3000, -3000, 20), 39.25f),
    };

    // random one-shots: event, position, min/max seconds between plays
    private static readonly (string Ev, Vector Pos, float Min, float Max)[] AmbientRandom =
    {
        ("birds", new Vector(-4600, -500, 640), 6, 9),
        ("birds", new Vector(1000, -5400, 640), 6, 9),
        ("bats", new Vector(1825, 7000, 130), 5, 10),
        ("bats", new Vector(7000, 100, 640), 5, 10),
        ("tormentor", new Vector(7500, -7770, 250), 5, 15),
        ("tormentor", new Vector(-7250, 7900, 260), 5, 15),
    };

    private static readonly string[] LaningMusic = { "laning_01_layer_01", "laning_02_layer_01", "laning_03_layer_01" };
    private static readonly string[] BattleMusic = { "battle_01", "battle_02", "battle_03" };
    private static readonly Dictionary<string, float> MusicLen = new()
    {
        ["laning_01_layer_01"] = 161.5f, ["laning_02_layer_01"] = 87.4f, ["laning_03_layer_01"] = 100.4f,
        ["battle_01"] = 41.2f, ["battle_02"] = 48.2f, ["battle_03"] = 75f, ["roshan"] = 42.5f,
        ["killed"] = 20f, ["respawn"] = 9.4f, ["dire_win"] = 50.9f, ["dire_lose"] = 43.2f,
    };

    private readonly List<(CSoundEventEntity Ent, float Len, float Next)> _loops = new();
    private readonly float[] _randomNext = new float[16];
    private readonly Dictionary<int, float> _playerBirdsNext = new();
    private readonly Random _rng = new();
    private CSoundEventEntity? _music;
    private string _musicKind = "";
    private float _musicEnd;
    private int _musicIndex;
    private float _lastAmbientTick;

    private CSoundEventEntity? MakeSoundEntity(string ev, Vector? pos, bool start)
    {
        var e = Utilities.CreateEntityByName<CSoundEventEntity>("point_soundevent");
        if (e == null) return null;
        e.SoundName = ev;
        e.ToLocalPlayer = pos == null;   // no position: plays for everyone, like UI music
        e.StopOnNew = true;
        e.StartOnSpawn = start;
        e.DispatchSpawn();
        if (pos != null) e.Teleport(pos, null, null);
        if (start) e.AcceptInput("StartSound");
        return e;
    }

    private void UpdateAmbient()
    {
        var now = Server.CurrentTime;
        if (now - _lastAmbientTick < 0.5f) return;
        _lastAmbientTick = now;
        var humans = Utilities.GetPlayers().Where(p => p != null && p.IsValid && !p.IsBot).ToList();
        if (humans.Count == 0) return;
        SpawnWildlife();
        UpdateLights(humans);
        UpdateFootsteps(humans);

        try
        {
            // loops: create once, restart when the file ends
            if (_loops.Count == 0 || _loops.Any(l => !l.Ent.IsValid))
            {
                foreach (var l in _loops) if (l.Ent.IsValid) l.Ent.Remove();
                _loops.Clear();
                foreach (var (ev, pos, len) in AmbientLoops)
                {
                    var e = MakeSoundEntity("dota.amb." + ev, pos, true);
                    if (e != null) _loops.Add((e, len, now + len));
                }
            }
            for (var i = 0; i < _loops.Count; i++)
            {
                if (now < _loops[i].Next) continue;
                _loops[i].Ent.AcceptInput("StartSound");
                _loops[i] = (_loops[i].Ent, _loops[i].Len, now + _loops[i].Len);
            }

            // random birds, bats, tormentor
            for (var i = 0; i < AmbientRandom.Length; i++)
            {
                if (now < _randomNext[i]) continue;
                var r = AmbientRandom[i];
                if (_randomNext[i] > 0) PlayDotaSound("amb." + r.Ev, r.Pos);
                _randomNext[i] = now + r.Min + (float)_rng.NextDouble() * (r.Max - r.Min);
            }

            // birds somewhere near every CS player, so the forest never sounds empty
            foreach (var p in humans)
            {
                var pawn = p.PlayerPawn.Value;
                var pos = pawn?.AbsOrigin;
                if (pos == null || !p.PawnIsAlive) continue;
                if (_playerBirdsNext.TryGetValue(p.Slot, out var t) && now < t) continue;
                if (t > 0)
                {
                    var a = _rng.NextDouble() * Math.PI * 2;
                    PlayDotaSound("amb.birds", new Vector(pos.X + (float)Math.Cos(a) * 700, pos.Y + (float)Math.Sin(a) * 700, pos.Z + 300));
                }
                _playerBirdsNext[p.Slot] = now + 10 + (float)_rng.NextDouble() * 12;
            }

            UpdateMusic(humans, now);
        }
        catch (Exception e) { Logger.LogWarning("DotaCS ambience: {Error}", e.Message); }
    }

    // ------------------------------------------------------------ music: laning / battle / Roshan, like in Dota
    private void UpdateMusic(List<CCSPlayerController> humans, float now)
    {
        var kind = "laning";
        foreach (var p in humans)
        {
            var pos = p.PlayerPawn.Value?.AbsOrigin;
            if (pos == null || !p.PawnIsAlive) continue;
            if (_units.Values.Any(u => u.Alive && u.Model == "roshan" && Dist2(u.X, u.Y, pos) < 1500)) { kind = "roshan"; break; }
            if (_heroes.Values.Any(h => h.Alive && Dist2(h.X, h.Y, pos) < 1800)) kind = "battle";
        }

        var switching = kind != _musicKind && !(_musicKind == "stinger" && now < _musicEnd);
        if (!switching && now < _musicEnd) return;

        var track = kind switch
        {
            "roshan" => "roshan",
            "battle" => BattleMusic[_musicIndex++ % BattleMusic.Length],
            _ => LaningMusic[_musicIndex++ % LaningMusic.Length],
        };
        PlayMusic(track, kind);
    }

    private void PlayMusic(string track, string kind)
    {
        if (_music != null && _music.IsValid) { _music.AcceptInput("StopSound"); _music.Remove(); }
        _music = MakeSoundEntity("dota.music." + track, null, true);
        _musicKind = kind;
        _musicEnd = Server.CurrentTime + (MusicLen.TryGetValue(track, out var len) ? len : 60f);
    }

    // short music cues: death, respawn, win/lose
    private void PlayStinger(string track)
    {
        try { PlayMusic(track, "stinger"); } catch { }
    }

    private static float Dist2(float x, float y, Vector p)
    {
        var dx = x - p.X; var dy = y - p.Y;
        return (float)Math.Sqrt(dx * dx + dy * dy);
    }
}
