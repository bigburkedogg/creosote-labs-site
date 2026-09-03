#!/usr/bin/env python3
"""Creosote Labs site admin — edit content, preview, publish.

Runs locally at http://localhost:8786. Standard library only.
  GET  /                      admin UI
  GET  /api/tree              list of editable files
  GET  /api/file?path=...     one content file (JSON)
  PUT  /api/file?path=...     save it, then rebuild docs/
  POST /api/media             upload an image {name, data_base64}
  POST /api/build             rebuild docs/
  POST /api/publish           git add + commit + push (GitHub Pages redeploys)
  GET  /api/status            git status summary, last publish
  GET  /api/notes  PUT /api/notes   notes for Claude (content/notes.md)
  GET  <base_path>/...        preview of docs/
"""
import base64
import json
import re
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"
UI = Path(__file__).resolve().parent / "ui.html"
PORT = 8786
GIT = "/usr/bin/git"
PY = sys.executable


def base_path():
    try:
        return json.loads((CONTENT / "site.json").read_text()).get("base_path", "").rstrip("/")
    except Exception:
        return ""


def run(cmd, cwd=ROOT):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def build():
    return run([PY, str(ROOT / "build.py")])


def safe_content_path(rel):
    p = (CONTENT / rel).resolve()
    if CONTENT.resolve() not in p.parents and p != CONTENT.resolve():
        raise ValueError("path outside content/")
    return p


def tree():
    items = []
    for f in sorted(CONTENT.rglob("*.json")):
        rel = f.relative_to(CONTENT).as_posix()
        if rel.startswith("landing/pages/"):
            group = "Landing pages"
        elif rel.startswith("landing/"):
            group = "Landing taxonomy"
        elif rel.startswith("pages/"):
            group = "Pages"
        else:
            group = "Site"
        items.append({"path": rel, "group": group, "label": f.stem.replace("__", " / ").replace("-", " ")})
    return items


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter
        pass

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            body = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/tree":
            self._json(200, {"files": tree(), "base_path": base_path()})
        elif u.path == "/api/file":
            try:
                p = safe_content_path(q["path"][0])
                self._json(200, {"path": q["path"][0], "data": json.loads(p.read_text())})
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif u.path == "/api/status":
            code, out = run([GIT, "status", "--porcelain"])
            changed = [l for l in out.splitlines() if l.strip()]
            _, last = run([GIT, "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M"])
            self._json(200, {"changed": len(changed), "last_commit": last})
        elif u.path == "/api/notes":
            n = CONTENT / "notes.md"
            self._json(200, {"text": n.read_text() if n.exists() else ""})
        else:
            # preview: serve docs/ under the site's base path
            bp = base_path()
            path = u.path
            if bp and path.startswith(bp + "/"):
                path = path[len(bp):]
            elif bp and path == bp:
                path = "/"
            self.path = path
            self.directory = str(DOCS)
            return super().do_GET()

    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/file":
            try:
                p = safe_content_path(q["path"][0])
                data = self._read_json()["data"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                code, out = build()
                self._json(200 if code == 0 else 500, {"saved": q["path"][0], "build": out})
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif u.path == "/api/notes":
            (CONTENT / "notes.md").write_text(self._read_json().get("text", ""))
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/build":
            code, out = build()
            self._json(200 if code == 0 else 500, {"build": out})
        elif u.path == "/api/media":
            d = self._read_json()
            name = re.sub(r"[^A-Za-z0-9._-]", "-", d.get("name", "upload"))
            (CONTENT / "media").mkdir(exist_ok=True)
            (CONTENT / "media" / name).write_bytes(base64.b64decode(d["data_base64"]))
            build()
            self._json(200, {"file": name})
        elif u.path == "/api/publish":
            msg = (self._read_json().get("message") or "Site update via admin").strip()
            code, out = build()
            if code != 0:
                return self._json(500, {"error": "build failed", "log": out})
            log = [out]
            for cmd in ([GIT, "add", "-A", "content", "docs", "assets"],
                        [GIT, "commit", "-q", "-m", msg + "\n\nPublished from the site admin."],
                        [GIT, "push", "-q"]):
                code, out = run(cmd)
                log.append(" ".join(cmd[1:3]) + ": " + (out or "ok"))
                if code != 0 and "nothing to commit" not in out:
                    return self._json(500, {"error": "publish failed", "log": "\n".join(log)})
            self._json(200, {"published": True, "log": "\n".join(log)})
        else:
            self._json(404, {"error": "not found"})


if __name__ == "__main__":
    build()
    print(f"Creosote Labs admin: http://localhost:{PORT}/")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
