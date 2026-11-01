"""EGO Filo Takip - web arayüzü (yalnızca standart kütüphane).

ego_tracker.py tarafından kullanılır: make_handler(E) bir HTTP istek işleyicisi döndürür;
E, ego_tracker modülünün kendisidir (veritabanı ve sorgu fonksiyonları oradan gelir).
"""
import csv
import html
import io
import json
import gzip as _gzip
import math
import os
import re
import time
import urllib.parse
from http.cookies import SimpleCookie
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler

esc = html.escape

CSS = """
:root{--bg:#f3f4f6;--card:#fff;--ink:#15181e;--muted:#6b7280;--line:#e6e8ec;--accent:#c8102e;--accent2:#a50d26;
--ok:#166534;--okbg:#e6f5ea;--bad:#991b1b;--badbg:#fdecec;--warn:#7a5b00;--warnbg:#fff6dc;--chip:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--ink:#e8eaee;--muted:#9aa3b2;--line:#272c37;
--ok:#7ddc9b;--okbg:#10291a;--bad:#ff9b9b;--badbg:#341415;--warn:#f1d27a;--warnbg:#2f2610;--chip:#222732}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 Cairo,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
header{position:sticky;top:0;z-index:2000;background:var(--card);border-bottom:1px solid var(--line)}
.bar{max-width:1000px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.1rem;color:var(--ink);text-decoration:none}
.logo{width:30px;height:30px;border-radius:8px;background:var(--accent);color:#fff;display:grid;place-items:center;font-size:.9rem}
nav{display:flex;gap:4px;flex:1;flex-wrap:wrap}
nav a{padding:8px 11px;border-radius:999px;text-decoration:none;color:var(--muted);font-weight:600;font-size:.95rem}
nav a:hover{background:var(--chip)}
nav a.on{background:var(--accent);color:#fff}
.chip.dol{white-space:nowrap}.times{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}.times .chip{font-variant-numeric:tabular-nums}
.stops{list-style:none;margin:8px 0 0;padding:0;border-left:3px solid var(--line)}.stops li{padding:6px 10px;border-bottom:1px solid var(--line);font-size:.92rem}
.stops li.hasbus{background:var(--okbg)}.stops a{text-decoration:none}
.pill{padding:5px 11px;border-radius:999px;font-size:.82rem;font-weight:600;white-space:nowrap}
.pill.ok{background:var(--okbg);color:var(--ok)}.pill.bad{background:var(--badbg);color:var(--bad)}
main{max-width:1000px;margin:0 auto;padding:18px 16px 60px}
h1{font-size:1.35rem;margin:6px 0 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.form{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;align-items:end}
.form.two{grid-template-columns:1fr 1fr auto}
.field label{display:block;font-size:.82rem;font-weight:600;color:var(--muted);margin-bottom:5px}
input{width:100%;padding:12px 13px;font-size:1rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
.btn{padding:13px 22px;font-size:1rem;font-weight:700;border:0;border-radius:10px;background:var(--accent);color:#fff;cursor:pointer}
.btn:hover{background:var(--accent2)}
.adv{grid-column:1/-1;font-size:.9rem;color:var(--muted)}.adv .field{max-width:180px;margin-top:8px}
.form .btn{grid-column:1/-1}
@media(min-width:760px){.form .btn{grid-column:auto}.form{grid-template-columns:2fr 1fr 1fr auto}.adv{grid-column:1/-1}}
@media(max-width:620px){.form,.form.two{grid-template-columns:1fr 1fr}.form .field.grow{grid-column:1/-1}}
.vtabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}.vtabs button{padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;font-size:.82rem;cursor:pointer}.vtabs button.on{background:var(--brand,#c8102e);border-color:var(--brand,#c8102e);color:#fff}
.vhead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.plate{font-weight:800;font-size:1.25rem;letter-spacing:.5px;border:2px solid var(--ink);border-radius:8px;padding:2px 10px}
.chip{background:var(--chip);border-radius:999px;padding:3px 11px;font-size:.88rem;font-weight:600}
.muted{color:var(--muted)}
.badge{display:inline-block;background:var(--accent);color:#fff;border-radius:7px;padding:1px 9px;font-size:.8rem;font-weight:700;margin-right:6px}
details.trip{border:1px solid var(--line);border-radius:12px;margin:10px 0;background:var(--card)}
details.trip>summary{cursor:pointer;padding:11px 14px;list-style:none;display:flex;gap:6px 10px;flex-wrap:wrap;align-items:center}
details.trip>summary::-webkit-details-marker{display:none}
details.trip>summary::before{content:"▸";color:var(--muted)}details.trip[open]>summary::before{content:"▾"}
.time{margin-left:auto;font-weight:700;font-variant-numeric:tabular-nums}
.tbody{padding:0 14px 12px}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th{position:sticky;top:0;background:var(--card);text-align:left;font-size:.78rem;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);padding:7px 8px;border-bottom:1px solid var(--line)}
td{padding:6px 8px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
.scroll{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.note{padding:10px 14px;border-radius:10px;margin-bottom:12px;font-size:.92rem}
.note.warn{background:var(--warnbg);color:var(--warn)}.note.info{background:var(--chip)}
.empty{text-align:center;color:var(--muted);padding:28px}
.hatrow{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.hatrow a{background:#050505;color:#ffb000;font-family:'Pixelify Sans',Cairo,monospace;font-weight:600;letter-spacing:1px;border:2px solid #1d1d1d;text-shadow:0 0 5px rgba(255,176,0,.7);text-decoration:none;border-radius:999px;padding:4px 11px;font-size:.88rem}
.hatrow a:hover{background:#1a1204;color:#ffd060}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kv div{background:var(--chip);border-radius:12px;padding:12px 14px}
.kv b{display:block;font-size:1.25rem}.kv span{font-size:.82rem;color:var(--muted)}
footer{max-width:1000px;margin:0 auto;padding:0 16px 30px;color:var(--muted);font-size:.8rem}

nav a i{font-style:normal}
@media (max-width:760px){
 body{padding-bottom:calc(72px + env(safe-area-inset-bottom));-webkit-tap-highlight-color:transparent}
 header{background:var(--accent);border:0;padding-top:env(safe-area-inset-top)}
 .bar{padding:12px 16px;gap:8px;flex-wrap:nowrap}
 .brand{color:#fff;font-size:1.05rem}.logo{background:#fff;color:var(--accent)}
 .pill{margin-left:auto;font-size:.75rem}
 nav{position:fixed;left:0;right:0;bottom:0;z-index:20;background:var(--card);border-top:1px solid var(--line);
  padding:6px 4px calc(6px + env(safe-area-inset-bottom));gap:0;flex-wrap:nowrap;justify-content:space-around;box-shadow:0 -4px 16px rgba(0,0,0,.08)}
 nav a{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 2px;border-radius:14px;font-size:.66rem;font-weight:600;min-width:0}
 nav a i{font-size:1.25rem;line-height:1}
 nav a span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
 nav a.on{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent)}
 main{padding:14px 12px 24px}
 h1{font-size:1.2rem}
 .card{border-radius:20px;padding:14px 14px}
 input,.btn{min-height:48px;border-radius:14px}
 .btn{width:100%}
 footer{padding-bottom:20px}
}
@media (min-width:761px){nav a i{display:none}}
@media (display-mode:standalone){footer{display:none}}
@media (min-width:761px){.bar{max-width:1180px;row-gap:6px}.pill{margin-left:auto;max-width:300px;overflow:hidden;text-overflow:ellipsis}nav{order:3;flex:1 0 100%;flex-wrap:nowrap;gap:2px;border-top:1px solid var(--line);padding-top:6px;margin:0 -4px}nav a{white-space:nowrap;padding:7px 14px;font-size:.92rem}}
@media (max-width:760px){nav a.desk{display:none}.brand{white-space:nowrap;flex-shrink:0}.pill{min-width:0;overflow:hidden;text-overflow:ellipsis}}
.citychip{display:inline-flex;align-items:center;gap:4px;padding:5px 11px;border-radius:999px;background:var(--chip);color:var(--ink);
 font-size:.82rem;font-weight:700;text-decoration:none;white-space:nowrap}
@media (max-width:760px){.citychip{background:rgba(255,255,255,.22);color:#fff}}
.cities{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:6px}
.city{display:block;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:20px;padding:20px 20px 18px;
 box-shadow:0 1px 2px rgba(0,0,0,.04)}
a.city:hover{border-color:var(--accent);box-shadow:0 4px 18px rgba(200,16,46,.15)}
.city h2{margin:0 0 2px;font-size:1.35rem}.city .kurum{color:var(--muted);font-size:.9rem;margin-bottom:12px}
.city .stat{font-size:.88rem;color:var(--muted)}.city .stat b{color:var(--ink)}
.city.off{opacity:.62}
.tag{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.75rem;font-weight:700;margin-bottom:10px}
.tag.on{background:var(--okbg);color:var(--ok)}.tag.soon{background:var(--warnbg);color:var(--warn)}
.hero{text-align:center;margin:18px 0 8px}.hero h1{font-size:1.5rem;margin-bottom:6px}
.dnav{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:-4px 0 14px}
.dnav a,.csvbtn{background:var(--chip);color:var(--ink);text-decoration:none;border-radius:999px;padding:6px 13px;font-size:.88rem;font-weight:600}
.dnav a:hover,.csvbtn:hover{background:var(--accent);color:#fff}
.csvbtn{display:inline-block;margin-left:auto}
.vmap{isolation:isolate;height:300px;border-radius:14px;border:1px solid var(--line);margin:2px 0 4px}
.vmapwrap{margin:4px 0 12px}.vnow:empty{display:none}.vlive{width:auto!important;min-height:0!important}
.bar2{height:8px;border-radius:99px;background:var(--chip);overflow:hidden;min-width:70px}
.bar2 i{display:block;height:100%;background:var(--accent);border-radius:99px}
.fgrid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:10px;align-items:end}
@media(max-width:760px){.fgrid{grid-template-columns:1fr 1fr}.fgrid .field.grow{grid-column:1/-1}}
select{width:100%;padding:12px 13px;font-size:1rem;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)}

/* ===== Radar teması (Flightradar tarzı): koyu, harita öncelikli ===== */
:root{--bg:#0a111c;--card:#121c2c;--ink:#e8edf5;--muted:#8d9bb2;--line:#22304a;--accent:#ffb400;--accent2:#e6a200;--onacc:#16120a;
--ok:#5ee08a;--okbg:#10301e;--bad:#ff9b9b;--badbg:#341418;--warn:#f1d27a;--warnbg:#2f2610;--chip:#1a2740;--hh:56px;--rail:78px;--bar:#0c1424;--pill:var(--pill)}
@media (prefers-color-scheme:light){:root{--bg:#0a111c;--card:#121c2c;--ink:#e8edf5;--muted:#8d9bb2;--line:#22304a;--chip:#1a2740}}
body{color-scheme:dark}
html[data-mode="day"]{--bg:#eef1f5;--card:#fff;--ink:#1b2430;--muted:#657285;--line:#d8dee7;--chip:#e7ebf1;--bar:#fff;--pill:rgba(255,255,255,.95);--ok:#166534;--okbg:#e3f4e8;--bad:#991b1b;--badbg:#fdecec;--warn:#7a5b00;--warnbg:#fff3d0}
html[data-mode="day"] body{color-scheme:light}
.leaflet-container{background:var(--bg)}
.sun{display:inline-flex;align-items:center;gap:6px;height:38px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:var(--chip);color:var(--ink);font:600 .8rem Cairo,sans-serif;cursor:pointer;white-space:nowrap}
.sun b{font-variant-numeric:tabular-nums}
@media(max-width:760px){.sun .st{display:none}}
button,input,select,textarea{font-family:inherit}
header{background:var(--bar);border-bottom:1px solid var(--line);height:var(--hh)}
.bar{max-width:none;height:var(--hh);padding:0 14px;gap:12px;flex-wrap:nowrap}
.brand{font-size:1rem;white-space:nowrap}
.logo{background:var(--accent);color:var(--onacc);border-radius:9px}
.hsearch{flex:1;max-width:560px;position:relative;margin:0}
.hsearch input{height:38px;padding:0 14px 0 36px;border-radius:999px;background:var(--bg);border:1px solid var(--line);font-size:.95rem}
.hsearch:before{content:"🔍";position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:.85rem;opacity:.7;pointer-events:none}
.hsearch input:focus{outline:2px solid var(--accent);outline-offset:0}
.citychip{background:var(--chip);color:var(--ink)}
.pill{margin-left:auto}
.btn,nav a.on,.badge{color:var(--onacc)}
.btn{background:var(--accent)}.btn:hover{background:var(--accent2)}
.vtabs button.on,.fr-tabs button.on{background:var(--accent)!important;border-color:var(--accent)!important;color:var(--onacc)!important}
.dnav a:hover,.csvbtn:hover{background:var(--accent);color:var(--onacc)}
a{color:var(--accent)}
.card{box-shadow:none;border-radius:14px}
a.city:hover{box-shadow:0 4px 18px rgba(255,180,0,.15)}
.fr-plate{border-color:var(--accent);color:var(--accent)}
.fr-arrow div{color:var(--accent)!important;text-shadow:0 0 3px #000!important}
html:not([data-mode="day"]) .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.82) contrast(.92) saturate(.55)}
@media (min-width:761px){
 nav{position:fixed;left:0;top:var(--hh);bottom:0;width:var(--rail);z-index:1900;flex:none;order:0;flex-direction:column;flex-wrap:nowrap;gap:2px;margin:0;padding:10px 6px;
  background:var(--bar);border-top:0;border-right:1px solid var(--line);overflow:auto}
 nav a i{display:block;font-size:1.3rem;line-height:1}
 nav a{display:flex;flex-direction:column;align-items:center;gap:3px;padding:9px 2px;border-radius:12px;font-size:.66rem;white-space:normal;text-align:center}
 nav a.on{background:var(--accent)}
 main{margin-left:var(--rail);max-width:1100px}
 footer{margin-left:var(--rail)}
}
@media (max-width:760px){
 header{background:var(--bar);padding-top:env(safe-area-inset-top);height:auto}
 .bar{height:var(--hh);padding:0 10px;gap:8px}
 .brand{font-size:0}.logo{font-size:.9rem}
 .brand{color:var(--ink)}
 .hsearch{max-width:none}
 .citychip{background:var(--chip);color:var(--ink)}
 header .pill{display:none}
 nav{background:var(--bar);border-top:1px solid var(--line)}
 nav a.on{background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
}
/* tam ekran harita modu */
body.mapmode main{max-width:none;margin:0;padding:0}
body.mapmode footer{display:none}
body.mapmode #frwrap{position:fixed;top:var(--hh);left:var(--rail);right:0;bottom:0;z-index:10}
@media (max-width:760px){body.mapmode #frwrap{left:0;bottom:calc(62px + env(safe-area-inset-bottom));top:calc(var(--hh) + env(safe-area-inset-top))}}
body.mapmode #frwrap .fmap{position:absolute;inset:0}
body.mapmode #frwrap #map{position:absolute;inset:0;height:100%!important;min-height:0!important;border:0!important;border-radius:0!important}
.fr-filters{position:absolute;top:12px;left:12px;z-index:1400;max-width:calc(100% - 24px)}
.fr-filters>button{padding:8px 14px;border-radius:999px;border:1px solid var(--line);background:var(--pill);color:var(--ink);font:inherit;font-size:.88rem;font-weight:600;cursor:pointer;backdrop-filter:blur(6px)}
.fr-filters .fbox{display:none;margin-top:8px;padding:12px;width:290px;max-width:100%;background:var(--pill);border:1px solid var(--line);border-radius:14px;backdrop-filter:blur(8px);gap:10px;flex-direction:column}
.fr-filters.open .fbox{display:flex}
.fr-filters .fbox input[type=text],.fr-filters .fbox input:not([type]),.fr-filters .fbox input[type=number],.fr-filters .fbox select{height:38px;padding:0 10px}
.fr-count{position:absolute;left:12px;bottom:12px;z-index:1400;padding:7px 13px;border-radius:999px;background:var(--pill);border:1px solid var(--line);font-size:.82rem;color:var(--muted);max-width:calc(100% - 24px)}
.fr-count b{color:var(--accent)}
.fr-dock{position:absolute;left:50%;transform:translateX(-50%);bottom:14px;z-index:1400;display:none;gap:2px;background:#1b2432;border-radius:18px;padding:6px;box-shadow:0 8px 30px rgba(0,0,0,.4)}
.fr-dock button,.fr-dock a{display:grid;justify-items:center;gap:2px;border:0;background:none;color:#fff;font:600 .7rem Cairo,sans-serif;padding:7px 18px;border-radius:12px;cursor:pointer;text-decoration:none}
.fr-dock button:hover,.fr-dock a:hover{background:rgba(255,255,255,.12)}.fr-dock .di{font-size:1.15rem;line-height:1}
@media(min-width:761px){.fr-dock{display:flex}.fr-filters>button{display:none}body.mapmode .fr-count{bottom:14px}}
.bz{position:relative;width:30px;height:30px;display:grid;place-items:center}
.bz svg{display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.75));transition:transform .3s}
.bz .bb{fill:var(--accent);stroke:#0a111c;stroke-width:1.4}.bz .bw{fill:#0a111c;opacity:.78}
.bz.off .bb{fill:#5b6b85}.bz.off .bw{opacity:.5}
.bz.sel .bb{fill:#fff;stroke:var(--accent);stroke-width:2.4}.bz.sel{filter:drop-shadow(0 0 6px var(--accent))}
.bl{position:absolute;top:100%;left:50%;transform:translate(-50%,-4px);background:var(--accent);color:var(--onacc);font:800 10px/14px Cairo,sans-serif;padding:0 5px;border-radius:7px;border:1.5px solid #0a111c;white-space:nowrap}
.bz.off .bl{background:#5b6b85;color:#e6ecf5}
body.mapmode #frwrap #panel{top:12px;right:12px;bottom:12px;background:var(--pill);backdrop-filter:blur(8px)}
@media(max-width:700px){body.mapmode #panel{top:auto;left:8px;right:8px;bottom:8px;max-height:56%}.fr-count{bottom:auto;top:56px;left:12px}.fr-filters{top:12px}}
body.mapmode .fr-count{left:auto;right:12px;bottom:12px}
body.mapmode #panel[style*="flex"]~.fr-count{display:none}
body.mapmode .leaflet-control-zoom{margin-top:60px}
"""

ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" rx="20" fill="#c8102e"/>'
    '<rect x="18" y="24" width="60" height="38" rx="8" fill="#fff"/><rect x="24" y="30" width="48" height="14" rx="3" fill="#c8102e"/>'
    '<circle cx="34" cy="68" r="6" fill="#fff"/><circle cx="62" cy="68" r="6" fill="#fff"/></svg>'
)

ICON_PNG = {'192': 'iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAYAAABS3GwHAAADgUlEQVR42u3dwXHbShBF0cEUAqASoZbOf0ctHYlDoBNQqSgRInr6nZOAP4C+06As82+3y3Wc7D5It531B+8GngLuZwWxG3qKB7GtHIDB56gZ2lYKwOCzRAi7wSc5hN3gkxzCNPw0+wnSSwMw/CwdwW7wSX4lmoaf5G0wDT/JEUzDT3IE0/CTHMF0j0g2nf4kb4Fp+EmOYBp+kiPwGQCfAZz+pG4BGwAbwOlP6hawAbABnP6kbgEbABvA6U/qFrABsAEgPQCvP0S+BtkA2AAgAAgNwPs/NgAIAAQAAgABgABAACAAEAAIAAQAAgABgABAALCWvcNF/Pn315M8ycfb+9L//dvtcr0belJjWC4Agy+E2M8Aht9zitwABt82iN0Aht828AoEiQE4/W2B2AAMvwi8AkFiAE5/W8AGgOF3gUba76Y4ycM3wDM31/DXP2SqxTM9FJLv9/QwSL7v00Mg+f77KRDD3wOAAEAAIAAQAAgABAACAAGAAEAAIAAQAAgABAACAAGAAEAAIIDhS5qGL8kSgIdg+AXgYbjfAvBQ3Ofhy3E9HGwAEAAIAAQAAgABgABAACAAEAAIAAQAAgABgABAACAAEAAIAAQAAgABwAoBfLy9eyqNVXu+NgA2AAjAmiTwudoA2ABOC1Kf53TTSH6OXoHwCuT0IPX5bbfL9T589z+hB9d0U0l+TkttANvA4AtADIZeAK8PZ8UH3f36BHDCxlhhULpfn78HOPF1qfrrVvfrE0CBh1t1SLpfnwAKPdRqQ9L9+gQAAqh1mlU5JbtfnwBAADVPsbNPye7XJwAQAAgABAACAAGAAMbZv9149m9Pdr8+AYAAap5iVU7H7tcnABBArdOs2unY/foEUOihVh2O7tcngAIPt/pwdL++4R/FD9+a4PoE8KpB6TAY3a9PAOAzAAgABAACAAGAAEAAIAAQAAgABABzjLG5DdgAIAAQAMQF4HMAiTYbABsABOA1iLDXHxsAG+CzKiDh9LcBsAG+qgM6n/42ADbAI5VAx9PfBsAG+E4t0On0f2QDiIC2w//oK5AIaDn8PgPgM8ARFcGKp/93N4AIaDX8P3kFEgFthv+nnwFEQIvhH2OM/ck/xP9eiSUH/6ifAtkGLDv8R/0YVAQsOfzPvAJ5JWLpwT86ACGw1OD/VgBCYInB/+0AhEDpwX9VAJ9dhBgo84OV/4Ks9MgKBNNaAAAAAElFTkSuQmCC', '512': 'iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAYAAAD0eNT6AAALaklEQVR42u3csXHbQBCG0cXOFUA2QobsPyNDVsIS4EyBx5qxPRJ1uP+9CgQQuPuwgL3dT5firXanAOBTm1PwHsMpsMkDHGT9FAcCwGYPYL0VBQLAhg9gTRYEAsCmD2C9FgMCwIYPYC0XBALAxg8QvsYLAQFg0wfwmkAA2PgBMBUQADZ+AISAALDpA+D1gACw8QNgKnBcbfMHgLz9ZPihACBvGjBs/ACQFwLDxg8AeSHQNn8AyNuHhhMOAHnTgLb5A0De/tROLgDk7VPDCQWAvFcCbfMHgLz9q508AMjbx4YTBgB5rwTa5g8AeftbOzkAkLfPtZMCAHn7XTsZAJC377WTAAB5+1/b/AEgbx9smz8A5EVA2/wBIC8C2uYPAHkR0DZ/AMiLgLb5A0BeBLTNHwDyIqBt/gCQFwFt8weAvAho5xYA8rSnfwDImwK0zR8A8iKgbf4AkBcBvgEAgPINgKd/AAiYArTNHwDyIqBt/gCQFwG+AQCA8g2Ap38ACJgCtM0fAPIiwCsAACivADz9A0DAFMAEAABMADz9A0DCFMAEAABMADz9A0DCFKBt/gCQFwFeAQBAeQXg6R8AAqYAJgAAYAIAAAiAMv4HgFrwNYAJAACYAHj6B4CEKYAJAACYAHj6B4CEKYAJAACYAAAA6QFg/A8AteZrABMAADAB8PQPAAlTABMAADABAAAEAAAQEwDe/wNArf0dgAkAAJgAAACJAWD8DwC1/msAEwAAMAEAAAQAALB8AHj/DwCV8R2ACQAAeAUAAAgAAEAAAABrBYAPAAEgx24CAABeAQAAAgAAEAAAgAAAAAQAAHCkAPBPAAHABAAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAACAAHAKAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAIAAAAAyDKeA391eTycBFvQ4X50EPmz302V3Gmz2gChAAGDTB8QAAgCbPiAGEADY+AEhgADAxg8IAco/A+TnN36bP+ChAgHgBgXwgIEAsPkDWG/wDYAbEaB8G2ACgM0fwDokAHDTAViPBABuNgDrkgDATQZgfRIAuLkA65R1SgDgpgKsVwgA3EyAdQsBAAAIAFQ0YP1CAODmAaxjCAA3DQAIAAA80CAA3CwA1jUEAAAgAFQygPUNAQAACAB1DGCdEwAAgAAAAAQAZSwGYL0TAACAAAAADmS7ny6701DGYf/gcb760cBaYi05uOEU4EaF9e5T79kRANj4IfjeFQKUbwCw+YP7GEwAsGCAaQAmAJSPdmz+IO59tCgAAAABgKcDwH2OAMCiALjfEQAAgADA0wDgvkcAAAACAAAQAJQxIOD+RwAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAIAABAAAIAAAAAEAAAgAAAAAQAACADmdHs9nQRw/yMAAAABAAAIAMoYEHDfIwAAAAGApwHA/Y4AwKIAuM8RAACAAMDTAeD+5ucMp4DPFonH+epkgI0fEwAsGoD7GBMATAMAGz8CgJzFRAyATR8BgEUGgPINAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEwHIe56uTAFj/EAAAgAAAAAQAACAAAAABUD6EAbDuIQAAAAEAAAiAMg4DsN4JAABAAACAp38BgBsDAAEAAAgATAEArG8CAAAQAKhkwLpmXRMAuFkA6xkCAAAQAKhmwDqGAMDNA1i/EAAA2PwRAG4kABAAIgDAeoUAcFMBWKcQAG4uAOsTAsBNBmBdEgC42QCsRwIANx3A36xB1iEBgBsQ8ACCAMDNCFhvmNl2P112p2Ett9fTSQBs/JgAuEkBrCuYAJgGANj4BYAAEAIANn0BgBgAbPwIAMQAYNNHACAKAJs9AgBWCRILo2vKNYUAgOBJhEXbNeWaQgBA8CsIi7ZryjVF+Y+AIO/7A99BuKZcU5gAQPji6MnNNeWawgQAAp+MPLm5plxTCAAIXQgt2K4p1xQCAEIXQAu238g1hQCA0IXPgu238XcjACB0wbNg+038/QgACF3oLNh+C8eBAIDQBc6C7TdwPAgAAEAAQMqTjSc2595xIQAgdEGzYDvnjg8BAAAIAEh5kvHE5lw7TgQAACAA8KTmeHGOHS8CAAAQAACAAKCMLh03zq3jRgAAAAIAABAAAIAAoLyzdPzOqeMHAQAACAAAQAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAkeJyvjh/n1PEjAAAAAQAACAAAQABQ3lk6bpxbx40AAAAEAAAgACijS8frHDteEAAAgADAE4zjdK4dJwgAAEAA4EnG8Tnnjg8BABY0x+XcOy4EAAAgAMCTjSc1v4HjQQBA+gJnofZbOA4EAIQtdBZqv4m/HwEAYQuehdpv4+9GAEDYwmeh9hu5phAAELYAWqhdU64pBACELYQWateUa4oVbffTZXcamMXt9bRI45oCEwA8uVmocU2BCQCe3CzSuKZAAGDRtkjjmgIBgIXbAo1rCgQAFm+LM64pEAAAQPlXAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAABMGwCb0wAAJgAAgAAAAAQAACAAAAABAAAIAABg5gDwTwEBIMdmAgAAXgEAAAIAABAAAMB6AeBDQABY32YCAAAmAACAAAAAYgLAdwAAUGu//zcBAAATAAAgOQC8BgCAWnf8bwIAACYAAIAAAADiAsB3AABQa77/NwEAABMAUwAASHj6NwEAABMAAEAAlNcAAFALjv9NAADABMAUAAASnv5NAADABMAUAAASnv5NAADABAAAEADlNQAA1ILjfxMAADABMAUAgISn//+dAIgAADjw5u8VAACUVwCmAAAQ8PRvAgAAJgCmAACQ8PRvAgAAJgCmAACQ8PT/VRMAEQAAB9r8vQIAgPIKwBQAAAKe/r96AiACAOAAm/93vAIQAQAw+ebvGwAAKN8AmAIAQMDT/3dOAEQAAEy8r/aR/lgAsPn7BgAAmDQATAEAYMJ9tI/8xwOAzX/uVwAiAAAm2jd7pYMBAJv/nB8BigAAmGCf7JUPDgBs/nP9M0ARAAA/uC920sECgM1/jv8ISAQAYPMPDAARAIDNPzQARAAANv/QABABANj8QwNABABg8w8NABEAgM3/DcbkJ2l3vQBg48+YAJgGAGDzDw8AEQCAzb9yXgF4JQCAjT98AmAaAIB9KjwARAAA9qfKeQXglQAANv7wCYBpAAD2odAJgGkAADb+8AAQAgDY+IMDQAgAYOOvjG8AfB8AgP3EBMA0AAAbvwD4848oBgCInx6P4B9XCAAQ+9p4+LGFAIC9IM/w23s9AGDTFwAuCiEAYOMXAC4SQQBgwxcALiIxAGDTFwAuLkEAYMMXAC4+UQBgsz+IXxwxe9rZ8i7GAAAAAElFTkSuQmCC', 'm512': 'iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAYAAAD0eNT6AAAI4ElEQVR42u3dwXGDMBRF0UeGAqARWNL/DpZUQgmkAi8yGdtC/5wKImRJF8WZDPu03AEASvnxCABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAACACPAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAABAAAAAAgAAEAAAQHdGj4Cn2K7TQ+ARjnn1EGjesE/L7THgsAdRgAAAhz6IAQQAOPRBDCAAwMEPQgABAA5+EALEnwHCq4Pf4Q8iGQGADQ0QzAgAHP6A9UN8BwAbFxDfDcANAA5/sK5AAGCTAusLBAA2J7DOQABgUwLrDQQANiOw7kAAYBMC6w8EADYfsA4RAACAAABvHWA9IgDAZgPWJQIAmwwAAgAAgY4AwOYCWKcIAAAg/h0w3iriX6JirVgrfM/oERD/Bx3e8nl1HY8bALzROPixhqwh4jsAYOPC5xniVwBgo6TIZ9uvBXADQFxdOvwRuf4kEAEAAAgAvBWBzzsIANLv9b/NEBHg1wAIAABAAOAtCHz+QQAAAAIAABAA5FlfHHL9CZ9ZB74IiAAAAAQAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAcDTbdfpIWAdWAcIAABAAAAAAoC4/gSffxAAAIAAwFsQ+NyDAMBmCD7vIAAAAAGAtyLwOae60SOgxc3xmFcPAwc/uAHAZgk+z+AGALcB4OAHAUCdTVQM4NAHAYDNFYD4DgAAIAAAAAEAAAgAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgADg/4559RDAekYAAAACAAAQAACAAAAABADxxSHAOkYAAAACAAAQAMT1IWD9IgAAAAEAgLd/BAA2EgAEAAAgAHALANYrCAAAQADgrQKsUwQA2FzA+kQAAAACALxlgHWJAACbDViPCAAAHP4IAGw8AAgARABg/SEAsAkB1h0CAJsRYL0hALApAdYZAgCbE2B9IQCwSUHVNWVdIQCwYYGgBgGAzQusH/i7YZ+W22PgE7br9BDAwY8bAGxqgHWCGwDcBoCDHwQAQgAc+iAAEAPg4AcBgBgAhz4IAEQBOOxBACAMHBDm0BxC/BkgDg4/t2fh5wYBgIPDz+8Z+PkRAB4BNl7jMHbjQACADdd4jNkcIgAAAAEA3rSMy1jdAiAAwAZrfMYoAhAAAIAAAG9WxmkOQQAAAAIAvFHVGa85BAEAAAgAAEAAQFyl9jZucwgCAAAQAACAAAAABABU/x1qD+M3h74HgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAaNoxr8ZvDMYPAgAAEAAAgAAAAAQA8TtU4zYW4wYBAAAIAAAQABBXqcZrTMaLAAAABAB4ozJOYzNOBAAAIADAm5XxGaO3fwQA2GCNyxyCAAAABAB40/LmaA5BAED1DbfywWEOQQBAyY3XwWEOQQBAsQ3YwWEOQQBAsY3YwWEOQQBAsQ3ZwWEOQQBAsY3ZwWEOoSXDPi23x0Bvtut0aJhDcwhuAPAm6eAwh+YQ3ADgTdKhYQ7NIQJAAOAQcWiYQ3OIAAAHiQPDHIIAAIeJw8IcggAAAOKvAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAAASARwAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAAAQAACAAAAABAAAIAAAQAB4BAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAAAAAQAACAAAQAAAAAIAABAAAIAAAAAEAAAgAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAAAAAgAAEAAAgAAAAAQAACAAAAABAAAIAABAAACAAAAABAAAIAAAAAEAAAgAAEAAAAACAABozC8PP70YFcRqKQAAAABJRU5ErkJggg=='}

MANIFEST = {
    "name": "Filo Takip", "short_name": "Filo Takip", "start_url": "/", "display": "standalone",
    "background_color": "#f3f4f6", "theme_color": "#c8102e",
    "id": "/", "scope": "/", "lang": "tr", "orientation": "any",
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
              {"src": "/icon-m512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
              {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
}

TABS = [("/", "Harita", "🗺️"), ("/ara", "Sorgula", "🔍"), ("/gun", "Gün özeti", "📅"), ("/durak", "Durak", "🚏"), ("/hat", "Hat", "🚍"), ("/hatlar", "İlk hatlar", "📊"), ("/modeller", "Modeller", "🚌"), ("/raporlar", "Raporlar", "📄"), ("/durum", "Durum", "📶")]

DESK_ONLY = {"/raporlar", "/modeller", "/hatlar", "/eslesme"}  # dar ekranda alt çubuktan gizlenir (Durum sayfasından erişilir)

# Şehir kayıt defteri: yeni şehir eklemek için buraya satır ekle ve toplayıcı bağdaştırıcısını yaz.
CITIES = [
    {"id": "ankara", "ad": "Ankara", "kurum": "EGO Genel Müdürlüğü", "aktif": True, "renk": "#d7182a",
     "kisa": "EGO", "merkez": [39.93, 32.86, 11], "ornek": "09-524 · EGO-22-370 · 06 BT 3809", "kaynak": "EGO canlı servisleri",
     "durak_ornek": "Kızılay veya 10940", "hat_ornek": "481 veya 523-6", "gun_ornek": "590 · Kızılay · Batıkent",
     "durak_not": "EGO durak koordinatı yayınlamadığı için “ne kadar yakın” bilgisi, aracın tahmini varış süresi ve kaç durak kaldığı olarak gösterilir."},
    {"id": "istanbul", "ad": "İstanbul", "kurum": "İETT · İBB", "aktif": False, "renk": "#e2231a", "db": "IETT_DB",
     "kisa": "İETT", "merkez": [41.04, 29.0, 10], "ornek": "C-1234 · 34 TB 1234", "kaynak": "İBB açık veri servisleri",
     "yerles": [("Durak konumları araç verisinden tahmin edilir, EGO koordinat yayınlamaz.", "Durak konumları İBB'nin resmi verisinden gelir."),
                ("EGO canlı listesinde", "canlı listede"), ("EGO canlı servisi", "Canlı servis"), ("canlı · EGO", "canlı"),
                ("EGO doluluk bilgisi", "Doluluk bilgisi"), ("EGO canlı verisi", "Canlı veri"),
                ("EGO listesinde şu an yok", "Canlı listede şu an yok"), ("EGO cevap vermedi", "Servis cevap vermedi"),
                ("Saatler EGO “Hareket Saatleri” sayfasındandır.", "Saatler İBB planlanan sefer saatleri verisindendir."),
                ("EGO Filo Takip", "İETT Filo Takip"),
                ("09-524 · 590 · Lion", "C-1234 · 500T · Mercedes"), ('id="hat" placeholder="590"', 'id="hat" placeholder="500T"'),
                ("MAN Lion&#39;s Classic CNG", "Mercedes-Benz Citaro"), ('placeholder="09-524"', 'placeholder="C-1234"'),
                ("(ör. <b>09-524</b>)", "(ör. <b>C-1234</b>)"), ("ör. <b>09-524</b>", "ör. <b>C-1234</b>")],
     "durak_ornek": "Kadıköy veya 100123", "hat_ornek": "500T veya 15F", "gun_ornek": "500T · Tuzla · Cevizlibağ",
     "durak_not": "Duraklar İBB açık verisinden gelir. İstanbul için canlı yaklaşan araç bilgisi yoktur; geçen araçlar kendi kayıtlarımızdan gösterilir."},
    {"id": "izmir", "ad": "İzmir", "kurum": "ESHOT · İzmir Büyükşehir", "aktif": False, "renk": "#0b6bb8", "db": "IZMIR_DB",
     "kisa": "ESHOT", "merkez": [38.42, 27.14, 11], "ornek": "2212 · 11848", "kaynak": "İzmir Büyükşehir açık veri servisleri",
     "durak_ornek": "Bahribaba veya 10005", "hat_ornek": "446 veya 5", "gun_ornek": "446 · Üçkuyular · Narlıdere",
     "durak_not": "Duraklar İzmir Büyükşehir açık verisinden gelir. İzmir için canlı yaklaşan araç bilgisi gösterilmez; geçen araçlar kendi kayıtlarımızdan gelir."},
]
CITY_BY_ID = {c["id"]: c for c in CITIES}
CITY_BY_ID["izmir"]["yerles"] = [
    (a, b) for a, b in CITY_BY_ID["istanbul"]["yerles"]
] + [("Durak konumları İBB'nin resmi verisinden gelir.", "Durak konumları İzmir Büyükşehir'in resmi verisinden gelir."),
     ("İETT Filo Takip", "ESHOT Filo Takip"), ("C-1234 · 500T · Mercedes", "2212 · 446 · Mercedes"),
     ('id="hat" placeholder="500T"', 'id="hat" placeholder="446"'), ("Saatler İBB planlanan sefer saatleri verisindendir.", "Saatler İzmir Büyükşehir hareket saatleri verisindendir."),
     ("(ör. <b>C-1234</b>)", "(ör. <b>2212</b>)"), ("ör. <b>C-1234</b>", "ör. <b>2212</b>"), ('placeholder="C-1234"', 'placeholder="2212"')]
GUN_AD = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def csv_cell(v):
    """Excel formül enjeksiyonuna karşı: =, +, @ ile başlayan metni kesme işaretiyle koru."""
    t = "" if v is None else str(v)
    if t.startswith(("=", "+", "@", "\t", "\r")) or (t.startswith("-") and len(t) > 1 and not t[1:].replace(".", "", 1).isdigit()):
        return "'" + t
    return t


def csv_bytes(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        w.writerow([csv_cell(c) for c in r])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def natural_key(s):
    return [int(p) if i % 2 else p for i, p in enumerate(re.split(r"(\d+)", s))]


def make_handler(E):

    _here = os.path.dirname(os.path.abspath(__file__))
    CITY_DB = {"istanbul": os.environ.get("IETT_DB", os.path.join(_here, "iett_filo.db")),
               "izmir": os.environ.get("IZMIR_DB", os.path.join(_here, "izmir_filo.db"))}
    for _c, _p in CITY_DB.items():
        CITY_BY_ID[_c]["aktif"] = os.path.exists(_p) and not (_c == "izmir" and os.environ.get("IZMIR_GOSTER") == "0")

    def city_meta():
        return CITY_BY_ID.get(cur_city(), CITY_BY_ID["ankara"])

    def cur_city():
        return getattr(E.CITY_CTX, "city", "ankara")

    def live_rows(*a, **k):
        """EGO canlı API'si yalnız Ankara için; İstanbul'da canlı sorgu yok."""
        if cur_city() != "ankara":
            return None
        return E.api_rows(*a, **k)
    TZ = E.TZ
    _models = {"mt": None, "rules": []}

    def _db_models():
        try:
            conn = E.connect()
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                             "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)")
                conn.commit()
                return {r[0]: (r[1], r[2] or "", r[3] or "", r[4] or "")
                        for r in conn.execute("SELECT anahtar, marka_model, kaynak, url, durum FROM arac_bilgi")}
            finally:
                conn.close()
        except Exception:
            return {}

    def model_for(arac_no, plaka="", db=None):
        """(marka_model, durum). Önce elle/otomatik eklenen kayıtlar (tam eşleşme), sonra modeller.csv ön ekleri."""
        db = _db_models() if db is None else db
        for key in (E.norm(arac_no), E.norm(plaka)):
            if key and key in db:
                return db[key][0], db[key][3] or "kesin"
        return _csv_model(arac_no)

    def _csv_model(arac_no):
        path = os.path.join(E.HERE, "modeller.csv")
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return "", ""
        if _models["mt"] != mt:
            rules = []
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.lower().startswith("onek;"):
                        continue
                    parts = [p.strip() for p in line.split(";")]
                    if len(parts) >= 2 and parts[0]:
                        rules.append((parts[0].upper(), parts[1], parts[2] if len(parts) > 2 else ""))
            _models["rules"], _models["mt"] = rules, mt
        a = (arac_no or "").strip().upper()
        best = ("", "", -1)
        for onek, model, durum in _models["rules"]:
            if a.startswith(onek) and len(onek) > best[2]:
                best = (model, durum, len(onek))
        return best[0], best[1]

    def today():
        return datetime.now(TZ).date()

    def fmt(ts, with_date=False):
        return E.fmt_ts(ts, with_date)

    def maps(lat, lng, text="Konum"):
        if lat and lng:
            return f'<a href="https://maps.google.com/?q={lat},{lng}" target="_blank" rel="noopener">{esc(text)}</a>'
        return ""

    def note(text, kind="warn"):
        return f'<div class="note {kind}">{esc(text)}</div>'

    def progress_info():
        """Devam eden turun ilerlemesi (meta 'progress'); 10 dakikadan eskiyse yok sayılır."""
        try:
            conn = E.connect()
            row = conn.execute("SELECT v FROM meta WHERE k='progress'").fetchone()
            conn.close()
            pr = json.loads(row[0]) if row else None
        except Exception:  # noqa: BLE001
            return None
        if pr and pr.get("total") and E.now_ts() - pr["ts"] <= 600:
            pr["pct"] = min(100, int(100 * pr["n"] / pr["total"]))
            return pr
        return None

    def status_chip():
        try:
            conn = E.connect()
            row = conn.execute("SELECT v FROM meta WHERE k='last_cycle'").fetchone()
            conn.close()
        except Exception:
            return '<span class="pill bad">Veritabanı okunamadı</span>'
        pr = progress_info()
        if not row and pr:
            return f'<span class="pill ok" title="{pr["veh"]} araç">● İlk tarama sürüyor · %{pr["pct"]}</span>'
        if not row:
            return '<span class="pill bad">Toplayıcı henüz çalışmadı</span>'
        c = json.loads(row[0])
        age = (E.now_ts() - c["ts"]) / 60
        if age <= max(25, 2.5 * c.get("interval", 10)):
            return f'<span class="pill ok" title="{c["vehicles"]} araç, {c["fails"]} hata">● Toplayıcı çalışıyor · son tur {fmt(c["ts"])}</span>'
        return f'<span class="pill bad">● Toplayıcı durmuş olabilir · son tur {fmt(c["ts"], True)}</span>'

    SOFT_REFRESH = "<script>(function(){var P=document.querySelector('[data-live]');if(!P)return;var iv=(parseInt(P.getAttribute('data-live'),10)||30)*1000;\nfunction busy(){var a=document.activeElement;if(a&&/^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))return true;var f=document.querySelectorAll('main input,main select');for(var i=0;i<f.length;i++){if(f[i].type!=='hidden'&&f[i].value!==f[i].defaultValue)return true;}return false;}\nfunction tick(){if(document.hidden||busy())return;\nfetch(location.href,{credentials:'same-origin'}).then(function(r){return r.ok?r.text():null}).then(function(t){if(!t)return;\nvar d=new DOMParser().parseFromString(t,'text/html'),nm=d.querySelector('main'),m=document.querySelector('main');if(!nm||!m||busy())return;\nvar open=[].map.call(m.querySelectorAll('details'),function(x){return x.open;});\nvar om=m.querySelectorAll('.vmapwrap'),nn=nm.querySelectorAll('.vmapwrap');\nnn.forEach(function(n,i){if(om[i])n.parentNode.replaceChild(om[i],n);});\nnm.querySelectorAll('details').forEach(function(x,i){if(open[i]!==undefined)x.open=open[i];});\nvar y=window.scrollY;m.replaceWith(document.adoptNode(nm));window.scrollTo(0,y);\nvar op=document.querySelector('header .pill'),np=d.querySelector('header .pill');if(op&&np)op.replaceWith(document.adoptNode(np));\n}).catch(function(){});}\nsetInterval(tick,iv);document.addEventListener('visibilitychange',function(){if(!document.hidden)tick();});})();</script>"

    def localize(html_text):
        for a, b in city_meta().get("yerles", ()):
            html_text = html_text.replace(a, b)
        return html_text

    def brand_css():
        c = city_meta().get("renk", "#ffb400").lstrip("#")
        r, g_, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        lum = (0.299 * r + 0.587 * g_ + 0.114 * b) / 255
        dark = "#%02x%02x%02x" % (int(r * .85), int(g_ * .85), int(b * .85))
        return (":root{--accent:#%s;--accent2:%s;--onacc:%s}" % (c, dark, "#16120a" if lum > .62 else "#ffffff"))

    SUN_JS = "(function(){var D=document.documentElement,LA=__LA__,LO=__LO__;\nfunction st(){var d=new Date(),r=Math.PI/180,N=Math.floor((Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate())-Date.UTC(d.getUTCFullYear(),0,0))/864e5);\nvar g=2*Math.PI/365*(N-.5),eq=229.18*(.000075+.001868*Math.cos(g)-.032077*Math.sin(g)-.014615*Math.cos(2*g)-.040849*Math.sin(2*g));\nvar dc=.006918-.399912*Math.cos(g)+.070257*Math.sin(g)-.006758*Math.cos(2*g)+.000907*Math.sin(2*g)-.002697*Math.cos(3*g)+.00148*Math.sin(3*g);\nvar c=Math.cos(90.833*r)/(Math.cos(LA*r)*Math.cos(dc))-Math.tan(LA*r)*Math.tan(dc);if(c>1)return{rise:1e9,set:-1e9};if(c<-1)return{rise:-1e9,set:1e9};\nvar ha=Math.acos(c)/r;return{rise:720-4*(LO+ha)-eq+180,set:720-4*(LO-ha)-eq+180};}\nfunction hm(m){m=((Math.round(m)%1440)+1440)%1440;return('0'+Math.floor(m/60)).slice(-2)+':'+('0'+m%60).slice(-2);}\nfunction pref(){try{return localStorage.getItem('tema')||'auto';}catch(e){return 'auto';}}\nfunction apply(){var m=pref(),s=st(),n=new Date(),t=(n.getUTCHours()*60+n.getUTCMinutes()+180)%1440,day=m==='auto'?(t>=s.rise-20&&t<s.set+20):m==='day';\nD.setAttribute('data-mode',day?'day':'night');var i=document.getElementById('sunico');\nif(i){i.textContent=day?'☀':'☾';document.getElementById('suntx').innerHTML='<b>'+hm(s.rise)+'</b> ↑ <b>'+hm(s.set)+'</b> ↓';\ndocument.getElementById('sunbtn').title='Tema: '+({auto:'otomatik (güneşe göre)',day:'gündüz',night:'gece'})[m]+' — değiştirmek için tıkla';\ndocument.getElementById('sunm').textContent=({auto:'Oto',day:'Gün',night:'Gece'})[m];}}\nwindow.__temaDon=function(){var o=['auto','day','night'],m=o[(o.indexOf(pref())+1)%3];try{localStorage.setItem('tema',m);}catch(e){}apply();};\napply();document.addEventListener('DOMContentLoaded',function(){apply();var b=document.getElementById('sunbtn');if(b)b.onclick=window.__temaDon;});setInterval(apply,60000);})();"

    def layout(active, body, title="EGO Filo Takip", picker=False, mapmode=False):
        if picker:
            nav, chip, status = "", "", ""
        else:
            nav = "".join(
                f'<a href="{h}" class="{"on" if h == active else ""}{" desk" if h in DESK_ONLY else ""}"><i>{ic}</i><span>{esc(t)}</span></a>'
                for h, t, ic in (TABS + ([("/eslesme", "Eşleme", "🔗")] if cur_city() == "izmir" else [])))
            chip = '<a class="citychip" href="/sehir" title="Şehri değiştir">📍 %s ▾</a>' % esc(CITY_BY_ID[cur_city()]["ad"])
            status = status_chip()
        sunchip = '' if picker else ('<button class="sun" id="sunbtn" type="button"><span id="sunico">☾</span><span id="sunm"></span><span class="st" id="suntx"></span></button>')
        if picker:
            hs = ""
        elif mapmode:
            hs = ('<form class="hsearch" onsubmit="return false"><input id="q" placeholder="Filo kodu, plaka, hat ara…" '
                  'autocomplete="off" aria-label="Ara"></form>')
        else:
            hs = ('<form class="hsearch" method="get" action="/ara"><input name="q" placeholder="Filo kodu veya plaka ara…" '
                  'autocomplete="off" aria-label="Ara" required></form>')
        return localize(
            '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<meta name="theme-color" content="#c8102e"><meta name="mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-capable" content="yes"><link rel="manifest" href="/manifest.json">'
            '<link rel="icon" href="/icon.svg" type="image/svg+xml">'
            f"<title>{esc(title.replace('EGO Filo Takip', city_meta()['kisa'] + ' Filo Takip'))}</title>"
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Pixelify+Sans:wght@400;600&display=swap&subset=latin-ext">'
            "<script>" + SUN_JS.replace("__LA__", str(city_meta()["merkez"][0])).replace("__LO__", str(city_meta()["merkez"][1])) + "</script>"
            f"<style>{CSS}{brand_css()}</style></head><body{' class=\"mapmode\"' if mapmode else ''}>"
            '<header><div class="bar"><a class="brand" href="/"><span class="logo">🚌</span>Filo Takip</a>'
            f"{hs}{chip}{sunchip}<nav>{nav}</nav>{status}</div></header><main>{body}</main>"
            "<footer>Resmi olmayan, ticari amaç gütmeyen kişisel arşiv. Veri: " + city_meta()["kaynak"] + ". "
            "Durak saatleri gözlemler arası ara değerle tahmin edilir.</footer>" + SOFT_REFRESH + "</body></html>"
        )

    # ------------------------------------------------------------------ Araç sorgula
    def form_ara(q, tarih, saat, tol):
        return (
            '<form class="card form" method="get" action="/ara">'
            '<div class="field grow"><label>Filo kodu veya plaka</label>'
            f'<input name="q" value="{esc(q, True)}" placeholder="{esc(city_meta()["ornek"], True)}" required autofocus autocomplete="off"></div>'
            f'<div class="field"><label>Tarih</label><input type="date" name="tarih" value="{esc(tarih, True)}"></div>'
            f'<div class="field"><label>Saat (boşsa tüm gün)</label><input type="time" name="saat" value="{esc(saat, True)}"></div>'
            f'<details class="adv"><summary>Gelişmiş</summary><div class="field"><label>Tolerans (dk)</label>'
            f'<input type="number" name="tol" value="{esc(tol, True)}" min="5" max="180"></div></details>'
            '<button class="btn">Ara</button></form>'
        )

    def tip_for(arac_no, plaka=""):
        try:
            conn = E.connect()
            try:
                for key in (E.norm(plaka), E.norm(arac_no)):
                    if key:
                        r = conn.execute("SELECT tip FROM arac_tip WHERE anahtar=?", (key,)).fetchone()
                        if r:
                            return r[0]
            finally:
                conn.close()
        except Exception:
            pass
        return ""

    def model_chip(arac_no, plaka=""):
        m, d = model_for(arac_no, plaka)
        bt = tip_for(arac_no, plaka)
        if not m and not bt:
            return ""
        tip = "doğrulanmış" if d == "kesin" else "tahmini: filo kodu ön ekinden"
        out = ""
        if m:
            out = f'<span class="chip" title="{esc(tip, True)}">{esc(m)}{"" if d == "kesin" else " ~"}</span>'
        if bt:
            out += f' <span class="chip" title="EGO canlı verisi">{esc(bt)}</span>'
        return out

    def vehicle_status(plaka):
        conn = E.connect()
        try:
            r = conn.execute("SELECT hat, last_ts FROM stints WHERE plaka=? ORDER BY last_ts DESC LIMIT 1", (plaka,)).fetchone()
        finally:
            conn.close()
        if not r:
            return ""
        age = (E.now_ts() - r[1]) / 60
        if age <= 15:
            return f'<span class="pill ok">● Şu an hatta: {esc(r[0])}</span>'
        if age < 120:
            when = f"{round(age)} dk önce"
        elif age < 2880:
            when = f"{round(age / 60)} saat önce"
        else:
            when = f"{round(age / 1440)} gün önce"
        return (f'<span class="pill bad" title="EGO listesinde şu an yok (hatta değil, garajda ya da veri yok)">'
                f'● Listede yok · son: hat {esc(r[0])}, {fmt(r[1], True)} ({when})</span>')

    # ------------------------------------------------------------------ Araç haritası (sorgu sonucunda)
    VMAP_JS = """
(function(){
var cols=['#c8102e','#1d4ed8','#15803d','#b45309','#7c3aed','#0e7490'];
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]});}
function ago(e){var m=Math.max(0,Math.round((Date.now()/1000-e)/60));return m<120?m+' dk önce':'';}
document.querySelectorAll('.vmap').forEach(function(el){
 var g=JSON.parse(el.getAttribute('data-geo')),map=L.map(el,{preferCanvas:true});
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap'}).addTo(map);
 var all=[],last=null,lastHat=g.h||'';
 var nt=g.trips.length,groups=[],vlast=null,tabs=document.createElement('div');
 tabs.className='vtabs';
 g.trips.forEach(function(t,i){
  var c=cols[i%cols.length],ll=t.p.map(function(x){return [x[0],x[1]];}),grp=L.layerGroup();all=all.concat(ll);
  L.polyline(ll,{color:c,weight:4,opacity:.85}).addTo(grp).bindTooltip('Sefer '+(i+1)+' · Hat '+esc(t.h));
  t.p.forEach(function(x){L.circleMarker([x[0],x[1]],{radius:3,color:c,weight:1,fillColor:c,fillOpacity:.9}).addTo(grp).bindTooltip(esc(x[2])+' · Hat '+esc(t.h));});
  L.circleMarker(ll[0],{radius:6,color:'#fff',weight:2,fillColor:c,fillOpacity:1}).addTo(grp).bindTooltip('Sefer '+(i+1)+' başlangıç '+esc(t.p[0][2])+' · Hat '+esc(t.h));
  groups.push({g:grp,ll:ll});
  last=t.p[t.p.length-1];lastHat=t.h;
  if(nt>1){var b=document.createElement('button');b.type='button';b.textContent='Sefer '+(i+1)+' · '+esc(t.h);b.title=esc(t.p[0][2]);b.setAttribute('data-i',i);tabs.appendChild(b);}
 });
 var cur=-1;
 function show(i){
  groups.forEach(function(x,k){if(i===-1||k===i){x.g.addTo(map);}else{map.removeLayer(x.g);}});
  cur=i;
  var pts=[];(i===-1?groups:[groups[i]]).forEach(function(x){pts=pts.concat(x.ll);});
  if(vlast)pts.push(vlast);
  if(pts.length)map.fitBounds(pts,{padding:[34,34],maxZoom:16});
  [].forEach.call(tabs.children,function(b){b.className=(+b.getAttribute('data-i')===i||(i===-1&&b.getAttribute('data-i')==='all'))?'on':'';});
 }
 if(nt>1){
  var ball=document.createElement('button');ball.type='button';ball.textContent='Tümü';ball.setAttribute('data-i','all');tabs.appendChild(ball);
  el.parentNode.insertBefore(tabs,el);
  tabs.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;var v=b.getAttribute('data-i');show(v==='all'?-1:+v);});
  var card=el.closest('.card')||el.parentNode;
  card.querySelectorAll('details>summary').forEach(function(sm,k){sm.addEventListener('click',function(){if(k<nt){show(k);el.scrollIntoView({block:'nearest',behavior:'smooth'});}});});
 }
 var label='';
 if(last){label='Son konum '+last[2]+(g.bugun&&ago(last[3])?' ('+ago(last[3])+')':'');}
 else if(g.son){last=[g.son.la,g.son.lo,g.son.t,g.son.e];lastHat=g.son.h;all.push([g.son.la,g.son.lo]);label='Son bilinen konum '+g.son.t+' · Hat '+g.son.h;}
 if(!last){el.style.display='none';return;}
 var mk=L.circleMarker([last[0],last[1]],{radius:10,color:'#fff',weight:3,fillColor:'#c8102e',fillOpacity:1}).addTo(map);
 mk.bindTooltip(esc(label),{permanent:true,direction:'top',offset:[0,-8]});
 all.push([last[0],last[1]]);
 vlast=[last[0],last[1]];
 if(groups.length){show(nt-1);}else{map.fitBounds(all,{padding:[34,34],maxZoom:16});}
 var btn=el.parentNode.querySelector('.vlive'),now=el.parentNode.querySelector('.vnow'),st=el.parentNode.querySelector('.vlives');
 var DL={'az':'🟢 Az yoğun','orta':'🟡 Orta yoğun','çok':'🔴 Çok yoğun','dolu':'🔴 Dolu'};
 function dolTxt(d){for(var k in DL){if(d&&d.indexOf(k)===0)return DL[k];}return '';}
 function poll(manual){
  if(manual){btn.disabled=true;st.textContent=' alınıyor…';}
  return fetch('/api/canli?hat='+encodeURIComponent(lastHat)).then(function(r){return r.json()}).then(function(j){
   var n=(j.araclar||[]).filter(function(x){return (g.f&&x.f===g.f)||x.p.replace(/ /g,'')===g.p.replace(/ /g,'');})[0];
   if(manual)btn.disabled=false;
   if(!n){now.innerHTML='<span class="muted">Araç şu an EGO canlı listesinde yok (hat '+esc(lastHat)+').</span>';if(manual)st.textContent='';return;}
   lastHat=n.h||lastHat;
   var wasNear=map.getBounds().contains(mk.getLatLng());
   mk.setLatLng([n.la,n.lo]);mk.setTooltipContent('Anlık konum '+esc(n.t.slice(-5))+' ('+n.age+' dk önce)');
   if(manual||wasNear)map.panTo([n.la,n.lo]);
   var where=n.d?(n.a?'<b>'+esc(n.a)+'</b> → <b>'+esc(n.d)+'</b> arasında':'<b>'+esc(n.d)+'</b> durağına gidiyor'):'konum alındı';
   now.innerHTML='<div class="card" style="margin:0 0 8px"><b>Şimdi · Hat '+esc(n.h)+'</b> · '+where+' · '+esc(n.v||'0')+' km/sa'+(dolTxt(n.dl)?' · '+dolTxt(n.dl):'')+' <span class="muted">· '+esc(n.t.slice(-5))+' ('+n.age+' dk önce)</span></div>';
   if(manual)st.textContent=' güncellendi';
  }).catch(function(){if(manual){btn.disabled=false;st.textContent=' alınamadı';}});
 }
 if(btn&&g.bugun){btn.style.display='';btn.onclick=function(){poll(true);};
  poll(false);setInterval(function(){if(!document.hidden&&document.body.contains(el))poll(false);},20000);}
});
})();
"""

    def vehicle_map(v, bugun, window_items=None):
        """Araç kartı için harita kutusu; konum yoksa son bilinen konuma düşer, hiç yoksa boş döner."""
        trips = []
        if window_items is not None:
            for it in window_items:
                pos = it.get("pos")
                if pos and pos[1] and pos[2]:
                    trips.append({"h": it["hat"], "p": [[round(pos[1], 5), round(pos[2], 5), fmt(pos[0], False), pos[0]]]})
        else:
            for tr in v["trips"]:
                pts = [[round(x["lat"], 5), round(x["lng"], 5), fmt(x["t"], False), x["t"]]
                       for x in tr["samples"] if x["lat"] and x["lng"]]
                if pts:
                    trips.append({"h": tr["hat"], "p": pts})
        son = None
        if not trips:
            conn = E.connect()
            try:
                r = conn.execute("SELECT COALESCE(kts, ts), hat, lat, lng FROM sightings WHERE plaka=? AND lat IS NOT NULL "
                                 "AND lat<>0 ORDER BY ts DESC LIMIT 1", (v["plaka"],)).fetchone()
            finally:
                conn.close()
            if r:
                son = {"t": fmt(r[0], True), "e": r[0], "h": r[1], "la": round(r[2], 5), "lo": round(r[3], 5)}
        if not trips and not son:
            return ""
        geo = {"p": E.pretty_plate(v["plaka"]), "f": v.get("arac_no") or "", "trips": trips, "son": son, "bugun": bool(bugun)}
        big = urllib.parse.quote(v.get("arac_no") or E.pretty_plate(v["plaka"]))
        return (f'<div class="vmapwrap">' + ('<div class="vnow"></div>' if bugun else "") + f'<div class="vmap" data-geo="{esc(json.dumps(geo, ensure_ascii=False), True)}"></div>'
                f'<div class="dnav" style="margin:8px 0 0"><a href="/harita?q={big}">Büyük haritada aç</a>'
                + ('<button type="button" class="btn vlive" style="display:none;padding:6px 13px;font-size:.88rem">Anlık konumu al</button>'
                   '<span class="muted vlives"></span>' if bugun else "") + "</div></div>")

    def map_assets():
        return ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>'
                "<script>if(window.L){" + VMAP_JS + "}</script>")

    def render_day(res):
        out = [note(w) for w in res["warnings"]]
        if res["vehicles"] and res["kind"] == "yaklasik":
            out.append(note("Filo kodu yaklaşık eşleşti (birden fazla araç olabilir); kesin sonuç için plaka kullanın."))
        if not res["vehicles"]:
            out.append('<div class="card empty">Bu kodla eşleşen araç kayıtlarda yok.<br>Plaka ile deneyin ya da '
                       '<a href="/gun">Gün özeti</a> sayfasından aracı bulun.</div>')
            return "".join(out)
        for v in res["vehicles"]:
            trips = v["trips"]
            parts = [f'<div class="vhead"><span class="plate">{esc(E.pretty_plate(v["plaka"]))}</span>'
                     f'<span class="chip">Filo {esc(v["arac_no"] or "-")}</span>{eslesme_chip(v["plaka"])}'
                     f'{model_chip(v["arac_no"], v["plaka"])}'
                     f'<span class="muted">{len(trips)} sefer · {esc(res["day"].strftime("%d.%m.%Y"))}</span>'
                     f'{vehicle_status(v["plaka"])}</div>']
            parts.append(vehicle_map(v, res["day"] == today()))
            if not trips and not v["stints"]:
                parts.append('<p class="muted">Bu tarihte kayıt yok.</p>')
            for st in v["stints"]:
                parts.append(f'<p>Hat <b>{esc(st[0])}</b> · {fmt(st[1])} – {fmt(st[2])} '
                             f'<span class="muted">({st[3]} gözlem, durak ayrıntısı yok)</span></p>')
            for i, tr in enumerate(trips, 1):
                s0, s1 = tr["samples"][0], tr["samples"][-1]
                sira = f" · durak {s0['sira']} → {s1['sira']}" if s0["sira"] is not None and s1["sira"] is not None else ""
                summary = (f'<span class="badge">Sefer {i}</span><b>Hat {esc(tr["hat"])}</b>'
                           f'<span class="muted">{esc(tr["ad"])}</span>'
                           f'<span class="time" title="Aracın bu hatta ilk görüldüğü saat">▶ {fmt(s0["t"])}</span>')
                obs = []
                for s in ([s0, s1] if len(tr["samples"]) > 1 else [s0]):
                    if s["sira"] is not None:
                        a = tr["route"].get(s["sira"] - 1, ("", ""))[1] or "?"
                        b = tr["route"].get(s["sira"], ("", ""))[1] or "?"
                        obs.append(f'{fmt(s["t"])}: <b>{esc(a)}</b> → <b>{esc(b)}</b> arası')
                meta = (f'<p class="muted">{len(tr["samples"])} gözlem{sira}'
                        + (" · " + maps(s1["lat"], s1["lng"], "son konum") if s1["lat"] else "") + "</p>")
                obs_html = f'<p class="muted">Gözlem: {" · ".join(obs)}</p>' if obs else ""
                if tr["passages"]:
                    rows = "".join(
                        f'<tr><td>{p["sira"]}</td><td>{esc(p["durak"])}</td><td>{esc(p["ad"])}</td>'
                        f'<td><b>{"" if p.get("gercek") else "~"}{fmt(p["t"])}</b></td></tr>' for p in tr["passages"])
                    table = ('<div class="scroll"><table><thead><tr><th>#</th><th>Durak no</th><th>Durak</th>'
                             f'<th>Geçiş saati</th></tr></thead><tbody>{rows}</tbody></table></div>'
                             '<p class="muted" style="font-size:.8rem">Başında ~ olmayan saatler, aracın o durağı geçtiği tarama anında yakalanmıştır (en fazla ~1 dk sapma). '
                             '~ ile başlayanlar, tarama arasında kalan duraklar için ara değerle tahmin edilmiştir.</p>')
                else:
                    table = '<p class="muted">Durak geçişi tahmini için yeterli gözlem yok.</p>'
                open_attr = ""  # seferler kapalı gelir; kullanıcı kendisi açar
                parts.append(f'<details class="trip"{open_attr}><summary>{summary}</summary>'
                             f'<div class="tbody">{meta}{obs_html}{table}</div></details>')
            out.append('<div class="card">' + "".join(parts) + "</div>")
        return "".join(out)

    def render_window(res):
        out = [note(w) for w in res["warnings"]]
        if res["vehicles"] and res["kind"] == "yaklasik":
            out.append(note("Filo kodu yaklaşık eşleşti; kesin sonuç için plaka kullanın."))
        if not res["vehicles"]:
            return "".join(out) + '<div class="card empty">Bu kodla eşleşen araç kayıtlarda yok.</div>'
        out.append(note(f'{fmt(res["when"], True)} çevresinde ±{res["tol_min"]} dk', "info"))
        for v in res["vehicles"]:
            parts = [f'<div class="vhead"><span class="plate">{esc(E.pretty_plate(v["plaka"]))}</span>'
                     f'<span class="chip">Filo {esc(v["arac_no"] or "-")}</span>{eslesme_chip(v["plaka"])}</div>']
            parts.append(vehicle_map(v, False, v["items"]))
            if v["items"]:
                rows = ""
                for it in v["items"]:
                    tag = "aralığın içinde" if it["conf"] == "kesin" else f'{it["diff_min"]} dk fark'
                    pos = it["pos"]
                    mp = maps(pos[1], pos[2], f'{fmt(pos[0])} konumu') if pos and pos[1] and pos[2] else ""
                    rows += (f'<tr><td><b>{esc(it["hat"])}</b></td><td>{esc(it["ad"])}</td>'
                             f'<td>{fmt(it["first"])} – {fmt(it["last"])}</td><td>{esc(tag)}</td><td>{mp}</td></tr>')
                parts.append('<div class="scroll"><table><thead><tr><th>Hat</th><th>Güzergâh</th><th>Görüldü</th>'
                             f'<th>Eşleşme</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>')
            else:
                parts.append('<p class="muted">Bu zaman aralığında kayıt yok.</p>')
                for label, st in (("Önceki", v["before"]), ("Sonraki", v["after"])):
                    if st:
                        parts.append(f'<p>{label} kayıt: hat <b>{esc(st[0])}</b> · {fmt(st[1], True)} – {fmt(st[2])}</p>')
            out.append('<div class="card">' + "".join(parts) + "</div>")
        return "".join(out)

    def page_ara(g):
        q, tarih, saat, tol = g("q"), g("tarih"), g("saat"), g("tol", "30")
        body = "<h1>Araç sorgula</h1>" + form_ara(q, tarih or today().isoformat(), saat, tol)
        if q:
            day = E.parse_day(tarih)
            conn = E.connect()
            try:
                if saat:
                    res = E.query_vehicle(conn, q, E.to_epoch(day, E.parse_time(saat)), max(5, min(180, int(tol or 30))))
                    body += render_window(res)
                else:
                    body += day_nav(q, day)
                    body += render_day(E.query_day(conn, q, day))
                    body += history_card(conn, q, day)
            finally:
                conn.close()
        else:
            body += '<div class="card empty">Bir filo kodu (ör. <b>09-524</b>) ya da plaka yazın, tarihi seçin.<br>' \
                    'Saat boş bırakılırsa o günün tüm seferleri ve durak saatleri gelir.</div>'
        if q and not saat and E.parse_day(tarih) == today():
            body += '<i data-live="60" hidden></i>'
        if 'class="vmap"' in body:
            body += map_assets()
        return layout("/ara", body)

    # ------------------------------------------------------------------ Ortak veri yardımcıları
    def _tips():
        try:
            conn = E.connect()
            try:
                return {r[0]: r[1] for r in conn.execute("SELECT anahtar, tip FROM arac_tip")}
            finally:
                conn.close()
        except Exception:
            return {}

    def _tip_of(tips, arac_no, plaka):
        return tips.get(E.norm(plaka)) or tips.get(E.norm(arac_no)) or ""

    def _hesap_gun(g, varsayilan=1, ust=366):
        try:
            return max(1, min(ust, int(g("gun", str(varsayilan)))))
        except ValueError:
            return varsayilan

    def vehicle_days(conn, plakalar, bitis, gun):
        """Araç(lar)ın son `gun` gündeki hat dilimleri: [(gün, plaka, filo, hat, ilk, son)], yeniden eskiye."""
        if not plakalar:
            return []
        ilk_gun = bitis - timedelta(days=gun - 1)
        start = E.day_bounds(ilk_gun)[0]
        ph = ",".join("?" * len(plakalar))
        rows = conn.execute(
            f"SELECT plaka, arac_no, hat, first_ts, last_ts FROM stints WHERE plaka IN ({ph}) AND last_ts>=? AND first_ts<? "
            "ORDER BY first_ts", (*plakalar, start, E.day_bounds(bitis)[1])).fetchall()
        out = []
        for i in range(gun):
            d = bitis - timedelta(days=i)
            s0, s1 = E.day_bounds(d)
            for plaka, arac, hat, a, b in rows:
                if b >= s0 and a < s1:
                    out.append((d, plaka, arac or "", hat, max(a, s0), min(b, s1 - 1)))
        return out

    def first_data_day(conn):
        r = conn.execute("SELECT v FROM meta WHERE k='first_data_ts'").fetchone()
        if r:
            try:
                return datetime.fromtimestamp(int(r[0]), TZ).date()
            except (ValueError, OSError):
                pass
        r = conn.execute("SELECT MIN(first_ts) FROM stints").fetchone()
        return datetime.fromtimestamp(r[0], TZ).date() if r and r[0] else None

    def url_ara(q, d):
        return "/?q=%s&tarih=%s" % (urllib.parse.quote(q), d.isoformat())

    def day_nav(q, day):
        t = today()
        links = [("‹ Önceki gün", day - timedelta(days=1)), ("Bugün", t), ("Dün", t - timedelta(days=1)),
                 ("2 gün önce", t - timedelta(days=2))]
        if day < t:
            links.append(("Sonraki gün ›", day + timedelta(days=1)))
        html_ = "".join(f'<a href="{esc(url_ara(q, d), True)}">{esc(lbl)}</a>' for lbl, d in links)
        return f'<div class="dnav">{html_}</div>'

    def history_card(conn, q, day, gun=14):
        plakalar, _ = E.resolve_vehicle(conn, q)
        if not plakalar:
            return ""
        fd = first_data_day(conn)
        items = vehicle_days(conn, plakalar, day, gun)
        by_day = {}
        for d, plaka, arac, hat, a, b in items:
            by_day.setdefault(d, []).append((a, plaka, hat, b))
        rows = []
        gorulen = 0
        for i in range(gun):
            d = day - timedelta(days=i)
            if fd and d < fd:
                break
            lst = sorted(by_day.get(d, []))
            etiket = f'{d.strftime("%d.%m.%Y")} {GUN_AD[d.weekday()]}'
            if not lst:
                rows.append(f'<tr><td><a href="{esc(url_ara(q, d), True)}">{etiket}</a></td><td class="muted">kayıt yok</td></tr>')
                continue
            gorulen += 1
            cok = len(plakalar) > 1
            parca = " · ".join(
                f'{(esc(E.pretty_plate(pl)) + " ") if cok else ""}<b>{esc(hat)}</b> {fmt(a)}–{fmt(b)}' for a, pl, hat, b in lst)
            rows.append(f'<tr><td><a href="{esc(url_ara(q, d), True)}">{etiket}</a></td><td>{parca}</td></tr>')
        if not rows:
            return ""
        csv_url = "/csv/arac?q=%s&tarih=%s&gun=%d" % (urllib.parse.quote(q), day.isoformat(), gun)
        return (f'<div class="card"><div class="vhead"><b>Son {gun} gün</b>'
                f'<span class="muted">{gorulen} gün kayıtlı</span>'
                f'<a class="csvbtn" href="{esc(csv_url, True)}">CSV indir</a></div>'
                '<div class="scroll"><table><thead><tr><th>Tarih</th><th>Hat ve saatler</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div></div>')

    # ------------------------------------------------------------------ İlk hatlar
    def hat_stats(day, gun, limit=50):
        start = E.day_bounds(day - timedelta(days=gun - 1))[0]
        end = E.day_bounds(day)[1]
        conn = E.connect()
        try:
            rows = conn.execute(
                "SELECT hat, COUNT(DISTINCT plaka), COUNT(*) FROM stints WHERE last_ts>=? AND first_ts<? "
                "GROUP BY hat ORDER BY 2 DESC, 3 DESC, hat LIMIT ?", (start, end, limit)).fetchall()
            names = {r[0]: r[1] for r in conn.execute("SELECT hat, ad FROM lines")}
        finally:
            conn.close()
        return rows, names

    def page_hatlar(g):
        day = E.parse_day(g("tarih"))
        gun = _hesap_gun(g, 1, 90)
        rows, names = hat_stats(day, gun)
        sec = "".join(f'<option value="{v}"{" selected" if v == gun else ""}>{t}</option>'
                      for v, t in ((1, "Seçili gün"), (7, "Son 7 gün"), (30, "Son 30 gün")))
        form = ('<form class="card form two" method="get" action="/hatlar" style="grid-template-columns:1fr 1fr auto">'
                f'<div class="field"><label>Tarih</label><input type="date" name="tarih" value="{esc(day.isoformat(), True)}"></div>'
                f'<div class="field"><label>Aralık</label><select name="gun">{sec}</select></div>'
                '<button class="btn">Göster</button></form>')
        body = "<h1>İlk 50 hat</h1>" + form
        if not rows:
            body += '<div class="card empty">Bu aralıkta kayıt yok.</div>'
        else:
            top = max(r[1] for r in rows) or 1
            tr = "".join(
                f'<tr><td>{i}</td><td><a href="/gun?tarih={day.isoformat()}&hat={urllib.parse.quote(h)}"><b>{esc(h)}</b></a>'
                f'<div class="muted" style="font-size:.8rem">{esc(names.get(h, ""))}</div></td>'
                f'<td><b>{n_v}</b></td><td>{n_s}</td><td><div class="bar2"><i style="width:{round(100 * n_v / top)}%"></i></div></td></tr>'
                for i, (h, n_v, n_s) in enumerate(rows, 1))
            ara = day.strftime("%d.%m.%Y") if gun == 1 else f'{(day - timedelta(days=gun - 1)).strftime("%d.%m.%Y")} – {day.strftime("%d.%m.%Y")}'
            csv_url = "/csv/hatlar?tarih=%s&gun=%d" % (day.isoformat(), gun)
            body += (note("Sıralama o aralıkta hatta görülen farklı araç sayısına göredir. Çalışma dilimi, bir aracın hatta kesintisiz "
                          "görüldüğü her süredir; gerçek sefer sayısı değildir.", "info")
                     + f'<div class="card"><div class="vhead"><b>{esc(ara)}</b><a class="csvbtn" href="{esc(csv_url, True)}">CSV indir</a></div>'
                     '<div class="scroll" style="max-height:none"><table><thead><tr><th>#</th><th>Hat</th><th>Araç</th>'
                     f'<th>Çalışma dilimi</th><th></th></tr></thead><tbody>{tr}</tbody></table></div></div>')
        return layout("/hatlar", body, "İlk hatlar · EGO Filo Takip")

    # ------------------------------------------------------------------ Durak ve hat sayfaları
    DOL_CHIP = {"az": ("🟢", "Az yoğun"), "orta": ("🟡", "Orta yoğun"), "çok": ("🔴", "Çok yoğun"), "dolu": ("🔴", "Dolu")}

    def dol_chip(d):
        d = (d or "").lower()
        for k, (ic, t) in DOL_CHIP.items():
            if d.startswith(k):
                return f'<span class="chip dol" title="EGO doluluk bilgisi">{ic} {t}</span>'
        return ""

    def eta_text(r):
        sn = E.to_int(E.sv(r, "saniye"))
        if sn is not None and sn >= 0:
            return "Durakta" if sn < 45 else "%d dk" % max(1, round(sn / 60))
        return E.sv(r, "sure")

    def stop_name(conn, no):
        r = conn.execute("SELECT ad FROM line_route WHERE durak=? AND ad<>'' LIMIT 1", (no,)).fetchone()
        return r[0] if r else ""

    def stop_search(q):
        conn = E.connect()
        try:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            return conn.execute(
                "SELECT durak, MIN(ad), COUNT(DISTINCT hat) FROM line_route WHERE durak=? OR ad LIKE ? "
                "GROUP BY durak ORDER BY 3 DESC LIMIT 40", (q, like)).fetchall()
        finally:
            conn.close()

    def stop_data(no):
        """Duraktaki durum: yaklaşan araçlar (EGO canlı) + son geçenler (kendi kayıtlarımız)."""
        conn = E.connect()
        try:
            ad = stop_name(conn, no)
            hats = [r[0] for r in conn.execute("SELECT hat FROM line_stops WHERE durak=?", (no,))]
            names = {r[0]: r[1] for r in conn.execute("SELECT hat, ad FROM lines")}
            sira_of = {h: s for h, s in conn.execute("SELECT hat, sira FROM line_route WHERE durak=?", (no,))}
            now = E.now_ts()
            sights = conn.execute(
                "SELECT plaka, arac_no, hat, ts, sira FROM sightings WHERE ts>=? AND hat IN (%s) AND sira IS NOT NULL ORDER BY ts"
                % ",".join("?" * len(hats)), (now - 3600, *hats)).fetchall() if hats else []
        finally:
            conn.close()
        rows = live_rows(E.Http(False), "Otobusler", DURAK=no)
        yak, nxt = [], {}
        for r in rows or []:
            hat = E.sv(r, "hat_kisa_kod") or E.sv(r, "hat_no")
            if not E.is_live(r):
                txt = " ".join(str(v) for v in r.values() if isinstance(v, str) and ("Hareket" in v or ":" in v))
                nxt[hat] = (E.sv(r, "sure") or txt)[:80]
                continue
            vs = E.to_int(E.sv(r, "durak_sira_no"))
            ss = E.to_int(E.sv(r, "secili_durak_sira_no")) or sira_of.get(hat)
            away = (ss - vs) if (ss is not None and vs is not None) else None
            yak.append({"hat": hat, "f": E.sv(r, "arac_no"), "p": E.sv(r, "plaka_no"), "eta": eta_text(r),
                        "sn": E.to_int(E.sv(r, "saniye")), "away": away, "dol": E.parse_dol(r),
                        "tip": E.parse_tip(E.sv(r, "detay"))})
        yak.sort(key=lambda x: (x["sn"] if x["sn"] is not None else 99999, x["away"] if x["away"] is not None else 999))
        # geçenler: son 60 dk'da bu durağın sırasının gerisinden önüne geçenler
        by = {}
        for plaka, f, hat, ts, sira in sights:
            by.setdefault((plaka, hat), []).append((ts, sira, f))
        gecen = {}
        for (plaka, hat), lst in by.items():
            ss = sira_of.get(hat)
            if ss is None:
                continue
            before = [x for x in lst if x[1] <= ss]
            after = [x for x in lst if x[1] > ss]
            if before and after and after[0][0] >= before[-1][0]:
                t = after[0][0]
                if plaka not in gecen or gecen[plaka]["ts"] < t:
                    gecen[plaka] = {"hat": hat, "f": lst[-1][2], "p": plaka, "ts": t}
        gec = sorted(gecen.values(), key=lambda x: -x["ts"])[:12]
        return {"no": no, "ad": ad, "hatlar": [(h, names.get(h, "")) for h in sorted(hats, key=natural_key)],
                "yak": yak, "nxt": nxt, "gec": gec, "ok": rows is not None, "now": now}

    # ------------------------------------------------------------------ İzmir: durak + resmi yaklaşan araç servisi
    IZ_LIVE = os.environ.get("IZMIR_LIVE", "https://openapi.izmir.bel.tr/api/iztek").rstrip("/")
    _iz_cache = {}

    def _comma(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def izmir_approaching(durak, slat, slng):
        """Resmi servis: durağa yaklaşan otobüsler -> [{hat, ad, id, kalan, yon, m, eng, bis}] (5 sn önbellek)."""
        hit = _iz_cache.get(durak)
        if hit and time.time() - hit[0] < 5:
            return hit[1]
        try:
            raw = E.Http(False).request(f"{IZ_LIVE}/duragayaklasanotobusler/{urllib.parse.quote(durak)}", timeout=10, retries=1,
                                        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (FiloTakip arsiv)"})
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            return None
        out = []
        for r in data if isinstance(data, list) else []:
            la, lo = _comma(r.get("KoorX")), _comma(r.get("KoorY"))
            m = None
            if la and lo and slat is not None:
                m = int(math.hypot((la - slat) * 111000, (lo - slng) * 111000 * math.cos(math.radians(slat))))
            out.append({"hat": str(r.get("HatNumarasi") or ""), "ad": r.get("HatAdi") or "", "id": str(r.get("OtobusId") or ""),
                        "kalan": r.get("KalanDurakSayisi"), "yon": r.get("HattinYonu"), "m": m,
                        "eng": bool(r.get("EngelliMi")), "bis": bool(r.get("BisikletAparatliMi"))})
        out.sort(key=lambda x: (x["m"] if x["m"] is not None else 10**9))
        _iz_cache[durak] = (time.time(), out)
        return out

    # ------------------------------------------------------------------ İzmir: elle plaka eşleme (araç no <-> plaka / filo kodu)
    ESLESME_PAROLA = os.environ.get("ESLESME_PAROLA", "")
    _RE_PLAKA = re.compile(r"\b(\d{2})\s*([A-Za-zÇĞİÖŞÜçğıöşü]{1,3})\s*(\d{2,4})\b")
    _RE_FILO = re.compile(r"\b(\d{2})\s*-\s*(\d{1,3})\b")

    def eslesme_init(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS eslesme (arac_no TEXT PRIMARY KEY, plaka TEXT, filo TEXT, ts INTEGER)")

    def eslesme_map():
        """{arac_no: (plaka, filo)}; tablo yoksa boş."""
        if cur_city() != "izmir":
            return {}
        conn = E.connect()
        try:
            eslesme_init(conn)
            return {r[0]: (r[1] or "", r[2] or "") for r in conn.execute("SELECT arac_no, plaka, filo FROM eslesme")}
        except Exception:  # noqa: BLE001
            return {}
        finally:
            conn.close()

    def eslesme_chip(arac_no, mp=None):
        v = (mp if mp is not None else eslesme_map()).get(str(arac_no))
        if not v:
            return ""
        out = ""
        if v[0]:
            out += f'<span class="plate">{esc(E.pretty_plate(E.norm(v[0])))}</span>'
        if v[1]:
            out += f'<span class="chip">Filo {esc(v[1])}</span>'
        return out

    def save_eslesme(conn, arac_no, plaka, filo):
        arac_no = E.norm(arac_no)
        if not arac_no or not (plaka or filo):
            return False
        pl = E.norm(plaka)
        eslesme_init(conn)
        conn.execute("INSERT OR REPLACE INTO eslesme (arac_no, plaka, filo, ts) VALUES (?,?,?,?)",
                     (arac_no, pl, (filo or "").strip(), E.now_ts()))
        for alias in (pl, E.norm(filo)):
            if alias and alias != arac_no:
                conn.execute("INSERT OR REPLACE INTO aliases (alias, plaka) VALUES (?,?)", (alias, arac_no))
        return True

    def parse_eslesme_line(line):
        """'2051 35 AS 8162 16-005' -> (arac_no, plaka, filo); ayraç olarak ; veya , da olur."""
        line = line.strip()
        if not line:
            return None
        m = re.match(r"^\s*(\d{1,6})\b[\s;,]*(.*)$", line)
        if not m:
            return None
        rest = m.group(2)
        filo = ""
        fm = _RE_FILO.search(rest)
        if fm:
            filo = "%s-%s" % (fm.group(1), fm.group(2).zfill(3))
            rest = rest[:fm.start()] + " " + rest[fm.end():]
        pm = _RE_PLAKA.search(rest)
        plaka = ("%s %s %s" % (pm.group(1), pm.group(2).upper(), pm.group(3))) if pm else ""
        return (m.group(1), plaka, filo) if (plaka or filo) else None

    def page_eslesme(g, msg=""):
        body = "<h1>Araç eşleme</h1>"
        if cur_city() != "izmir":
            return layout("/eslesme", body + note("Bu sayfa yalnızca İzmir için kullanılır: İzmir'in canlı servisi plaka vermez, "
                                                  "araç numarası ile plakayı burada elle eşleriz.", "info"), "Eşleme · Filo Takip")
        if msg:
            body += note(msg, "info")
        mp = eslesme_map()
        conn = E.connect()
        try:
            seen = conn.execute("SELECT plaka, MAX(last_ts) FROM stints GROUP BY plaka ORDER BY MAX(last_ts) DESC LIMIT 8").fetchall()
        finally:
            conn.close()
        kilit = ("" if ESLESME_PAROLA else
                 note("Kayıt ekleme kapalı: sunucuda ESLESME_PAROLA tanımlanmamış. Kayıtlar herkese açık görünür, ekleme yalnızca parola ile yapılır."))
        par = '<div class="field"><label>Parola</label><input name="parola" type="password" autocomplete="off"></div>'
        body += note("İzmir'in resmi servisi plaka vermiyor. Burada bildiğiniz araç numarası ↔ plaka eşleşmeleri saklanır; "
                     "kayıtlı araçlarda plaka ve filo kodu sorgu, durak ve hat sayfalarında görünür, plaka ya da filo koduyla arama da çalışır.", "info")
        body += kilit
        body += ('<form class="card form" method="post" action="/eslesme/kaydet"><div class="field"><label>Araç no (uygulamadaki/sitedeki)</label>'
                 '<input name="arac_no" placeholder="ör. 2051" autocomplete="off"></div>'
                 '<div class="field"><label>Plaka</label><input name="plaka" placeholder="ör. 35 AS 8162" autocomplete="off"></div>'
                 '<div class="field"><label>Filo kodu (isteğe bağlı)</label><input name="filo" placeholder="ör. 16-005" autocomplete="off"></div>'
                 + par + '<button class="btn">Kaydet</button></form>')
        body += ('<details class="card"><summary><b>Toplu ekle</b> (her satır: araç no, plaka, filo kodu)</summary>'
                 '<form method="post" action="/eslesme/toplu"><textarea name="metin" rows="6" style="width:100%;margin-top:10px;padding:10px;'
                 'border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)" placeholder="2051 35 AS 8162 16-005&#10;11220 35 DA 7587"></textarea>'
                 + par + '<button class="btn" style="margin-top:10px">İçe aktar</button></form></details>')
        rows = "".join(
            '<tr><td><a href="/?q=%s"><b>%s</b></a></td><td>%s</td><td>%s</td>'
            '<td><form method="post" action="/eslesme/sil" style="margin:0"><input type="hidden" name="arac_no" value="%s">'
            '<input name="parola" type="password" placeholder="parola" style="width:90px"> <button class="btn" style="padding:4px 10px">Sil</button></form></td></tr>'
            % (urllib.parse.quote(a), esc(a), esc(E.pretty_plate(E.norm(v[0])) if v[0] else "-"), esc(v[1] or "-"), esc(a, True))
            for a, v in sorted(mp.items(), key=lambda kv: kv[0]))
        body += ('<div class="card"><div class="vhead"><b>Kayıtlı eşleşmeler (%d)</b></div>' % len(mp)
                 + ('<table><thead><tr><th>Araç no</th><th>Plaka</th><th>Filo kodu</th><th></th></tr></thead><tbody>%s</tbody></table>' % rows
                    if rows else '<div class="muted">Henüz kayıt yok.</div>') + '</div>')
        return layout("/eslesme", body, "Eşleme · Filo Takip")

    def page_durak_izmir(g):
        no, q = g("no"), g("q")
        form = ('<form class="card form" method="get" action="/durak"><div class="field"><label>Durak adı veya numarası</label>'
                f'<input name="q" value="{esc(q or no, True)}" placeholder="ör. {esc(city_meta()["durak_ornek"], True)}" autocomplete="off"></div>'
                '<button class="btn">Ara</button></form>')
        body = "<h1>Durak takibi</h1>" + form
        conn = E.connect()
        try:
            if q and not no:
                like = "%" + q.replace("%", "").replace("_", "") + "%"
                res = conn.execute("SELECT durak, ad, (SELECT COUNT(*) FROM line_stops l WHERE l.durak=g.durak) FROM stops_geo g "
                                   "WHERE durak=? OR ad LIKE ? ORDER BY 3 DESC LIMIT 40", (q, like)).fetchall()
                if len(res) == 1:
                    no = res[0][0]
                elif not res:
                    return layout("/durak", body + '<div class="card empty">Eşleşen durak yok.</div>', "Durak · Filo Takip")
                else:
                    li = "".join(f'<tr><td><a href="/durak?no={esc(d, True)}"><b>{esc(d)}</b></a></td><td>{esc(a)}</td><td>{n} hat</td></tr>' for d, a, n in res)
                    return layout("/durak", body + f'<div class="card"><table><tbody>{li}</tbody></table></div>', "Durak · Filo Takip")
            if not no:
                body += note("Durağı adıyla ya da numarasıyla arayın. " + city_meta()["durak_not"], "info")
                return layout("/durak", body, "Durak · Filo Takip")
            st = conn.execute("SELECT ad, lat, lng FROM stops_geo WHERE durak=?", (no,)).fetchone()
            hats = [r[0] for r in conn.execute("SELECT hat FROM line_stops WHERE durak=?", (no,))]
            names = {r[0]: r[1] for r in conn.execute("SELECT hat, ad FROM lines")}
        finally:
            conn.close()
        if not st:
            return layout("/durak", body + '<div class="card empty">Durak bulunamadı.</div>', "Durak · Filo Takip")
        head = f'<div class="card"><div class="vhead"><b>{esc(st[0] or "Durak")} · {esc(no)}</b></div>'
        if hats:
            head += '<div class="muted" style="margin-top:6px">' + " ".join(
                f'<a class="chip" href="/hat?no={urllib.parse.quote(h)}" title="{esc(names.get(h, ""), True)}">{esc(h)}</a>'
                for h in sorted(hats, key=natural_key)) + "</div>"
        body += head + "</div>"
        rows = izmir_approaching(no, st[1], st[2])
        if rows is None:
            body += note("İzmir canlı servisi şu an cevap vermedi; yaklaşan araçlar gösterilemiyor.")
        elif not rows:
            body += '<div class="card empty">Şu an bu durağa yaklaşan canlı araç görünmüyor.</div>'
        else:
            tr = ""
            emp = eslesme_map()
            for y in rows:
                kalan = "" if y["kalan"] is None else (f'{y["kalan"]} durak kaldı' if y["kalan"] > 0 else "durağa geliyor")
                rozet = ("♿ " if y["eng"] else "") + ("🚲" if y["bis"] else "")
                tr += (f'<tr><td><a href="/hat?no={urllib.parse.quote(y["hat"])}"><b>{esc(y["hat"])}</b></a>'
                       f'<div class="muted" style="font-size:.78rem">{esc(y["ad"])}</div></td>'
                       f'<td><a href="/?q={urllib.parse.quote(y["id"])}"><b>{esc(y["id"])}</b></a><div>{eslesme_chip(y["id"], emp)}</div></td>'
                       f'<td><b>{"-" if y["m"] is None else str(y["m"]) + " m"}</b><div class="muted" style="font-size:.78rem">{esc(kalan)}</div></td>'
                       f'<td>{rozet}</td></tr>')
            body += ('<div class="card"><div class="vhead"><b>Yaklaşan araçlar</b><span class="muted">canlı · resmi servis</span></div>'
                     '<table><thead><tr><th>Hat</th><th>Araç no</th><th>Durağa uzaklık</th><th></th></tr></thead>'
                     f'<tbody>{tr}</tbody></table></div>'
                     '<div class="muted" style="font-size:.8rem;margin-top:6px">Uygulamadaki liste ile aynı anda karşılaştırın: aynı hat ve aynı mesafedeki araç aynı araçtır.</div>')
        return layout("/durak", body + '<i data-live="10" hidden></i>', "Durak · Filo Takip")

    def page_durak(g):
        no = g("no")
        q = g("q")
        form = ('<form class="card form" method="get" action="/durak"><div class="field"><label>Durak adı veya numarası</label>'
                f'<input name="q" value="{esc(q or no, True)}" placeholder="ör. {esc(city_meta()['durak_ornek'], True)}" autocomplete="off"></div>'
                '<button class="btn">Ara</button></form>')
        body = "<h1>Durak takibi</h1>" + form
        if q and not no:
            res = stop_search(q)
            if len(res) == 1:
                no = res[0][0]
            elif not res:
                return layout("/durak", body + '<div class="card empty">Eşleşen durak yok.</div>', "Durak · Filo Takip")
            else:
                li = "".join(f'<tr><td><a href="/durak?no={esc(d, True)}"><b>{esc(d)}</b></a></td><td>{esc(a)}</td><td>{n} hat</td></tr>'
                             for d, a, n in res)
                return layout("/durak", body + f'<div class="card"><table><tbody>{li}</tbody></table></div>', "Durak · Filo Takip")
        if not no:
            body += note("Durağı adıyla ya da numarasıyla arayın. " + city_meta()["durak_not"], "info")
            return layout("/durak", body, "Durak · Filo Takip")
        d = stop_data(no)
        head = f'<div class="card"><div class="vhead"><b>{esc(d["ad"] or "Durak")} · {esc(no)}</b></div>'
        if d["hatlar"]:
            head += '<div class="muted" style="margin-top:6px">' + " ".join(
                f'<a class="chip" href="/hat?no={urllib.parse.quote(h)}" title="{esc(n, True)}">{esc(h)}</a>' for h, n in d["hatlar"]) + "</div>"
        body += head + "</div>"
        if not d["ok"]:
            body += note("EGO canlı servisi şu an cevap vermedi; yaklaşan araçlar gösterilemiyor.")
        elif not d["yak"]:
            body += '<div class="card empty">Şu an bu durağa yaklaşan canlı araç görünmüyor.</div>'
        else:
            tr = ""
            for y in d["yak"]:
                if y["away"] is None:
                    yak = ""
                elif y["away"] > 0:
                    yak = f'{y["away"]} durak kaldı'
                elif y["away"] == 0:
                    yak = "durağa geliyor"
                else:
                    yak = f'{-y["away"]} durak önce geçti'
                tr += (f'<tr><td><a href="/hat?no={urllib.parse.quote(y["hat"])}"><b>{esc(y["hat"])}</b></a></td>'
                       f'<td><a href="/?q={urllib.parse.quote(y["f"] or y["p"])}">{esc(y["f"])}</a><div class="muted" style="font-size:.78rem">{esc(y["p"])}</div></td>'
                       f'<td><b>{esc(y["eta"])}</b><div class="muted" style="font-size:.78rem">{esc(yak)}</div></td>'
                       f'<td>{dol_chip(y["dol"])} {model_chip(y["f"], y["p"])}</td></tr>')
            body += ('<div class="card"><div class="vhead"><b>Yaklaşan araçlar</b><span class="muted">canlı · EGO</span></div>'
                     '<div class="scroll" style="max-height:none"><table><thead><tr><th>Hat</th><th>Araç</th><th>Varış</th><th>Bilgi</th></tr></thead>'
                     f'<tbody>{tr}</tbody></table></div></div>')
        if d["nxt"]:
            li = "".join(f'<tr><td><b>{esc(h)}</b></td><td>{esc(t)}</td></tr>' for h, t in sorted(d["nxt"].items(), key=lambda x: natural_key(x[0])))
            body += f'<div class="card"><div class="vhead"><b>Hatların sonraki hareketi</b></div><table><tbody>{li}</tbody></table></div>'
        if d["gec"]:
            li = "".join(f'<tr><td><b>{esc(x["hat"])}</b></td><td><a href="/?q={urllib.parse.quote(x["f"] or x["p"])}">{esc(x["f"] or x["p"])}</a></td>'
                         f'<td>{fmt(x["ts"])} ({max(0, (d["now"] - x["ts"]) // 60)} dk önce)</td></tr>' for x in d["gec"])
            body += ('<div class="card"><div class="vhead"><b>Son geçenler</b><span class="muted">kendi kayıtlarımızdan, son 1 saat</span></div>'
                     f'<table><tbody>{li}</tbody></table></div>')
        else:
            body += note("“Son geçenler” kendi tarama kayıtlarımızdan çıkarılır; son 1 saatte bu durağı geçtiği yakalanan araç yok.", "info")
        return layout("/durak", body + '<i data-live="30" hidden></i>', "Durak %s · Filo Takip" % no)

    def page_hat(g):
        hat = g("no")
        q = g("q")
        form = ('<form class="card form" method="get" action="/hat"><div class="field"><label>Hat numarası veya güzergâh</label>'
                f'<input name="q" value="{esc(q or hat, True)}" placeholder="ör. {esc(city_meta()['hat_ornek'], True)}" autocomplete="off"></div>'
                '<button class="btn">Göster</button></form>')
        body = "<h1>Hat bilgisi</h1>" + form
        if q and not hat:
            conn = E.connect()
            try:
                like = "%" + q.replace("%", "").replace("_", "") + "%"
                res = conn.execute("SELECT hat, ad FROM lines WHERE hat=? OR hat LIKE ? OR ad LIKE ? ORDER BY hat LIMIT 40", (q, like, like)).fetchall()
            finally:
                conn.close()
            exact = [r for r in res if r[0].lower() == q.lower()]
            if exact:
                hat = exact[0][0]
            elif len(res) == 1:
                hat = res[0][0]
            elif not res:
                return layout("/hat", body + '<div class="card empty">Eşleşen hat yok.</div>', "Hat · Filo Takip")
            else:
                res.sort(key=lambda r: natural_key(r[0]))
                li = "".join(f'<tr><td><a href="/hat?no={urllib.parse.quote(h)}"><b>{esc(h)}</b></a></td><td>{esc(a)}</td></tr>' for h, a in res)
                return layout("/hat", body + f'<div class="card"><table><tbody>{li}</tbody></table></div>', "Hat · Filo Takip")
        if not hat:
            return layout("/hat", body + note("Hat numarasıyla ya da güzergâh adıyla arayın: duraklar, hareket saatleri ve şu an hattaki araçlar.", "info"), "Hat · Filo Takip")
        conn = E.connect()
        try:
            ad = (conn.execute("SELECT ad FROM lines WHERE hat=?", (hat,)).fetchone() or [""])[0]
            route = conn.execute("SELECT sira, durak, ad FROM line_route WHERE hat=? ORDER BY sira", (hat,)).fetchall()
            info = conn.execute("SELECT kalkis, varis, mesafe, sure FROM line_info WHERE hat=?", (hat,)).fetchone()
            times = conn.execute("SELECT gun, yon, saat, nt FROM line_times WHERE hat=? ORDER BY gun, yon, saat", (hat,)).fetchall()
        finally:
            conn.close()
        if not ad and not route:
            return layout("/hat", body + '<div class="card empty">Hat bulunamadı.</div>', "Hat · Filo Takip")
        live = {}
        rows = live_rows(E.Http(False), "Otobus", HAT=hat, DURAK=route[0][1]) if route else None
        for r in rows or []:
            if E.is_live(r):
                live.setdefault(E.to_int(E.sv(r, "durak_sira_no")), []).append(r)
        head = f'<div class="card"><div class="vhead"><b>{esc(hat)} · {esc(ad)}</b><a class="csvbtn" href="/harita?hat={urllib.parse.quote(hat)}">Haritada gör</a></div>'
        if info and any(info):
            lab = ("Kalkış: ", "Varış: ", "Mesafe: ", "Süre: ")
            head += '<div class="muted" style="margin-top:6px">' + " · ".join(esc(l + v) for l, v in zip(lab, info) if v) + "</div>"
        body += head + "</div>"
        if rows is None and route:
            body += note("EGO canlı servisi şu an cevap vermedi; hattaki araçlar gösterilemiyor.")
        elif route:
            body += f'<div class="muted" style="margin:0 2px 8px">Şu an hatta {sum(len(v) for v in live.values())} canlı araç var.</div>'
        if times:
            wd = datetime.now(E.TZ).weekday()
            bugun = "pazar" if wd == 6 else "cumartesi" if wd == 5 else "haftaici"
            nowhm = datetime.now(E.TZ).strftime("%H:%M")
            for key, lab in (("haftaici", "Hafta içi"), ("cumartesi", "Cumartesi"), ("pazar", "Pazar")):
                ts_ = [t for t in times if t[0] == key]
                if not ts_:
                    continue
                inner = ""
                for y in sorted({t[1] for t in ts_}):
                    sa = [t for t in ts_ if t[1] == y]
                    chips = " ".join(
                        f'<span class="chip"{(" title=" + chr(34) + esc(t[3], True) + chr(34)) if t[3] else ""}>{esc(t[2])}{"*" if t[3] else ""}</span>' for t in sa)
                    inner += f'<div style="margin:6px 0"><span class="muted">{len(sa)} sefer</span><div class="times">{chips}</div></div>'
                nx = ""
                if key == bugun:
                    nxt = [t[2] for t in ts_ if t[1] == 0 and t[2] >= nowhm][:3]
                    nx = '<div style="margin:6px 0"><b>Sıradaki kalkışlar:</b> ' + (", ".join(nxt) if nxt else "bugün için kalmadı") + "</div>"
                body += f'<div class="card"><div class="vhead"><b>{lab}</b>{"<span class=pill>bugün</span>" if key == bugun else ""}</div>{nx}{inner}</div>'
            body += '<div class="muted" style="font-size:.8rem;margin-bottom:12px">* işaretli seferlerin notu üzerine gelince görünür. Saatler EGO “Hareket Saatleri” sayfasındandır.</div>'
        else:
            body += note("Bu hattın hareket saatleri henüz çekilmedi; toplayıcı arka planda tüm hatları yavaş yavaş tarıyor.", "info")
        if route:
            li = ""
            for sira, durak, dad in route:
                vs = "".join(f' <a class="chip" href="/?q={urllib.parse.quote(E.sv(r, "arac_no") or E.sv(r, "plaka_no"))}">🚌 {esc(E.sv(r, "arac_no"))}</a> '
                             + dol_chip(E.parse_dol(r)) for r in live.get(sira, []))
                li += (f'<li{" class=hasbus" if vs else ""}><a href="/durak?no={esc(durak, True)}"><b>{sira}.</b> {esc(dad)}</a>'
                       f'<span class="muted"> · {esc(durak)}</span>{vs}</li>')
            body += f'<div class="card"><div class="vhead"><b>Duraklar ({len(route)})</b><span class="muted">🚌 = aracın bir sonraki durağı</span></div><ol class="stops">{li}</ol></div>'
        return layout("/hat", body + '<i data-live="30" hidden></i>', "Hat %s · Filo Takip" % hat)

    def api_durak(g):
        d = stop_data(g("no"))
        return json.dumps({k: d[k] for k in ("no", "ad", "yak", "nxt", "gec", "ok")}, ensure_ascii=False)

    # ------------------------------------------------------------------ CSV dışa aktarma
    def csv_gun(g):
        day = E.parse_day(g("tarih"))
        hat = g("hat")
        start, end = E.day_bounds(day)
        conn = E.connect()
        try:
            sql = ("SELECT hat, plaka, arac_no, first_ts, last_ts, n FROM stints WHERE last_ts>=? AND first_ts<? ")
            args = [start, end]
            if hat:
                sql += "AND hat=? "
                args.append(hat)
            rows = conn.execute(sql + "ORDER BY hat, first_ts", args).fetchall()
        finally:
            conn.close()
        mdb, tips = _db_models(), _tips()
        out = []
        for h, plaka, arac, a, b, n in sorted(rows, key=lambda r: (natural_key(r[0]), r[3])):
            out.append((day.isoformat(), h, E.pretty_plate(plaka), arac or "", model_for(arac, plaka, mdb)[0],
                        _tip_of(tips, arac, plaka), fmt(max(a, start), False), fmt(min(b, end - 1), False), n))
        return ("gun-%s%s.csv" % (day.isoformat(), "-hat" + re.sub(r"[^0-9A-Za-z_-]", "", hat) if hat else ""),
                csv_bytes(["tarih", "hat", "plaka", "filo_no", "marka_model", "tip", "ilk_gorulme", "son_gorulme", "gozlem"], out))

    def csv_hatlar(g):
        day = E.parse_day(g("tarih"))
        gun = _hesap_gun(g, 1, 90)
        rows, names = hat_stats(day, gun)
        ilk = day - timedelta(days=gun - 1)
        out = [(i, h, names.get(h, ""), n_v, n_s, ilk.isoformat(), day.isoformat()) for i, (h, n_v, n_s) in enumerate(rows, 1)]
        return ("ilk-hatlar-%s-%dg.csv" % (day.isoformat(), gun),
                csv_bytes(["sira", "hat", "hat_adi", "arac_sayisi", "calisma_dilimi", "baslangic", "bitis"], out))

    def csv_arac(g):
        q = g("q")
        day = E.parse_day(g("tarih"))
        gun = _hesap_gun(g, 14, 366)
        conn = E.connect()
        try:
            plakalar, _ = E.resolve_vehicle(conn, q)
            items = vehicle_days(conn, plakalar, day, gun)
        finally:
            conn.close()
        mdb, tips = _db_models(), _tips()
        out = [(d.isoformat(), E.pretty_plate(pl), arac, model_for(arac, pl, mdb)[0], _tip_of(tips, arac, pl), hat,
                fmt(a, False), fmt(b, False)) for d, pl, arac, hat, a, b in sorted(items, key=lambda r: (r[0], r[4]))]
        ad = re.sub(r"[^0-9A-Za-z_-]", "", E.norm(q)) or "arac"
        return ("arac-%s-%s-%dg.csv" % (ad, day.isoformat(), gun),
                csv_bytes(["tarih", "plaka", "filo_no", "marka_model", "tip", "hat", "ilk_gorulme", "son_gorulme"], out))

    # ------------------------------------------------------------------ Şehir seçimi
    def city_stats(cid="ankara"):
        try:
            conn = E.connect(CITY_DB.get(cid) or E.DB_PATH)
            try:
                n = conn.execute("SELECT COUNT(DISTINCT plaka) FROM stints").fetchone()[0]
                fd = first_data_day(conn)
            finally:
                conn.close()
        except Exception:
            return None
        return n, fd

    def page_sehir(g):
        kart = []
        for c in CITIES:
            if c["id"] == "izmir" and not c["aktif"]:
                continue  # İzmir şimdilik gizli (plaka verisi yok); veri korunur, IZMIR_GOSTER=0 ile gizlenir
            if c["aktif"]:
                st = city_stats(c["id"])
                alt = ""
                if st and st[0]:
                    alt = (f'<div class="stat"><b>{f"{st[0]:,}".replace(",", ".")}</b> araç kayıtlı'
                           + (f' · <b>{st[1].strftime("%d.%m.%Y")}</b>\'den beri' if st[1] else "") + "</div>")
                kart.append(f'<a class="city" href="/sehir/sec?s={c["id"]}"><span class="tag on">Aktif</span>'
                            f'<h2>{esc(c["ad"])}</h2><div class="kurum">{esc(c["kurum"])}</div>{alt}</a>')
            else:
                kart.append(f'<div class="city off"><span class="tag soon">Yakında</span>'
                            f'<h2>{esc(c["ad"])}</h2><div class="kurum">{esc(c["kurum"])}</div>'
                            '<div class="stat">Veri toplama hazırlanıyor</div></div>')
        uyari = ""
        if g("yakinda"):
            ad = CITY_BY_ID.get(g("yakinda"), {}).get("ad", "Bu şehir")
            uyari = note(f"{ad} henüz hazır değil. Hazır olunca buradan seçilebilecek.", "info")
        body = ('<div class="hero"><h1>Hangi şehrin arşivini görmek istiyorsun?</h1>'
                '<div class="muted">Seçimin bu cihazda hatırlanır; üstteki şehir düğmesinden değiştirebilirsin.</div></div>'
                + uyari + f'<div class="cities">{"".join(kart)}</div>')
        return layout("/sehir", body, "Şehir seç · Filo Takip", picker=True)

    # ------------------------------------------------------------------ Gün özeti
    def page_gun(g):
        day = E.parse_day(g("tarih"))
        hat = g("hat")
        start, end = E.day_bounds(day)
        conn = E.connect()
        try:
            sql = ("SELECT hat, plaka, MAX(arac_no), MIN(first_ts), MAX(last_ts) FROM stints "
                   "WHERE last_ts>=? AND first_ts<? ")
            args = [start, end]
            sql += "GROUP BY hat, plaka"
            rows = conn.execute(sql, args).fetchall()
            names = {r[0]: r[1] for r in conn.execute("SELECT hat, ad FROM lines")}
        finally:
            conn.close()
        if hat:
            def _tl(x):
                return (x or "").replace("İ", "i").replace("I", "ı").lower()
            hq = _tl(hat)
            ok_h = {h for h in {r[0] for r in rows}
                    if _tl(h) == hq or _tl(h).startswith(hq + "-") or hq in _tl(names.get(h, ""))}
            rows = [r for r in rows if r[0] in ok_h]
        hat_opts = "".join(f'<option value="{esc(h, True)}">{esc(n)}</option>' for h, n in sorted(names.items(), key=lambda x: natural_key(x[0])))
        conn = E.connect()
        try:
            pass
        finally:
            conn.close()
        by_hat = {}
        for h, plaka, arac, a, b in rows:
            by_hat.setdefault(h, []).append((a, plaka, arac, b))
        form = ('<form class="card form two" method="get" action="/gun">'
                f'<div class="field"><label>Tarih</label><input type="date" name="tarih" value="{esc(day.isoformat(), True)}"></div>'
                f'<div class="field"><label>Hat no veya güzergâh adı (boşsa tümü)</label><input name="hat" list="hatlist" value="{esc(hat, True)}" placeholder="{esc(city_meta()['gun_ornek'], True)}" autocomplete="off"></div>'
                f'<datalist id="hatlist">{hat_opts}</datalist>'
                '<button class="btn">Göster</button></form>')
        body = "<h1>Gün özeti</h1>" + form
        total = sum(len(v) for v in by_hat.values())
        if not by_hat:
            body += '<div class="card empty">Bu tarihte ' + ("bu hatta " if hat else "") + "kayıt yok.</div>"
        else:
            csv_url = "/csv/gun?tarih=%s%s" % (day.isoformat(), "&hat=" + urllib.parse.quote(hat) if hat else "")
            body += note(f"{len(by_hat)} hat, {total} araç. Bir araca tıklayarak o günkü seferlerini ve durak saatlerini açın.", "info")
            body += f'<div class="dnav"><a href="{esc(csv_url, True)}">CSV indir</a><a href="/hatlar?tarih={day.isoformat()}">İlk 50 hat</a></div>'
        if not hat:
            conn = E.connect()
            try:
                ps, pe = start - 86400, start
                lost = conn.execute(
                    "SELECT plaka, MAX(arac_no), MAX(last_ts), (SELECT hat FROM stints s2 WHERE s2.plaka=s.plaka ORDER BY last_ts DESC LIMIT 1) "
                    "FROM stints s WHERE last_ts>=? AND first_ts<? AND plaka NOT IN "
                    "(SELECT plaka FROM stints WHERE last_ts>=? AND first_ts<?) GROUP BY plaka ORDER BY MAX(last_ts) DESC",
                    (ps, pe, start, end)).fetchall()
            finally:
                conn.close()
            if lost and start >= 0:
                chips = "".join(
                    f'<a href="/?q={urllib.parse.quote(a or p_)}&tarih={day.isoformat()}">{esc(a or E.pretty_plate(p_))} '
                    f'<span class="muted">hat {esc(h)} · son {fmt(t, True)}</span></a>' for p_, a, t, h in lost[:300])
                body += (f'<div class="card"><b>Önceki gün görülüp bu gün görülmeyen</b> '
                         f'<span class="muted">{len(lost)} araç (hizmet dışı, yedek, arıza veya veri yok olabilir)</span>'
                         f'<div class="hatrow">{chips}</div></div>')
        for h in sorted(by_hat, key=natural_key):
            items = sorted(by_hat[h])
            links = "".join(
                f'<a href="/?q={urllib.parse.quote(arac or plaka)}&tarih={day.isoformat()}" title="{esc(E.pretty_plate(plaka))}">'
                f'{esc(arac or E.pretty_plate(plaka))} <span class="muted">{fmt(a)}–{fmt(b)}</span></a>'
                for a, plaka, arac, b in items)
            body += (f'<div class="card"><b>Hat {esc(h)}</b> <span class="muted">{esc(names.get(h, ""))} · {len(items)} araç</span>'
                     f'<div class="hatrow">{links}</div></div>')
        return layout("/gun", body + ('<i data-live="120" hidden></i>' if day == today() else ""), "Gün özeti · EGO Filo Takip")

    # ------------------------------------------------------------------ Raporlar
    def page_raporlar(g, msg=""):
        files = []
        if os.path.isdir(E.REPORT_DIR):
            for f in sorted(os.listdir(E.REPORT_DIR), reverse=True):
                if f.endswith(".csv"):
                    files.append((f, os.path.getsize(os.path.join(E.REPORT_DIR, f))))
        dun = (today() - timedelta(days=1)).isoformat()
        form = ('<form class="card form two" method="get" action="/rapor-uret">'
                f'<div class="field"><label>Rapor tarihi</label><input type="date" name="tarih" value="{dun}"></div>'
                '<div></div><button class="btn">Raporu üret</button></form>')
        rows = "".join(f'<tr><td><a href="/rapor/{esc(urllib.parse.quote(f))}">{esc(f)}</a></td>'
                       f'<td>{round(s / 1024, 1)} KB</td></tr>' for f, s in files[:200])
        table = (f'<div class="card"><table><thead><tr><th>Dosya</th><th>Boyut</th></tr></thead><tbody>{rows}</tbody></table></div>'
                 if files else '<div class="card empty">Henüz rapor yok. Her gece yarısı önceki günün raporu otomatik yazılır.</div>')
        if g("uretildi"):
            msg = f"Rapor üretildi ({g('uretildi')} araç)."
        body = "<h1>Raporlar</h1>" + (note(msg, "info") if msg else "") + form + table
        body += f'<p class="muted">Klasör: {esc(E.REPORT_DIR)}</p>'
        return layout("/raporlar", body, "Raporlar · EGO Filo Takip")

    # ------------------------------------------------------------------ Durum
    def page_durum(g):
        conn = E.connect()
        try:
            last = conn.execute("SELECT v FROM meta WHERE k='last_cycle'").fetchone()
            first = conn.execute("SELECT v FROM meta WHERE k='first_data_ts'").fetchone()
            n_veh = conn.execute("SELECT COUNT(DISTINCT plaka) FROM stints").fetchone()[0]
            n_sight = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM sightings").fetchone()[0]
            n_lines = conn.execute("SELECT COUNT(DISTINCT hat) FROM line_route").fetchone()[0]
            n_cat = conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0]
        finally:
            conn.close()
        c = json.loads(last[0]) if last else None
        try:
            mb = round(os.path.getsize(getattr(E.CITY_CTX, "db", None) or E.DB_PATH) / 1048576, 1)
        except OSError:
            mb = 0
        days = max(1, round((E.now_ts() - int(first[0])) / 86400, 1)) if first else 0
        cells = [
            (fmt(c["ts"], True) if c else "-", "Son tarama turu"),
            (f'{c["due"]} hat · {c["vehicles"]} araç' if c else "-", "Son turda sorgulanan / yakalanan"),
            (str(c["fails"]) if c else "-", "Son turdaki hata"),
            (f'{c["interval"]:g} dk' if c else "-", "Tarama aralığı"),
            (fmt(int(first[0]), True) if first else "-", "Kayıt başlangıcı"),
            (f"{days} gün" if first else "-", "Toplam kayıt süresi"),
            (f"{n_veh:,}".replace(",", "."), "Görülen farklı araç"),
            (f"{n_sight:,}".replace(",", "."), "Ham gözlem (yaklaşık)"),
            (f"{n_lines}/{n_cat}", "Rotası bilinen hat"),
            (f"{mb} MB", "Veritabanı boyutu"),
        ]
        grid = "".join(f"<div><b>{esc(v)}</b><span>{esc(k)}</span></div>" for v, k in cells)
        pr = progress_info()
        bar = ""
        if pr:
            gecen = max(1, E.now_ts() - pr["t0"])
            kalan = int(gecen * (pr["total"] - pr["n"]) / max(1, pr["n"]) / 60)
            bar = (f'<div class="card"><div class="vhead"><b>Tarama sürüyor</b><span class="muted">%{pr["pct"]} · {pr["n"]}/{pr["total"]} hat · '
                   f'{pr["veh"]} araç · {pr["fails"]} hata · yaklaşık {kalan} dk kaldı</span></div>'
                   f'<div style="height:12px;border-radius:8px;background:var(--line);overflow:hidden"><div style="height:100%;width:{pr["pct"]}%;background:var(--ok,#2e9e5b)"></div></div></div>')
        body = ("<h1>Durum</h1>" + bar + f'<div class="card"><div class="kv">{grid}</div></div>'
                '<div class="dnav"><a href="/raporlar">Günlük raporlar</a><a href="/sehir">Şehir değiştir</a></div>'
                f'<p class="muted">Veritabanı: {esc(getattr(E.CITY_CTX, "db", None) or E.DB_PATH)}</p>')
        return layout("/durum", body + '<i data-live="30" hidden></i>', "Durum · EGO Filo Takip")


    # ------------------------------------------------------------------ Harita
    _arac_cache = {}

    def _doldur_bir_kez():
        for _c, _p in CITY_DB.items():
            if os.path.exists(_p):
                try:
                    _cn = E.sqlite3.connect(_p, timeout=60)
                    _cn.executescript(E.SCHEMA)
                    E.arac_son_doldur(_cn)
                    _cn.close()
                except Exception:
                    pass
        try:
            _cn = E.connect()
            E.arac_son_doldur(_cn)
            _cn.close()
        except Exception:
            pass
    import threading as _th
    _th.Thread(target=_doldur_bir_kez, daemon=True).start()

    def api_araclar(g):
        try:
            saat = max(1, min(168, int(g("saat", "24"))))
        except ValueError:
            saat = 24
        ck = (cur_city(), saat)
        hit = _arac_cache.get(ck)
        if hit and time.time() - hit[0] < 5:
            return hit[1]  # aynı anda açılan haritalar tek sorguyu paylaşır
        body = _api_araclar(saat)
        _arac_cache[ck] = (time.time(), body)
        return body

    def _api_araclar(saat):
        since = E.now_ts() - saat * 3600
        conn = E.connect()
        yon = {}
        try:
            rows = conn.execute("SELECT plaka, arac_no, hat, lat, lng, hiz, sira, COALESCE(kts, ts), plat, plng FROM arac_son "
                                "WHERE ts>=? AND lat<>0", (since,)).fetchall()
            if rows:
                route = {(h, sr): ad for h, sr, ad in conn.execute("SELECT hat, sira, ad FROM line_route")}
                for pl_, _a, _h, la_, lo_, _v, _s, _t, pla, plo in rows:
                    if pla is not None and plo is not None:
                        dy, dx = (la_ - pla) * 111320, (lo_ - plo) * 111320 * math.cos(math.radians(la_))
                        yon[pl_] = int((math.degrees(math.atan2(dx, dy)) + 360) % 360)
                rows = [r[:8] for r in rows]
            else:  # arac_son henüz dolmadıysa eski (yavaş) yol
                rows = conn.execute(
                    "SELECT plaka, arac_no, hat, lat, lng, hiz, sira, MAX(COALESCE(kts, ts)) FROM sightings "
                    "WHERE ts>=? AND lat IS NOT NULL AND lng IS NOT NULL AND lat<>0 GROUP BY plaka", (since,)).fetchall()
                route = {(h, sr): ad for h, sr, ad in conn.execute("SELECT hat, sira, ad FROM line_route")}
        finally:
            conn.close()
        now = E.now_ts()
        mdb, tips = _db_models(), _tips()
        ops = {}
        try:
            conn = E.connect()
            try:
                ops = dict(conn.execute("SELECT arac_no, operator FROM arac_operator").fetchall())
            finally:
                conn.close()
        except Exception:
            ops = {}
        out = []
        for plaka, arac, hat, lat, lng, hiz, sira, t in rows:
            out.append({"p": E.pretty_plate(plaka), "f": arac or "", "h": hat, "la": lat, "lo": lng,
                        "v": hiz, "d": route.get((hat, sira), "") if sira is not None else "",
                        "t": fmt(t, True), "age": int((now - t) / 60), "m": model_for(arac, plaka, mdb)[0],
                        "tp": _tip_of(tips, arac, plaka), "yn": yon.get(plaka), "sr": sira, "op": ops.get(arac or "", "")})
        return json.dumps({"n": len(out), "araclar": out}, ensure_ascii=False)

    def api_foto(g):
        conn = E.connect()
        try:
            for k in (E.norm(g("f")), E.norm(g("p"))):
                if not k:
                    continue
                try:
                    r = conn.execute("SELECT img, post, yazar FROM arac_foto WHERE anahtar=?", (k,)).fetchone()
                except Exception:
                    r = None
                if r:
                    return json.dumps({"img": r[0], "post": r[1], "yazar": r[2]}, ensure_ascii=False)
        finally:
            conn.close()
        return json.dumps({})

    def _gun_tipi():
        wd = datetime.now(E.TZ).weekday()
        return "pazar" if wd == 6 else "cumartesi" if wd == 5 else "haftaici"

    def _sure_dk(t):
        m = re.findall(r"\d+", t or "")
        if not m:
            return 0
        if ":" in (t or "") and len(m) >= 2:
            return int(m[0]) * 60 + int(m[1])
        return int(m[0])

    def api_arac_iz(g):
        """Seçili aracın bugünkü seferleri ve iz noktaları (harita yan paneli için)."""
        q = g("q")
        if not q:
            return json.dumps({"seferler": []})
        conn = E.connect()
        try:
            res = E.query_day(conn, q, today())
            planli = {}
            for tr_ in (res["vehicles"][0]["trips"] if res["vehicles"] else []):
                h_ = tr_["hat"]
                if h_ in planli:
                    continue
                base = h_.split(" ")[0]
                try:
                    tm = [r[0] for r in conn.execute("SELECT saat FROM line_times WHERE hat IN (?,?) AND gun=? ORDER BY saat", (h_, base, _gun_tipi()))]
                    inf = conn.execute("SELECT sure FROM line_info WHERE hat IN (?,?)", (h_, base)).fetchone()
                except Exception:
                    tm, inf = [], None
                planli[h_] = (tm, _sure_dk(inf[0]) if inf else 0)
        finally:
            conn.close()
        out = []
        v = res["vehicles"][0] if res["vehicles"] else None
        for tr in (v["trips"] if v else []):
            pts = [[round(x["lat"], 5), round(x["lng"], 5), fmt(x["t"], False), x.get("hiz") or "", x.get("sira")]
                   for x in tr["samples"] if x["lat"] and x["lng"]]
            if pts:
                t0 = fmt(tr["samples"][0]["t"], False)
                tm, sure = planli.get(tr["hat"], ([], 0))
                pl = ""
                if tm:
                    dk = lambda x: int(x[:2]) * 60 + int(x[3:5])
                    try:
                        pl = min(tm, key=lambda x: abs(dk(x) - dk(t0)))
                        if abs(dk(pl) - dk(t0)) > 40:
                            pl = ""
                    except ValueError:
                        pl = ""
                hm_ = lambda m: "%02d:%02d" % ((m // 60) % 24, m % 60)
                try:
                    pv = hm_(int(pl[:2]) * 60 + int(pl[3:5]) + sure) if pl and sure else ""
                    ev = hm_(int(t0[:2]) * 60 + int(t0[3:5]) + sure) if sure else ""
                except ValueError:
                    pv = ev = ""
                out.append({"h": tr["hat"], "ad": tr.get("ad", ""), "t0": t0,
                            "t1": fmt(tr["samples"][-1]["t"], False), "p": pts, "pl": pl, "pv": pv, "ev": ev})
        return json.dumps({"seferler": out}, ensure_ascii=False)

    def api_hat_rota(g):
        """Hattın durak sırasına göre rotası: [[enlem, boylam, sira, ad]]; konumu bilinen duraklar."""
        hat = g("hat")
        if not hat:
            return json.dumps({"rota": []})
        conn = E.connect()
        try:
            rows = conn.execute("SELECT sira, durak, ad FROM line_route WHERE hat=? ORDER BY sira", (hat,)).fetchall()
            hat_ad = (conn.execute("SELECT ad FROM lines WHERE hat=?", (hat,)).fetchone() or [""])[0] or ""
            pos = {d: (la, lo) for d, la, lo in conn.execute("SELECT durak, lat, lng FROM stop_pos")}
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stops_geo'").fetchone():
                for d, la, lo in conn.execute("SELECT durak, lat, lng FROM stops_geo"):
                    pos[d] = (la, lo)  # resmi koordinat tahminin önüne geçer
        finally:
            conn.close()
        rota = [[round(pos[d][0], 5), round(pos[d][1], 5), sr, ad or ""] for sr, d, ad in rows if d in pos and pos[d][0]]
        return json.dumps({"rota": rota, "ad": hat_ad}, ensure_ascii=False)

    CANLI_CACHE = {}

    def api_canli(g):
        hat = g("hat")
        hit = CANLI_CACHE.get(hat)
        if hit and time.time() - hit[0] < 12:  # çok izleyici olsa da EGO'ya hat başına ~12 sn'de bir istek
            return hit[1]
        out = api_canli_raw(g)
        CANLI_CACHE[hat] = (time.time(), out)
        if len(CANLI_CACHE) > 300:
            CANLI_CACHE.clear()
        return out

    def api_canli_raw(g):
        hat = g("hat")
        conn = E.connect()
        try:
            ok = conn.execute("SELECT 1 FROM lines WHERE hat=?", (hat,)).fetchone()
            stops = [r[0] for r in conn.execute("SELECT durak FROM line_stops WHERE hat=? LIMIT 6", (hat,))]
            route = {sr: ad for sr, ad in conn.execute("SELECT sira, ad FROM line_route WHERE hat=?", (hat,))}
        finally:
            conn.close()
        if not ok or not stops:
            return json.dumps({"hata": "hat bulunamadı", "araclar": []})
        http = E.Http(False)
        rows = None
        for st in stops[:2]:
            rows = live_rows(http, "Otobus", HAT=hat, DURAK=st)
            if rows is not None:
                break
        if rows is None:
            return json.dumps({"hata": "EGO cevap vermedi", "araclar": []})
        now = E.now_ts()
        out = []
        for r in rows:
            if not E.is_live(r):
                continue
            la, lo = E.to_float(E.sv(r, "lat")), E.to_float(E.sv(r, "lng"))
            if not la or not lo:
                continue
            kts = E.parse_konum(E.sv(r, "konum_tarihi")) or now
            try:
                sira = int(E.sv(r, "durak_sira_no"))
            except ValueError:
                sira = None
            out.append({"p": E.sv(r, "plaka_no"), "f": E.sv(r, "arac_no"), "h": hat, "la": la, "lo": lo,
                        "v": E.sv(r, "hiz"), "d": route.get(sira, "") if sira is not None else "",
                        "a": route.get(sira - 1, "") if sira is not None else "", "s": sira, "dl": E.parse_dol(r) or "",
                        "t": fmt(kts, True), "age": max(0, int((now - kts) / 60)), "m": model_for(E.sv(r, "arac_no"), E.sv(r, "plaka_no"))[0]})
        return json.dumps({"araclar": out}, ensure_ascii=False)

    def api_duraklar(g):
        try:
            s_, w_, n_, e_ = (float(g(k)) for k in ("s", "w", "n", "e"))
        except ValueError:
            return json.dumps({"duraklar": []})
        conn = E.connect()
        try:
            if cur_city() in CITY_DB:  # resmi durak koordinatları (n=0 → kesin)
                rows = conn.execute(
                    "SELECT g.durak, g.lat, g.lng, 0, g.ad, '' FROM stops_geo g "
                    "WHERE g.lat BETWEEN ? AND ? AND g.lng BETWEEN ? AND ? LIMIT 400", (s_, n_, w_, e_)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT p.durak, p.lat, p.lng, p.n, (SELECT ad FROM line_route r WHERE r.durak=p.durak AND r.ad<>'' LIMIT 1), "
                    "(SELECT adres FROM stop_info i WHERE i.durak=p.durak) FROM stop_pos p "
                    "WHERE p.lat BETWEEN ? AND ? AND p.lng BETWEEN ? AND ? LIMIT 400", (s_, n_, w_, e_)).fetchall()
            out = []
            for d, la, lo, n, ad, adres in rows:
                hats = [r[0] for r in conn.execute("SELECT hat FROM line_stops WHERE durak=? LIMIT 40", (d,))]
                out.append({"d": d, "la": round(la, 5), "lo": round(lo, 5), "n": n, "ad": ad or "", "adres": adres or "",
                            "h": sorted(hats, key=natural_key)})
        finally:
            conn.close()
        return json.dumps({"duraklar": out}, ensure_ascii=False)

    MAP_JS = """
(function(){
var map=L.map('map',{preferCanvas:true}).setView(__MERKEZ__);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap'}).addTo(map);
var layer=(L.markerClusterGroup?L.markerClusterGroup({disableClusteringAtZoom:15,maxClusterRadius:45,showCoverageOnHover:false,chunkedLoading:true}):L.layerGroup()).addTo(map),data=[];
if(!layer.addLayers){layer.addLayers=function(a){a.forEach(function(x){layer.addLayer(x);});};layer.zoomToShowLayer=function(m,f){f();};}
function $(i){return document.getElementById(i);}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]});}
function op(a){return String(a.p||'').replace(/\\s/g,'').toUpperCase().indexOf('06HO')===0?'oho':'ego';}
var BUS_SVG='<svg viewBox="0 0 20 38" style="width:calc(__S__ * 20px);height:calc(__S__ * 38px);transform:rotate(__R__deg)"><rect class="bb" x="2" y="1" width="16" height="36" rx="5"/><rect class="bw" x="4.5" y="3.5" width="11" height="6" rx="2"/><rect class="bw" x="4.5" y="12" width="11" height="3"/><rect class="bw" x="4.5" y="17" width="11" height="3"/><rect class="bw" x="4.5" y="22" width="11" height="3"/><rect class="bw" x="4.5" y="29" width="11" height="4" rx="1.5"/></svg>';
function zc(z){return z<11?0:z<13?1:z<14?2:3;}var lastZ=-1;
var panel=$('panel'),trail=L.layerGroup().addTo(map),selM=null,selA=null,tcols=['#c8102e','#1d4ed8','#15803d','#b45309','#7c3aed','#0e7490'];
function bearing(a,b){var r=Math.PI/180,y=Math.sin((b[1]-a[1])*r)*Math.cos(b[0]*r),x=Math.cos(a[0]*r)*Math.sin(b[0]*r)-Math.sin(a[0]*r)*Math.cos(b[0]*r)*Math.cos((b[1]-a[1])*r);return (Math.atan2(y,x)/r+360)%360;}
function statusOf(a){return a.age<=15?'<span class="fr-live">● canlı</span>':'<span class="fr-off">● '+(a.age<120?a.age+' dk önce':'son bilinen konum')+'</span>';}
function head(a){
 return '<div class="fr-plate">'+esc(a.p)+'</div><span class="fr-chips2"><span class="c1">'+esc(a.f||'-')+'</span>'+(a.tp?'<span class="c2">'+esc(a.tp)+'</span>':'')+'</span><div class="fr-opr">'+(a.m?esc(a.m)+' · ':'')+'Hat '+esc(a.h)+'</div>';
}
function info(a){
 function kv(l,v,w){return '<div'+(w?' class="w"':'')+'><small>'+l+'</small><b>'+v+'</b></div>';}
 var yn=a.yn==null?'-':a.yn+'°';
 return kv('Model',a.m?esc(a.m)+' ~':'-',1)+kv('Plaka',esc(a.p))+kv('Filo kodu',esc(a.f||'-'))+(a.op?kv('İşletmeci',esc(a.op),1):'')+kv('Hız',esc(a.v||0)+' km/sa')+kv('Yön',yn)+kv('Durum',statusOf(a))+kv('Son görülme',esc(String(a.t).slice(-11)))+(a.d?kv('Yöneldiği durak',esc(a.d),1):'');
}
function upd(a){var h=panel.querySelector('.fr-head'),i=panel.querySelector('.fr-info'),n=panel.querySelector('.led-next');if(n)n.textContent=a.d||'—';if(h)h.innerHTML=head(a);if(i)i.innerHTML=info(a);}
function sec(t,h,o){return '<button class="pc-sec" aria-expanded="'+(o?'true':'false')+'">'+t+'</button><div class="pc-body"'+(o?'':' hidden')+'>'+h+'</div>';}
var LEDF={A:[14,17,17,31,17,17,17],B:[30,17,17,30,17,17,30],C:[14,17,16,16,16,17,14],D:[30,17,17,17,17,17,30],E:[31,16,16,30,16,16,31],F:[31,16,16,30,16,16,16],G:[14,17,16,23,17,17,15],H:[17,17,17,31,17,17,17],I:[14,4,4,4,4,4,14],J:[7,2,2,2,2,18,12],K:[17,18,20,24,20,18,17],L:[16,16,16,16,16,16,31],M:[17,27,21,21,17,17,17],N:[17,25,21,19,17,17,17],O:[14,17,17,17,17,17,14],P:[30,17,17,30,16,16,16],Q:[14,17,17,17,21,18,13],R:[30,17,17,30,20,18,17],S:[15,16,16,14,1,1,30],T:[31,4,4,4,4,4,4],U:[17,17,17,17,17,17,14],V:[17,17,17,17,17,10,4],W:[17,17,17,21,21,21,10],X:[17,17,10,4,10,17,17],Y:[17,17,17,10,4,4,4],Z:[31,1,2,4,8,16,31],
'0':[14,17,19,21,25,17,14],'1':[4,12,4,4,4,4,14],'2':[14,17,1,2,4,8,31],'3':[31,2,4,2,1,17,14],'4':[2,6,10,18,31,2,2],'5':[31,16,30,1,1,17,14],'6':[6,8,16,30,17,17,14],'7':[31,1,2,4,8,8,8],'8':[14,17,17,14,17,17,14],'9':[14,17,17,15,1,2,12],
'.':[0,0,0,0,0,12,12],'-':[0,0,0,31,0,0,0],'/':[1,1,2,4,8,16,16],"'":[4,4,8,0,0,0,0],',':[0,0,0,0,12,4,8],' ':[0,0,0,0,0,0,0]};
var LEDX={'Ç':['C',[0,0],4],'Ş':['S',[0,0],4],'Ğ':['G',[10,4],0],'İ':['I',[0,4],0],'Ö':['O',[0,10],0],'Ü':['U',[0,10],0]};
function ledGlyph(ch){var x=LEDX[ch];if(x)return {rows:LEDF[x[0]],acc:x[1],tail:x[2]};return {rows:LEDF[ch]||LEDF[' '],acc:[0,0],tail:0};}
function ledBits(text,scale){ // [rows][cols] kutusu: 2 aksan + 7 harf + 1 kuyruk satırı, ölçekle
 var cell=[],cols=0,gl=[],i;for(i=0;i<text.length;i++){gl.push(ledGlyph(text[i]));}
 var W=gl.length*6*scale,H=10*scale,out=[],r,c;for(r=0;r<H;r++){out.push(new Uint8Array(W));}
 gl.forEach(function(g,gi){var rows=[g.acc[0],g.acc[1]].concat(g.rows).concat([g.tail]);
  rows.forEach(function(bits,ri){for(var cb=0;cb<5;cb++){if(bits&(16>>cb)){for(var sy=0;sy<scale;sy++)for(var sx=0;sx<scale;sx++){out[ri*scale+sy][(gi*6+cb)*scale+sx]=1;}}}});});
 return {b:out,w:W,h:H};
}
function ledStil(m){var T=window.TABELA||{},d=T.varsayilan||{arka:'#050505',no:'#ff9a1a',ust:'#ff9a1a',alt:'#ff9a1a',iki_satir:true,nokta:3},x=String(m||'').toLowerCase(),r=d;
 (T.modeller||[]).some(function(k){if(k.eslesen&&x.indexOf(String(k.eslesen).toLowerCase())>=0){r=Object.assign({},d,k);return true;}return false;});return r;}
function pulSegs(t){return String(t||'').replace(/\\(([^)]*)\\)/g,function(m){return m.replace(/[-–]/g,' ');}).replace(/\\(/g,' (').split(/\\s*[-–]\\s*/).map(function(x){return x.replace(/\\s+/g,' ').trim();}).filter(Boolean);}
function startLed(a,hat,l1,l2,adi){
 var box=panel.querySelector('.led'),cv=box&&box.querySelector('canvas');if(!cv)return;
 cancelAnimationFrame(panel._ledR);
 var st=ledStil(a.m),p=st.nokta||3,hs0=(hat||'').split('-')[0];
 if(st.pul){var Lw=0;pulSegs(adi||l2||l1||'').forEach(function(sg){sg.split(' ').forEach(function(x){Lw=Math.max(Lw,x.length);});});
  var cap=function(pp){var cc=Math.floor(box.clientWidth/pp),n1=hs0.length*6;return Math.floor((cc-(2+n1+3)-1)/6);};
  while(p>2&&cap(p)<Lw)p--;}
 var cols=Math.floor(box.clientWidth/p),rows=24,dpr=window.devicePixelRatio||1,ctx=cv.getContext('2d');
 cv.style.width=cols*p+'px';cv.style.height=rows*p+'px';cv.width=cols*p*dpr;cv.height=rows*p*dpr;box.style.background=st.arka;
 var hs=(hat||'').split('-')[0],ns=(st.pul||hs.length>3)?1:2,nb=ledBits(hs,ns),nx=2,tx=nx+nb.w+3,tw=Math.max(8,cols-tx-1);
 var L1=ledBits(l1||'',1),L2=ledBits(l2||'',1),two=st.iki_satir&&l1;
 var pulPages=null;if(st.pul){var mc=Math.max(4,Math.floor(tw/6)),segs=pulSegs(adi||l2||l1||''),pgs=[],pg=[];
  function wrapSeg(t){var us=[];t.replace(/(\\S)-(?=\\S)/g,'$1- ').split(/\\s+/).forEach(function(w){if(!w)return;if(us.length&&/^[A-ZÇĞİÖŞÜ]{1,4}\\.$/.test(w))us[us.length-1].push(w);else us.push([w]);});
   var ps=[];us.forEach(function(u){var j=u.join(' ');if(j.length<=mc)ps.push(j);else u.forEach(function(x){ps.push(x);});});
   var out=[],cur='';ps.forEach(function(w){while(w.length>mc){if(cur){out.push(cur);cur='';}out.push(w.slice(0,mc));w=w.slice(mc);}
    var cj=cur+(cur.slice(-1)==='-'?'':' ')+w;if(!cur)cur=w;else if(cj.length<=mc)cur=cj;else{out.push(cur);cur=w;}});if(cur)out.push(cur);return out;}
  segs.forEach(function(sg){var ls=wrapSeg(sg);if(pg.length&&pg.length+ls.length>2){pgs.push(pg);pg=[];}
   ls.forEach(function(l){if(pg.length>=2){pgs.push(pg);pg=[];}pg.push(l);});});
  if(pg.length)pgs.push(pg);
  pulPages=pgs.map(function(p){return [ledBits(p[0]||'',1),ledBits(p[1]||'',1)];});if(!pulPages.length)pulPages=[[ledBits('',1),ledBits('',1)]];}
 var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches,t0=performance.now(),gap=10,last=-1;
 function lit(bits,r,c){return bits&&r>=0&&r<bits.length&&bits[r][c]?1:0;}
 function smp(L,rr,cc,o){if(!L.w||rr<0||rr>=L.h)return 0;var x=cc+o;if(L.w>tw){x=x%(L.w+gap);}if(x>=L.w)return 0;return L.b[rr][x]?1:0;}
 function pulCol(pi,r,c){if(c>=nx&&c<nx+nb.w){var nr=r-Math.floor((rows-nb.h)/2);return lit(nb.b,nr,c-nx)?st.no:null;}
  if(c>=tx&&c<tx+tw){var P=pulPages[pi],cc=c-tx;if(P[0].w&&r>=1&&r-1<P[0].h&&cc<P[0].w&&P[0].b[r-1][cc])return st.ust;if(P[1].w&&r>=12&&r-12<P[1].h&&cc<P[1].w&&P[1].b[r-12][cc])return st.alt;}
  return null;}
 function colOff(L,t){if(L.w<=tw||reduce)return 0;var step=Math.max(0,Math.floor((t-t0-1800)/80));return step%(L.w+gap);}
 function frame(now){
  if(!panel.contains(cv)||selA!==a)return;
  var o1=colOff(L1,now),o2=colOff(L2,now),key=o1*10007+o2;
  var PG=3600,pi=0,pv=-1,tr=1e9;
  if(pulPages){var el=Math.max(0,now-t0);pi=Math.floor(el/PG)%pulPages.length;var since=el%PG;tr=since;
   pv=(pi===0&&el<PG)?-1:(pi-1+pulPages.length)%pulPages.length;if(pulPages.length===1&&el>=PG)pv=pi;
   o1=0;o2=0;key=pi*100000+(since<1100&&!reduce?Math.floor(since/40):99999);}
  var fl=pulPages&&!reduce&&tr<1100;
  if(key!==last){last=key;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,cols*p,rows*p);
   var unl=st.arka==='#050505'?'rgba(255,255,255,.045)':'rgba(255,255,255,.05)',R=p*0.42,r,c;
   for(r=0;r<rows;r++)for(c=0;c<cols;c++){var col=null;
    var nr=r-Math.floor((rows-nb.h)/2);if(c>=nx&&c<nx+nb.w&&lit(nb.b,nr,c-nx))col=st.no;
    else if(c>=tx&&c<tx+tw){var cc=c-tx;
     if(two){if(smp(L1,r-1,cc,o1))col=st.ust;if(smp(L2,r-12,cc,o2))col=st.alt;}
     else if(smp(L2,r-7,cc,o2))col=st.alt;}
    var x=c*p+p/2,y=r*p+p/2;
    if(st.pul){var pc=pulCol(pi,r,c),pp=pv<0?null:pulCol(pv,r,c),hr=Math.abs((Math.sin(c*12.9898+r*78.233)*43758.5453)%1),ph=(fl&&(pc!==pp))?Math.max(0,Math.min(1,(tr-hr*700)/300)):1,sx=Math.abs(Math.cos(ph*Math.PI)),on=ph>=.5?pc:pp;
     ctx.fillStyle='#0b0d09';ctx.beginPath();ctx.arc(x,y,p*.5,0,6.3);ctx.fill();
     ctx.fillStyle=on||'#15190f';ctx.beginPath();ctx.ellipse(x,y,Math.max(.4,R*1.08*sx),R*1.08,0,0,6.3);ctx.fill();
     if(on&&sx>.8){ctx.fillStyle='rgba(255,255,255,.12)';ctx.beginPath();ctx.arc(x-R*.25,y-R*.3,R*.35,0,6.3);ctx.fill();}}
    else if(col){ctx.fillStyle=col;ctx.globalAlpha=.22;ctx.beginPath();ctx.arc(x,y,R*1.9,0,6.3);ctx.fill();ctx.globalAlpha=1;ctx.beginPath();ctx.arc(x,y,R,0,6.3);ctx.fill();}
    else{ctx.fillStyle=unl;ctx.beginPath();ctx.arc(x,y,R*.8,0,6.3);ctx.fill();}}}
  panel._ledR=requestAnimationFrame(frame);
 }
 panel._ledR=requestAnimationFrame(frame);
}
function routeBlock(a){
 getRota(a.h).then(function(rota){
  var bx=panel.querySelector('.pc-rt'),pg=panel.querySelector('.pc-pg');if(selA!==a||!bx||!rota||rota.length<2){if(bx)bx.style.display='none';return;}
  var f=rota[0],l=rota[rota.length-1];function cd(n){return String(n||'?').slice(0,3).toLocaleUpperCase('tr');}
  var TR=function(x){return String(x||'').toLocaleUpperCase('tr');};
  bx.innerHTML='<div class="led"><canvas></canvas></div><div class="led-sub"><span>Sıradaki durak</span><b class="led-next">'+esc(a.d||'—')+'</b></div>';
  startLed(a,TR(a.h),TR(f[3]||''),TR(l[3]||''),TR(rota.ad||''));
  if(a.sr!=null&&l[2]>f[2]){var fr=Math.max(0,Math.min(1,(a.sr-f[2])/(l[2]-f[2])))*100;
   pg.innerHTML='<div class="bar2"><i style="width:'+fr.toFixed(0)+'%"></i></div><div class="pr"><span>'+a.sr+'. durak</span><span>%'+fr.toFixed(0)+' · toplam '+rota.length+' durak</span></div>';}
 });
}
function closePanel(){cancelAnimationFrame(panel._ledR);panel.style.display='none';trail.clearLayers();if(selM&&selA){styleOf(selM,selA,false);}selM=selA=null;}
function styleOf(m,a,on){var live=a.age<=15;m.setStyle(on?{radius:10,color:'#fff',weight:3,fillColor:'#c8102e',fillOpacity:1}:{radius:live?7:5,color:live?'#166534':'#6b7280',fillColor:live?'#22c55e':'#9ca3af',fillOpacity:live?.9:.6,weight:1});}
var rotaCache={};
function getRota(h){
 if(rotaCache[h])return Promise.resolve(rotaCache[h]);
 return fetch('/api/hat_rota?hat='+encodeURIComponent(h)).then(function(r){return r.json()}).then(function(j){var r=j.rota||[];r.ad=j.ad||'';return (rotaCache[h]=r);}).catch(function(){return [];});
}
function drawTrip(t,i,rota){
 trail.clearLayers();
 var c=tcols[i%tcols.length],ll=t.p.map(function(x){return [x[0],x[1]];}),sr=t.p.map(function(x){return x[4];}).filter(function(v){return v!=null&&v!=='';}),seg=[];
 if(rota&&rota.length&&sr.length){var lo=Math.min.apply(null,sr)-1,hi=Math.max.apply(null,sr);seg=rota.filter(function(r){return r[2]>=lo&&r[2]<=hi;}).map(function(r){return [r[0],r[1]];});}
 var real=seg.length>=2,line=real?seg:ll;
 L.polyline(line,{color:c,weight:5,opacity:.85,dashArray:real?null:'2 8'}).addTo(trail).bindTooltip('Sefer '+(i+1)+' · Hat '+esc(t.h)+(real?' · hat güzergâhı':' · gözlem noktaları'));
 t.p.forEach(function(x){L.circleMarker([x[0],x[1]],{radius:3,color:'#fff',weight:1,fillColor:c,fillOpacity:1}).addTo(trail).bindTooltip(esc(x[2])+(x[3]?' · '+esc(x[3])+' km/sa':''));});
 if(ll.length>1){var br=bearing(ll[ll.length-2],ll[ll.length-1]);L.marker(ll[ll.length-1],{icon:L.divIcon({className:'fr-arrow',html:'<div style="transform:rotate('+br+'deg)">▲</div>',iconSize:[22,22]}),interactive:false,keyboard:false}).addTo(trail);}
 return {pts:line.concat(ll),real:real};
}
function openPanel(a,m){
 if(selM&&selA&&selM!==m)styleOf(selM,selA,false);
 selM=m;selA=a;styleOf(m,a,true);m.bringToFront&&m.bringToFront();
 panel.style.display='flex';
 panel.innerHTML='<div class="pc-h"><button class="fr-x" aria-label="Kapat">×</button><div class="fr-head">'+head(a)+'</div></div><div class="pc-s"><div class="fr-photo"><div class="none">Fotoğraf aranıyor…</div></div><div class="pc-rt"></div><div class="pc-tm"></div><div class="pc-pg"></div>'+sec('Araç bilgisi','<div class="fr-info kv2">'+info(a)+'</div>',true)+sec('Bugünkü seferler','<div class="fr-tabs"></div><div class="fr-tr muted">Seferler yükleniyor…</div>',true)+'</div><div class="pc-a"><button class="fr-rf">⟳ Anlık yenile</button><a href="/?q='+encodeURIComponent(a.f||a.p)+'">Sorgu sayfası →</a><span class="fr-rfs"></span></div>';
 panel.onclick=function(e){var t=e.target;if(t.classList&&t.classList.contains('pc-sec')){var o=t.getAttribute('aria-expanded')==='true';t.setAttribute('aria-expanded',!o);t.nextElementSibling.hidden=o;}};
 routeBlock(a);
 panel.querySelector('.fr-x').onclick=closePanel;
 panel.querySelector('.fr-rf').onclick=function(){refreshLive(a,m);};
 fetch('/api/foto?f='+encodeURIComponent(a.f||'')+'&p='+encodeURIComponent(a.p)).then(function(r){return r.json()}).then(function(j){
  if(selA!==a)return;var bx=panel.querySelector('.fr-photo');if(!bx)return;
  if(!j.img){bx.innerHTML='<div class="none">Bu araç için forumda fotoğraf bulunamadı.</div>';return;}
  bx.innerHTML='<img referrerpolicy="no-referrer" loading="lazy" alt="'+esc(a.p)+'" src="'+esc(j.img)+'"><div class="cr">© '+esc(j.yazar||'forum üyesi')+' · <a target="_blank" rel="noopener" href="'+esc(j.post)+'">forumda gör</a></div>';
  bx.querySelector('img').onerror=function(){bx.innerHTML='<div class="none">Fotoğraf yüklenemedi.</div>';};
 }).catch(function(){});
 fetch('/api/arac_iz?q='+encodeURIComponent(a.p)).then(function(r){return r.json()}).then(function(j){
  if(selA!==a)return;
  var tr=j.seferler||[],box=panel.querySelector('.fr-tr'),tabs=panel.querySelector('.fr-tabs');
  if(!tr.length){box.textContent='Bugün için sefer izi yok.';trail.clearLayers();return;}
  function pick(i){
   [].forEach.call(tabs.children,function(b,k){b.className=(k===i)?'on':'';});
   var t=tr[i];
   getRota(t.h).then(function(rota){
    if(selA!==a)return;
    var d=drawTrip(t,i,rota);
    (function(){var b=panel.querySelector('.pc-tm');if(!b)return;function c(l,v){return '<div>'+l+'<b>'+(v||'—')+'</b></div>';}b.innerHTML=c('Planlanan kalkış',t.pl)+c('Planlanan varış',t.pv)+c('Gözlenen kalkış',t.t0)+c('Tahmini varış',t.ev);})();
    box.innerHTML='<b>Sefer '+(i+1)+' · Hat '+esc(t.h)+'</b> <span class="muted">'+esc(t.ad||'')+'</span><br><span class="muted">'+esc(t.t0)+' – '+esc(t.t1)+' · '+t.p.length+' gözlem · '+(d.real?'hat güzergâhı gösteriliyor':'bu hat için güzergâh yok, gözlem noktaları gösteriliyor')+'</span>';
    var pts=d.pts.slice();pts.push([a.la,a.lo]);
    if(pts.length>1)map.fitBounds(pts,{padding:[60,60],maxZoom:15});
   });
  }
  tabs.innerHTML='';tr.forEach(function(t,i){var b=document.createElement('button');b.textContent='Sefer '+(i+1);b.title='Hat '+t.h+' · '+t.t0;b.onclick=function(){pick(i);};tabs.appendChild(b);});
  pick(tr.length-1);
 }).catch(function(){panel.querySelector('.fr-tr').textContent='Sefer izi alınamadı.';});
}
function refreshLive(a,m){
 var b=panel.querySelector('.fr-rf'),st=panel.querySelector('.fr-rfs');b.disabled=true;st.textContent=' alınıyor…';
 fetch('/api/canli?hat='+encodeURIComponent(a.h)).then(function(r){return r.json()}).then(function(j){
  var n=(j.araclar||[]).filter(function(x){return (a.f&&x.f===a.f)||(a.p&&x.p.replace(/ /g,'')===a.p.replace(/ /g,''));})[0];
  b.disabled=false;
  if(!n){st.textContent=j.hata?' '+j.hata:' araç şu an canlı listede yok';return;}
  Object.keys(n).forEach(function(k){a[k]=n[k];});
  layer.removeLayer(m);m.setLatLng([a.la,a.lo]);layer.addLayer(m);styleOf(m,a,true);
  upd(a);
  st.textContent=' güncellendi';map.panTo([a.la,a.lo]);
 }).catch(function(){b.disabled=false;st.textContent=' alınamadı';});
}
function draw(){
 var q=$('q').value.trim().toLowerCase(),hat=$('hat').value.trim().toLowerCase(),o=$('op').value,tp=$('tip').value;
 var onlyLive=$('live').checked,zl=map.getZoom();lastZ=zc(zl);
 layer.clearLayers();var shown=0,live=0,b=[],ms=[];
 data.forEach(function(a){
  var txt=(a.f+' '+a.p+' '+a.h+' '+(a.m||'')).toLowerCase();
  if(q&&txt.indexOf(q)<0)return;
  if(hat&&String(a.h).toLowerCase()!==hat)return;
  if(o&&op(a)!==o)return;
  if(tp&&(a.tp||'')!==tp)return;
  var isLive=a.age<=15; if(onlyLive&&!isLive)return;
  shown++; if(isLive)live++;
  var isSel=!!(selA&&a.p===selA.p),sc=zl<11?.55:zl<13?.75:1,m;
  m=L.marker([a.la,a.lo],{icon:L.divIcon({className:'',iconSize:[30,30],iconAnchor:[15,15],
   html:'<div class="bz'+(isLive?'':' off')+(isSel?' sel':'')+'">'+BUS_SVG.replace('__R__',a.yn==null?0:a.yn).replace('__S__',sc)+(zl>=14?'<span class="bl">'+esc(a.h)+'</span>':'')+'</div>'})});
  m.setStyle=function(st){var e=m.getElement&&m.getElement();if(e&&e.firstChild)e.firstChild.classList.toggle('sel',st.radius===10);return m;};
  m.on('click',function(){openPanel(a,m);});
  if(selA&&a.p===selA.p){selM=m;selA=a;styleOf(m,a,true);}
  ms.push(m); b.push([a.la,a.lo]);
 });
 layer.addLayers(ms);
 $('cnt').innerHTML='<b>'+shown+'</b> araç · <b>'+live+'</b> canlı';
 if(selA&&panel.style.display==='flex'){upd(selA);}
 if((q||hat)&&b.length&&b.length<=30)map.fitBounds(b,{maxZoom:15,padding:[40,40]});
}
map.on('zoomend',function(){if(zc(map.getZoom())!==lastZ&&data.length)draw();});
var stopLayer=L.layerGroup().addTo(map),stopKey='';
function loadStops(){
 if(map.getZoom()<15){stopLayer.clearLayers();stopKey='';return;}
 var b=map.getBounds(),k=[b.getSouth(),b.getWest(),b.getNorth(),b.getEast()].map(function(x){return x.toFixed(3);}).join(',');
 if(k===stopKey)return;stopKey=k;
 fetch('/api/duraklar?s='+b.getSouth()+'&w='+b.getWest()+'&n='+b.getNorth()+'&e='+b.getEast()).then(function(r){return r.json()}).then(function(j){
  stopLayer.clearLayers();
  (j.duraklar||[]).forEach(function(s){
   var m=L.circleMarker([s.la,s.lo],{radius:7,color:'#fff',weight:2,fillColor:'#1d4ed8',fillOpacity:.95,pane:'markerPane'});
   var hl=s.h.map(function(h){return '<a href="/hat?no='+encodeURIComponent(h)+'">'+esc(h)+'</a>';}).join(' · ');
   m.bindPopup('<b>'+esc(s.ad||'Durak')+'</b> &middot; '+esc(s.d)+(s.adres?'<br>'+esc(s.adres):'')+'<br>Hatlar: '+(hl||'-')+'<br><a href="/durak?no='+encodeURIComponent(s.d)+'">Yaklaşan araçlar</a><br><span style="opacity:.7;font-size:.8em">'+(s.n>0?'Konum araç verisinden tahminidir ('+s.n+' geçiş)':'Resmi durak konumu')+'</span>');
   m.addTo(stopLayer);
  });
 }).catch(function(){});
}
map.on('moveend',loadStops);
function load(){
 fetch('/api/araclar?saat='+$('saat').value).then(function(r){return r.json()}).then(function(j){data=j.araclar;draw();}).catch(function(){$('cnt').textContent='Veri alınamadı';});
}
['q','hat'].forEach(function(i){$(i).addEventListener('input',draw);});
['op','tip','live'].forEach(function(i){$(i).addEventListener('change',draw);});
$('saat').addEventListener('change',load);
$('ftog').onclick=function(){$('flt').classList.toggle('open');};
$('dFlt').onclick=$('ftog').onclick;$('dTema').onclick=function(){window.__temaDon&&window.__temaDon();};
$('full').onclick=function(){var w=$('frwrap'),on=!w.classList.contains('full');w.classList.toggle('full',on);document.body.style.overflow=on?'hidden':'';$('full').textContent=on?'✕ Tam ekrandan çık':'⛶ Tam ekran';setTimeout(function(){map.invalidateSize();},60);};
document.addEventListener('keydown',function(e){if(e.key==='Escape'){if($('frwrap').classList.contains('full'))$('full').onclick();else closePanel();}});
map.on('click',function(){});
var u=new URLSearchParams(location.search);if(u.get('q'))$('q').value=u.get('q');if(u.get('hat'))$('hat').value=u.get('hat');
load();loadStops();setInterval(function(){if(!document.hidden)load();},15000);
})();
"""

    FR_CSS = """<style>
#frwrap{position:relative}
#frwrap.full{position:fixed;inset:0;z-index:3000;background:var(--bg);padding:10px 12px;display:flex;flex-direction:column;gap:6px;overflow:auto}
#frwrap .fmap{position:relative}
#frwrap.full .fmap{flex:1;display:flex;min-height:0}
#frwrap.full .fmap #map{flex:1;height:auto!important;min-height:0}
.fr-bar{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:6px 2px 8px}
.fr-bar button{padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card,var(--bg));color:var(--ink);font:inherit;font-size:.85rem;cursor:pointer}
#panel{display:none;position:absolute;top:10px;right:10px;bottom:10px;width:330px;max-width:calc(100% - 20px);overflow:auto;z-index:1500;background:var(--card,#1a1d23);color:var(--ink);border:1px solid var(--line);border-radius:16px;padding:14px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
@media(max-width:700px){#panel{top:auto;left:8px;right:8px;bottom:8px;width:auto;max-height:52%}}
.fr-x{position:absolute;top:8px;right:10px;border:0;background:none;color:var(--ink);font-size:1.6rem;line-height:1;cursor:pointer}
.fr-plate{display:inline-block;font-weight:800;font-size:1.25rem;border:2px solid var(--ink);border-radius:8px;padding:2px 10px;letter-spacing:.04em;margin-right:30px}
.fr-chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.fr-chips span{font-size:.8rem;padding:3px 9px;border-radius:999px;border:1px solid var(--line)}
.fr-kv{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.fr-kv div{background:var(--bg);border-radius:10px;padding:8px;text-align:center}
.fr-kv b{display:block;font-size:.95rem}.fr-kv i{display:block;font-style:normal;font-size:.72rem;opacity:.65;margin-top:2px}
.fr-photo{margin:10px -14px 0;position:relative;background:#0a111c;min-height:96px}
.fr-photo img{display:block;width:100%;max-height:190px;object-fit:cover}
.fr-photo .cr{font-size:.72rem;padding:5px 12px;background:rgba(0,0,0,.55);color:#fff;position:absolute;left:0;right:0;bottom:0}
.fr-photo .cr a{color:var(--accent)}
.fr-photo .none{display:grid;place-items:center;height:96px;color:var(--muted);font-size:.78rem;text-align:center;padding:8px}
.fr-live{color:#22c55e}
#panel{padding:0!important;flex-direction:column;overflow:hidden!important;background:var(--card)!important;color:var(--ink)}
.pc-h{background:#1b2432;color:#fff;padding:12px 14px 10px;position:relative;flex:none}
.pc-h .fr-x{color:#fff}
.pc-h .fr-plate{color:var(--accent);border:0;padding:0;margin:0 8px 0 0;font-size:1.55rem;font-weight:800;line-height:1.1}
.fr-chips2{display:inline-flex;gap:6px;vertical-align:5px}.fr-chips2 .c1{background:#e4e7ec;color:#1b2432}.fr-chips2 .c2{background:#33648a;color:#fff}
.fr-chips2 span{font-size:.72rem;font-weight:700;padding:3px 6px;border-radius:5px}
.fr-opr{color:#aeb9ca;font-size:.82rem;margin-top:4px}
.pc-s{overflow:auto;flex:1;min-height:0}
.pc-s .fr-photo{margin:0}
.pc-rt{background:var(--chip);padding:12px 0 2px}
.led{position:relative;background:#050505;border:3px solid #1d1d1d;border-radius:8px;margin:0 14px;overflow:hidden;box-shadow:inset 0 0 14px rgba(0,0,0,.8),0 0 0 1px #3a3a3a;padding:0;line-height:0}
.led canvas{display:block;margin:0 auto}
.led-sub{display:flex;justify-content:space-between;gap:8px;padding:7px 16px 9px;font-size:.72rem;color:var(--muted);text-transform:uppercase;font-weight:700}.led-sub b{color:var(--ink);text-align:right}

.pc-rt .nm{font-weight:700;font-size:.8rem;margin-top:6px;text-transform:uppercase}.pc-rt .sb{font-size:.7rem;color:var(--muted);margin-top:2px}
.pc-rt .mid{position:absolute;left:50%;top:50%;width:40px;height:40px;border-radius:50%;background:var(--card);transform:translate(-50%,-50%);display:grid;place-items:center}
.pc-tm{display:grid;grid-template-columns:1fr 1fr;gap:2px;margin-top:2px}
.pc-tm div{background:var(--chip);padding:9px 12px;display:flex;justify-content:space-between;align-items:baseline;gap:6px;font-size:.66rem;font-weight:700;color:var(--muted);text-transform:uppercase}
.pc-tm b{font-size:1.05rem;color:var(--ink);font-variant-numeric:tabular-nums}
.pc-pg{padding:10px 14px 12px}.pc-pg .bar2{margin-bottom:6px}.pc-pg .pr{display:flex;justify-content:space-between;font-size:.74rem;color:var(--muted)}
.pc-sec{display:block;width:100%;text-align:left;border:0;background:#33648a;color:#fff;font:700 .85rem Cairo,sans-serif;padding:9px 14px;cursor:pointer}
.pc-sec::after{content:"▾";float:right}.pc-sec[aria-expanded="false"]::after{content:"▸"}
.pc-body{padding:10px 14px}.pc-body[hidden]{display:none}
.kv2{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px;padding:0}
.kv2 div{min-width:0}.kv2 .w{grid-column:1/-1}.kv2 small{display:block;font-size:.66rem;text-transform:uppercase;color:var(--muted);font-weight:700;letter-spacing:.3px}.kv2 b{font-size:.9rem}
.pc-a{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:9px 14px;background:#1b2432;color:#fff;flex:none}
.pc-a button{border:0;background:rgba(255,255,255,.12);color:#fff;border-radius:999px;padding:6px 12px;font:600 .8rem Cairo,sans-serif;cursor:pointer}
.pc-a a{color:var(--accent);font-size:.82rem}.pc-a .fr-rfs{font-size:.74rem;opacity:.75}.fr-off{color:#9ca3af}
.fr-line{font-size:.88rem;margin:4px 0}
.fr-btns{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
.fr-btns button{padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;font-size:.85rem;cursor:pointer}
.fr-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.fr-tabs button{padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;font-size:.8rem;cursor:pointer}
.fr-tabs button.on{background:var(--accent);border-color:var(--accent);color:var(--onacc)}
.fr-arrow div{color:var(--accent);font-size:20px;text-align:center;text-shadow:0 0 3px #fff}
</style>"""

    def tabela_stilleri():
        try:
            with open(os.path.join(_here, "tabela_stilleri.json"), encoding="utf-8") as f:
                return json.dumps(json.load(f), ensure_ascii=False).replace("</", "<\\/")
        except Exception:
            return '{"varsayilan":{"no":"#ffb000","ust":"#ffb000","metin":"#ffb000","iki_satir":false},"modeller":[]}'

    def page_harita(g):
        body = (
            FR_CSS + '<div id="frwrap"><div class="fmap"><div id="map"></div><div id="panel"></div>'
            '<div class="fr-filters" id="flt"><button type="button" id="ftog">⚙ Filtreler</button><div class="fbox">'
            '<div class="field"><label>Tam hat</label><input id="hat" placeholder="' + esc(city_meta()["hat_ornek"].split(" ")[0], True) + '" autocomplete="off"></div>'
            + ('<div class="field"><label>İşletme</label><select id="op"><option value="">Tümü</option><option value="ego">EGO</option>'
               '<option value="oho">ÖHO / Halk otobüsü (06 HO)</option></select></div>' if cur_city() == "ankara"
               else '<input type="hidden" id="op" value="">')
            + ('<div class="field"><label>Tip</label><select id="tip"><option value="">Tümü</option><option value="Körüklü">Körüklü</option>'
               '<option value="Solo">Solo</option></select></div>' if cur_city() == "ankara" else '<input type="hidden" id="tip" value="">') +
            '<div class="field"><label>Son kaç saat</label><input id="saat" type="number" value="24" min="1" max="168"></div>'
            '<label style="display:flex;gap:8px;align-items:center;color:var(--ink)"><input id="live" type="checkbox" style="width:auto"> yalnız canlı araçlar</label>'
            '</div></div>'
            '<div class="fr-dock"><button type="button" id="dTema"><span class="di">☀</span>Görünüm</button><button type="button" id="dFlt"><span class="di">⚙</span>Filtreler</button><a href="/hat"><span class="di">🚍</span>Hatlar</a></div>'
            '<div class="fr-count"><span id="cnt">Yükleniyor…</span></div><button type="button" id="full" hidden></button>'
            '</div></div>'
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
            '<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">'
            '<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>'
            '<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>'
            "<script>window.TABELA=" + tabela_stilleri() + ";</script><script>" + MAP_JS.replace("__MERKEZ__", "[%s,%s],%s" % tuple(city_meta()["merkez"])) + "</script>"
        )
        return layout("/", body, "Harita · EGO Filo Takip", mapmode=True)


    # ------------------------------------------------------------------ Modeller (marka/model yönetimi)
    DURUMLAR = ("kesin", "tahmini")

    def page_modeller(g, msg=""):
        conn = E.connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                         "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)")
            kayit = conn.execute("SELECT anahtar, marka_model, kaynak, url, durum FROM arac_bilgi ORDER BY anahtar").fetchall()
            known = {r[0] for r in kayit}
            seen = conn.execute("SELECT MAX(arac_no), plaka, MAX(last_ts) FROM stints WHERE arac_no<>'' GROUP BY plaka "
                                "ORDER BY MAX(last_ts) DESC LIMIT 4000").fetchall()
        finally:
            conn.close()
        eksik = []
        for a, p, t in seen:
            if E.norm(a) in known or E.norm(p) in known:
                continue
            if _csv_model(a)[0]:
                continue
            eksik.append((a, p, t))
        form = ('<form class="card form" method="post" action="/modeller/kaydet" style="grid-template-columns:1fr 2fr 1fr">'
                '<div class="field"><label>Filo kodu veya plaka</label><input name="anahtar" placeholder="09-524" required></div>'
                '<div class="field"><label>Marka / model</label><input name="marka_model" placeholder="MAN Lion&#39;s Classic CNG" required></div>'
                '<div class="field"><label>Durum</label><input name="durum" value="kesin" list="d"><datalist id="d"><option>kesin</option><option>tahmini</option></datalist></div>'
                '<div class="field" style="grid-column:1/3"><label>Kaynak / not (isteğe bağlı)</label><input name="kaynak" placeholder="Busphotos.eu, forum başlığı, kendi çekimim…"></div>'
                '<div class="field"><label>Bağlantı (isteğe bağlı)</label><input name="url" placeholder="https://…"></div>'
                '<button class="btn">Kaydet</button></form>')
        toplu = ('<details class="card"><summary><b>Toplu ekle</b> (her satır: <code>kod;marka model;durum;kaynak</code>)</summary>'
                 '<form method="post" action="/modeller/toplu"><textarea name="metin" rows="6" style="width:100%;margin-top:10px;padding:10px;border-radius:10px;'
                 'border:1px solid var(--line);background:var(--bg);color:var(--ink)" placeholder="24-114;Mercedes-Benz Conecto CNG;kesin;Busphotos"></textarea>'
                 '<button class="btn" style="margin-top:10px">İçe aktar</button></form></details>')
        def kaynak_html(s, u):
            if u.startswith(("http://", "https://")):
                return '<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(u, True), esc(s or u))
            return esc(s or "")

        rows = "".join(
            '<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td>'
            '<td><form method="post" action="/modeller/sil" style="margin:0"><input type="hidden" name="anahtar" value="%s">'
            '<button class="btn" style="padding:4px 10px;font-size:.8rem;background:var(--muted)">Sil</button></form></td></tr>'
            % (esc(k), esc(m), esc(d or ""), kaynak_html(s, u), esc(k, True))
            for k, m, s, u, d in kayit)
        tablo = (f'<div class="card"><b>Kayıtlı bilgiler</b> <span class="muted">{len(kayit)} kayıt (ön ek kuralları modeller.csv içinde)</span>'
                 f'<div class="scroll" style="margin-top:8px"><table><thead><tr><th>Kod</th><th>Model</th><th>Durum</th><th>Kaynak</th><th></th></tr></thead>'
                 f'<tbody>{rows or "<tr><td colspan=5 class=muted>Henüz elle eklenmiş kayıt yok.</td></tr>"}</tbody></table></div></div>')
        def ara_linkleri(a, p):
            q = urllib.parse.quote_plus("ego %s %s" % (a, E.pretty_plate(p)))
            qi = urllib.parse.quote_plus("ego %s" % a)
            return ('<a href="https://www.google.com/search?tbm=isch&q=%s" target="_blank" rel="noopener">Google görseller</a> · '
                    '<a href="https://www.google.com/search?q=%s" target="_blank" rel="noopener">Google</a> · '
                    '<a href="https://www.google.com/search?q=site:forum.ulasimplatformu.com+%s" target="_blank" rel="noopener">Ulaşım Platformu</a>'
                    % (qi, q, urllib.parse.quote_plus(a)))
        satir = "".join(
            '<tr><td><a href="/modeller?doldur=%s"><b>%s</b></a></td><td>%s</td><td>%s</td></tr>'
            % (urllib.parse.quote(a), esc(a), esc(E.pretty_plate(p)), ara_linkleri(a, p)) for a, p, t in eksik[:150])
        eks = (f'<div class="card"><b>Modeli bilinmeyen araçlar</b> <span class="muted">{len(eksik)} araç; koda tıklayınca forma gelir, '
               f'arama bağlantıları yeni sekmede açılır (sonucu elle girersin)</span>'
               + ('<div class="scroll" style="margin-top:8px"><table><thead><tr><th>Kod</th><th>Plaka</th><th>İnternette ara</th></tr></thead>'
                  f'<tbody>{satir}</tbody></table></div>' if eksik else '<div class="hatrow"><span class="muted">Hepsinin modeli tanımlı.</span></div>')
               + '</div>')
        pre = g("doldur")
        body = ("<h1>Modeller</h1>" + (note(msg, "info") if msg else "")
                + '<p class="muted">Araç marka/modelini buradan elle ekleyebilirsin. Otomatik arama yok; boş kalan araç boş görünür.</p>'
                + form + toplu + eks + tablo)
        if pre:
            body = body.replace('name="anahtar" placeholder="09-524"', f'name="anahtar" value="{esc(pre, True)}" placeholder="09-524"', 1)
        return layout("/modeller", body, "Modeller · EGO Filo Takip")

    def save_model(conn, anahtar, model, durum, kaynak, url):
        key = E.norm(anahtar)
        model = (model or "").strip()[:120]
        if not key or not model:
            return False
        url = (url or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = ""
        conn.execute("INSERT OR REPLACE INTO arac_bilgi (anahtar, marka_model, kaynak, url, durum, ts) VALUES (?,?,?,?,?,?)",
                     (key, model, (kaynak or "").strip()[:200], url[:300], durum if durum in DURUMLAR else "tahmini", E.now_ts()))
        return True

    # ------------------------------------------------------------------ HTTP
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="text/html; charset=utf-8", code=200, extra=None):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            gz = len(data) > 1200 and "gzip" in (self.headers.get("Accept-Encoding") or "") and ctype.startswith(("application/json", "text/"))
            if gz:
                data = _gzip.compress(data, 4)
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            if gz:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, to, extra=None):
            self.send_response(303)
            self.send_header("Location", to)
            self.send_header("Content-Length", "0")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()

        def _sehir(self):
            try:
                c = SimpleCookie(self.headers.get("Cookie") or "")
                v = c["sehir"].value if "sehir" in c else ""
            except Exception:
                v = ""
            return v if v in CITY_BY_ID and CITY_BY_ID[v]["aktif"] else ""

        def _set_city(self):
            c = self._sehir() or "ankara"
            E.CITY_CTX.city = c
            E.CITY_CTX.db = CITY_DB.get(c)

        def do_GET(self):
            self._set_city()
            u = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(u.query)

            def g(k, d=""):
                return (qs.get(k, [d])[0] or d).strip()

            try:
                if u.path == "/":
                    if not g("q") and not self._sehir():
                        return self._send(page_sehir(g))
                    return self._send(page_ara(g) if g("q") else page_harita(g))
                if u.path == "/ara":
                    return self._send(page_ara(g))
                if u.path == "/sehir":
                    return self._send(page_sehir(g))
                if u.path == "/sehir/sec":
                    sec = g("s")
                    if sec in CITY_BY_ID and CITY_BY_ID[sec]["aktif"]:
                        return self._redirect("/", {"Set-Cookie": "sehir=%s; Path=/; Max-Age=31536000; SameSite=Lax" % sec})
                    return self._redirect("/sehir?yakinda=" + urllib.parse.quote(sec))
                if u.path == "/hatlar":
                    return self._send(page_hatlar(g))
                if u.path == "/durak":
                    return self._send(page_durak_izmir(g) if cur_city() == "izmir" else page_durak(g))
                if u.path == "/hat":
                    return self._send(page_hat(g))
                if u.path == "/api/durak":
                    return self._send(api_durak(g), "application/json; charset=utf-8")
                if u.path in ("/csv/gun", "/csv/hatlar", "/csv/arac"):
                    fn = {"/csv/gun": csv_gun, "/csv/hatlar": csv_hatlar, "/csv/arac": csv_arac}[u.path]
                    name, data = fn(g)
                    return self._send(data, "text/csv; charset=utf-8",
                                      extra={"Content-Disposition": f'attachment; filename="{name}"'})
                if u.path == "/modeller":
                    return self._send(page_modeller(g, "Kaydedildi." if g("ok") else ""))
                if u.path == "/eslesme":
                    return self._send(page_eslesme(g, {"1": "Kaydedildi.", "0": "Parola yanlış ya da kayıt kapalı."}.get(g("ok"), "")))
                if u.path == "/api/foto":
                    return self._send(api_foto(g), "application/json; charset=utf-8")
                if u.path == "/harita":
                    return self._send(page_harita(g))
                if u.path == "/api/canli":
                    return self._send(api_canli(g), "application/json; charset=utf-8")
                if u.path == "/api/duraklar":
                    return self._send(api_duraklar(g), "application/json; charset=utf-8")
                if u.path == "/api/hat_rota":
                    return self._send(api_hat_rota(g), "application/json; charset=utf-8")
                if u.path == "/api/arac_iz":
                    return self._send(api_arac_iz(g), "application/json; charset=utf-8")
                if u.path == "/api/araclar":
                    return self._send(api_araclar(g), "application/json; charset=utf-8")
                if u.path == "/gun":
                    return self._send(page_gun(g))
                if u.path == "/raporlar":
                    return self._send(page_raporlar(g))
                if u.path == "/durum":
                    return self._send(page_durum(g))
                if u.path == "/rapor-uret":
                    conn = E.connect()
                    try:
                        _, _, n = E.write_report(conn, E.parse_day(g("tarih")))
                    finally:
                        conn.close()
                    return self._redirect("/raporlar?uretildi=" + str(n))
                if u.path.startswith("/rapor/"):
                    name = os.path.basename(urllib.parse.unquote(u.path[len("/rapor/"):]))
                    p = os.path.join(E.REPORT_DIR, name)
                    if name.endswith(".csv") and os.path.isfile(p):
                        with open(p, "rb") as f:
                            return self._send(f.read(), "text/csv; charset=utf-8",
                                              extra={"Content-Disposition": f'attachment; filename="{name}"'})
                    return self._send("Bulunamadı", code=404)
                if u.path == "/manifest.json":
                    return self._send(json.dumps(MANIFEST), "application/manifest+json")
                if u.path in ("/icon-192.png", "/icon-512.png", "/icon-m512.png"):
                    import base64 as _b64
                    return self._send(_b64.b64decode(ICON_PNG[u.path[6:-4]]), "image/png")
                if u.path == "/icon.svg":
                    return self._send(ICON, "image/svg+xml")
                if u.path == "/saglik":
                    return self._send("ok", "text/plain; charset=utf-8")
                return self._send(layout("", '<div class="card empty">Sayfa bulunamadı.</div>'), code=404)
            except Exception as e:  # kullanıcıya anlaşılır hata sayfası
                msg = f"Hata: {e}"
                return self._send(layout("", f'<div class="card">{note(msg)}<a href="/">Başa dön</a></div>'), code=500)

    def do_post_impl(self):
        u = urllib.parse.urlparse(self.path)
        host = (self.headers.get("Host") or "").lower()
        origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
        if origin and urllib.parse.urlparse(origin).netloc.lower() != host:
            return self._send("Geçersiz istek kaynağı", code=403)
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 200000)
        except ValueError:
            n = 0
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        f = lambda k: (form.get(k, [""])[0] or "").strip()
        if u.path.startswith("/eslesme/"):
            self._set_city()
            if cur_city() != "izmir" or not ESLESME_PAROLA or f("parola") != ESLESME_PAROLA:
                return self._redirect("/eslesme?ok=0")
            conn = E.connect()
            try:
                if u.path == "/eslesme/kaydet":
                    save_eslesme(conn, f("arac_no"), f("plaka"), f("filo"))
                elif u.path == "/eslesme/toplu":
                    for line in f("metin").splitlines()[:2000]:
                        r = parse_eslesme_line(line)
                        if r:
                            save_eslesme(conn, *r)
                elif u.path == "/eslesme/sil":
                    a = E.norm(f("arac_no"))
                    eslesme_init(conn)
                    old = conn.execute("SELECT plaka, filo FROM eslesme WHERE arac_no=?", (a,)).fetchone()
                    conn.execute("DELETE FROM eslesme WHERE arac_no=?", (a,))
                    for al in (old or ()):
                        if al:
                            conn.execute("DELETE FROM aliases WHERE alias=? AND plaka=?", (E.norm(al), a))
                else:
                    return self._send("Bulunamadı", code=404)
                conn.commit()
            finally:
                conn.close()
            return self._redirect("/eslesme?ok=1")
        conn = E.connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                         "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)")
            if u.path == "/modeller/kaydet":
                save_model(conn, f("anahtar"), f("marka_model"), f("durum"), f("kaynak"), f("url"))
            elif u.path == "/modeller/sil":
                conn.execute("DELETE FROM arac_bilgi WHERE anahtar=?", (E.norm(f("anahtar")),))
            elif u.path == "/modeller/toplu":
                for line in f("metin").splitlines()[:2000]:
                    p = [x.strip() for x in line.split(";")]
                    if len(p) >= 2:
                        save_model(conn, p[0], p[1], p[2] if len(p) > 2 else "tahmini", p[3] if len(p) > 3 else "", "")
            else:
                return self._send("Bulunamadı", code=404)
            conn.commit()
        finally:
            conn.close()
        return self._redirect("/modeller?ok=1")

    H.do_POST = do_post_impl
    return H
