# Mjenzi Cloud form backend

One small Python server (standard library only, Python 3.9+) that receives every form on the site:

| Form | Where | `type` |
|---|---|---|
| Contact form | Home page | `contact` |
| Send results / book review | Cloud & AI Rapid Assessment | `assessment` |
| Request a quote | Server Sizing Configurator | `sizing` |
| Request pricing | Cloud Configuration Sheet | `cloud` |

Each submission is:

1. Checked (name, valid email, honeypot field, max 8 per IP per 15 minutes).
2. Saved to a SQLite database (`LEADS_DB`), so nothing is lost if email fails.
3. Emailed to `MAIL_TO` (default cloudmjenzi@gmail.com) with the customer as Reply-To. Tool submissions include the full sheet as text plus a `.json` attachment.

If the server can't be reached, the website offers to send the details by email instead.

## Run locally

```bash
cd mjenzi-site/api
STATIC_DIR=.. python3 form_server.py
```

Open http://127.0.0.1:8082. With no `SMTP_HOST` set, leads are saved to `leads.sqlite3` but not emailed.

## Deploy (nginx + systemd)

1. Copy the `mjenzi-site` folder to the server, e.g. `/var/www/mjenzi`.
2. Copy `form.env.example` to `/etc/mjenzi/form.env` and fill in SMTP details and `ADMIN_TOKEN`.
3. systemd unit `/etc/systemd/system/mjenzi-forms.service`:

   ```ini
   [Unit]
   Description=Mjenzi website form backend
   After=network.target

   [Service]
   EnvironmentFile=/etc/mjenzi/form.env
   ExecStart=/usr/bin/python3 /var/www/mjenzi/api/form_server.py
   User=www-data
   StateDirectory=mjenzi
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

4. nginx: serve the site as static files and proxy `/api/` (this also stops the `api` folder's files being served):

   ```nginx
   root /var/www/mjenzi;
   location ^~ /api/ {
       proxy_pass http://127.0.0.1:8082;
       proxy_set_header X-Real-IP $remote_addr;
       client_max_body_size 256k;
   }
   ```

5. `sudo systemctl enable --now mjenzi-forms`, then check `curl https://mjenzi.cloud/api/health`.

## Download leads

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://mjenzi.cloud/api/leads.csv -o leads.csv
```

## API on a different domain

If the site is on static hosting and the API is elsewhere, add this before `assets/common.js` in each page and set `ALLOWED_ORIGINS` on the server:

```html
<script>window.MJENZI_API = "https://api.mjenzi.cloud/api/submit";</script>
```
