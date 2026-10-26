// DotaCS: Dota style HP bars over Dota heroes and units in CS2 (world text that always faces the player).
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private const float HpBarRange = 1800f;      // bars only near CS players (world text is not free)
    private const int HpBarSegments = 10, HpBarSegmentsHero = 14;
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
                if (h.Alive && h.Visible && h.MaxHp > 0 && players.Min(p => Dist2(h.X, h.Y, p)) < HpBarRange)
                    wanted["h" + h.Id] = (new Vector(h.X, h.Y, HeroFeetZ(h) + HeroCyl(h).Top + 40), h.Hp, h.MaxHp, true);
            foreach (var u in _units.Values)
            {
                if (!u.Alive || u.MaxHp <= 0 || players.Min(p => Dist2(u.X, u.Y, p)) > HpBarRange) continue;
                var hgt = UnitHitbox.TryGetValue(u.Model, out var hb) ? Math.Max(hb.H, 70f) : 95f;
                wanted["u" + u.Id] = (new Vector(u.X, u.Y, u.Z + hgt + 18), u.Hp, u.MaxHp, false);
            }
        }

        // rune labels, ward markers: also stood up and turned to the nearest player
        _billboards.RemoveAll(b => !b.IsValid);
        if (players.Count > 0)
            foreach (var b in _billboards)
            {
                var bp = b.AbsOrigin;
                if (bp == null) continue;
                var nb = players.OrderBy(p => (p.X - bp.X) * (p.X - bp.X) + (p.Y - bp.Y) * (p.Y - bp.Y)).First();
                b.Teleport(null, new QAngle(0, (float)(Math.Atan2(nb.Y - bp.Y, nb.X - bp.X) * 180 / Math.PI) + 90 + (_hpFlip ? 180 : 0), 90), null);
            }

        foreach (var id in _hpBar.Keys.ToList())
            if (!wanted.ContainsKey(id.TrimEnd('#')))
            {
                if (_hpBar[id].IsValid) _hpBar[id].Remove();
                _hpBar.Remove(id); _hpBarText.Remove(id);
            }

        foreach (var (id, w) in wanted)
        {
            var frac = Math.Clamp(w.Hp / (float)w.Max, 0f, 1f);
            var segs = w.Hero ? HpBarSegmentsHero : HpBarSegments;
            var filled = (int)Math.Ceiling(frac * segs);
            var color = frac > 0.6f ? System.Drawing.Color.FromArgb(255, 60, 220, 60)
                      : frac > 0.3f ? System.Drawing.Color.FromArgb(255, 235, 200, 40)
                      : System.Drawing.Color.FromArgb(255, 230, 50, 40);
            // the bar itself and, under it, the numbers
            // stand the text up and turn it to the nearest CS player (point_worldtext lies flat by default)
            var near = players.OrderBy(p => (p.X - w.Pos.X) * (p.X - w.Pos.X) + (p.Y - w.Pos.Y) * (p.Y - w.Pos.Y)).First();
            var yawTo = (float)(Math.Atan2(near.Y - w.Pos.Y, near.X - w.Pos.X) * 180 / Math.PI);
            var ang = new QAngle(0, yawTo + 90 + (_hpFlip ? 180 : 0), 90);
            // a thin Dota-like strip (the block glyph is ~1.6 em wide): hero ~140 units, creep ~80 units wide
            HpText(id, new string('█', filled) + new string('░', segs - filled), w.Pos, ang, color, 40, w.Hero ? 0.155f : 0.125f, false);
            HpText(id + "#", $"{Math.Max(0, w.Hp)} / {w.Max}", new Vector(w.Pos.X, w.Pos.Y, w.Pos.Z + (w.Hero ? 11 : 9)), ang,
                System.Drawing.Color.FromArgb(255, 255, 255, 255), 40, w.Hero ? 0.2f : 0.16f, false);
        }
    }

    private bool _hpFlip;
    private readonly List<CPointWorldText> _billboards = new();

    private void HpText(string id, string text, Vector pos, QAngle ang, System.Drawing.Color color, int font, float upp, bool background)
    {
        if (!_hpBar.TryGetValue(id, out var bar) || !bar.IsValid)
        {
            try
            {
                bar = Utilities.CreateEntityByName<CPointWorldText>("point_worldtext")!;
                if (bar == null) return;
                bar.MessageText = text;
                bar.Enabled = true;
                bar.Fullbright = true;
                bar.FontSize = font;
                bar.WorldUnitsPerPx = upp;
                bar.DrawBackground = background;
                bar.BackgroundBorderWidth = 3f; bar.BackgroundBorderHeight = 1.5f;
                bar.Color = color;
                bar.JustifyHorizontal = PointWorldTextJustifyHorizontal_t.POINT_WORLD_TEXT_JUSTIFY_HORIZONTAL_CENTER;
                bar.JustifyVertical = PointWorldTextJustifyVertical_t.POINT_WORLD_TEXT_JUSTIFY_VERTICAL_CENTER;
                bar.ReorientMode = PointWorldTextReorientMode_t.POINT_WORLD_TEXT_REORIENT_NONE;
                bar.DispatchSpawn();
                _hpBar[id] = bar; _hpBarText[id] = text;
            }
            catch { return; }
        }
        if (_hpBarText[id] != text)
        {
            _hpBarText[id] = text;
            bar.MessageText = text;
            bar.Color = color;
            Utilities.SetStateChanged(bar, "CPointWorldText", "m_messageText");
            Utilities.SetStateChanged(bar, "CPointWorldText", "m_Color");
        }
        bar.Teleport(pos, ang, null);
    }
}
