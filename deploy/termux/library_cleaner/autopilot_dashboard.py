"""Dependency-free local dashboard for Centinal26 autopilot status."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path.home() / ".local" / "share" / "frost-library-cleaner"
STATUS = APP / "autopilot-status.json"
AUTOPILOT_LOG = APP / "autopilot-cycle.jsonl"
HOST = "127.0.0.1"
PORT = 8765

HTML = r'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Centinal26 Autopilot</title>
<style>
:root{font-family:system-ui,sans-serif;color-scheme:light dark}body{margin:0;padding:20px;background:#111827;color:#e5e7eb}.wrap{max-width:900px;margin:auto}.top{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}.badge{padding:6px 10px;border:1px solid #4b5563;border-radius:999px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:16px}.card{border:1px solid #374151;border-radius:12px;padding:14px;background:#1f2937}.muted{color:#9ca3af}.item{border-top:1px solid #374151;padding:12px 0}.item:first-child{border-top:0}.err{color:#fca5a5}.ok{color:#86efac}button{font:inherit;padding:9px 12px;border-radius:8px;border:1px solid #4b5563;background:#111827;color:inherit}code{word-break:break-all}</style>
<div class="wrap">
  <div class="top"><div><h1>Centinal26 Autopilot</h1><div class="muted">Strict action-only status</div></div><button id="refresh">Refresh</button></div>
  <div class="grid">
    <div class="card"><div class="muted">Watch state</div><h2 id="state">Loading…</h2></div>
    <div class="card"><div class="muted">Actionable changes</div><h2 id="count">—</h2></div>
    <div class="card"><div class="muted">Last update</div><h2 id="updated">—</h2></div>
  </div>
  <div class="card" style="margin-top:12px"><h3>Required action</h3><div id="changes" class="muted">No status loaded.</div></div>
  <div class="card" style="margin-top:12px"><h3>Evidence health</h3><div id="errors" class="muted">—</div></div>
</div>
<script>
const q=id=>document.getElementById(id);
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function load(){try{const r=await fetch('/api/status',{cache:'no-store'});const s=await r.json();q('state').textContent=s.watch_state||'UNKNOWN';q('count').textContent=s.actionable_count??0;q('updated').textContent=s.updated_at?new Date(s.updated_at*1000).toLocaleString():'—';const ch=s.actionable_changes||[];q('changes').innerHTML=ch.length?ch.map(x=>`<div class="item"><b>${esc(x.kind)} · ${esc(x.affected_item)}</b><div>${esc(x.change)}</div><div class="muted">Evidence: ${esc(x.evidence_state)}</div><div>Next: ${esc(x.next_step)}</div></div>`).join(''):'<span class="ok">No action required.</span>';const er=s.evidence_errors||[];q('errors').innerHTML=er.length?er.map(x=>`<div class="err">${esc(x)}</div>`):'<span class="ok">No evidence-access errors.</span>';}catch(e){q('state').textContent='UNAVAILABLE';q('errors').innerHTML='<span class="err">Dashboard status endpoint unavailable.</span>';}}
q('refresh').addEventListener('click',load);load();setInterval(load,15000);
</script>'''


def status_payload() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema": "centinal26.autopilot.status.v1",
            "watch_state": "NO_DATA",
            "actionable_count": 0,
            "actionable_changes": [],
            "evidence_errors": ["No autopilot status has been written yet."],
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/status":
            body = json.dumps(status_payload(), sort_keys=True).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in {"/", "/index.html"}:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Centinal26 Autopilot dashboard: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
