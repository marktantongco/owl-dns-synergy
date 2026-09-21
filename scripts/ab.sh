#!/usr/bin/env bash
# ab.sh — stealth-daemon control helper
# Usage: ab.sh <name> [arg]
#   ab.sh url
#   ab.sh shot /abs/path.png
#   ab.sh click "786,330"
#   ab.sh eval "navigator.userAgent"
#   ab.sh open "https://..."
#   ab.sh type 'input[type="email"]:::someone@gmail.com'
DAEMON="http://127.0.0.1:18899/cmd"
if [ $# -eq 0 ]; then echo "usage: ab.sh <name> [arg]"; exit 1; fi
NAME="$1"; ARG="${2:-}"
if [ -n "$ARG" ]; then
  curl -sG --max-time 120 "$DAEMON" --data-urlencode "name=$NAME" --data-urlencode "arg=$ARG"
else
  curl -sG --max-time 120 "$DAEMON" --data-urlencode "name=$NAME"
fi
echo
