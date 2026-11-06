#!/usr/bin/env bash
# Push the website to the VPS. Run from your computer:
#   SERVER=203.0.113.10 ./deploy/deploy.sh          # update files + restart form backend
#   SERVER=203.0.113.10 ./deploy/deploy.sh --setup  # first time: also run setup-server.sh
#
# Uses SSH key login (set it up once with: ssh-copy-id root@SERVER).
# Optional: SSH_USER (root), SSH_PORT (22), SSH_KEY (path to a private key)
set -euo pipefail
cd "$(dirname "$0")/.."

: "${SERVER:?Set SERVER to the VPS IP or hostname, e.g. SERVER=203.0.113.10}"
SSH_USER="${SSH_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"
TARGET="$SSH_USER@$SERVER"
SSH="ssh -p $SSH_PORT -o BatchMode=yes"
# Optional: SSH_KEY=~/.ssh/mjenzi_deploy to use a specific key
[ -n "${SSH_KEY:-}" ] && SSH="$SSH -i $SSH_KEY -o IdentitiesOnly=yes"

echo "==> Checking SSH key access to $TARGET"
$SSH "$TARGET" true || { echo "Can't log in with an SSH key. Run: ssh-copy-id -p $SSH_PORT $TARGET"; exit 1; }

echo "==> Uploading site"
$SSH "$TARGET" "mkdir -p /var/www/mjenzi; command -v rsync >/dev/null || { command -v dnf >/dev/null && dnf install -y -q rsync || { apt-get update -qq && apt-get install -y -qq rsync; }; }"
rsync -az --delete -e "$SSH" \
  --exclude '.git' --exclude '.DS_Store' --exclude 'api/leads.sqlite3' --exclude 'api/form.env' --exclude 'zz-*' --exclude 'api/config.php' \
  ./ "$TARGET:/var/www/mjenzi/"

if [ "${1:-}" = "--setup" ]; then
  echo "==> Running server setup"
  $SSH "$TARGET" "bash /var/www/mjenzi/deploy/setup-server.sh"
else
  $SSH "$TARGET" "chmod -R a+rX /var/www/mjenzi && systemctl restart mjenzi-forms && nginx -t -q && systemctl reload nginx"
fi
echo "==> Done: https://mjenzi.cloud"
