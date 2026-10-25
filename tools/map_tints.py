# DotaCS: per-material tint colors of the real Dota map.
# Dota colors its gray rocks, cliffs and stairs per placed prop (aggregate m_vTintColor in maps/dota/worldnodes/n0.vwnod_c).
# Usage: Source2Viewer-CLI -i n0.vwnod_c -b DATA > n0.txt ; python3 map_tints.py n0.txt > tints.json
# START_ALL.bat recompiles the tinted vmats (g_vColorTint = tint * 1.25) once.
import re, sys, json, statistics
t = open(sys.argv[1]).read()
seg = t[t.index('m_aggregateSceneObjects'):]
res = {}
for o in re.split(r'\n\t\t\{\n\t\t\tm_allFlags', seg)[1:]:
    m = re.search(r'm_renderableModel = (?:resource:)?"([^"]+)"', o)
    if not m: continue
    tints = [tuple(int(x) for x in c.split(',')) for c in re.findall(r'm_vTintColor = \[ ([\d, ]+)\]', o)]
    if not tints: continue
    name = re.sub(r'_\d+\.vmdl$', '', re.sub(r'.*n0_lr\d+_agg_(prop_|merge_)?', '', m.group(1)))
    res.setdefault(name, []).extend(tints)
out = {k: [round(statistics.mean(x[i] for x in v) / 255, 3) for i in range(3)] for k, v in res.items()}
print(json.dumps({k: v for k, v in out.items() if any(abs(c - 1) > 0.03 for c in v)}, indent=0))
