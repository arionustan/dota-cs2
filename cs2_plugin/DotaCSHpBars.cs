// DotaCS: Dota style HP bars over Dota heroes and units in CS2 (world text that always faces the player).
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private const float HpBarRange = 1800f;      // bars only near CS players (world text is not free)
    private const int HpBarSegments = 12;
    private readonly Dictionary<string, CPointWorldText> _hpBar = new();
    private readonly Dictionary<string, string> _hpBarText = new();

    private void UpdateHpBars()
    {
        var players = Utilities.GetPlayers().Where(p => p.IsValid && !p.IsBot && p.PawnIsAlive)
            .Select(p => p.PlayerPawn.Value?.AbsOrigin).Where(o => o != null).Select(o => o!).ToList();
        var wanted = new Dictionary<string, (Vector Pos, int Hp, int Max, bool Hero)>();
        if (players.Count > 0)
        {
            foreach (var h in _heroes.Values)
                if (h.Alive && h.Visible && h.MaxHp > 0 && players.Min(p => Dist2(h.X, h.Y, p)) < HpBarRange * HpBarRange)
                    wanted["h" + h.Id] = (new Vector(h.X, h.Y, h.Z + 255), h.Hp, h.MaxHp, true);
            foreach (var u in _units.Values)
            {
                if (!u.Alive || u.MaxHp <= 0 || players.Min(p => Dist2(u.X, u.Y, p)) > HpBarRange * HpBarRange) continue;
                var hgt = UnitHitbox.TryGetValue(u.Model, out var hb) ? Math.Max(hb.H, 70f) : 95f;
                wanted["u" + u.Id] = (new Vector(u.X, u.Y, u.Z + hgt + 18), u.Hp, u.MaxHp, false);
            }
        }

        foreach (var id in _hpBar.Keys.ToList())
            if (!wanted.ContainsKey(id))
            {
                if (_hpBar[id].IsValid) _hpBar[id].Remove();
                _hpBar.Remove(id); _hpBarText.Remove(id);
            }

        foreach (var (id, w) in wanted)
        {
            var frac = Math.Clamp(w.Hp / (float)w.Max, 0f, 1f);
            var filled = (int)Math.Ceiling(frac * HpBarSegments);
            var text = new string('█', filled) + new string('░', HpBarSegments - filled);
            if (!_hpBar.TryGetValue(id, out var bar) || !bar.IsValid)
            {
                try
                {
                    bar = Utilities.CreateEntityByName<CPointWorldText>("point_worldtext")!;
                    if (bar == null) continue;
                    bar.MessageText = text;
                    bar.Enabled = true;
                    bar.Fullbright = true;
                    bar.FontSize = w.Hero ? 34 : 24;
                    bar.WorldUnitsPerPx = 0.25f;
                    bar.JustifyHorizontal = PointWorldTextJustifyHorizontal_t.POINT_WORLD_TEXT_JUSTIFY_HORIZONTAL_CENTER;
                    bar.JustifyVertical = PointWorldTextJustifyVertical_t.POINT_WORLD_TEXT_JUSTIFY_VERTICAL_CENTER;
                    bar.ReorientMode = PointWorldTextReorientMode_t.POINT_WORLD_TEXT_REORIENT_AROUND_UP;
                    bar.DispatchSpawn();
                    _hpBar[id] = bar; _hpBarText[id] = "";
                }
                catch { continue; }
            }
            if (_hpBarText[id] != text)
            {
                _hpBarText[id] = text;
                bar.MessageText = text;
                bar.Color = frac > 0.6f ? System.Drawing.Color.FromArgb(255, 60, 220, 60)
                          : frac > 0.3f ? System.Drawing.Color.FromArgb(255, 235, 200, 40)
                          : System.Drawing.Color.FromArgb(255, 230, 50, 40);
                Utilities.SetStateChanged(bar, "CPointWorldText", "m_messageText");
                Utilities.SetStateChanged(bar, "CPointWorldText", "m_Color");
            }
            bar.Teleport(w.Pos, null, null);
        }
    }
}
