// DotaCS: CS players can shoot Dota towers, barracks, fillers and the Ancient.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private record Building(string Id, float X, float Y, float Z, int Hp, int MaxHp, bool Alive, bool Invuln, string Name);
    private List<Building> _buildings = new();
    private readonly Dictionary<int, float> _buildingMsg = new();

    private static readonly Dictionary<string, float> WeaponDamage = new()
    {
        ["ak47"] = 36, ["m4a1"] = 33, ["m4a1_silencer"] = 38, ["awp"] = 115, ["ssg08"] = 88, ["deagle"] = 53, ["glock"] = 30,
        ["usp_silencer"] = 35, ["hkp2000"] = 35, ["p250"] = 38, ["fiveseven"] = 32, ["tec9"] = 33, ["cz75a"] = 31,
        ["elite"] = 38, ["revolver"] = 86, ["famas"] = 30, ["galilar"] = 30, ["aug"] = 28, ["sg556"] = 30, ["mp9"] = 26,
        ["mac10"] = 29, ["mp7"] = 29, ["mp5sd"] = 27, ["ump45"] = 35, ["p90"] = 26, ["bizon"] = 27, ["nova"] = 26,
        ["xm1014"] = 20, ["sawedoff"] = 32, ["mag7"] = 30, ["m249"] = 32, ["negev"] = 35, ["scar20"] = 80, ["g3sg1"] = 80,
    };

    private void ParseBuildings(string text)
    {
        var list = new List<Building>();
        foreach (var raw in text.Split('\n'))
        {
            var p = raw.Trim().Split(' ');
            // B id x y z hp maxhp alive invuln name
            if (p.Length < 10 || p[0] != "B") continue;
            list.Add(new Building(p[1], F(p[2]), F(p[3]), F(p[4]), (int)F(p[5]), (int)F(p[6]), p[7] == "1", p[8] == "1", p[9]));
        }
        if (list.Count > 0) _buildings = list;
    }

    private static float BuildingRadius(string name) =>
        name.Contains("fort") ? 300 : name.Contains("rax") ? 190 : name.Contains("tower") ? 140 : name.Contains("filler") ? 110 : 120;

    private HookResult OnBulletImpact(EventBulletImpact ev, GameEventInfo info)
    {
        try
        {
            var shooter = ev.Userid;
            if (shooter == null || !shooter.IsValid || shooter.IsBot) return HookResult.Continue;
            Building? hit = null;
            foreach (var b in _buildings)
            {
                if (!b.Alive) continue;
                var dx = ev.X - b.X; var dy = ev.Y - b.Y;
                var r = BuildingRadius(b.Name);
                if (dx * dx + dy * dy > r * r) continue;
                if (ev.Z < b.Z - 50 || ev.Z > b.Z + 900) continue;
                hit = b; break;
            }
            var weapon = shooter.PlayerPawn.Value?.WeaponServices?.ActiveWeapon.Value?.DesignerName ?? "weapon_gun";
            var key = weapon.Replace("weapon_", "");
            var dmg = WeaponDamage.TryGetValue(key, out var d) ? d : 25f;
            if (TryHitUnit(shooter, ev.X, ev.Y, ev.Z, dmg, weapon)) return HookResult.Continue;
            if (hit == null) return HookResult.Continue;
            if (!hit.Invuln) _hits.Enqueue(string.Format(Inv, "D {0} {1} {2} {3}", hit.Id, dmg, shooter.Slot, weapon));

            // show the building's HP to the shooter (at most twice a second)
            if (!_buildingMsg.TryGetValue(shooter.Slot, out var t) || Server.CurrentTime - t > 0.5f)
            {
                _buildingMsg[shooter.Slot] = Server.CurrentTime;
                var name = Pretty(hit.Name.Replace("goodguys_", "").Replace("badguys_", ""));
                shooter.PrintToCenter(hit.Invuln ? $"{name}: неуязвимо (сначала снеси предыдущую башню)" : $"{name}: {hit.Hp}/{hit.MaxHp}");
            }
        }
        catch { }
        return HookResult.Continue;
    }
}
