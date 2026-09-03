#!/bin/zsh
# Double-click to open the Creosote Labs site admin.
cd "$(dirname "$0")"
if ! curl -s -o /dev/null http://localhost:8786/api/status; then
  nohup /usr/bin/python3 admin/server.py >/tmp/creosote-admin.log 2>&1 &
  sleep 1
fi
open "http://localhost:8786/"
