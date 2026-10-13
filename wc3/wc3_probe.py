# Asks a LAN game hosted by Warcraft III itself for the exact map checksums (what our bridge must announce).
# 1) In WC3: Local Area Network -> New Game -> pick "DotaWC3 LAN" -> Create Game (stay in the lobby)
# 2) Run this script. It joins as a player for a second, reads MAPCHECK and leaves.
import socket, struct, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'DotaWC3_probe.json')
LOG = os.path.join(HERE, 'probe_log.txt')
lines = []

def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); lines.append(s)
    open(LOG, 'w', encoding='utf-8').write('\n'.join(lines))

def pkt(pid, body=b''): return struct.pack('<BBH', 0xF7, pid, len(body) + 4) + body

def decode_stat(enc):
    out = bytearray(); i = 0
    while i < len(enc):
        mask = enc[i]; chunk = enc[i + 1:i + 8]; i += 1 + len(chunk)
        for j, b in enumerate(chunk): out.append(b if mask & (1 << (j + 1)) else b - 1)
    return bytes(out)

def find_game():
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    u.bind(('0.0.0.0', 0)); u.settimeout(0.5)
    for attempt in range(20):
        for ver in (29, 30, 28, 31, 26):
            q = pkt(0x2F, b'PX3W' + struct.pack('<II', ver, 0))
            for addr in (('127.0.0.1', 6112), ('255.255.255.255', 6112)):
                try: u.sendto(q, addr)
                except OSError: pass
        t = time.time()
        while time.time() - t < 1.0:
            try: data, addr = u.recvfrom(4096)
            except socket.timeout: continue
            if len(data) > 4 and data[0] == 0xF7 and data[1] == 0x30:
                return data[4:], addr
        log('жду LAN-игру WC3... (создай её: Локальная сеть -> Новая игра -> DotaWC3 LAN)')
    return None, None

def main():
    body, addr = find_game()
    if not body:
        log('ОШИБКА: не нашёл LAN-игру, созданную в WC3'); return
    product, ver, hc, ek = body[:4], *struct.unpack_from('<III', body, 4)
    p = 16
    e = body.index(b'\0', p); name = body[p:e].decode('utf-8', 'ignore'); p = e + 1
    e = body.index(b'\0', p); p = e + 1
    e = body.index(b'\0', p); stat = decode_stat(body[p:e]); p = e + 1
    slots_total, gtype, unk, slots_open, uptime = struct.unpack_from('<IIIII', body, p); p += 20
    port = struct.unpack_from('<H', body, p)[0]
    flags, z, w, h, crc = struct.unpack_from('<IBHHI', stat, 0)
    q = 13; e = stat.index(b'\0', q); path = stat[q:e].decode('utf-8', 'ignore'); q = e + 1
    e = stat.index(b'\0', q); host = stat[q:e].decode('utf-8', 'ignore'); q = e + 1
    rest = stat[q:]
    info = {'game': name, 'product': product.decode(), 'version': ver, 'gameinfo_from': addr[0], 'port': port,
            'stat_flags': flags, 'width': w, 'height': h, 'stat_xoro': crc, 'stat_path': path, 'stat_host': host,
            'stat_rest_hex': rest.hex(), 'slots_total': slots_total, 'game_type': gtype, 'unknown': unk, 'slots_open': slots_open}
    log('GAMEINFO:', info)
    c = socket.create_connection((addr[0], port), timeout=5)
    c.sendall(pkt(0x1E, struct.pack('<IIBHI', hc, ek, 0, 6112, 0) + b'probe\0' + struct.pack('<I', 0) + b'\x02\x00' + b'\0' * 14))
    def rd():
        hd = b''
        while len(hd) < 4: hd += c.recv(4 - len(hd))
        n = struct.unpack_from('<H', hd, 2)[0]; b = b''
        while len(b) < n - 4: b += c.recv(n - 4 - len(b))
        return hd[1], b
    for _ in range(20):
        pid, b = rd()
        log('пакет 0x%02X, %d байт: %s' % (pid, len(b), b[:80].hex()))
        if pid == 0x04:
            info['slotinfojoin_hex'] = b.hex()
        if pid == 0x3D:
            q = 4; e = b.index(b'\0', q)
            info['path'] = b[q:e].decode('utf-8', 'ignore'); q = e + 1
            info['size'], info['crc32'], info['xoro'] = struct.unpack_from('<III', b, q); q += 12
            info['sha1'] = b[q:q + 20].hex(); info['mapcheck_rest_hex'] = b[q + 20:].hex()
            break
    try: c.sendall(pkt(0x21, struct.pack('<I', 7)))
    except OSError: pass
    c.close()
    json.dump(info, open(OUT, 'w'), indent=1)
    log('ГОТОВО, сохранено в', OUT)
    log(json.dumps(info, indent=1))

if __name__ == '__main__':
    try: main()
    except Exception as e: log('ОШИБКА:', repr(e))
    input('Enter чтобы закрыть')
