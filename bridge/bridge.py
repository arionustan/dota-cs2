# DotaCS bridge: relays state and events between the CS2 server plugin and Dota.
#
# CS2 -> bridge  (POST /cs)    lines:  P slot x y z fx fy isBot hp      (alive CS players)
#                                      D heroId damage attackerSlot weapon (CS player hit a Dota hero)
#   answer: H lines + C lines for CS2
# Dota -> bridge (POST /dota)  lines:  H heroId x y z fx fy hp maxhp alive name  (Dota heroes, CS coords)
#                                      C T slot x y        teleport CS player (hook, push...)
#                                      C S slot seconds    freeze CS player (stun, root)
#                                      C K slot damage killer  damage CS player
#                                      C H slot heroId     draw Pudge's hook chain in CS2
#                                      E K hero killer weapon  a CS player killed a hero (CS2 score)
#                                      E S event x y z     play a Dota sound in CS2
#                                      U id x y z fx fy hp maxhp alive model act  creeps, neutrals, Roshan near CS players
#   answer: P lines + D lines for Dota
#
# Run:  python bridge.py            (only this PC)
#       python bridge.py --public   (friends / a published Dota custom game can reach it on port 3000)
# Stop: Ctrl+C

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 3000

state = {
    "players": [],       # latest P lines from CS2
    "heroes": [],        # latest H lines from Dota
    "to_cs": [],         # queued C lines for CS2
    "to_dota": [],       # queued D lines for Dota
    "cs_time": 0.0, "dota_time": 0.0,
    "cs_updates": 0, "dota_updates": 0,
    "hits": 0, "commands": 0,
}
lock = threading.Lock()


def split(body):
    return [l.strip() for l in body.splitlines() if l.strip() and l.strip() != "none"]


class Handler(BaseHTTPRequestHandler):
    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode("utf-8", "ignore") if length else ""

    def _reply(self, lines):
        data = ("\n".join(lines) if lines else "none").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        lines = split(self._body())
        now = time.time()

        if self.path.startswith("/cs"):
            with lock:
                state["players"] = [l for l in lines if l.startswith("P ")]
                hits = [l for l in lines if l.startswith(("D ", "T ", "G "))]   # G: grenades, runes
                state["to_dota"] += hits
                state["hits"] += len(hits)
                state["cs_time"] = now
                state["cs_updates"] += 1
                fresh = now - state["dota_time"] < 2.0
                answer = (state["heroes"] + state.get("buildings", []) if fresh else []) + state["to_cs"]
                state["to_cs"] = []
            self._reply(answer)
            return

        if self.path.startswith("/dota"):
            with lock:
                state["heroes"] = [l for l in lines if l.startswith(("H ", "U ", "N "))]   # N: day/night
                state["buildings"] = [l for l in lines if l.startswith("B ")] or state.get("buildings", [])
                cmds = [l for l in lines if l.startswith("C ") or l.startswith("E ")]
                state["to_cs"] += cmds
                state["commands"] += len(cmds)
                state["dota_time"] = now
                state["dota_updates"] += 1
                fresh = now - state["cs_time"] < 2.0
                answer = (state["players"] if fresh else []) + state["to_dota"]
                state["to_dota"] = []
            self._reply(answer)
            return

        self._reply([])

    def do_GET(self):
        self._reply(["DotaCS bridge is running"])

    def log_message(self, format, *args):
        pass


class Server(ThreadingHTTPServer):
    # on Windows "reuse" lets two programs grab the same port, so turn it off
    allow_reuse_address = False


def status_loop():
    last = {"cs_updates": 0, "dota_updates": 0}
    while True:
        time.sleep(1)
        with lock:
            cs_rate = state["cs_updates"] - last["cs_updates"]
            dota_rate = state["dota_updates"] - last["dota_updates"]
            last["cs_updates"] = state["cs_updates"]
            last["dota_updates"] = state["dota_updates"]
            players = list(state["players"])
            heroes = list(state["heroes"])
            hits, commands = state["hits"], state["commands"]
        line = "КС2: %d игроков, %d обн/сек  |  Дота: %d героев, %d обн/сек  |  попаданий по героям: %d, команд ксникам: %d" % (
            len(players), cs_rate, len(heroes), dota_rate, hits, commands)
        print(line)
        try:
            with open("bridge_status.txt", "w", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + "  " + line + "\n\nCS2 players:\n" + "\n".join(players or ["-"])
                        + "\n\nDota heroes:\n" + "\n".join(heroes or ["-"]) + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    host = "0.0.0.0" if "--public" in sys.argv else "127.0.0.1"
    try:
        server = Server((host, PORT), Handler)
    except OSError:
        print("ОШИБКА: порт %d уже занят. Закрой другие окна с мостом." % PORT)
        raise SystemExit(1)
    print("Мост запущен на http://%s:%d  (Ctrl+C чтобы остановить)" % (host, PORT))
    threading.Thread(target=status_loop, daemon=True).start()
    server.serve_forever()
