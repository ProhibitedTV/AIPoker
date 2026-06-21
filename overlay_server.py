"""Small HTTP server for OBS/browser-source overlays and JSON game state."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import urlparse


OVERLAY_HTML = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Poker Overlay</title>
<style>
:root { --bg: __BACKGROUND__; --accent: __ACCENT__; --font: __FONT__; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: transparent; color: white; font-family: var(--font); }
.board { background: color-mix(in srgb, var(--bg) 92%, transparent); border: 2px solid var(--accent);
  border-radius: 18px; padding: 18px; text-shadow: 0 2px 3px #000; }
.top, .players { display: flex; gap: 12px; justify-content: space-between; align-items: stretch; }
.pill, .player { background: #0009; border-radius: 10px; padding: 10px 14px; }
.cards { min-height: 50px; text-align: center; font-size: 28px; letter-spacing: 5px; margin: 15px; }
.player { flex: 1; border-bottom: 4px solid transparent; }
.layout-vertical .players { flex-direction: column; }
.player.next { border-color: var(--accent); }
.name { color: var(--accent); font-weight: 700; }
.action { min-height: 1.2em; opacity: .86; }
.commentary { margin-top: 12px; text-align: center; font-size: 18px; }
</style>
<main class="board layout-__LAYOUT__">
  <section class="top"><div class="pill" id="stage">Waiting</div><div class="pill" id="pot">Pot: 0</div>
    <div class="pill" id="blinds">Blinds: 0 / 0</div><div class="pill" id="dealer">Dealer: -</div></section>
  <div class="cards" id="cards">No community cards</div>
  <section class="players" id="players"></section>
  <div class="commentary" id="commentary"></div>
</main>
<script>
const suit = {hearts:'♥', diamonds:'♦', clubs:'♣', spades:'♠'};
const rank = {11:'J',12:'Q',13:'K',14:'A'};
const card = c => `${rank[c.rank] || c.rank}${suit[c.suit]}`;
async function refresh() {
  try {
    const state = await (await fetch('/state', {cache:'no-store'})).json();
    document.getElementById('stage').textContent = `Hand ${state.hand_number} · ${state.stage}`;
    document.getElementById('pot').textContent = `Pot: ${state.pot}`;
    document.getElementById('blinds').textContent = `Blinds: ${state.blinds.small} / ${state.blinds.big}`;
    document.getElementById('dealer').textContent = `Dealer: ${state.dealer || '-'}`;
    document.getElementById('cards').textContent = state.community_cards.map(card).join('  ') || 'No community cards';
    document.getElementById('players').innerHTML = state.players.map(p => `
      <article class="player ${p.next_to_act ? 'next' : ''}">
        <div class="name">${p.name}${p.is_dealer ? ' · D' : ''}</div>
        <div>${p.chips} chips · ${Number(p.win_percentage).toFixed(1)}% wins · ${p.ties} ties</div>
        <div class="action">${p.action || 'Waiting'}</div>
      </article>`).join('');
    const feed = state.commentary || [];
    document.getElementById('commentary').textContent = feed.length ? feed[feed.length - 1] : '';
  } catch (_) { document.getElementById('stage').textContent = 'Reconnecting…'; }
}
refresh(); setInterval(refresh, 750);
</script>
</html>"""


class OverlayServer:
    def __init__(self, game, host="127.0.0.1", port=8765, background="#071c13", accent="#e6b94a", font="Arial, sans-serif", layout="horizontal"):
        self.game = game
        self.host = host
        self.port = port
        self.background = background
        self.accent = accent
        self.font = font
        self.layout = layout if layout in {"horizontal", "vertical"} else "horizontal"
        self._server = None
        self._thread = None

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/state":
                    self._send_json(outer.game.state_snapshot())
                elif path in ("/", "/overlay"):
                    page = (OVERLAY_HTML.replace("__BACKGROUND__", outer.background)
                            .replace("__ACCENT__", outer.accent)
                            .replace("__FONT__", outer.font)
                            .replace("__LAYOUT__", outer.layout))
                    self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
                elif path == "/health":
                    self._send_json({"status": "ok"})
                else:
                    self._send_json({"error": "not found"}, status=404)

            def _send_json(self, value, status=200):
                self._send(status, "application/json; charset=utf-8", json.dumps(value).encode("utf-8"))

            def _send(self, status, content_type, body):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._server.server_address[1]
        self._thread = Thread(target=self._server.serve_forever, name="poker-overlay", daemon=True)
        self._thread.start()
        return self

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/overlay"

    def close(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
