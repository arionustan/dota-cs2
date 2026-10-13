# DotaWC3 bridge: Dota 2 custom game (HTTP, port 3000)  <->  Warcraft III map (Preload files).
#
# WC3 writes  Documents\Warcraft III\CustomMapData\DotaWC3\out.txt : "S seq lastK", "P 0 x y 0 fx fy 0 hp name", "D heroId dmg 0 weapon;"
# WC3 reads   Documents\Warcraft III\CustomMapData\DotaWC3\in.txt  : a Preload script that puts our data into an ability tooltip
# Dota posts  /dota  : H lines (heroes), C lines (commands for the WC3 hero); gets back P and D lines.
#
# Run: python bridge_wc3.py      Stop: Ctrl+C
import os, re, sys, time, threading, ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 3000

def documents():
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)   # CSIDL_PERSONAL
        if buf.value: return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')

WC3_DIR = r'C:\Games\Warcraft III'
DIRS = [os.path.join(documents(), 'Warcraft III', 'CustomMapData', 'DotaWC3'),
        os.path.join(WC3_DIR, 'DotaWC3')]
for d in DIRS:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

lock = threading.Lock()
state = {'heroes': [], 'dota_time': 0.0, 'players': [], 'wc3_time': 0.0, 'to_dota': [],
         'k_cmds': [], 'k_next': 1, 'acked_k': 0, 'cmd': {}, 'wc3_seq': -1, 'in_seq': 0, 'dota_n': 0, 'wc3_n': 0}

def split(body):
    return [l.strip() for l in body.splitlines() if l.strip() and l.strip() != 'none']

class Handler(BaseHTTPRequestHandler):
    def _reply(self, lines):
        data = ('\n'.join(lines) if lines else 'none').encode()
        self.send_response(200); self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        lines = split(self.rfile.read(n).decode('utf-8', 'ignore') if n else '')
        now = time.time()
        if not self.path.startswith('/dota'):
            return self._reply([])
        with lock:
            state['heroes'] = [l for l in lines if l.startswith('H ')]
            for l in lines:
                p = l.split()
                if p[0] != 'C' or len(p) < 3: continue
                kind, slot = p[1], p[2]
                if kind == 'K' and len(p) >= 4:
                    state['k_cmds'].append((state['k_next'], 'K %s %s %d' % (slot, p[3], state['k_next']))); state['k_next'] += 1
                elif kind == 'T' and len(p) >= 5:
                    state['cmd'][('T', slot)] = ('T %s %s %s' % (slot, p[3], p[4]), now)
                elif kind == 'S' and len(p) >= 4:
                    state['cmd'][('S', slot)] = ('S %s %s' % (slot, p[3]), now)
                elif kind == 'V' and len(p) >= 4:
                    state['cmd'][('V', slot)] = ('V %s %s' % (slot, p[3]), now)
                elif kind == 'H' and len(p) >= 4:
                    state['cmd'][('L', slot)] = ('L %s %s' % (slot, p[3]), now)
            state['dota_time'] = now; state['dota_n'] += 1
            fresh = now - state['wc3_time'] < 2.0
            answer = (state['players'] if fresh else []) + state['to_dota']
            state['to_dota'] = []
        self._reply(answer)

    def do_GET(self):
        self._reply(['DotaWC3 bridge is running'])

    def log_message(self, *a): pass

PRELOAD_RE = re.compile(r'call Preload\(\s*"(.*?)"\s*\)')

def read_wc3():
    best = None
    for d in DIRS:
        f = os.path.join(d, 'out.txt')
        try:
            m = os.path.getmtime(f)
            if best is None or m > best[0]: best = (m, f)
        except OSError: pass
    if not best: return
    try: text = open(best[1], encoding='utf-8', errors='ignore').read()
    except OSError: return
    lines = []
    for s in PRELOAD_RE.findall(text):
        lines += [x.strip() for x in s.split(';') if x.strip()]
    if not lines or not lines[0].startswith('S '): return
    hdr = lines[0].split()
    seq = int(hdr[1]); acked = int(hdr[2]) if len(hdr) > 2 else 0
    with lock:
        if seq == state['wc3_seq']: return
        state['wc3_seq'] = seq; state['wc3_time'] = time.time(); state['wc3_n'] += 1
        state['acked_k'] = max(state['acked_k'], acked)
        state['players'] = [l for l in lines[1:] if l.startswith('P ')]
        state['to_dota'] += [l for l in lines[1:] if l.startswith('D ')]

def write_wc3():
    now = time.time()
    with lock:
        state['in_seq'] += 1
        out = ['#%d' % state['in_seq']]
        if now - state['dota_time'] < 2.0:
            for h in state['heroes']:
                p = h.split()
                # H id x y z fx fy hp maxhp alive name act fx  ->  H id x y fx fy hp maxhp alive act
                if len(p) >= 10:
                    act = p[11] if len(p) > 11 else '-'
                    out.append('H %s %s %s %s %s %s %s %s %s' % (p[1], p[2], p[3], p[5], p[6], p[7], p[8], p[9], act))
        state['k_cmds'] = [(i, c) for i, c in state['k_cmds'] if i > state['acked_k']]
        out += [c for _, c in state['k_cmds']]
        for key, (c, t) in list(state['cmd'].items()):
            if now - t > 0.35: del state['cmd'][key]
            else: out.append(c)
    data = ';'.join(out) + ';'
    data = data[:1000]
    script = ('function PreloadFiles takes nothing returns nothing\n\n\tcall PreloadStart()\n'
              '\tcall BlzSetAbilityTooltip(\'AHbz\', "%s", 0)\n\tcall PreloadEnd( 0.0 )\n\nendfunction\n' % data)
    for d in DIRS:
        f = os.path.join(d, 'in.txt'); tmp = f + '.tmp'
        try:
            open(tmp, 'w', encoding='utf-8').write(script)
            os.replace(tmp, f)
        except OSError: pass

def loop():
    last_write = 0.0; last_print = 0.0
    while True:
        read_wc3()
        now = time.time()
        if now - last_write >= 0.1:
            write_wc3(); last_write = now
        if now - last_print >= 1.0:
            last_print = now
            with lock:
                print('WC3: %s, %d upd/s  |  Dota: %d heroes, %d upd/s' % (
                    'Мастер клинка' if state['players'] else 'нет героя', state['wc3_n'], len(state['heroes']), state['dota_n']))
                state['wc3_n'] = 0; state['dota_n'] = 0
        time.sleep(0.03)

if __name__ == '__main__':
    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        print('ОШИБКА: порт %d занят. Закрой старый мост или сервер КС.' % PORT); input(); sys.exit(1)
    print('DotaWC3 мост запущен. Файлы обмена:', DIRS[0])
    threading.Thread(target=server.serve_forever, daemon=True).start()
    loop()
