"""OBS-ready 1080p overlay, state v2 endpoint, and SSE event feed."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
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
.table{position:relative;min-height:0;display:grid;grid-template-rows:1fr auto;gap:14px;padding:10px 3% 0}.felt-ring{position:absolute;inset:2% 6% 14%;border:3px solid #cfae582b;border-radius:48%;box-shadow:inset 0 0 70px #0007,0 0 0 10px #0002}.center{z-index:1;align-self:center;text-align:center}.street{color:var(--accent);font-size:12px;font-weight:950;letter-spacing:.2em;text-transform:uppercase}.cards{display:flex;justify-content:center;gap:11px;min-height:108px;margin:14px 0 10px;perspective:900px}.card{width:72px;height:100px;display:flex;flex-direction:column;justify-content:space-between;padding:9px 8px;background:linear-gradient(145deg,#fff,#e8e4d8);color:#111a17;border:1px solid #fff;border-radius:9px;box-shadow:0 10px 22px #000a;text-shadow:none;transform-style:preserve-3d;backface-visibility:hidden}.card.fresh{animation:cardFlip .72s cubic-bezier(.2,.76,.22,1) both;animation-delay:calc(var(--deal-index,0) * 90ms)}.card b{align-self:flex-start;font-size:25px;line-height:1}.card i{align-self:flex-end;font-size:31px;font-style:normal;line-height:1}.card.red{color:#c52f39}.card.placeholder{background:#0003;border:1px dashed #ffffff2c;box-shadow:inset 0 0 18px #0004}.potline{display:flex;justify-content:center;gap:7px;min-height:29px}.pot-chip{display:inline-flex;align-items:center;gap:7px;padding:5px 11px 5px 7px;border-radius:16px;background:#07130fe8;border:1px solid #dabd6966;color:#f3d579;font-size:11px;font-weight:850}.pot-chip:before{content:'';width:18px;height:18px;border-radius:50%;background:repeating-conic-gradient(#f4d77e 0 12deg,#7d2b27 12deg 24deg);border:3px solid #f0d174;box-shadow:inset 0 0 0 3px #8c322d,0 3px 7px #0009}.analysis-note{min-height:18px;margin-top:7px;color:#9bb6aa;font-size:11px}
.players{z-index:2;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.player{position:relative;min-width:0;padding:12px 13px 11px;border-radius:12px;border-bottom:4px solid var(--player,#446c5b);transition:transform .3s,opacity .3s,box-shadow .3s}.player.next{transform:translateY(-6px);border-color:var(--accent);box-shadow:0 0 0 1px #e7c56799,0 12px 28px #000b}.player.winner{border-color:#f2cf68;box-shadow:0 0 0 2px #f2cf68,0 0 34px #e6b94a99;animation:winnerPop 1.15s ease both}.player.folded,.player.eliminated{opacity:.42;filter:saturate(.35)}.player.all_in{box-shadow:0 0 0 1px #e45f5f,0 10px 25px #0009}.player-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:18px;font-weight:900}.badges{display:flex;gap:4px}.badge{min-width:22px;padding:3px 5px;background:#ffffff14;border-radius:10px;color:#c8dad2;font-size:9px;font-weight:950;text-align:center}.badge.gold{background:var(--accent);color:#182019;text-shadow:none}.badge.danger{background:#a43838;color:#fff}.model{margin-top:2px;color:#74968a;font-size:9px;text-transform:uppercase;letter-spacing:.08em}.hole{display:flex;justify-content:center;gap:5px;min-height:55px;margin:7px 0 2px;perspective:700px}.hole .card{width:39px;height:54px;padding:5px 4px;border-radius:5px;box-shadow:0 5px 10px #0009}.hole .card b{font-size:14px}.hole .card i{font-size:17px}.wager{height:25px;display:flex;align-items:center;justify-content:center;gap:0;margin:0 0 4px;color:#f5d778;font-size:11px;font-weight:900}.wager.empty{visibility:hidden}.wager.fresh{animation:chipSlide .58s cubic-bezier(.16,.78,.24,1) both}.mini-chip{width:17px;height:17px;margin-left:-5px;border-radius:50%;background:repeating-conic-gradient(#fff 0 11deg,var(--chip,#b83632) 11deg 22deg);border:3px solid var(--chip,#b83632);box-shadow:0 3px 7px #0009}.mini-chip:first-child{margin-left:0}.wager b{margin-left:7px}.stackrow,.statrow{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#c9dad3}.stackrow strong{color:#fff}.statrow{margin-top:5px;color:#8fafA3;font-size:9px}.meter{height:4px;margin:7px 0;background:#ffffff10;border-radius:3px;overflow:hidden}.meter span{display:block;height:100%;background:linear-gradient(90deg,var(--player,#4fb77b),var(--accent));border-radius:inherit}.action{min-height:28px;padding:6px;background:#ffffff0c;border-radius:6px;color:#dce8e3;font-size:12px;font-weight:850;text-align:center}.next .action{background:var(--accent);color:#172018;text-shadow:none}
.ticker{min-height:52px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:14px;padding:10px 16px;border-radius:12px}.ticker-label{color:#8eaa9e;font-size:9px;font-weight:950;letter-spacing:.13em}.commentary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#f7d879;font-size:16px;font-weight:750}.history{color:#9eb4aa;font-size:10px;text-align:right;white-space:nowrap}body[data-connected=false] .live{color:#ff9a7a}body[data-connected=false] .live:before{background:#ff6a55;animation:none}
.compact{padding:18px}.compact .board{height:auto;padding:16px;border-radius:20px}.compact .felt-ring{display:none}.compact .header{grid-template-columns:1.4fr repeat(3,1fr)}.compact .header .optional{display:none}.compact .table{padding:6px 0 0}.compact .cards{min-height:72px;margin:8px}.compact .card{width:50px;height:70px}.compact .card b{font-size:18px}.compact .card i{font-size:23px}.compact .hole .card{width:32px;height:44px}.compact .player{padding:8px}.compact .ticker{min-height:40px}.reduced *,body.reduced *{animation:none!important;transition:none!important}
.layout-vertical .players{grid-template-columns:1fr 1fr;max-width:1100px;width:100%;margin:0 auto}
@keyframes pulse{50%{opacity:.45;transform:scale(.8)}}@keyframes cardFlip{0%{opacity:0;transform:translateY(-24px) rotateY(88deg) scale(.88);box-shadow:0 2px 4px #0004}55%{opacity:1;transform:translateY(2px) rotateY(-8deg) scale(1.04)}100%{opacity:1;transform:none}}
@keyframes chipSlide{0%{opacity:0;transform:translateY(28px) scale(.7)}65%{opacity:1;transform:translateY(-3px) scale(1.08)}100%{opacity:1;transform:none}}@keyframes chipPulse{50%{transform:scale(1.14);box-shadow:0 0 20px #e6b94a88}}@keyframes winnerGlow{50%{box-shadow:inset 0 0 130px #d9b94b44,0 24px 80px #000d}}@keyframes winnerPop{0%{transform:translateY(5px) scale(.97)}45%{transform:translateY(-8px) scale(1.025)}100%{transform:translateY(-3px) scale(1)}}
.board.fx-action .pot-chip{animation:chipPulse .55s ease}.board.fx-community .cards{animation:chipPulse .48s ease}.board.fx-winner{animation:winnerGlow 1.8s ease}
@media(max-width:1100px){body{padding:14px}.header{grid-template-columns:1.5fr repeat(3,1fr)}.header .optional{display:none}.players{grid-template-columns:repeat(2,1fr)}}

/* Casino broadcast v3: premium hierarchy, newcomer guidance, and event choreography. */
body{padding:24px;background:radial-gradient(circle at 50% 48%,#07150f 0,#010503 72%)}
.board{position:relative;isolation:isolate;grid-template-rows:auto auto minmax(0,1fr) auto;gap:10px;padding:18px 20px 16px;border:1px solid #f0cf7252;border-top:4px solid var(--accent);border-radius:30px;background:
 radial-gradient(ellipse at 50% 42%,#176044 0,#0c432f 36%,#082d21 67%,#03130e 100%),
 repeating-radial-gradient(circle at 50% 45%,#ffffff06 0 1px,transparent 1px 7px);
 box-shadow:0 26px 90px #000f,inset 0 0 120px #0009,0 0 0 1px #000;overflow:hidden}
.board:before{content:'';position:absolute;z-index:-1;inset:-40% -20%;background:linear-gradient(108deg,transparent 38%,#f5d4770b 47%,#ffffff12 50%,#f5d47708 53%,transparent 62%);animation:tableSweep 13s ease-in-out infinite;pointer-events:none}
.board:after{content:'';position:absolute;z-index:8;inset:0;border-radius:inherit;box-shadow:inset 0 0 0 1px #fff1,inset 0 -70px 100px #0004;pointer-events:none}
.header,.storybar,.table,.ticker{position:relative;z-index:2}
.header{grid-template-columns:minmax(300px,1.8fr) repeat(4,minmax(112px,.62fr));gap:8px;min-height:60px}
.brand,.metric,.storybar,.player,.ticker{backdrop-filter:blur(12px);border:1px solid #ffffff17;background:linear-gradient(165deg,#0a211adf,#020906ed);box-shadow:0 10px 24px #0006,inset 0 1px #ffffff08}
.brand{position:relative;overflow:hidden;padding:9px 17px;border-radius:12px}
.brand:after{content:'AUTONOMOUS AI LEAGUE';position:absolute;right:15px;bottom:9px;color:#8ca99e;font-size:8px;font-weight:900;letter-spacing:.16em}.simulation-tag{position:absolute;right:15px;top:9px;color:#e6ca70;font-size:7px;font-weight:950;letter-spacing:.1em}.simulation-tag.hidden{display:none}
.health-pill{position:absolute;right:13px;top:23px;display:flex;align-items:center;gap:6px;max-width:190px;padding:3px 7px;border:1px solid #6bd49a44;border-radius:9px;background:#0b2b20d9;color:#bce8d0;text-shadow:none}.health-dot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#65d694;box-shadow:0 0 9px #65d694}.health-copy{display:flex;align-items:baseline;gap:5px;min-width:0}.health-copy strong{font-size:7px;letter-spacing:.08em;white-space:nowrap}.health-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#86ad9d;font-size:6px}.health-pill.degraded{border-color:#efc65b66;background:#382a0ed9;color:#ffe29a}.health-pill.degraded .health-dot{background:#f0c252;box-shadow:0 0 10px #f0c252}.health-pill.warning,.health-pill.disconnected{border-color:#ed6d5f77;background:#401713e8;color:#ffd0c8}.health-pill.warning .health-dot,.health-pill.disconnected .health-dot{background:#ec6557;box-shadow:0 0 11px #ec6557}.health-pill.recovered,.health-pill.notice{border-color:#72b7ea66;background:#102c41d9;color:#cfeaff}.health-pill.recovered .health-dot,.health-pill.notice .health-dot{background:#72b7ea;box-shadow:0 0 10px #72b7ea}.health-pill:not(.normal) .health-dot{animation:tensionPulse 1.8s ease-in-out infinite}.compact .health-copy small{display:none}
.logo{font-size:24px;letter-spacing:.17em;background:linear-gradient(180deg,#ffe99b,#c99734);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 2px 8px #f0c85b33)}
.live{font-size:9px}.metric{position:relative;display:flex;flex-direction:column;justify-content:center;padding:7px 10px;border-radius:10px;overflow:hidden}.metric small{font-size:8px}.metric strong{font-size:19px}.metric.emphasis{border-color:#dbbc6266;background:linear-gradient(160deg,#1b2818e8,#080c08ed)}.metric.emphasis strong{color:#f7d675}.metric.bump strong{animation:numberBump .5s cubic-bezier(.2,.8,.2,1)}.metric-sub{height:11px;margin-top:1px;color:#78978a;font-size:8px;font-weight:800;letter-spacing:.05em;white-space:nowrap}
.storybar{display:grid;grid-template-columns:auto minmax(280px,1.15fr) minmax(360px,1fr);align-items:center;gap:14px;min-height:52px;padding:7px 12px;border-radius:12px;border-color:#d4b95b33;background:linear-gradient(90deg,#071712f2,#10281feb 52%,#07120ff2)}
.moment-badge{min-width:112px;padding:8px 11px;border-radius:8px;background:#17382c;color:#b8d6ca;font-size:9px;font-weight:950;letter-spacing:.13em;text-align:center;box-shadow:inset 0 0 0 1px #ffffff12}.moment-badge.hot{background:linear-gradient(135deg,#922f28,#421816);color:#ffe0c8;box-shadow:0 0 22px #e1513644,inset 0 0 0 1px #ff987155;animation:tensionPulse 1.65s ease-in-out infinite}.moment-badge.gold{background:linear-gradient(135deg,#e0b84f,#6e4d12);color:#15140e;text-shadow:none}
.story{min-width:0}.story-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#fff6da;font-size:14px;font-weight:950;letter-spacing:.015em}.story-copy{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px;color:#a9c0b7;font-size:10px}.story-copy b{color:#f3d06b}
.street-progress{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}.step{position:relative;padding:6px 2px 5px;border-radius:7px;background:#ffffff08;color:#67847a;font-size:8px;font-weight:900;letter-spacing:.06em;text-align:center}.step:before{content:'';display:block;width:7px;height:7px;margin:0 auto 3px;border:2px solid currentColor;border-radius:50%}.step.done{color:#80b99d;background:#0b3124}.step.current{color:#171a13;background:linear-gradient(180deg,#ffe28a,#c99c37);text-shadow:none;box-shadow:0 0 20px #e9bd4d45;animation:stepArrival .5s ease}.step.current:before{background:#172019;border-color:#172019}
.table{grid-template-rows:minmax(175px,1fr) auto;gap:9px;padding:5px 2.5% 0}.felt-ring{inset:1% 5.5% 10%;border:2px solid #dfc3672c;box-shadow:inset 0 0 95px #0008,0 0 0 8px #0002,0 0 45px #ddbd4c0c}.felt-ring:after{content:'';position:absolute;inset:12% 10%;border:1px dashed #e2ca7630;border-radius:48%}
.center{position:relative}.stage{display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border:1px solid #e2c36343;border-radius:20px;background:#07130dcc;color:#f4d477;font-size:10px;font-weight:950;letter-spacing:.18em;text-transform:uppercase}.stage:before{content:'';width:6px;height:6px;border-radius:50%;background:#f1cc62;box-shadow:0 0 12px #ffd96a}.stage-help{min-height:15px;margin-top:5px;color:#a9bfb6;font-size:10px}.cards{min-height:96px;margin:8px 0 6px;gap:9px}.card{position:relative;width:68px;height:94px;padding:0;border:1px solid #fff;border-radius:9px;background:linear-gradient(145deg,#fffef8,#ddd8ca);box-shadow:0 10px 20px #000b,0 1px #fff inset;overflow:hidden}.card:before{content:'';position:absolute;inset:4px;border:1px solid #1e2b2514;border-radius:6px}.card-corner{position:absolute;z-index:2;left:7px;top:6px;display:flex;flex-direction:column;align-items:center;font-weight:950;line-height:.9}.card-corner b{font-size:20px}.card-corner i{font-size:14px;font-style:normal}.card-corner.bottom{left:auto;right:7px;top:auto;bottom:6px;transform:rotate(180deg)}.card-pip{position:absolute;inset:0;display:grid;place-items:center;font-size:43px;opacity:.92}.card-sheen{position:absolute;inset:-80% -40%;background:linear-gradient(110deg,transparent 42%,#fff9 49%,transparent 56%);transform:translateX(-70%)}.card.fresh .card-sheen{animation:cardSheen .85s .18s ease both}.card.placeholder{background:linear-gradient(145deg,#09291e,#04150f);border:1px dashed #d7bf6d2d}.card.placeholder:after{content:'AI';position:absolute;inset:7px;display:grid;place-items:center;border:1px solid #d6be6823;border-radius:5px;color:#d4ba5f2d;font-size:14px;font-weight:950;letter-spacing:.12em}.potline{min-height:31px}.pot-chip{border-color:#e4c75c5e;background:linear-gradient(180deg,#151b0ffa,#070b07f3);font-size:10px;box-shadow:0 6px 14px #0007}.pot-chip.total{padding-right:14px;color:#ffe18a;font-size:12px}.analysis-note{margin-top:3px;color:#87a79a;font-size:9px}
.players{grid-template-columns:repeat(var(--seat-count,4),minmax(0,1fr));gap:8px}.player{isolation:isolate;min-height:214px;padding:10px 11px 9px;border-radius:12px;border:1px solid #ffffff14;border-bottom:4px solid var(--player,#446c5b);background:linear-gradient(150deg,#092019ed,#020906f5);box-shadow:0 10px 26px #0008,inset 0 1px #fff1;overflow:hidden}.player:after{content:'';position:absolute;z-index:-1;inset:0;background:radial-gradient(circle at 20% 0,var(--player,#446c5b) 0,transparent 45%);opacity:.13}.player.next{z-index:3;transform:translateY(-7px) scale(1.012);border-color:#f0ce67;box-shadow:0 0 0 1px #f2d37099,0 0 34px #edc95e45,0 16px 32px #000c}.player.next:before{content:'ACTING';position:absolute;right:9px;top:42px;padding:3px 6px;border-radius:6px;background:#f1cd65;color:#172019;font-size:7px;font-weight:950;letter-spacing:.12em;text-shadow:none;animation:actingPulse 1.4s ease-in-out infinite}.player.favorite:not(.folded):not(.eliminated){box-shadow:0 0 0 1px color-mix(in srgb,var(--player) 50%,transparent),0 12px 28px #0009}.player.winner{z-index:5;animation:winnerPop 1.15s ease both,winnerHalo 1.4s ease-in-out infinite}.player.folded,.player.eliminated{opacity:.34;filter:saturate(.25)}.player.folded:before,.player.eliminated:before{content:'FOLDED';position:absolute;z-index:4;left:50%;top:48%;transform:translate(-50%,-50%) rotate(-7deg);padding:5px 12px;border:2px solid #b6c2bd99;border-radius:5px;color:#dce6e2;font-size:13px;font-weight:950;letter-spacing:.12em}.player.eliminated:before{content:'OUT'}.player.all_in:not(.folded){border-color:#e26950;box-shadow:0 0 0 1px #e26950,0 0 28px #c9432f3d,0 12px 28px #000a}
.player-head{align-items:flex-start}.identity{display:flex;align-items:center;min-width:0;gap:8px}.avatar{flex:0 0 30px;height:30px;display:grid;place-items:center;border:1px solid #ffffff22;border-radius:50%;background:linear-gradient(145deg,var(--player),#0a1611);color:white;font-size:14px;font-weight:950;box-shadow:0 0 18px color-mix(in srgb,var(--player) 35%,transparent)}.name-block{min-width:0}.name{font-size:16px}.model{max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:8px}.badge{padding:3px 5px;font-size:7px;letter-spacing:.04em}.badge.leader{background:#e7bd4e;color:#15180f;text-shadow:none}.badge.danger{animation:tensionPulse 1.5s infinite}.hole{min-height:53px;margin:5px 0 0}.hole .card{width:38px;height:52px}.hole .card:before{inset:2px}.hole .card-corner{left:4px;top:4px}.hole .card-corner b{font-size:13px}.hole .card-corner i{font-size:10px}.hole .card-corner.bottom{right:4px;bottom:4px;left:auto;top:auto}.hole .card-pip{font-size:24px}.wager{height:22px;margin-bottom:2px}.wager.fresh .mini-chip{animation:chipBounce .62s cubic-bezier(.2,.8,.2,1) both}.wager.fresh .mini-chip:nth-child(2){animation-delay:.07s}.wager.fresh .mini-chip:nth-child(3){animation-delay:.14s}.mini-chip{width:15px;height:15px}.handline,.stackrow{display:flex;align-items:center;justify-content:space-between;gap:8px}.hand-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e7f0ec;font-size:10px;font-weight:850;text-transform:uppercase}.chance{flex:0 0 auto;color:#a9bfb6;font-size:9px;font-weight:800}.chance b{color:#fff;font-size:12px}.equity-meter{height:6px;margin:5px 0;background:#ffffff0d;border:1px solid #ffffff09;border-radius:8px;overflow:hidden}.equity-meter span{display:block;height:100%;background:linear-gradient(90deg,var(--player),#f2d36d);border-radius:inherit;box-shadow:0 0 10px var(--player);transition:width .65s ease}.action{min-height:25px;padding:5px;margin-top:4px;font-size:10px}.action.fresh{animation:actionToast .5s ease}.next .action{background:linear-gradient(180deg,#f6db83,#c79c36);box-shadow:0 5px 15px #d9ad3b38}.stackrow{margin-top:5px;font-size:10px}.stackrow strong{font-size:11px}.statrow{margin-top:3px;font-size:8px}.statrow .plain-stat{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ticker{min-height:46px;grid-template-columns:auto minmax(220px,1fr) auto;gap:10px;padding:8px 13px;border-radius:11px}.ticker-label{display:flex;align-items:center;gap:6px}.ticker-label:before{content:'';width:7px;height:7px;border-radius:50%;background:#ee4c40;box-shadow:0 0 10px #ff5a4d;animation:pulse 1.4s infinite}.commentary{font-size:14px}.commentary.fresh{animation:tickerSlide .42s ease}.history{max-width:460px;overflow:hidden;text-overflow:ellipsis;color:#779488;font-size:8px}.history:before{content:'RECENT  ';color:#d2b95d;font-weight:900;letter-spacing:.1em}
.winner-banner{position:absolute;z-index:20;left:50%;top:43%;width:min(680px,74%);transform:translate(-50%,-34%) scale(.84);padding:20px 26px 22px;border:1px solid #ffe38abb;border-radius:22px;background:radial-gradient(circle at 50% 0,#4a3711ee 0,#151208f5 42%,#040705fa 100%);box-shadow:0 0 0 2px #d1a63c3d,0 30px 100px #000f,0 0 82px #f2c55266,inset 0 1px #fff3;opacity:0;visibility:hidden;text-align:center;overflow:hidden;transition:opacity .2s,transform .55s cubic-bezier(.12,.84,.2,1),visibility .2s}.winner-banner:before{content:'';position:absolute;inset:-45% -25%;background:linear-gradient(115deg,transparent 37%,#fff7 49%,transparent 58%);opacity:.45;transform:translateX(-54%)}.winner-banner.show{opacity:1;visibility:visible;transform:translate(-50%,-50%) scale(1)}.winner-banner.show:before{animation:winnerSweep 1.45s .12s ease both}.winner-kicker{position:relative;color:#eac65d;font-size:9px;font-weight:950;letter-spacing:.24em}.winner-title{position:relative;margin-top:5px;color:#fff2b7;font-size:18px;font-weight:950;letter-spacing:.22em}.winner-player{position:relative;margin-top:3px;color:#fff;font-size:38px;font-weight:950;letter-spacing:.025em;line-height:1.05;text-transform:uppercase}.winner-hand{position:relative;display:inline-block;margin-top:8px;padding:6px 14px;border:1px solid #f1cd6688;border-radius:999px;background:#080d09d9;color:#ffe39a;font-size:15px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.winner-card-row{position:relative;display:flex;justify-content:center;align-items:center;gap:7px;min-height:74px;margin:11px auto 7px;perspective:900px}.winner-card-row .card{width:50px;height:70px;border-radius:7px;box-shadow:0 9px 18px #000b}.winner-card-row .card-corner{left:5px;top:5px}.winner-card-row .card-corner b{font-size:15px}.winner-card-row .card-corner i{font-size:11px}.winner-card-row .card-corner.bottom{right:5px;bottom:5px;left:auto;top:auto}.winner-card-row .card-pip{font-size:30px}.winner-plus{align-self:center;margin:0 3px;padding:4px 7px;border-radius:999px;background:#ffffff12;color:#99b5aa;font-size:8px;font-weight:950;letter-spacing:.12em}.winner-explainer{max-width:420px;color:#b9c8c2;font-size:12px;font-weight:800}.winner-detail{position:relative;margin:5px auto 0;max-width:560px;color:#d7e1dc;font-size:13px;line-height:1.35}.winner-amount{position:relative;display:inline-block;margin-top:11px;padding:7px 16px;border-radius:18px;background:linear-gradient(180deg,#ffe28a,#c99734);color:#17170f;font-size:15px;font-weight:950;text-shadow:none;box-shadow:0 8px 22px #0008}
.celebration{position:absolute;z-index:19;inset:0;overflow:hidden;pointer-events:none;visibility:hidden}.celebration.show{visibility:visible}.confetti{position:absolute;left:var(--x);top:-20px;width:8px;height:16px;border-radius:2px;background:var(--c);animation:confettiFall var(--d) var(--delay) ease-in both}
[data-seats='5'] .player,[data-seats='6'] .player{padding-left:8px;padding-right:8px}.seats-many .model,.seats-many .statrow{display:none}.seats-many .name{font-size:14px}.seats-many .badge{font-size:6px}.seats-many .avatar{display:none}.seats-many .hole{margin-top:3px}
.compact .storybar{grid-template-columns:auto 1fr}.compact .street-progress{display:none}.compact .player{min-height:175px}.compact .stage-help,.compact .statrow{display:none}
@keyframes tableSweep{0%,18%{transform:translateX(-42%)}62%,100%{transform:translateX(42%)}}
@keyframes numberBump{0%{transform:scale(1)}45%{transform:scale(1.22);color:#fff2a9}100%{transform:scale(1)}}
@keyframes tensionPulse{50%{filter:brightness(1.25);box-shadow:0 0 26px #d44a3655}}
@keyframes stepArrival{0%{opacity:.4;transform:translateY(5px) scale(.95)}100%{opacity:1;transform:none}}
@keyframes cardSheen{0%{transform:translateX(-70%)}100%{transform:translateX(70%)}}
@keyframes actingPulse{50%{transform:scale(1.08);box-shadow:0 0 17px #efd06d}}
@keyframes chipBounce{0%{opacity:0;transform:translateY(24px) scale(.6)}65%{opacity:1;transform:translateY(-4px) scale(1.12)}100%{transform:none}}
@keyframes actionToast{0%{opacity:.25;transform:translateY(8px)}100%{opacity:1;transform:none}}
@keyframes tickerSlide{0%{opacity:0;transform:translateX(18px)}100%{opacity:1;transform:none}}
@keyframes winnerHalo{50%{box-shadow:0 0 0 2px #f2cf68,0 0 50px #e6b94abb}}
@keyframes winnerSweep{0%{transform:translateX(-60%) rotate(4deg)}100%{transform:translateX(60%) rotate(4deg)}}
@keyframes confettiFall{0%{opacity:0;transform:translateY(-30px) rotate(0)}8%{opacity:1}100%{opacity:0;transform:translateY(780px) rotate(720deg)}}
/* Casino seated-table layout: players orbit the felt; bottom bar carries broadcast context. */
.table{position:relative;min-height:610px;display:block;padding:0 2.5%}.center{position:absolute;z-index:4;left:50%;top:47%;width:min(560px,48vw);transform:translate(-50%,-50%)}.dealer-station{position:absolute;z-index:5;left:50%;top:4%;width:318px;transform:translateX(-50%);display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;padding:8px 12px;border:1px solid #efd16b4a;border-radius:16px;background:linear-gradient(180deg,#07130ff2,#020906f6);box-shadow:0 12px 30px #0009,inset 0 1px #fff1}.dealer-icon{width:38px;height:38px;border-radius:50%;background:radial-gradient(circle at 50% 28%,#f5d99c 0 20%,#2c1d14 21% 36%,#0c1712 37%);border:1px solid #efd16b66;box-shadow:0 0 18px #e7bd4d33}.dealer-copy{min-width:0}.dealer-copy strong{display:block;color:#ffe28a;font-size:10px;font-weight:950;letter-spacing:.14em}.dealer-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#9fb6ac;font-size:8px;font-weight:800}.dealer-tray{display:flex;gap:3px}.tray-chip{width:12px;height:24px;border-radius:4px;background:repeating-linear-gradient(180deg,#f4d77e 0 3px,#8e322b 3px 6px);box-shadow:0 2px 5px #0008}.deck-stack{position:absolute;left:calc(50% + 190px);top:16%;width:48px;height:66px;border-radius:8px;background:linear-gradient(145deg,#14335a,#071a2e);border:1px solid #d8c06b55;box-shadow:6px 5px 0 #061422,12px 10px 0 #040c14,0 8px 18px #000b}.deck-stack:after{content:'DECK';position:absolute;inset:0;display:grid;place-items:center;color:#d9c67477;font-size:8px;font-weight:950;letter-spacing:.12em}.burn-stack{position:absolute;left:calc(50% - 240px);top:16%;padding:6px 9px;border:1px dashed #d7bf6d44;border-radius:9px;background:#06130fd9;color:#a7b8b0;font-size:8px;font-weight:900;letter-spacing:.1em}.center .potline{margin-top:3px}.players{position:absolute;z-index:6;inset:0;display:block;pointer-events:none}.player{position:absolute;pointer-events:auto;width:265px;min-height:186px;padding:9px 10px 8px}.player:before{content:'';position:absolute;z-index:-2;left:50%;top:50%;width:120px;height:28px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(ellipse,#0007 0,#0000 70%)}.seat-label{position:absolute;left:10px;top:-12px;padding:3px 8px;border-radius:999px;background:#07130ff0;border:1px solid #ffffff18;color:#98b1a6;font-size:7px;font-weight:950;letter-spacing:.12em}.stack-graphic{display:flex;align-items:flex-end;gap:2px}.stack-chip{width:13px;border-radius:4px 4px 2px 2px;background:repeating-linear-gradient(180deg,#fff4b8 0 3px,var(--player,#b83632) 3px 6px);border:1px solid #0005;box-shadow:0 2px 5px #0009}.stack-chip:nth-child(1){height:17px}.stack-chip:nth-child(2){height:23px}.stack-chip:nth-child(3){height:14px}body[data-seats="2"] .player:nth-child(1){left:8%;bottom:7%}body[data-seats="2"] .player:nth-child(2){right:8%;top:13%}body[data-seats="3"] .player:nth-child(1){left:8%;bottom:7%}body[data-seats="3"] .player:nth-child(2){right:8%;bottom:7%}body[data-seats="3"] .player:nth-child(3){left:50%;top:8%;transform:translateX(-50%)}body[data-seats="4"] .player:nth-child(1){left:5%;bottom:7%}body[data-seats="4"] .player:nth-child(2){right:5%;bottom:7%}body[data-seats="4"] .player:nth-child(3){left:6%;top:14%}body[data-seats="4"] .player:nth-child(4){right:6%;top:14%}body[data-seats="5"] .player:nth-child(1){left:5%;bottom:7%}body[data-seats="5"] .player:nth-child(2){left:50%;bottom:5%;transform:translateX(-50%)}body[data-seats="5"] .player:nth-child(3){right:5%;bottom:7%}body[data-seats="5"] .player:nth-child(4){left:7%;top:13%}body[data-seats="5"] .player:nth-child(5){right:7%;top:13%}body[data-seats="6"] .player:nth-child(1){left:3%;bottom:7%}body[data-seats="6"] .player:nth-child(2){left:50%;bottom:5%;transform:translateX(-50%)}body[data-seats="6"] .player:nth-child(3){right:3%;bottom:7%}body[data-seats="6"] .player:nth-child(4){left:3%;top:13%}body[data-seats="6"] .player:nth-child(5){left:50%;top:8%;transform:translateX(-50%)}body[data-seats="6"] .player:nth-child(6){right:3%;top:13%}.ticker{grid-template-columns:auto minmax(260px,1.2fr) minmax(320px,1fr) minmax(230px,.7fr);min-height:64px}.broadcast-context{min-width:0;display:grid;gap:3px}.broadcast-context strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#fff0b4;font-size:11px;font-weight:950}.broadcast-context span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#9fb8ad;font-size:10px}.compact .table{min-height:360px;display:grid}.compact .dealer-station,.compact .deck-stack,.compact .burn-stack{display:none}.compact .center{position:relative;left:auto;top:auto;width:auto;transform:none}.compact .players{position:relative;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:7px}.compact .player{position:relative;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;transform:none!important;width:auto;min-height:160px}.compact .ticker{grid-template-columns:auto 1fr}.compact .broadcast-context,.compact .history{display:none}
@media(max-width:1100px){.storybar{grid-template-columns:auto 1fr}.street-progress{display:none}.players{grid-template-columns:repeat(2,1fr)}.header{grid-template-columns:1.4fr repeat(3,1fr)}.header .optional{display:none}}
</style></head>
<body data-connected="false" data-music="__MUSIC__" class="__REDUCED__ __AUDIO__">
<main class="board layout-__LAYOUT__">
 <header class="header"><div class="brand"><div class="logo">AI POKER</div><div class="live" id="connection">RECONNECTING</div><div class="simulation-tag __DISCLAIMER_CLASS__">SIMULATION ONLY · FICTIONAL CHIPS · NO REAL MONEY</div><div class="health-pill normal" id="healthPill"><i class="health-dot"></i><span class="health-copy"><strong id="healthLabel">TABLE HEALTHY</strong><small id="healthDetail">Broadcast systems ready</small></span></div></div>
  <div class="metric"><small>HAND</small><strong id="hand">0</strong><span class="metric-sub">CURRENT DEAL</span></div>
  <div class="metric emphasis" id="potMetric"><small>TOTAL POT</small><strong id="pot">0</strong><span class="metric-sub">CHIPS TO WIN</span></div>
  <div class="metric"><small>BLINDS</small><strong id="blinds">0 / 0</strong><span class="metric-sub">FORCED OPENERS</span></div>
  <div class="metric optional"><small id="modeLabel">FORMAT</small><strong id="mode">-</strong><span class="metric-sub" id="level">-</span></div></header>
 <section class="storybar" aria-live="polite"><div class="moment-badge" id="momentBadge">LIVE HAND</div>
  <div class="story"><div class="story-title" id="storyTitle">The table is getting ready</div><div class="story-copy" id="storyCopy">Watch here for the key decision in plain English.</div></div>
  <div class="street-progress" id="streetProgress"><div class="step" data-step="pre-flop">PRIVATE CARDS</div><div class="step" data-step="flop">FLOP</div><div class="step" data-step="turn">TURN</div><div class="step" data-step="river">RIVER</div><div class="step" data-step="showdown">WINNER</div></div>
 </section>
 <section class="table"><div class="felt-ring"></div><div class="dealer-station"><div class="dealer-icon"></div><div class="dealer-copy"><strong id="dealerTitle">DEALER STATION</strong><small id="dealerDetail">Deck ready · burn 0</small></div><div class="dealer-tray"><i class="tray-chip"></i><i class="tray-chip"></i><i class="tray-chip"></i></div></div><div class="deck-stack"></div><div class="burn-stack" id="burnStack">BURN 0</div><div class="center"><div class="stage" id="stage">Waiting</div><div class="stage-help" id="stageHelp">Two private cards are dealt to every player.</div>
  <div class="cards" id="cards"><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span><span class="card placeholder"></span></div>
  <div class="potline" id="pots"></div><div class="analysis-note" id="analysis">Spectator analysis warming up</div></div><div class="players" id="players"></div></section>
 <footer class="ticker"><div class="ticker-label">LIVE ACTION</div><div class="commentary" id="commentary" aria-live="polite">Table ready</div><div class="broadcast-context"><strong id="programContext">Program warming up</strong><span id="storyContext">Season storylines loading</span></div><div class="history" id="history"></div></footer>
 <aside class="winner-banner" id="winnerBanner"><div class="winner-kicker" id="winnerKicker">HAND COMPLETE</div><div class="winner-title" id="winnerTitle">WINNER</div><div class="winner-player" id="winnerPlayer">PLAYER</div><div class="winner-hand" id="winnerHand">WINNING HAND</div><div class="winner-card-row" id="winnerCards"></div><div class="winner-detail" id="winnerDetail"></div><div class="winner-amount" id="winnerAmount"></div></aside>
 <div class="celebration" id="celebration" aria-hidden="true"></div>
</main>
<script>
const suits={hearts:'&hearts;',diamonds:'&diams;',clubs:'&clubs;',spades:'&spades;'},ranks={11:'J',12:'Q',13:'K',14:'A'},musicTracks=__MUSIC_TRACKS__,soundEffects=__SOUND_EFFECTS__;
const q=new URLSearchParams(location.search);document.body.classList.toggle('compact',q.get('compact')==='1');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stageOrder=['pre-flop','flop','turn','river','showdown'];
const stageHelpCopy={
 'pre-flop':'Every player has two private cards. The first betting round decides who continues.',
 flop:'Three shared cards are available to every remaining player.',
 turn:'A fourth shared card is added. One betting round remains after this.',
 river:'The fifth and final shared card is down. This is the last chance to bet.',
 showdown:'Cards are compared. The best five-card poker hand wins each pot.'
};
const card=(c,index=0,fresh=false)=>{const rank=ranks[c.rank]||c.rank,suit=suits[c.suit];return `<span class="card ${c.suit==='hearts'||c.suit==='diamonds'?'red':''} ${fresh?'fresh':''}" style="--deal-index:${index}"><span class="card-corner"><b>${rank}</b><i>${suit}</i></span><span class="card-pip">${suit}</span><span class="card-corner bottom"><b>${rank}</b><i>${suit}</i></span><span class="card-sheen"></span></span>`};
let lastState=null,refreshing=false,boardCount=0,winnerTimer=null,lastPot=-1,lastCommentary='',lastWinnerSignature='';
let holeSignatures=new Map(),wagerAmounts=new Map(),actionSignatures=new Map(),highlightedWinners=new Set();
async function refresh(){if(refreshing)return;refreshing=true;try{const response=await fetch('/state',{cache:'no-store'});if(!response.ok)throw Error();const s=await response.json();lastState=s;render(s);document.body.dataset.connected='true'}catch(_){document.body.dataset.connected='false';connection.textContent='RECONNECTING';commentary.textContent='Waiting for the game-state feed…'}finally{refreshing=false}}
function plainAction(action){return ({small_blind:'posts small blind',big_blind:'posts big blind',ante:'posts ante',all_in:'moves all-in'})[action]||String(action||'waits').replaceAll('_',' ')}
function momentFor(s,actor){
 const allIns=s.players.filter(p=>p.all_in&&!p.folded).length,potBB=Number(s.pot)/Math.max(1,Number(s.blinds.big));
 if(s.stage.toLowerCase()==='showdown')return ['SHOWDOWN','gold'];
 if(allIns>1)return ['ALL-IN COLLISION','hot'];
 if(allIns===1)return ['ALL-IN DRAMA','hot'];
 if(potBB>=50)return ['MONSTER POT','hot'];
 if(potBB>=20)return ['BIG POT','hot'];
 if(actor)return ['DECISION TIME',''];
 return ['LIVE HAND',''];
}
function storyFor(s,actor){
 const stageKey=s.stage.toLowerCase(),active=s.players.filter(p=>p.active&&!p.folded);
 if(stageKey==='showdown')return ['The cards are being compared',active.length>1?'The best five-card combination takes each pot.':'Everyone else folded, so the last player wins without showing.'];
 if(!actor){
   if(stageKey==='pre-flop'&&(s.action_history||[]).length<2)return ['Private cards are being dealt','The small and big blinds will seed the pot before anyone chooses an action.'];
   return [`${s.stage} betting is complete`,stageKey==='river'?'The remaining hands are about to be compared.':'The next shared card is coming up.'];
 }
 const legal=actor.legal_actions||[],call=legal.find(a=>a.action==='call'),canBet=legal.some(a=>a.action==='bet'||a.action==='raise');
 if(call){const amount=Number(call.amount||0);return [`${actor.name} must decide`,`It costs <b>${amount.toLocaleString()} chips</b> to stay in. ${canBet?'They can also raise the pressure or fold.':'They can call or fold.'}`]}
 if(canBet)return [`${actor.name} controls the action`,'They can <b>check for free</b> or bet to make opponents pay to continue.'];
 return [`${actor.name} can check`,'Checking costs nothing and passes the decision to the next player.'];
}
function updateProgress(stageName){const current=Math.max(0,stageOrder.indexOf(stageName.toLowerCase()));streetProgress.querySelectorAll('.step').forEach((step,index)=>{step.classList.toggle('done',index<current);step.classList.toggle('current',index===current)})}
function updateHealth(s){const h=s.health||{},state=h.overall||'normal';healthPill.className=`health-pill ${state}`;healthLabel.textContent=h.label||'TABLE HEALTHY';healthDetail.textContent=h.detail||'Broadcast systems ready';healthPill.title=Object.entries(h.components||{}).map(([key,value])=>`${key}: ${value}`).join(' · ')}
function audioMix(){const a=lastState?.audio||{};return{master:Math.max(0,Math.min(1,Number(a.master??.45))),effects:Math.max(0,Math.min(1,Number(a.effects??.72))),music:Math.max(0,Math.min(1,Number(a.music??.18))),musicOn:a.music_enabled!==false}}
let musicPlayer=null,musicIndex=0,musicBlocked=false;
let lastEffectAt=0;
function nextMusicTrack(){if(!musicTracks.length)return null;const track=musicTracks[musicIndex%musicTracks.length];musicIndex+=1;return track}
function updateMusicVolume(){if(!musicPlayer)return;const mix=audioMix();musicPlayer.volume=Math.max(0,Math.min(.55,mix.master*mix.music))}
function startMusic(){if(!document.body.classList.contains('audio-on')||document.body.dataset.music!=='on'||!musicTracks.length)return;const mix=audioMix();if(!mix.musicOn||mix.master<=0||mix.music<=0)return;if(musicPlayer&&!musicPlayer.paused){updateMusicVolume();return}const track=nextMusicTrack();if(!track)return;musicPlayer=new Audio(track);musicPlayer.preload='auto';musicPlayer.onended=()=>{musicPlayer=null;setTimeout(startMusic,350)};musicPlayer.onerror=()=>{musicPlayer=null;setTimeout(startMusic,1500)};updateMusicVolume();musicPlayer.play().then(()=>{musicBlocked=false}).catch(()=>{musicBlocked=true})}
function unlockAudio(){try{const C=window.AudioContext||window.webkitAudioContext,ctx=window.__ctx||(window.__ctx=new C());if(ctx.state==='suspended')ctx.resume()}catch(_){}startMusic()}
function render(s){
 document.body.dataset.seats=s.players.length;document.body.classList.toggle('seats-many',s.players.length>4);players.style.setProperty('--seat-count',s.players.length);
 connection.textContent=s.services?.ollama==='online'?'LOCAL LIVE · OLLAMA':s.services?.ollama==='preview'?'LOCAL LIVE · DEMO':s.services?.ollama==='unknown'?'LOCAL LIVE':'LOCAL LIVE · MODEL FALLBACK';
 updateHealth(s);
 hand.textContent=Number(s.hand_number).toLocaleString();stage.textContent=s.stage;stageHelp.textContent=stageHelpCopy[s.stage.toLowerCase()]||'The table is preparing the next hand.';
 dealerTitle.textContent=s.dealer?`DEALER: ${s.dealer}`:'DEALER STATION';dealerDetail.textContent=`${s.program?.segment||'Live Table'} · hand ${Number(s.hand_number||0).toLocaleString()}`;burnStack.textContent=`BURN ${Number(s.burn_count||0)}`;
 const livePot=Number(s.pot||0);pot.textContent=livePot.toLocaleString();if(lastPot>=0&&livePot!==lastPot){potMetric.classList.remove('bump');requestAnimationFrame(()=>potMetric.classList.add('bump'));setTimeout(()=>potMetric.classList.remove('bump'),600)}lastPot=livePot;
 blinds.textContent=`${s.blinds.small} / ${s.blinds.big}${s.blinds.ante?' + '+s.blinds.ante:''}`;mode.textContent=s.mode==='tournament'?'SIT & GO':'CASH GAME';level.textContent=s.tournament?`LEVEL ${s.tournament.level} · ${s.tournament.hands_remaining} HANDS LEFT`:'FIXED 10 / 20 STAKES';
 const actor=s.players.find(p=>p.next_to_act),moment=momentFor(s,actor),story=storyFor(s,actor);momentBadge.textContent=moment[0];momentBadge.className=`moment-badge ${moment[1]}`;storyTitle.textContent=story[0];storyCopy.innerHTML=story[1];updateProgress(s.stage);
 const previousBoardCount=boardCount,newBoardCount=s.community_cards.length;
 const board=s.community_cards.map((c,index)=>card(c,index,index>=previousBoardCount)).join('')+'<span class="card placeholder"></span>'.repeat(Math.max(0,5-newBoardCount));
 if(cards.innerHTML!==board)cards.innerHTML=board;boardCount=newBoardCount;
 const breakdown=(s.pots||[]).filter(p=>Number(p.amount)>0),breakdownTotal=breakdown.reduce((sum,p)=>sum+Number(p.amount),0);
 pots.innerHTML=`<span class="pot-chip total">TOTAL POT ${livePot.toLocaleString()}</span>`+(breakdown.length>1&&breakdownTotal===livePot?breakdown.map(p=>`<span class="pot-chip">${p.kind.toUpperCase()} ${Number(p.amount).toLocaleString()}</span>`).join(''):'');
 const champion=s.tournament?.complete?s.players.find(p=>p.id===s.tournament.winner):null;analysis.textContent=champion?`${champion.name.toUpperCase()} IS THE SIT & GO CHAMPION`:s.analysis?.pending?'Updating everyone’s chance to win…':'Chance-to-win estimates are spectator-only and never shown to the AI players.';
 const livePlayers=s.players.filter(p=>!p.eliminated),leader=livePlayers.reduce((best,p)=>!best||p.chips>best.chips?p:best,null),equityPlayers=s.players.filter(p=>!p.folded&&p.equity!=null),favorite=equityPlayers.reduce((best,p)=>!best||Number(p.equity)>Number(best.equity)?p:best,null);
 players.innerHTML=s.players.map(p=>{
   const cardsForPlayer=p.hole_cards||[],holeSignature=JSON.stringify(cardsForPlayer),holeFresh=cardsForPlayer.length>0&&holeSignatures.get(p.id)!==holeSignature;holeSignatures.set(p.id,holeSignature);
   const wager=Number(p.street_commitment||0),wagerFresh=wager>0&&wagerAmounts.get(p.id)!==wager;wagerAmounts.set(p.id,wager);
   const actionSignature=`${p.action}|${p.hand_commitment}`,actionFresh=actionSignatures.has(p.id)&&actionSignatures.get(p.id)!==actionSignature;actionSignatures.set(p.id,actionSignature);
   const wagerMarkup=wager?`<div class="wager ${wagerFresh?'fresh':''}"><span class="mini-chip" style="--chip:${esc(p.profile?.color||'#b83632')}"></span><span class="mini-chip" style="--chip:${esc(p.profile?.color||'#b83632')}"></span><span class="mini-chip" style="--chip:${esc(p.profile?.color||'#b83632')}"></span><b>${wager.toLocaleString()} BET</b></div>`:'<div class="wager empty">No wager</div>';
   const roles=`${p.id===leader?.id?'<span class="badge leader">CHIP LEADER</span>':''}${p.is_dealer?'<span class="badge gold">DEALER</span>':''}${p.is_small_blind?'<span class="badge">SMALL BLIND</span>':''}${p.is_big_blind?'<span class="badge">BIG BLIND</span>':''}${p.all_in?'<span class="badge danger">ALL-IN</span>':''}`;
   const equity=p.equity==null?null:Number(p.equity),equityWidth=equity==null?0:Math.max(2,equity),chance=equity==null?'<span class="chance">CALCULATING ODDS</span>':`<span class="chance"><b>${equity.toFixed(0)}%</b> CHANCE TO WIN</span>`;
   return `<article class="player ${p.next_to_act?'next':''} ${p.id===favorite?.id?'favorite':''} ${highlightedWinners.has(p.id)?'winner':''} ${esc(p.status)}" style="--player:${esc(p.profile?.color||'#4fb77b')}"><div class="seat-label">SEAT ${Number(p.seat)+1}</div><div class="player-head"><div class="identity"><div class="avatar">${esc(p.name.slice(0,1).toUpperCase())}</div><div class="name-block"><div class="name">${esc(p.name)}</div><div class="model">${esc(p.profile?.persona||'AI player')}</div></div></div><div class="badges">${roles}</div></div><div class="hole">${cardsForPlayer.map((c,index)=>card(c,index,holeFresh)).join('')}</div>${wagerMarkup}<div class="handline"><span class="hand-name">${esc(p.hand_label||'Waiting for cards')}</span>${chance}</div><div class="equity-meter"><span style="width:${equityWidth}%"></span></div><div class="action ${actionFresh?'fresh':''}">${esc(p.action||'Waiting')}${p.hand_commitment?' · '+Number(p.hand_commitment).toLocaleString()+' committed':''}</div><div class="stackrow"><strong>${Number(p.chips).toLocaleString()} CHIPS</strong><div class="stack-graphic"><i class="stack-chip"></i><i class="stack-chip"></i><i class="stack-chip"></i></div><span>${p.folded?'OUT THIS HAND':p.all_in?'EVERY CHIP IS IN':'STACK'}</span></div><div class="statrow"><span class="plain-stat">Plays ${Number(p.stats?.vpip||0).toFixed(0)}% of hands</span><span class="plain-stat">Raises ${Number(p.stats?.pfr||0).toFixed(0)}%</span></div></article>`;
 }).join('');
 const feed=s.commentary||[],latest=feed.at(-1)||'Table ready';commentary.textContent=latest;if(latest!==lastCommentary){commentary.classList.remove('fresh');requestAnimationFrame(()=>commentary.classList.add('fresh'));lastCommentary=latest}
 const beat=(s.storylines||[])[Number(s.hand_number||0)%(Math.max(1,(s.storylines||[]).length))]||{};programContext.textContent=`${s.program?.segment||'Live Table'} — ${s.league?.current_title||'AI Poker League'}`;storyContext.textContent=beat.text||s.program?.bumper||'Season context warming up.';
 history.textContent=(s.action_history||[]).slice(-3).map(a=>`${s.players[a.seat]?.name||''} ${plainAction(a.action)}${a.amount?' '+Number(a.amount).toLocaleString():''}`).join('  ·  ')
  updateMusicVolume();startMusic();maybeRevealWinnerFromState(s);
}
function sampleCue(type){const sample=(type==='deal'||type==='community')?soundEffects.card_flip:null;if(!sample)return false;const now=performance.now();if(now-lastEffectAt<80)return true;lastEffectAt=now;try{const mix=audioMix(),a=new Audio(sample);a.volume=Math.max(.01,Math.min(.65,mix.master*mix.effects));a.play().catch(()=>{});return true}catch(_){return false}}
function cue(type){if(!document.body.classList.contains('audio-on'))return;if(sampleCue(type))return;try{const C=window.AudioContext||window.webkitAudioContext,ctx=window.__ctx||(window.__ctx=new C()),o=ctx.createOscillator(),g=ctx.createGain(),mix=audioMix(),level=Math.max(.006,Math.min(.055,.04*mix.master*mix.effects));if(ctx.state==='suspended')ctx.resume();o.frequency.value=type==='winner'?740:type==='community'?440:type==='all_in'||type==='tournament_winner'?185:260;g.gain.setValueAtTime(level,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+(type==='winner'?.22:.12));o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+(type==='winner'?.24:.13))}catch(_){}}
const confettiColors=['#f1cb61','#fff0a8','#e45f56','#69c69a','#67aee8'];celebration.innerHTML=Array.from({length:34},(_,i)=>'<i class="confetti" style="--x:'+(3+(i*29)%94)+'%;--c:'+confettiColors[i%confettiColors.length]+';--d:'+(2.4+(i%7)*.18)+'s;--delay:'+((i%11)*.07)+'s"></i>').join('');
function eventWinnerIds(event){if(Array.isArray(event.player_ids)&&event.player_ids.length)return event.player_ids;return (event.players||[]).map(value=>lastState?.players?.find(p=>p.id===value||p.name===value)?.id||value)}
function eventWinnerNames(event,ids){const found=(ids||[]).map(id=>lastState?.players?.find(p=>p.id===id||p.name===id)).filter(Boolean);if(found.length)return found.map(p=>p.name);return (event.players||[]).map(String)}
function winnerSignature(event,ids){return `${lastState?.hand_number||''}|${(ids||eventWinnerIds(event)).join(',')}|${event.amount||''}|${event.hand||event.hand_detail||event.message||''}`}
function winnerFromState(s){if((s.stage||'').toLowerCase()!=='showdown')return null;const winners=(s.players||[]).filter(p=>String(p.action||'').startsWith('Won'));if(!winners.length)return null;const amount=winners.reduce((sum,p)=>sum+(Number(String(p.action||'').match(/\d+/)?.[0]||0)),0),detail=[...(s.commentary||[])].reverse().find(line=>/\bwins?\b|\bshare\b/i.test(line));return{type:'winner',players:winners.map(p=>p.name),player_ids:winners.map(p=>p.id),hand:winners[0]?.hand_label||'Winning hand',hand_detail:detail||'Showdown complete. The highlighted player has the best five-card hand.',amount,split:winners.length>1}}
function maybeRevealWinnerFromState(s){const event=winnerFromState(s);if(!event){if((s.stage||'').toLowerCase()!=='showdown')lastWinnerSignature='';return}const sig=winnerSignature(event,event.player_ids);if(sig===lastWinnerSignature||winnerBanner.classList.contains('show'))return;highlightedWinners=new Set(event.player_ids);lastWinnerSignature=sig;showWinner(event)}
function showWinner(event){const ids=eventWinnerIds(event),winners=ids.map(id=>lastState?.players?.find(p=>p.id===id||p.name===id)).filter(Boolean),names=eventWinnerNames(event,ids),primary=winners[0];lastWinnerSignature=winnerSignature(event,ids);const joined=names.length?names.join(event.split?' + ':', '):'PLAYER';winnerKicker.textContent='HAND COMPLETE';winnerTitle.textContent=event.split?'SPLIT POT':'WINNER';winnerPlayer.textContent=event.split?`${joined} SHARE IT`:`${joined} WINS`;winnerHand.textContent=event.hand||primary?.hand_label||'WINNING HAND';winnerDetail.textContent=event.hand_detail||event.message||'The best five-card poker hand takes the pot.';winnerAmount.textContent=event.amount?Number(event.amount).toLocaleString()+' CHIPS AWARDED':'POT AWARDED';const showcase=[];if(primary?.hole_cards?.length)showcase.push(...primary.hole_cards.map((c,index)=>card(c,index,true)));if(lastState?.community_cards?.length){if(showcase.length)showcase.push('<span class="winner-plus">BOARD</span>');showcase.push(...lastState.community_cards.map((c,index)=>card(c,index+2,true)))}winnerCards.innerHTML=showcase.length?showcase.join(''):'<span class="winner-explainer">Won before showdown; opponents folded, so no hand reveal was needed.</span>';winnerBanner.classList.add('show');celebration.classList.remove('show');requestAnimationFrame(()=>celebration.classList.add('show'));clearTimeout(winnerTimer);winnerTimer=setTimeout(()=>{winnerBanner.classList.remove('show');celebration.classList.remove('show');highlightedWinners.clear();if(lastState)render(lastState)},6200)}
function animateEvent(event){const type=event.type,b=document.querySelector('.board'),fx=type==='pot_awarded'||type==='winner'?'winner':type==='community'?'community':type==='action'?'action':'';if(fx){b.classList.remove('fx-action','fx-community','fx-winner');requestAnimationFrame(()=>b.classList.add('fx-'+fx));setTimeout(()=>b.classList.remove('fx-'+fx),1900)}if(type==='pot_awarded'||type==='winner'){const ids=event.player_ids||event.players||[];highlightedWinners=new Set(ids);if(lastState)render(lastState)}if(type==='winner')showWinner(event)}
const source=new EventSource('/events');source.onmessage=e=>{try{const event=JSON.parse(e.data);cue(event.type);animateEvent(event);refresh()}catch(_){}};source.onopen=()=>{document.body.dataset.connected='true';if(lastState)updateHealth(lastState)};source.onerror=()=>{document.body.dataset.connected='false';healthPill.className='health-pill disconnected';healthLabel.textContent='RECONNECTING';healthDetail.textContent='Game state is catching up'};
document.addEventListener('pointerdown',unlockAudio,{once:false});document.addEventListener('keydown',unlockAudio,{once:false});
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
    def __init__(self, game, host="127.0.0.1", port=8765, background="#071c13", accent="#e6b94a", font="Arial, sans-serif", layout="horizontal", reduced_motion=False, audio_enabled=False, disclaimer_enabled=True, music_dir="music", music_enabled=True, sound_effects_dir="sound_effects"):
        self.game = game
        self.host = host
        self.port = port
        self.background = background if re.fullmatch(r"#[0-9a-fA-F]{3,8}", background) else "#071c13"
        self.accent = accent if re.fullmatch(r"#[0-9a-fA-F]{3,8}", accent) else "#e6b94a"
        self.font = re.sub(r"[{};<>\r\n]", "", font) or "Arial, sans-serif"
        self.layout = layout if layout in {"horizontal", "vertical"} else "horizontal"
        self.reduced_motion = bool(reduced_motion)
        self.audio_enabled = bool(audio_enabled)
        self.disclaimer_enabled = bool(disclaimer_enabled)
        self.music_dir = Path(music_dir)
        self.music_enabled = bool(music_enabled)
        self.music_tracks = self._discover_music_tracks()
        self.sound_effects_dir = Path(sound_effects_dir)
        self.sound_effects = self._discover_sound_effects()
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
                    query = parse_qs(parsed.query)
                    audio_on = outer._query_enabled(query, "audio", outer.audio_enabled)
                    music_on = audio_on and outer._query_enabled(query, "music", outer.music_enabled and bool(outer.music_tracks))
                    music_tracks = [f"/music/{index}.wav" for index, _track in enumerate(outer.music_tracks)] if music_on else []
                    effects = outer.sound_effect_urls() if audio_on else {}
                    page = (OVERLAY_HTML.replace("__BACKGROUND__", outer.background).replace("__ACCENT__", outer.accent).replace("__FONT__", outer.font).replace("__LAYOUT__", outer.layout).replace("__REDUCED__", "reduced" if outer.reduced_motion else "").replace("__AUDIO__", "audio-on" if audio_on else "").replace("__MUSIC__", "on" if music_on else "off").replace("__MUSIC_TRACKS__", json.dumps(music_tracks)).replace("__SOUND_EFFECTS__", json.dumps(effects)).replace("__DISCLAIMER_CLASS__", "" if outer.disclaimer_enabled else "hidden"))
                    self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
                elif path == "/health":
                    state = outer.game.state_snapshot()
                    self._send_json({"status": "ok" if state["health"]["overall"] != "warning" else "warning", "schema_version": 2, "event_sequence": state["event_sequence"], "health": state["health"]})
                elif path == "/stream-info":
                    self._send_json(outer.stream_info())
                elif path.startswith("/music/"):
                    self._send_music(path)
                elif path.startswith("/sound/"):
                    self._send_sound(path)
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

            def _send_music(self, path):
                match = re.fullmatch(r"/music/([0-9]+)\.wav", path)
                if not match:
                    self._send_json({"error": "not found"}, status=404)
                    return
                index = int(match.group(1))
                if index < 0 or index >= len(outer.music_tracks):
                    self._send_json({"error": "not found"}, status=404)
                    return
                self._send_media_file(outer.music_tracks[index], "audio/wav")

            def _send_sound(self, path):
                match = re.fullmatch(r"/sound/([a-z0-9_]+)\.(mp3|wav|ogg)", path)
                if not match:
                    self._send_json({"error": "not found"}, status=404)
                    return
                key, extension = match.groups()
                track = outer.sound_effects.get(key)
                if not track or track.suffix.lower().lstrip(".") != extension:
                    self._send_json({"error": "not found"}, status=404)
                    return
                content_type = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg"}.get(extension, "application/octet-stream")
                self._send_media_file(track, content_type)

            def _send_media_file(self, track, content_type):
                try:
                    size = track.stat().st_size
                    start, end = 0, size - 1
                    status = 200
                    range_header = self.headers.get("Range", "")
                    match_range = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
                    if match_range:
                        left, right = match_range.groups()
                        if left == "" and right:
                            suffix = min(size, int(right))
                            start = size - suffix
                        elif left:
                            start = int(left)
                        if right and left:
                            end = min(size - 1, int(right))
                        if start > end or start >= size:
                            self.send_response(416)
                            self.send_header("Content-Range", f"bytes */{size}")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            return
                        status = 206
                    length = end - start + 1
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Accept-Ranges", "bytes")
                    if status == 206:
                        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with track.open("rb") as handle:
                        handle.seek(start)
                        remaining = length
                        while True:
                            if remaining <= 0:
                                break
                            chunk = handle.read(min(1024 * 256, remaining))
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

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

    @staticmethod
    def _query_enabled(query, key, default):
        if key not in query:
            return bool(default)
        value = (query.get(key) or [""])[-1].strip().lower()
        return value not in {"0", "false", "off", "no", "muted"}

    def _discover_music_tracks(self):
        if not self.music_dir.exists() or not self.music_dir.is_dir():
            return ()
        return tuple(
            sorted(
                (
                    path
                    for path in self.music_dir.iterdir()
                    if path.is_file() and path.suffix.lower() == ".wav"
                ),
                key=lambda path: path.name.lower(),
            )
        )

    def _discover_sound_effects(self):
        if not self.sound_effects_dir.exists() or not self.sound_effects_dir.is_dir():
            return {}
        effects = {}
        for path in sorted(self.sound_effects_dir.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or path.suffix.lower() not in {".mp3", ".wav", ".ogg"}:
                continue
            normalized = path.stem.lower().replace("-", "_").replace(" ", "_")
            if "card" in normalized and "flip" in normalized:
                effects["card_flip"] = path
        return effects

    def sound_effect_urls(self):
        return {
            key: f"/sound/{key}{path.suffix.lower()}"
            for key, path in self.sound_effects.items()
        }

    def stream_info(self):
        """Return copy-safe public metadata without cards, prompts, or local paths."""
        state = self.game.state_snapshot()
        tournament = state.get("tournament") or {}
        if state["mode"] == "tournament":
            program = f"Sit & Go {tournament.get('number', 1)} · Level {tournament.get('level', 1)}"
            summary = f"Tournament {tournament.get('number', 1)}, hand {tournament.get('hand', 0)}. All chips and records are fictional."
        else:
            program = "AI Poker League Exhibition Table"
            summary = f"Fixed {state['blinds']['small']}/{state['blinds']['big']} simulated-chip exhibition game."
        return {
            "schema_version": 1,
            "title": "AI Poker League | Autonomous AI Players | Simulation Only | No Real Money",
            "description": "Autonomous local AI players compete with fictional chips in a continuous rules-checked poker simulation. Entertainment software only; no real-world wagering or prizes.",
            "disclaimer": "Simulation only · fictional chips · no real money · no prizes",
            "current_program": program,
            "season_summary": summary,
            "players": [
                {"id": player["id"], "name": player["name"], "bio": player["profile"]["persona"]}
                for player in state["players"]
            ],
            "tech_stack": "Local-first Python rules engine, Ollama AI players, Qt control room, and an OBS browser overlay.",
        }

    def close(self):
        self._closing = True
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
