# Mjenzi Cloud website

Source for [mjenzi.cloud](https://mjenzi.cloud): sovereign cloud, GPU and AI infrastructure for Africa and Australia, with points of presence in Nairobi, Johannesburg, Gaborone, Sydney and Canberra.

## What's here

| Path | What it is |
|---|---|
| `index.html` | Home page: IaaS, Mjenzi AI, Forward Deployed Engineering, network, servers, contact |
| `assessment.html` | Cloud & AI Rapid Assessment (readiness score, maturity level, action plan) |
| `sizing.html` | Server Sizing Configurator (bill of materials / spec sheet) |
| `cloud-config.html` | Cloud Configuration Sheet (ready-to-quote cloud configuration) |
| `privacy.html`, `404.html` | Privacy policy and not-found page |
| `assets/` | Shared styles, header/footer script and favicon |
| `api/` | Form backend (Python, standard library only). See [api/README.md](api/README.md) |
| `deploy/` | Server setup and deploy scripts |

Plain static HTML, CSS and JavaScript. No build step.

## Run locally

```bash
cd api && STATIC_DIR=.. python3 form_server.py
```

Open http://127.0.0.1:8082. Form submissions are saved to `api/leads.sqlite3` (not emailed unless SMTP is configured).

## Deploy to the VPS

One-time: copy your SSH key to the server (asks for the root password once).

```bash
ssh-copy-id root@YOUR_SERVER_IP
```

First deploy (installs nginx, the form service and HTTPS):

```bash
SERVER=YOUR_SERVER_IP ./deploy/deploy.sh --setup
```

Then on the server, add the Gmail app password to `/etc/mjenzi/form.env` and run `systemctl restart mjenzi-forms`.

Later updates:

```bash
SERVER=YOUR_SERVER_IP ./deploy/deploy.sh
```

DNS (Namecheap → Domain List → mjenzi.cloud → Advanced DNS): an `A` record for `@` and for `www` pointing to the server IP.
