# Dota 2 × CS2

**Real Dota 2 and real Counter-Strike 2, in one match, at the same time.**

Dota players play Dota. CS players play CS2. They are on the same map and see each other:
Pudge hooks a CT in Dota, and the CT flies across the river in CS2. A CT shoots Pudge in CS2, and Pudge loses HP in Dota.

> Early alpha, made for streams and playing with friends. Expect bugs.

## How it works

```
 Dota 2 custom game  ──HTTP──▶  bridge.py  ◀──HTTP──  CS2 server plugin (CounterStrikeSharp)
   (Lua, 20 ticks/s)          (localhost:3000)          (C#, every tick)
```

- **Dota side** (`dota_addon/`): every CS player is a unit in Dota. Spells, stuns, slows, hooks and damage on that unit are sent to CS2.
- **CS2 side** (`cs2_plugin/`): every Dota hero is an invisible bot with a scaled hitbox and a Dota model on top. Creeps, neutrals, Roshan, towers, trees and wildlife are props synced from Dota.
- **Map**: the real Dota map, rebuilt as a CS2 map 1:1 (same coordinates on both sides).
- **Bridge** (`bridge/bridge.py`): a tiny Python relay between the two games.

## What already works

- Pudge in CS2 with real Dota model and animations. Hook, Rot (slow), Dismember (stun) affect CS players
- CS players shoot heroes, creeps, neutrals, Roshan, towers, barracks and the Ancient. Damage goes into Dota
- Lane creeps, 50+ neutral types and Roshan visible and animated in CS2
- Trees cut in Dota disappear in CS2. HE grenades in CS2 knock trees down in Dota
- Destroyed buildings fall in CS2
- Dota music, ambience, ability sounds, footsteps; Dota torches as real lights; 200+ animated critters
- Dota minimap as the CS2 radar, Dire fountain shop and heal for CTs, twin gates teleport CTs

## Not in this repo (on purpose)

Models, textures, sounds and the map belong to **Valve** and are not redistributed here.
`tools/` contains the scripts that extract and convert them **from your own Dota 2 install**
(Source 2 Viewer CLI + Blender), so you build the assets locally.

## Requirements

- Dota 2 + Dota 2 Workshop Tools
- CS2 + CS2 Workshop Tools, a local CS2 dedicated server with Metamod + CounterStrikeSharp
- Python 3, .NET SDK (to build the plugin), Blender 4+ and Source 2 Viewer CLI (for the asset tools)

## Status / roadmap

- [x] Pudge
- [ ] More heroes
- [ ] Match rules (rounds, economy for CS players)
- [ ] Online play for friends (public bridge + server)
- [ ] One-click installer

## Credits

Made by [@arionustan](https://github.com/arionustan) with Claude.
Dota 2 and Counter-Strike 2 are trademarks of Valve Corporation. This is a fan project, not affiliated with Valve.
