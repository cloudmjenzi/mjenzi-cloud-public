#!/usr/bin/env bash
# Store the Gmail app password on the VPS so website forms are emailed.
#   SERVER=162.0.238.214 SSH_KEY=~/.ssh/mjenzi_deploy ./deploy/set-mail-password.sh
# The password is typed here (hidden), sent over SSH on stdin, and written only to /etc/mjenzi/form.env.
set -euo pipefail
: "${SERVER:?Set SERVER to the VPS IP}"
SSH="ssh -p ${SSH_PORT:-22} -o BatchMode=yes"
[ -n "${SSH_KEY:-}" ] && SSH="$SSH -i $SSH_KEY -o IdentitiesOnly=yes"

read -rsp "Gmail app password for cloudmjenzi@gmail.com (16 letters, spaces are fine): " PW; echo
PW="${PW// /}"
[ ${#PW} -ge 16 ] || { echo "That doesn't look like a 16-character app password."; exit 1; }

printf '%s' "$PW" | $SSH "${SSH_USER:-root}@$SERVER" 'python3 -c "
import sys, re
pw = sys.stdin.read().strip()
p = \"/etc/mjenzi/form.env\"
s = open(p).read()
s = re.sub(r\"(?m)^SMTP_PASSWORD=.*$\", lambda m: \"SMTP_PASSWORD=\" + pw, s)
open(p, \"w\").write(s)
" && systemctl restart mjenzi-forms && sleep 1 && curl -s -X POST http://127.0.0.1:8082/api/submit -H "Content-Type: application/json" -d "{\"type\":\"contact\",\"name\":\"Mail test\",\"email\":\"cloudmjenzi@gmail.com\",\"message\":\"Test email from the mjenzi.cloud server setup\",\"website\":\"\"}" >/dev/null && sleep 8 && python3 -c "
import sqlite3
r = sqlite3.connect(\"/var/lib/mjenzi/leads.sqlite3\").execute(\"SELECT id, emailed FROM leads ORDER BY id DESC LIMIT 1\").fetchone()
print(\"Test email SENT - check the cloudmjenzi@gmail.com inbox.\" if r[1] else \"Email NOT sent. Recent log:\")
" && journalctl -u mjenzi-forms -n 4 --no-pager -o cat | grep -i "failed" || true'
unset PW
