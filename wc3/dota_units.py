# Preplaced units from DotA 6.83d main(): (player, id, x, y, facing) plus readable names from the map's string files.
import re, json, sys
sys.path.insert(0, '/tmp/w3')
from mpq import MPQ
a = MPQ('/tmp/w3/dota683.w3x')
j = open('/tmp/w3/dota683n.j', encoding='latin1').read().split('\n')
s = next(i for i, l in enumerate(j) if l.startswith('function main takes'))
e = next(i for i, l in enumerate(j) if l.startswith('function config takes'))
p = None; out = []
for l in j[s:e]:
    m = re.match(r'set p=(.*)', l)
    if m: p = m.group(1)
    for m in re.finditer(r"CreateUnit\((\w+|Player\(\d+\)),'(\w{4})',(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", l):
        pl = p if m.group(1) == 'p' else m.group(1)
        out.append([pl, m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5))])
names = {}
for f in a.listfile():
    if f.lower().endswith('strings.txt') or f.lower().endswith('func.txt'):
        cur = None
        for l in a.read(f).decode('utf-8', 'ignore').splitlines():
            m = re.match(r'\[(\w{4})\]', l)
            if m: cur = m.group(1)
            elif cur and l.startswith('Name=') and cur not in names: names[cur] = l[5:]
for o in out: o.append(names.get(o[1], '?'))
json.dump(out, open('/tmp/w3/gen/dota683_units.json', 'w'), indent=0)
from collections import Counter
print(len(out), Counter(o[0] for o in out))
for o in out: print(o)
