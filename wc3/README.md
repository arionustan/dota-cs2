# Dota 2 x Warcraft III (prototype)

- `wc3_to_dota.py`: WC3 MDX model -> SMD meshes/animations + vmdl/vmat for a Dota 2 custom game
- `pudge_to_mdx.py`: Dota 2 model (Blender scene) -> WC3 MDX v800 + BLP textures (run with `bpy`)
- `mpq.py`, `mdx.py`, `blp.py`: minimal MPQ, MDX and BLP1 readers/writers
- `build_map.py` + `dotawc3.j`: builds the test map from a melee map (WC3 1.29+, needs Blz natives)
- `bridge_wc3.py`: Dota (HTTP :3000) <-> WC3 (Preload files in Documents\Warcraft III\CustomMapData\DotaWC3)

Models and maps of Blizzard and Valve are not included; the scripts build them from your own game files.
