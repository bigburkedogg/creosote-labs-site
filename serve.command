#!/bin/zsh
cd "$(dirname "$0")"
open "http://localhost:8785/index.html"
python3 -m http.server 8785
