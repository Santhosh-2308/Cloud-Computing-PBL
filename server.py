"""Tiny web API (stdlib only): GET /orders, POST /orders, backed by SQLite."""
import json, sqlite3, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB = "workload/shop.db"
local = threading.local()

def db():
    if not hasattr(local, "c"):
        local.c = sqlite3.connect(DB, timeout=10)
    return local.c

def init(n=20000):
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, item TEXT, qty INT)")
    if c.execute("SELECT count(*) FROM orders").fetchone()[0] == 0:
        c.executemany("INSERT INTO orders(item,qty) VALUES(?,?)", [(f"sku{i%50}", i%5+1) for i in range(n)])
    c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        rows = db().execute("SELECT id,item,qty FROM orders ORDER BY id DESC LIMIT 50").fetchall()
        self._send(200, rows)
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        c = db(); c.execute("INSERT INTO orders(item,qty) VALUES(?,?)", (d["item"], d["qty"])); c.commit()
        self._send(201, {"ok": True})

if __name__ == "__main__":
    init()
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
