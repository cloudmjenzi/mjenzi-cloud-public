#!/usr/bin/env bash
# Deploy to Namecheap shared hosting (cPanel) over SSH on port 21098.
#   CPANEL_USER=youruser ./deploy/deploy-shared.sh
# Optional: SERVER (default 209.74.67.50), DOCROOT (default public_html), SSH_PORT (default 21098)
#
# One-time key setup:  ssh-copy-id -p 21098 youruser@209.74.67.50
set -euo pipefail
cd "$(dirname "$0")/.."

: "${CPANEL_USER:?Set CPANEL_USER to your cPanel username}"
SERVER="${SERVER:-209.74.67.50}"
SSH_PORT="${SSH_PORT:-21098}"
DOCROOT="${DOCROOT:-public_html}"
TARGET="$CPANEL_USER@$SERVER"
SSH="ssh -p $SSH_PORT -o BatchMode=yes"

echo "==> Checking SSH key access to $TARGET:$SSH_PORT"
$SSH "$TARGET" true || { echo "Key login failed. Run: ssh-copy-id -p $SSH_PORT $TARGET"; exit 1; }

echo "==> Uploading site to ~/$DOCROOT (existing files not in this repo are left alone)"
rsync -az -e "$SSH" \
  --exclude '.git' --exclude '.gitignore' --exclude '.DS_Store' --exclude 'zz-*' \
  --exclude 'deploy/' --exclude 'README.md' --exclude 'api/README.md' \
  --exclude 'api/*.py' --exclude 'api/form.env*' --exclude 'api/config.php' --exclude 'api/*.sqlite3' \
  ./ "$TARGET:$DOCROOT/"

$SSH "$TARGET" "mkdir -p ~/mjenzi-data && chmod 750 ~/mjenzi-data; \
  find ~/$DOCROOT -type d -exec chmod 755 {} +; find ~/$DOCROOT -type f -exec chmod 644 {} +; \
  [ -f ~/$DOCROOT/api/config.php ] || echo 'NOTE: create ~/$DOCROOT/api/config.php from config.example.php'"
echo "==> Done: https://mjenzi.cloud"
