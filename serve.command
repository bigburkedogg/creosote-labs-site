#!/bin/zsh
# Serve the built site locally (same paths as the live site).
cd "$(dirname "$0")"
/opt/homebrew/bin/python3 build.py
open "http://localhost:8785/creosote-labs-site/index.html"
cd docs && /opt/homebrew/bin/python3 -c "
import http.server, functools
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory='.')
class H(h):
    def translate_path(self, p):
        p = p.replace('/creosote-labs-site', '', 1)
        return super().translate_path(p)
http.server.ThreadingHTTPServer(('127.0.0.1', 8785), H).serve_forever()
"
