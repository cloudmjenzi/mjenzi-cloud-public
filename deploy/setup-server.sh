#!/usr/bin/env bash
# One-time (and safe to re-run) server setup for mjenzi.cloud.
# Run on the VPS as root:   bash /var/www/mjenzi/deploy/setup-server.sh
#
# Installs nginx, Python 3 and certbot, creates the form-backend service,
# configures nginx for mjenzi.cloud + www.mjenzi.cloud, and turns on HTTPS
# once DNS points at this server.
set -euo pipefail

DOMAIN="${DOMAIN:-mjenzi.cloud}"
WEBROOT="/var/www/mjenzi"
ENV_FILE="/etc/mjenzi/form.env"
CERT_EMAIL="${CERT_EMAIL:-cloudmjenzi@gmail.com}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "Run as root."; exit 1; }
[ -f "$WEBROOT/index.html" ] || { echo "Site files not found in $WEBROOT. Run deploy.sh from your computer first."; exit 1; }

# Don't fight an existing control panel / web server
if command -v whmapi1 >/dev/null 2>&1 || [ -d /usr/local/cpanel ]; then
  echo "This server runs cPanel/WHM. Upload the site through cPanel instead; this script would conflict with it."; exit 1
fi
if ss -ltnp 2>/dev/null | grep -E ':(80|443)\s' | grep -qv nginx; then
  echo "Something other than nginx is already listening on port 80/443:"; ss -ltnp | grep -E ':(80|443)\s'
  echo "Stop it (e.g. 'systemctl disable --now apache2' or 'httpd') if it isn't needed, then re-run."; exit 1
fi

say "Installing packages"
if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq nginx python3 rsync certbot python3-certbot-nginx >/dev/null
  NGINX_SITE="/etc/nginx/sites-available/mjenzi.conf"; NGINX_LINK="/etc/nginx/sites-enabled/mjenzi.conf"
  rm -f /etc/nginx/sites-enabled/default
elif command -v dnf >/dev/null; then
  dnf install -y -q epel-release || true
  dnf install -y -q nginx python3 rsync certbot python3-certbot-nginx
  NGINX_SITE="/etc/nginx/conf.d/mjenzi.conf"; NGINX_LINK=""
  if command -v getenforce >/dev/null && [ "$(getenforce)" = Enforcing ]; then
    setsebool -P httpd_can_network_connect 1   # let nginx proxy to the form backend
  fi
else
  echo "Unsupported OS (need apt or dnf)."; exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 9)' || { echo "Python 3.9+ required."; exit 1; }

say "Service user and folders"
id mjenzi >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin mjenzi
mkdir -p /etc/mjenzi /var/lib/mjenzi
chown mjenzi:mjenzi /var/lib/mjenzi && chmod 750 /var/lib/mjenzi
chmod -R a+rX "$WEBROOT"

if [ ! -f "$ENV_FILE" ]; then
  say "Creating $ENV_FILE (fill in the Gmail app password afterwards)"
  sed -e "s#^LEADS_DB=.*#LEADS_DB=/var/lib/mjenzi/leads.sqlite3#" \
      -e "s#^ADMIN_TOKEN=.*#ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')#" \
      "$WEBROOT/api/form.env.example" > "$ENV_FILE"
  NEW_ENV=1
fi
chown root:mjenzi "$ENV_FILE" && chmod 640 "$ENV_FILE"

say "Form backend service"
cat > /etc/systemd/system/mjenzi-forms.service <<EOF
[Unit]
Description=Mjenzi Cloud website form backend
After=network.target

[Service]
User=mjenzi
Group=mjenzi
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/python3 $WEBROOT/api/form_server.py
WorkingDirectory=/var/lib/mjenzi
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/mjenzi
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet mjenzi-forms
systemctl restart mjenzi-forms

say "nginx site for $DOMAIN"
# Keep the HTTPS block certbot adds on later runs: only write the file if it doesn't exist yet
if [ ! -f "$NGINX_SITE" ]; then
cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;
    root $WEBROOT;
    index index.html;
    error_page 404 /404.html;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Frame-Options SAMEORIGIN always;

    # Form backend (also hides the api/ source folder)
    location ^~ /api/ {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        client_max_body_size 256k;
    }
    location ^~ /deploy/ { return 404; }
    location ~ /\. { deny all; }

    location ~* \.(css|js|svg|png|ico|woff2?)$ { expires 7d; add_header Cache-Control "public"; }
    location / { try_files \$uri \$uri/ =404; }
}
EOF
fi
[ -n "$NGINX_LINK" ] && ln -sf "$NGINX_SITE" "$NGINX_LINK"
nginx -t
systemctl enable --quiet nginx
systemctl reload nginx 2>/dev/null || systemctl restart nginx

if command -v ufw >/dev/null && ufw status | grep -q active; then ufw allow 'Nginx Full' >/dev/null; fi
if command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
  firewall-cmd -q --permanent --add-service=http --add-service=https && firewall-cmd -q --reload
fi

say "HTTPS certificate"
MYIP=$(curl -fsS4 https://api.ipify.org || true)
DNSIP=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
if [ -n "$MYIP" ] && [ "$MYIP" = "$DNSIP" ]; then
  WWW=""; [ "$(getent ahostsv4 "www.$DOMAIN" | awk 'NR==1{print $1}')" = "$MYIP" ] && WWW="-d www.$DOMAIN"
  certbot --nginx -n --agree-tos -m "$CERT_EMAIL" --redirect -d "$DOMAIN" $WWW
else
  echo "Skipped: $DOMAIN points to '${DNSIP:-nothing}', this server is '${MYIP:-unknown}'."
  echo "Set the A records in Namecheap, wait for DNS, then re-run this script."
fi

say "Checks"
sleep 1
curl -fsS http://127.0.0.1:8082/api/health && echo "  form backend OK"
curl -fsS -o /dev/null -w "  website HTTP %{http_code}\n" -H "Host: $DOMAIN" http://127.0.0.1/
if [ "${NEW_ENV:-0}" = 1 ] || grep -q "your-16-character-app-password" "$ENV_FILE"; then
  echo
  echo "NEXT: put the Gmail app password in $ENV_FILE (SMTP_PASSWORD=...), then:"
  echo "      systemctl restart mjenzi-forms"
  echo "Until then, leads are saved on the server but not emailed."
fi
echo "Admin token for downloading leads is in $ENV_FILE (ADMIN_TOKEN)."
