import re
def parse_slk(data):
    cells = {}; x = y = None
    for l in data.decode('latin1').splitlines():
        if not l.startswith('C;'): continue
        k = None
        for part in l.split(';')[1:]:
            if part.startswith('X'): x = int(part[1:])
            elif part.startswith('Y'): y = int(part[1:])
            elif part.startswith('K'): k = part[1:].strip('"')
        if k is not None: cells[(y, x)] = k
    hdr = {v: kx for (ky, kx), v in cells.items() if ky == 1}
    rows = {v: ky for (ky, kx), v in cells.items() if kx == 1 and ky > 1}
    return cells, hdr, rows
