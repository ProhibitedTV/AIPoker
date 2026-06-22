"""OBS-ready 1080p overlay, state v2 endpoint, and SSE event feed."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import BoundedSemaphore, Thread
import sys
import time
from urllib.parse import parse_qs, urlparse
import re


OVERLAY_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Poker Overlay</title>
<style>
:root{--bg:__BACKGROUND__;--accent:__ACCENT__;--font:__FONT__;--cream:#f7f3e8;--muted:#9db5ab;--panel:#06130fd9}
*{box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden}body{margin:0;padding:32px;background:transparent;color:var(--cream);font-family:var(--font);text-shadow:0 2px 5px #000b}
.board{height:100%;display:grid;grid-template-rows:auto 1fr auto;gap:16px;padding:24px;background:radial-gradient(ellipse at 50% 43%,#166044 0,#0a3828 48%,var(--bg) 76%,#020b08 100%);border:2px solid #ffffff24;border-top:5px solid var(--accent);border-radius:34px;box-shadow:0 24px 80px #000d,inset 0 0 100px #0005;overflow:hidden}
.header{display:grid;grid-template-columns:1.5fr repeat(5,minmax(120px,.62fr));gap:10px}.brand,.metric,.player,.ticker{background:linear-gradient(180deg,#071914e8,#020906d9);border:1px solid #ffffff18;box-shadow:0 10px 22px #0005}.brand{display:flex;align-items:center;gap:16px;padding:12px 18px;border-radius:13px}.logo{color:var(--accent);font-size:25px;font-weight:950;letter-spacing:.12em}.live{font-size:10px;font-weight:900;letter-spacing:.12em;color:#79e29f}.live:before{content:'';display:inline-block;width:8px;height:8px;margin-right:7px;border-radius:50%;background:#61df8c;box-shadow:0 0 0 5px #61df8c22;animation:pulse 1.7s infinite}.metric{padding:9px 12px;text-align:center;border-radius:11px}.metric small{display:block;color:var(--muted);font-size:9px;font-weight:900;letter-spacing:.12em}.metric strong{display:block;margin-top:3px;font-size:20px;white-space:nowrap}
.table{position:relative;min-height:0;display:grid;grid-template-rows:1fr auto;gap:14px;padding:10px 3% 0}.felt-ring{position:absolute;inset:2% 6% 14%;border:3px solid #cfae582b;border-radius:48%;box-shadow:inset 0 0 70px #0007,0 0 0 10px #0002}.center{z-index:1;align-self:center;text-align:center}.street{color:var(--accent);font-size:12px;font-weight:950;letter-spacing:.2em;text-transform:uppercase}.cards{display:flex;justify-content:center;gap:11px;min-height:108px;margin:14px 0 10px}.card{width:72px;height:100px;display:flex;flex-direction:column;justify-content:space-between;padding:9px 8px;background:linear-gradient(145deg,#fff,#e8e4d8);color:#111a17;border:1px solid #fff;border-radius:9px;box-shadow:0 10px 22px #000a;text-shadow:none;animation:deal .35s ease both}.card b{align-self:flex-start;font-size:25px;line-height:1}.card i{align-self:flex-end;font-size:31px;font-style:normal;line-height:1}.card.red{color:#c52f39}.card.placeholder{background:#0003;border:1px dashed #ffffff2c;box-shadow:inset 0 0 18px #0004}.potline{display:flex;justify-content:center;gap:7px;min-height:25px}.pot-chip{padding:5px 10px;border-radius:14px;background:#07130fe8;border:1px solid #dabd6966;color:#f3d579;font-size:11px;font-weight:850}.analysis-note{min-height:18px;margin-top:7px;color:#9bb6aa;font-size:11px}
.players{z-index:2;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.player{position:relative;min-width:0;padding:12px 13px 11px;border-radius:12px;border-bottom:4px solid var(--player,#446c5b);transition:transform .2s,opacity .2s}.player.next{transform:translateY(-6px);border-color:var(--accent);box-shadow:0 0 0 1px #e7c56799,0 12px 28px #000b}.player.folded,.player.eliminated{opacity:.42;filter:saturate(.35)}.player.all_in{box-shadow:0 0 0 1px #e45f5f,0 10px 25px #0009}.player-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:18px;font-weight:900}.badges{display:flex;gap:4px}.badge{min-width:22px;padding:3px 5px;background:#ffffff14;border-radius:10px;color:#c8dad2;font-size:9px;font-weight:950;text-align:center}.badge.gold{background:var(--accent);color:#182019;text-shadow:none}.badge.danger{background:#a43838;color:#fff}.model{margin-top:2px;color:#74968a;font-size:9px;text-transform:uppercase;letter-spacing:.08em}.hole{display:flex;justify-content:center;gap:5px;min-height:55px;margin:7px 0}.hole .card{width:39px;height:54px;padding:5px 4px;border-radius:5px;box-shadow:0 5px 10px #0009}.hole .card b{font-size:14px}.hole .card i{font-size:17px}.stackrow,.statrow{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#c9dad3}.stackrow strong{color:#fff}.statrow{margin-top:5px;color:#8fafA3;font-size:9px}.meter{height:4px;margin:7px 0;background:#ffffff10;border-radius:3px;overflow:hidden}.meter span{display:block;height:100%;background:linear-gradient(90deg,var(--player,#4fb77b),var(--accent));border-radius:inherit}.action{min-height:28px;padding:6px;background:#ffffff0c;border-radius:6px;color:#dce8e3;font-size:12px;font-weight:850;text-align:center}.next .action{background:var(--accent);color:#172018;text-shadow:none}
.ticker{min-height:52px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:14px;padding:10px 16px;border-radius:12px}.ticker-label{color:#8eaa9e;font-size:9px;font-weight:950;letter-spacing:.13em}.commentary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#f7d879;font-size:16px;font-weight:750}.history{color:#9eb4aa;font-size:10px;text-align:right;white-space:nowrap}body[data-connected=false] .live{color:#ff9a7a}body[data-connected=false] .live:before{background:#ff6a55;animation:none}
.compact{padding:18px}.compact .board{height:auto;padding:16px;border-radius:20px}.compact .felt-ring{display:none}.compact .header{grid-template-columns:1.4fr repeat(3,1fr)}.compact .header .optional{display:none}.compact .table{padding:6px 0 0}.compact .cards{min-height:72px;margin:8px}.compact .card{width:50px;height:70px}.compact .card b{font-size:18px}.compact .card i{font-size:23px}.compact .hole .card{width:32px;height:44px}.compact .player{padding:8px}.compact .ticker{min-height:40px}.reduced *,body.reduced *{animation:none!important;transition:none!important}
.layout-vertical .players{grid-template-columns:1fr 1fr;max-width:1100px;width:100%;margin:0 auto}
@keyframes pulse{50%{opacity:.45;transform:scale(.8)}}@keyframes deal{from{opacity:0;transform:translateY(-18px) rotate(-3deg)}to{opacity:1;transform:none}}
@keyframes chipPulse{50%{transform:scale(1.14);box-shadow:0 0 20px #e6b94a88}}@keyframes winnerGlow{50%{box-shadow:inset 0 0 130px #d9b94b44,0 24px 80px #000d}}
.board.fx-action .pot-chip{animation:chipPulse .35s ease}.board.fx-community .cards{animation:chipPulse .35s ease}.board.fx-winner{animation:winnerGlow 1.2s ease}
@media(max-width:1100px){body{padding:14px}.header{grid-template-columns:1.5fr repeat(3,1fr)}.header .optional{display:none}.players{grid-template-columns:repeat(2,1fr)}}
</style></head>
<body data-connected="false" class="__REDUCED__ __AUDIO__">
<main class="board layout-__LAYOUT__">
 <header class="header"><div class="brand"><div class="logo">AI POKER</div><div class="live" id="connection">RECONNECTING</div></div>
  <div class="metric"><small>HAND</small><strong id="hand">0</strong></div><div class="metric"><small>POT</small><strong id="pot">0</strong></div>
  <div class="metric"><small>BLINDS</small><strong id="blinds">0 / 0</strong></div><div class="metric optional"><small>MODE</small><strong id="mode">-</strong></div>
  <div class="metric optional"><small>LEVEL</small><strong id="level">-</strong></div></header>
 <section class="table"><div class="felt-ring"></div><div class="center"><div class="street" id="stage">Waiting</div>
  <div class="cards" id="cards"><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span></div>
  <div class="potline" id="pots"></div><div class="analysis-note" id="analysis">Spectator analysis warming up</div></div><div class="players" id="players"></div></section>
 <footer class="ticker"><div class="ticker-label">LIVE CALL</div><div class="commentary" id="commentary" aria-live="polite">Table ready</div><div class="history" id="history"></div></footer>
</main>
<script>
const suits={hearts:'&hearts;',diamonds:'&diams;',clubs:'&clubs;',spades:'&spades;'},ranks={11:'J',12:'Q',13:'K',14:'A'};
const q=new URLSearchParams(location.search);document.body.classList.toggle('compact',q.get('compact')==='1');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const card=c=>`<span class="card ${c.suit==='hearts'||c.suit==='diamonds'?'red':''}"><b>${ranks[c.rank]||c.rank}</b><i>${suits[c.suit]}</i></span>`;
let lastState=null,refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;try{const response=await fetch('/state',{cache:'no-store'});if(!response.ok)throw Error();const s=await response.json();lastState=s;render(s);document.body.dataset.connected='true'}catch(_){document.body.dataset.connected='false';connection.textContent='RECONNECTING';commentary.textContent='Waiting for the game-state feed…'}finally{refreshing=false}}
function render(s){connection.textContent=s.services?.ollama==='online'?'LOCAL LIVE · OLLAMA':s.services?.ollama==='preview'?'LOCAL LIVE · DEMO':s.services?.ollama==='unknown'?'LOCAL LIVE':'LOCAL LIVE · MODEL FALLBACK';hand.textContent=s.hand_number;stage.textContent=s.stage;pot.textContent=Number(s.pot).toLocaleString();blinds.textContent=`${s.blinds.small} / ${s.blinds.big}${s.blinds.ante?' · A'+s.blinds.ante:''}`;mode.textContent=s.mode==='tournament'?'SIT & GO':'CASH';level.textContent=s.tournament?`${s.tournament.level} · ${s.tournament.hands_remaining}H`:'FIXED';
 const board=s.community_cards.map(card).join('')+'<span class="card placeholder"></span>'.repeat(Math.max(0,5-s.community_cards.length));cards.innerHTML=board;
 pots.innerHTML=(s.pots||[]).map(p=>`<span class="pot-chip">${p.kind.toUpperCase()} ${Number(p.amount).toLocaleString()}</span>`).join('')||'<span class="pot-chip">POT BUILDING</span>';
 const champion=s.tournament?.complete?s.players.find(p=>p.id===s.tournament.winner):null;analysis.textContent=champion?`🏆 ${champion.name.toUpperCase()} WINS SIT & GO ${s.tournament.number}`:s.analysis?.pending?'Calculating live equity…':'Live equity · exact from flop, bounded simulation preflop';
 const maximum=Math.max(1,...s.players.map(p=>p.chips));players.innerHTML=s.players.map(p=>`<article class="player ${p.next_to_act?'next':''} ${esc(p.status)}" style="--player:${esc(p.profile?.color||'#4fb77b')}"><div class="player-head"><div class="name">${esc(p.name)}</div><div class="badges">${p.is_dealer?'<span class="badge gold">D</span>':''}${p.is_small_blind?'<span class="badge">SB</span>':''}${p.is_big_blind?'<span class="badge">BB</span>':''}${p.all_in?'<span class="badge danger">ALL-IN</span>':''}</div></div><div class="model">${esc(p.profile?.persona||'AI player')} · ${esc(p.profile?.model||'auto')}</div><div class="hole">${(p.hole_cards||[]).map(card).join('')}</div><div class="stackrow"><strong>${Number(p.chips).toLocaleString()} chips</strong><span>${p.equity==null?'CALC':Number(p.equity).toFixed(1)+'%'} EQ</span></div><div class="meter"><span style="width:${Math.max(2,p.chips/maximum*100)}%"></span></div><div class="action">${esc(p.action||'Waiting')}${p.hand_commitment?' · '+Number(p.hand_commitment).toLocaleString()+' in':''}</div><div class="statrow"><span>${esc(p.hand_label||'Awaiting cards')}</span><span>VPIP ${Number(p.stats?.vpip||0).toFixed(0)} · PFR ${Number(p.stats?.pfr||0).toFixed(0)} · AF ${Number(p.stats?.aggression||0).toFixed(1)}</span></div></article>`).join('');
 const feed=s.commentary||[];commentary.textContent=feed.at(-1)||'Table ready';history.textContent=(s.action_history||[]).slice(-3).map(a=>`${s.players[a.seat]?.name||''} ${a.action}`).join('  ·  ')}
function cue(type){if(!document.body.classList.contains('audio-on'))return;try{const C=window.AudioContext||window.webkitAudioContext,ctx=window.__ctx||(window.__ctx=new C()),o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=type==='winner'?740:type==='community'?440:260;g.gain.setValueAtTime(.025,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.12);o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+.13)}catch(_){}}
function animateEvent(type){const b=document.querySelector('.board'),fx=type==='pot_awarded'||type==='winner'?'winner':type==='community'?'community':type==='action'?'action':'';if(!fx)return;b.classList.remove('fx-action','fx-community','fx-winner');requestAnimationFrame(()=>b.classList.add('fx-'+fx));setTimeout(()=>b.classList.remove('fx-'+fx),1300)}
const source=new EventSource('/events');source.onmessage=e=>{try{const event=JSON.parse(e.data);cue(event.type);animateEvent(event.type);refresh()}catch(_){}};source.onerror=()=>{document.body.dataset.connected='false'};
refresh();setInterval(refresh,2500);
</script></body></html>"""


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Do not dump harmless browser disconnects into a 24/7 operator log."""

    def handle_error(self, request, client_address):
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class OverlayServer:
    def __init__(self, game, host="127.0.0.1", port=8765, background="#071c13", accent="#e6b94a", font="Arial, sans-serif", layout="horizontal", reduced_motion=False, audio_enabled=False):
        self.game = game
        self.host = host
        self.port = port
        self.background = background if re.fullmatch(r"#[0-9a-fA-F]{3,8}", background) else "#071c13"
        self.accent = accent if re.fullmatch(r"#[0-9a-fA-F]{3,8}", accent) else "#e6b94a"
        self.font = re.sub(r"[{};<>\r\n]", "", font) or "Arial, sans-serif"
        self.layout = layout if layout in {"horizontal", "vertical"} else "horizontal"
        self.reduced_motion = bool(reduced_motion)
        self.audio_enabled = bool(audio_enabled)
        self._server = None
        self._thread = None
        self._closing = False
        self._sse_slots = BoundedSemaphore(8)

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                if path == "/state":
                    self._send_json(outer.game.state_snapshot())
                elif path == "/events":
                    self._send_events(parse_qs(parsed.query))
                elif path in ("/", "/overlay"):
                    page = (OVERLAY_HTML.replace("__BACKGROUND__", outer.background).replace("__ACCENT__", outer.accent).replace("__FONT__", outer.font).replace("__LAYOUT__", outer.layout).replace("__REDUCED__", "reduced" if outer.reduced_motion else "").replace("__AUDIO__", "audio-on" if outer.audio_enabled else ""))
                    self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
                elif path == "/health":
                    self._send_json({"status": "ok", "schema_version": 2, "event_sequence": outer.game.state_snapshot()["event_sequence"]})
                else:
                    self._send_json({"error": "not found"}, status=404)

            def _send_events(self, query):
                if not outer._sse_slots.acquire(blocking=False):
                    self._send_json({"error": "event client limit reached"}, status=503)
                    return
                self.close_connection = True
                try:
                    try:
                        sequence = int(self.headers.get("Last-Event-ID") or query.get("since", [0])[0])
                    except ValueError:
                        sequence = 0
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    deadline = time.monotonic() + 25
                    try:
                        while not outer._closing and time.monotonic() < deadline:
                            events = outer.game.wait_for_events(sequence, timeout=8)
                            if not events:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                                continue
                            for event in events:
                                sequence = event["id"]
                                body = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                                self.wfile.write(f"id: {sequence}\ndata: ".encode("utf-8") + body + b"\n\n")
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
                finally:
                    outer._sse_slots.release()

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

        self._server = QuietThreadingHTTPServer((self.host, self.port), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = Thread(target=self._server.serve_forever, name="poker-overlay", daemon=True)
        self._thread.start()
        return self

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/overlay"

    def close(self):
        self._closing = True
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
