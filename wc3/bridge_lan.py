# DotaWC3 LAN bridge: hosts a Warcraft III LAN game (the bridge is player 2, "DotaBridge") and talks to Dota 2 over HTTP.
#
#   WC3 -> bridge : the map syncs gamecache integers; the KEY of each sync action is our text ("S ..;P ..;D ..;")
#   bridge -> WC3 : the bridge player sends gamecache sync actions: integers "0".."n-1" (text packed 5 chars per int), "n", "s"
#   Dota <-> bridge: same HTTP protocol as the CS2 plugin (port 3000, POST /dota)
#
# Run: python bridge_lan.py      In WC3: Local Area Network -> join "DotaWC3"
import os, sys, time, json, socket, struct, threading, zlib, random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
INFO = json.load(open(os.path.join(HERE, 'DotaWC3_LAN.json')))
WC3_DIR = r'C:\Games\Warcraft III'
HOST_PORT = 6113
HTTP_PORT = 3000
GAME_NAME = 'DotaWC3'
BOT_NAME = 'DotaBridge'
VERSION = INFO.get('version', 29)
LATENCY = 100            # ms between action packets
NUM_SLOTS = INFO.get('slots', 4)
CACHE = b'dwc.w3v'
CHARS = " 0123456789;-.#ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"

def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)

# ------------------------------------------------------------------ W3GS packets
def pkt(pid, body=b''):
    return struct.pack('<BBH', 0xF7, pid, len(body) + 4) + body

def cstr(s): return s.encode('utf-8') + b'\0'

def encode_stat(data):
    out = bytearray()
    for i in range(0, len(data), 7):
        chunk = data[i:i + 7]; mask = 1; enc = bytearray()
        for j, b in enumerate(chunk):
            if b % 2 == 0: enc.append(b + 1)
            else: enc.append(b); mask |= 1 << (j + 1)
        out.append(mask); out += enc
    return bytes(out)

def sockaddr(ip='0.0.0.0', port=0):
    return b'\x02\x00' + struct.pack('>H', port) + socket.inet_aton(ip) + b'\0' * 8

class Slot:
    def __init__(self, pid=0, status=0, team=0, colour=0):
        self.pid, self.download, self.status, self.computer = pid, 255, status, 0
        self.team, self.colour, self.race, self.ctype, self.handicap = team, colour, 0x60, 1, 100
    def pack(self):
        return bytes([self.pid, self.download, self.status, self.computer, self.team, self.colour, self.race, self.ctype, self.handicap])

class Game:
    def __init__(self):
        self.host_counter = random.randint(1, 0xFFFF); self.entry_key = random.randint(1, 0x7FFFFFFF)
        self.seed = random.randint(0, 0x7FFFFFFF)
        self.reset()

    def reset(self):
        self.slots = [Slot(status=0, team=i, colour=i) for i in range(NUM_SLOTS)]
        for s in self.slots[2:]: s.status = 1                     # only 2 players: you and the bridge
        self.slots[1] = Slot(pid=1, status=2, team=1, colour=1)   # the bridge itself
        self.slots[1].download = 100
        self.conn = None; self.player_pid = 2; self.player_name = ''
        self.state = 'lobby'; self.loaded = False; self.started = time.time()
        self.map_ok = False
        self.pending = []

    def slot_info(self):
        b = bytes([len(self.slots)]) + b''.join(s.pack() for s in self.slots)
        return b + struct.pack('<IBB', self.seed, 0, len(self.slots))

    def gameinfo(self):
        flags = 0x00000002 | 0x00000800 | 0x00004000 | 0x00060000
        stat = struct.pack('<IBHHI', flags, 0, INFO['width'], INFO['height'], INFO['xoro'])
        stat += cstr(INFO['path']) + cstr(BOT_NAME) + b'\0' + bytes.fromhex(INFO['sha1'])
        open_slots = sum(1 for s in self.slots if s.status == 0)
        body = b'PX3W' + struct.pack('<III', VERSION, self.host_counter, self.entry_key)
        body += cstr(GAME_NAME) + b'\0' + encode_stat(stat) + b'\0'
        body += struct.pack('<IIIII', NUM_SLOTS, 1, 1, open_slots + 1, int(time.time() - self.started))
        body += struct.pack('<H', HOST_PORT)
        return pkt(0x30, body)

game = Game()
send_lock = threading.Lock()

def send(data):
    c = game.conn
    if not c: return
    try:
        with send_lock: c.sendall(data)
    except OSError as e:
        log('send error', e); game.conn = None

# ------------------------------------------------------------------ shared state with Dota (same as bridge_wc3.py)
lock = threading.Lock()
state = {'heroes': [], 'dota_time': 0.0, 'players': [], 'wc3_time': 0.0, 'to_dota': [],
         'k_cmds': [], 'k_next': 1, 'acked_k': 0, 'cmd': {}, 'wc3_seq': -1, 'in_seq': 0, 'dota_n': 0, 'wc3_n': 0}

def wc3_text():
    now = time.time()
    with lock:
        state['in_seq'] += 1
        out = ['#%d' % state['in_seq']]
        if now - state['dota_time'] < 2.0:
            for h in state['heroes']:
                p = h.split()
                if len(p) >= 10:
                    act = p[11] if len(p) > 11 else '-'
                    out.append('H %s %d %d %s %s %s %s %s %s' % (p[1], float(p[2]), float(p[3]), p[5], p[6], p[7], p[8], p[9], act))
        state['k_cmds'] = [(i, c) for i, c in state['k_cmds'] if i > state['acked_k']]
        out += [c for _, c in state['k_cmds']]
        for key, (c, t) in list(state['cmd'].items()):
            if now - t > 0.35: del state['cmd'][key]
            else: out.append(c)
    text = ';'.join(out) + ';'
    return ''.join(ch if ch in CHARS else '_' for ch in text)[:900]

def sync_int(key, value):
    return b'\x6b' + CACHE + b'\0' + b'i\0' + key.encode() + b'\0' + struct.pack('<i', value)

def bridge_actions():
    text = wc3_text()
    text += ' ' * (-len(text) % 5)
    acts = b''; n = 0
    for i in range(0, len(text), 5):
        v = 0
        for ch in reversed(text[i:i + 5]): v = v * 67 + CHARS.index(ch)
        acts += sync_int(str(n), v); n += 1
    acts += sync_int('n', n) + sync_int('s', state['in_seq'])
    return acts

def handle_wc3_text(t):
    lines = [x.strip() for x in t.split(';') if x.strip()]
    if not lines or not lines[0].startswith('S '): return
    hdr = lines[0].split()
    with lock:
        state['wc3_time'] = time.time(); state['wc3_n'] += 1
        if len(hdr) > 2: state['acked_k'] = max(state['acked_k'], int(hdr[2]))
        ps = [l for l in lines[1:] if l.startswith('P ')]
        if ps: state['players'] = ps
        state['to_dota'] += [l for l in lines[1:] if l.startswith('D ')]

def parse_actions(blob):
    # find our gamecache sync actions inside whatever the player sent
    mark = b'\x6b' + CACHE + b'\0' + b'o\0'
    i = 0
    while True:
        i = blob.find(mark, i)
        if i < 0: break
        j = i + len(mark); e = blob.find(b'\0', j)
        if e < 0: break
        handle_wc3_text(blob[j:e].decode('utf-8', 'ignore'))
        i = e + 5

# ------------------------------------------------------------------ TCP game connection
def recv_exact(c, n):
    b = b''
    while len(b) < n:
        d = c.recv(n - len(b))
        if not d: raise ConnectionError('closed')
        b += d
    return b

def on_packet(pid, body):
    if pid == 0x1E:                                    # REQJOIN
        name_end = body.index(b'\0', 15)
        game.player_name = body[15:name_end].decode('utf-8', 'ignore')
        s0 = game.slots[0]; s0.pid = game.player_pid; s0.status = 2; s0.download = 255
        si = game.slot_info()
        send(pkt(0x04, struct.pack('<H', len(si)) + si + bytes([game.player_pid]) + sockaddr('127.0.0.1', 0)))
        send(pkt(0x06, struct.pack('<I', 2) + bytes([1]) + cstr(BOT_NAME) + b'\x01\x00' + sockaddr() + sockaddr()))
        send(pkt(0x3D, struct.pack('<I', 1) + cstr(INFO['path']) + struct.pack('<III', INFO['size'], INFO['crc32'], INFO['xoro']) + bytes.fromhex(INFO['sha1'])))
        log('Игрок вошёл в лобби:', game.player_name)
    elif pid == 0x42:                                  # MAPSIZE
        flag = body[4]; size = struct.unpack_from('<I', body, 5)[0]
        if flag == 1 and size == INFO['size']:
            if not game.map_ok:
                game.map_ok = True; game.slots[0].download = 100
                si = game.slot_info(); send(pkt(0x09, struct.pack('<H', len(si)) + si))
                log('Карта у игрока совпадает, запускаю игру через 3 секунды')
                threading.Timer(3.0, start_game).start()
        else:
            log('ОШИБКА: WC3 говорит, что карта другая (flag %d, size %d, ждали %d). Положи DotaWC3_LAN.w3x в Maps.' % (flag, size, INFO['size']))
    elif pid == 0x23:                                  # GAMELOADED_SELF
        send(pkt(0x08, bytes([game.player_pid])))
        game.loaded = True; game.state = 'game'
        log('WC3 загрузил карту, игра идёт')
    elif pid == 0x26:                                  # OUTGOING_ACTION
        blob = body[4:]
        game.pending.append((game.player_pid, blob))
        parse_actions(blob)
    elif pid == 0x27:                                  # KEEPALIVE
        pass
    elif pid == 0x21:                                  # LEAVEGAME
        log('Игрок вышел из игры'); game.conn = None
    elif pid == 0x46:
        pass
    elif pid == 0x28:
        pass
    else:
        log('пакет 0x%02X (%d байт)' % (pid, len(body)))

def start_game():
    if not game.conn or game.state != 'lobby': return
    send(pkt(0x0A)); time.sleep(0.5); send(pkt(0x0B))
    game.state = 'loading'
    send(pkt(0x08, bytes([1])))                        # the bridge has "loaded" instantly
    log('Отсчёт закончен, WC3 грузит карту...')

def client_loop(c):
    game.reset(); game.conn = c; game.pending = []
    c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while game.conn is c:
            h = recv_exact(c, 4)
            if h[0] != 0xF7: raise ValueError('bad header %r' % h)
            n = struct.unpack_from('<H', h, 2)[0]
            on_packet(h[1], recv_exact(c, n - 4) if n > 4 else b'')
    except Exception as e:
        log('Соединение с WC3 закрыто:', e)
    finally:
        if game.conn is c: game.conn = None
        try: c.close()
        except OSError: pass
        game.reset()

def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', HOST_PORT)); s.listen(4)
    while True:
        c, addr = s.accept()
        if game.conn:
            c.close(); continue
        log('Подключение от', addr)
        threading.Thread(target=client_loop, args=(c,), daemon=True).start()

def udp_announcer():
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        if game.state == 'lobby':
            data = game.gameinfo()
            for addr in (('255.255.255.255', 6112),):
                try: u.sendto(data, addr)
                except OSError: pass
        time.sleep(1.0)

def game_loop():
    last_ping = 0; last_print = 0
    while True:
        t0 = time.time()
        if game.conn and game.state == 'game':
            acts = [(1, bridge_actions())] + game.pending
            game.pending = []
            sub = b''.join(struct.pack('<BH', p, len(a)) + a for p, a in acts)
            crc = zlib.crc32(sub) & 0xFFFF
            send(pkt(0x0C, struct.pack('<HH', LATENCY, crc) + sub))
        if game.conn and t0 - last_ping > 5:
            last_ping = t0; send(pkt(0x01, struct.pack('<I', int(t0 * 1000) & 0xFFFFFFFF)))
        if t0 - last_print >= 1.0:
            last_print = t0
            with lock:
                print('WC3: %s, %d upd/s  |  Dota: %d heroes, %d upd/s' % (
                    {'lobby': 'жду в LAN', 'loading': 'загрузка', 'game': 'игра'}[game.state] if game.conn or game.state == 'lobby' else '-',
                    state['wc3_n'], len(state['heroes']), state['dota_n']), flush=True)
                state['wc3_n'] = 0; state['dota_n'] = 0
        time.sleep(max(0.0, LATENCY / 1000.0 - (time.time() - t0)))

# ------------------------------------------------------------------ HTTP for Dota (same protocol as before)
class Handler(BaseHTTPRequestHandler):
    def _reply(self, lines):
        data = ('\n'.join(lines) if lines else 'none').encode()
        self.send_response(200); self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        lines = [l.strip() for l in (self.rfile.read(n).decode('utf-8', 'ignore') if n else '').splitlines() if l.strip() and l.strip() != 'none']
        now = time.time()
        if not self.path.startswith('/dota'): return self._reply([])
        with lock:
            state['heroes'] = [l for l in lines if l.startswith('H ')]
            for l in lines:
                p = l.split()
                if p[0] != 'C' or len(p) < 3: continue
                kind, slot = p[1], p[2]
                if kind == 'K' and len(p) >= 4:
                    state['k_cmds'].append((state['k_next'], 'K %s %s %d' % (slot, p[3], state['k_next']))); state['k_next'] += 1
                elif kind == 'T' and len(p) >= 5: state['cmd'][('T', slot)] = ('T %s %d %d' % (slot, float(p[3]), float(p[4])), now)
                elif kind == 'S' and len(p) >= 4: state['cmd'][('S', slot)] = ('S %s %s' % (slot, p[3]), now)
                elif kind == 'V' and len(p) >= 4: state['cmd'][('V', slot)] = ('V %s %s' % (slot, p[3]), now)
                elif kind == 'H' and len(p) >= 4: state['cmd'][('L', slot)] = ('L %s %s' % (slot, p[3]), now)
            state['dota_time'] = now; state['dota_n'] += 1
            fresh = now - state['wc3_time'] < 2.0
            answer = (state['players'] if fresh else []) + state['to_dota']
            state['to_dota'] = []
        self._reply(answer)
    def do_GET(self): self._reply(['DotaWC3 LAN bridge is running'])
    def log_message(self, *a): pass

if __name__ == '__main__':
    try:
        http = ThreadingHTTPServer(('127.0.0.1', HTTP_PORT), Handler)
    except OSError:
        print('ОШИБКА: порт %d занят. Закрой старый мост или сервер КС.' % HTTP_PORT); input(); sys.exit(1)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_announcer, daemon=True).start()
    log('DotaWC3 LAN мост запущен. В WC3: Локальная сеть -> игра "%s"' % GAME_NAME)
    game_loop()
