import sys, os
sys.path.insert(0, '/tmp/dx')
from vpk import read_dir, get, rerl
E, D = read_dir('/mnt/user-data/uploads/dota/pak01_dir.vpk')
CH = '/mnt/user-data/uploads/dota'; G = '/tmp/dx/game'
todo = [a.lower() for a in sys.argv[1:]]; seen = set(); missing = {}
while todo:
    n = todo.pop()
    if n in seen: continue
    seen.add(n)
    if n not in E: continue
    arc = E[n][0]
    if arc != 0x7fff and not os.path.exists(os.path.join(CH, 'pak01_%03d.vpk' % arc)):
        missing.setdefault(arc, []).append(n); continue
    buf = get(E, D, None, n, CH)
    out = os.path.join(G, n); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(buf)
    for r in rerl(buf):
        r = r.lower()
        if r.endswith(('.vmat', '.vtex', '.vmdl', '.vmesh', '.vagrp', '.vanim', '.vseq', '.vphys', '.vmorf')):
            todo.append(r + '_c')
print('extracted', len(seen) - sum(len(v) for v in missing.values()))
print('missing chunks', {k: len(v) for k, v in sorted(missing.items())})
