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
html, body { width: 100%; height: 100%; overflow: hidden; }
body { margin: 0; padding: clamp(18px, 2vw, 36px); background: transparent; color: #f7f4eb; font-family: var(--font); }
.board { width: 100%; height: 100%; margin: auto; padding: clamp(18px, 1.5vw, 28px); display: flex; flex-direction: column;
  background: radial-gradient(circle at 50% 42%, #174b37 0, var(--bg) 52%, #03110d 100%); border: 1px solid #ffffff25;
  border-top: 4px solid var(--accent); border-radius: 22px; box-shadow: 0 18px 55px #000b; text-shadow: 0 2px 4px #000b; }
.header { display: grid; grid-template-columns: minmax(240px, 1.5fr) repeat(4, minmax(140px, .7fr)); gap: 12px; }
.brand, .metric, .player, .commentary { background: #0006; border: 1px solid #ffffff14; border-radius: 11px; }
.brand { padding: 13px 16px; display: flex; align-items: center; gap: 14px; }
.logo { color: var(--accent); font-weight: 900; font-size: 24px; letter-spacing: 2px; }
.live { color: #80e6a4; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
.live::before { content: ''; display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 50%;
  background: #54dc82; box-shadow: 0 0 0 4px #54dc8228; animation: pulse 1.8s infinite; }
.metric { padding: 11px 14px; text-align: center; }
.metric small { display: block; color: #9cb5ab; font-size: 10px; font-weight: 800; letter-spacing: 1px; }
.metric strong { display: block; margin-top: 4px; font-size: 21px; }
.table { min-height: 0; flex: 1; padding: 24px 4px 14px; position: relative; display: flex; flex-direction: column; text-align: center; }
.table::before { content: ''; position: absolute; z-index: 0; inset: 9% 10% 21%; border: 2px solid #ffffff12;
  border-radius: 50%; background: radial-gradient(ellipse at center, #1a5b41aa 0, #0c3828aa 55%, #061c15aa 100%);
  box-shadow: inset 0 0 70px #0007, 0 12px 35px #0005; }
.table::after { content: 'LOCAL AI TABLE'; position: absolute; z-index: 0; top: 47%; left: 0; right: 0;
  color: #ffffff0d; font-size: clamp(34px, 4vw, 72px); font-weight: 900; letter-spacing: .16em; }
.table > * { position: relative; z-index: 1; }
.street { color: var(--accent); font-size: 12px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; }
.cards { display: flex; min-height: 112px; margin: auto 0; align-items: center; justify-content: center; gap: 12px; }
.empty-board { color: #7f9b90; font-size: 15px; }
.card { width: 72px; height: 96px; padding: 9px 7px; display: flex; flex-direction: column; justify-content: space-between;
  background: #faf8f1; color: #141b18; border: 1px solid #fff; border-radius: 9px; box-shadow: 0 9px 20px #0009; text-shadow: none; }
.card b { align-self: flex-start; font-size: 25px; line-height: 1; }
.card i { align-self: flex-end; font-size: 32px; font-style: normal; line-height: 1; }
.card.red { color: #c33636; }
.card.placeholder { background: #0003; border: 1px dashed #ffffff2d; box-shadow: inset 0 0 18px #0004; }
.players { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.layout-vertical .players { grid-template-columns: 1fr; }
.player { position: relative; overflow: hidden; padding: 15px 16px 13px; border-bottom: 4px solid #3c6756; transition: .25s ease; }
.player.next { background: #5a461fdd; border-color: var(--accent); transform: translateY(-3px); box-shadow: 0 7px 20px #0007; }
.player.folded { opacity: .48; filter: saturate(.45); border-color: #606c67; }
.player-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.name { color: #fff; font-size: 19px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badges { display: flex; gap: 5px; }
.badge { min-width: 22px; padding: 3px 5px; border-radius: 10px; background: #ffffff17; color: #c8dad2; font-size: 10px; font-weight: 900; text-align: center; }
.badge.dealer { background: var(--accent); color: #182019; text-shadow: none; }
.stack { margin-top: 9px; display: flex; justify-content: space-between; color: #c8d7d1; font-size: 14px; }
.meter { height: 5px; margin: 9px 0; overflow: hidden; background: #ffffff12; border-radius: 3px; }
.meter span { display: block; height: 100%; background: linear-gradient(90deg, #4fb77b, var(--accent)); border-radius: inherit; }
.action { min-height: 32px; padding: 7px 9px; background: #ffffff0d; border-radius: 7px; color: #dbe8e2;
  font-size: 14px; font-weight: 800; text-align: center; }
.next .action { background: var(--accent); color: #1d241f; text-shadow: none; }
.commentary { min-height: 52px; margin-top: 14px; padding: 12px 16px; display: flex; align-items: center;
  justify-content: center; color: #f7da83; font-size: 18px; font-weight: 650; text-align: center; }
.commentary::before { content: 'LIVE CALL'; margin-right: 12px; color: #92afa3; font-size: 9px; font-weight: 900; letter-spacing: 1px; }
body[data-connected="false"] .live { color: #ffad86; }
body[data-connected="false"] .live::before { background: #ff775c; animation: none; }
@keyframes pulse { 50% { opacity: .45; transform: scale(.82); } }
.compact { padding: 22px; }
.compact .board { height: auto; min-height: 0; max-width: 1800px; padding: 18px; }
.compact .table { padding: 14px 4px 12px; }
.compact .table::before, .compact .table::after { display: none; }
.compact .cards { min-height: 78px; margin: 10px 0 14px; gap: 8px; }
.compact .card { width: 54px; height: 72px; padding: 7px 5px; }
.compact .card b { font-size: 19px; }
.compact .card i { font-size: 25px; }
.compact .player { padding: 11px 12px 10px; }
.compact .name { font-size: 16px; }
.compact .stack, .compact .action { font-size: 12px; }
.compact .commentary { min-height: 43px; margin-top: 11px; padding: 10px 14px; font-size: 16px; }
@media (max-width: 950px) {
  body { padding: 10px; }
  .header { grid-template-columns: repeat(2, 1fr); }
  .brand { grid-column: 1 / -1; }
  .players { grid-template-columns: repeat(2, 1fr); }
}
</style>
<main class="board layout-__LAYOUT__">
  <header class="header">
    <div class="brand"><div class="logo">AI POKER</div><div class="live" id="connection">LOCAL LIVE</div></div>
    <div class="metric"><small>HAND</small><strong id="hand">0</strong></div>
    <div class="metric"><small>POT</small><strong id="pot">0</strong></div>
    <div class="metric"><small>BLINDS</small><strong id="blinds">0 / 0</strong></div>
    <div class="metric"><small>DEALER</small><strong id="dealer">-</strong></div>
  </header>
  <section class="table">
    <div class="street" id="stage">Waiting</div>
    <div class="cards" id="cards"><span class="empty-board">Waiting for the next hand</span></div>
    <div class="players" id="players"></div>
  </section>
  <div class="commentary" id="commentary" aria-live="polite">Table ready</div>
</main>
<script>
const suits = {hearts:'♥', diamonds:'♦', clubs:'♣', spades:'♠'};
const ranks = {11:'J',12:'Q',13:'K',14:'A'};
document.body.classList.toggle('compact', new URLSearchParams(location.search).get('compact') === '1');
const card = c => `<span class="card ${c.suit === 'hearts' || c.suit === 'diamonds' ? 'red' : ''}">
  <b>${ranks[c.rank] || c.rank}</b><i>${suits[c.suit]}</i></span>`;
const shortName = name => name.replace('AI Player ', 'P');
async function refresh() {
  try {
    const response = await fetch('/state', {cache:'no-store'});
    if (!response.ok) throw new Error('state unavailable');
    const state = await response.json();
    document.body.dataset.connected = 'true';
    document.getElementById('connection').textContent = 'LOCAL LIVE';
    document.getElementById('hand').textContent = state.hand_number;
    document.getElementById('stage').textContent = state.stage;
    document.getElementById('pot').textContent = Number(state.pot).toLocaleString();
    document.getElementById('blinds').textContent = `${state.blinds.small} / ${state.blinds.big}`;
    document.getElementById('dealer').textContent = state.dealer ? shortName(state.dealer) : '-';
    const visibleCards = state.community_cards.map(card).join('');
    const placeholders = '<span class="card placeholder"></span>'.repeat(Math.max(0, 5 - state.community_cards.length));
    document.getElementById('cards').innerHTML = visibleCards + placeholders;
    const maximum = Math.max(1, ...state.players.map(player => player.chips));
    document.getElementById('players').innerHTML = state.players.map(player => `
      <article class="player ${player.next_to_act ? 'next' : ''} ${player.active ? '' : 'folded'}">
        <div class="player-top"><div class="name">${player.name}</div><div class="badges">
          ${player.is_dealer ? '<span class="badge dealer">D</span>' : ''}
          ${player.next_to_act ? '<span class="badge">ACT</span>' : ''}
        </div></div>
        <div class="stack"><span>${Number(player.chips).toLocaleString()} chips</span>
          <span>${Number(player.win_percentage).toFixed(1)}% · ${player.ties}T</span></div>
        <div class="meter"><span style="width:${Math.max(2, player.chips / maximum * 100)}%"></span></div>
        <div class="action">${player.action || 'Waiting'}</div>
      </article>`).join('');
    const feed = state.commentary || [];
    document.getElementById('commentary').textContent = feed.length ? feed[feed.length - 1] : 'Table ready';
  } catch (_) {
    document.body.dataset.connected = 'false';
    document.getElementById('connection').textContent = 'RECONNECTING';
    document.getElementById('commentary').textContent = 'Waiting for the game-state feed…';
  }
}
refresh(); setInterval(refresh, 750);
</script>
</html>"""


class OverlayServer:
    def __init__(
        self,
        game,
        host="127.0.0.1",
        port=8765,
        background="#071c13",
        accent="#e6b94a",
        font="Arial, sans-serif",
        layout="horizontal",
    ):
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
                    page = (
                        OVERLAY_HTML.replace("__BACKGROUND__", outer.background)
                        .replace("__ACCENT__", outer.accent)
                        .replace("__FONT__", outer.font)
                        .replace("__LAYOUT__", outer.layout)
                    )
                    self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
                elif path == "/health":
                    self._send_json({"status": "ok"})
                else:
                    self._send_json({"error": "not found"}, status=404)

            def _send_json(self, value, status=200):
                body = json.dumps(value).encode("utf-8")
                self._send(status, "application/json; charset=utf-8", body)

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
