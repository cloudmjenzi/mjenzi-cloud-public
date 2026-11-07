# Mjenzi Cloud website

Source for [mjenzi.cloud](https://mjenzi.cloud): sovereign cloud, GPU and AI infrastructure for Africa and Australia, with points of presence in Nairobi, Johannesburg, Gaborone, Sydney and Canberra.

## What's here

| Path | What it is |
|---|---|
| `index.html` | Home page: IaaS, Mjenzi AI, Forward Deployed Engineering, network, servers, contact |
| `assessment.html` | Cloud & AI Rapid Assessment (readiness score, maturity level, action plan) |
| `sizing.html` | Server Sizing Configurator (bill of materials / spec sheet) |
| `cloud-config.html` | Cloud Configuration Sheet (ready-to-quote cloud configuration) |
| `cloud.html` | Cloud: use Mjenzi Cloud (service) or build a private cloud (hardware); resell programme |
| `ai.html` | AI: rent GPUs / AI platform (service) or buy GPU servers and clusters (hardware) |
| `infrastructure.html` | Server infrastructure: buy servers, storage and switches, or rent dedicated servers |
| `platform.html` | Redirect to `cloud.html` (old URL) |
| `blog/` | Blog. Write posts in `blog/posts/*.md`; `blog/build.py` turns them into pages |
| `privacy.html`, `404.html` | Privacy policy and not-found page |
| `assets/` | Shared styles, header/footer script and favicon |
| `api/` | Form backend (Python, standard library only). See [api/README.md](api/README.md) |
| `deploy/` | Server setup and deploy scripts |

Plain static HTML, CSS and JavaScript. No build step.

## Writing a blog post

1. Copy any file in `blog/posts/` and name it `YYYY-MM-DD-short-title.md`. The part after the date becomes the URL.
2. Edit the front matter at the top (`title`, `date`, `summary`, optional `author`, `tags`, `image`, `draft: true`).
3. Write the post in Markdown: `## headings`, lists, **bold**, [links](/sizing.html), tables, `> quotes` and code blocks.
4. Run `python3 blog/build.py` to preview locally (it also refreshes the blog index, RSS feed, sitemap and the home page's latest posts).
5. Deploy as usual. `deploy/deploy.sh` runs the build for you.

Images go in `blog/images/` and are referenced as `/blog/images/name.jpg`.

## Run locally

```bash
cd api && STATIC_DIR=.. python3 form_server.py
```

Open http://127.0.0.1:8082. Form submissions are saved to `api/leads.sqlite3` (not emailed unless SMTP is configured).

## Deploy to Namecheap shared hosting (mjenzi.cloud)

mjenzi.cloud is on Namecheap shared hosting (cPanel, LiteSpeed). There the form backend is the PHP version
(`api/submit.php`, `api/leads.php`, `api/lib.php`) and `.htaccess` routes `/api/submit` to it.

One-time: copy your SSH key (asks for your cPanel password once):

```bash
ssh-copy-id -p 21098 CPANEL_USER@209.74.67.50
```

Deploy:

```bash
CPANEL_USER=youruser ./deploy/deploy-shared.sh
```

Then on the server create `public_html/api/config.php` from `config.example.php` (set `admin_token`).
Leads are stored in `~/mjenzi-data/leads.sqlite3`, outside the web folder, and emailed to cloudmjenzi@gmail.com.

## Deploy to a VPS instead (nginx + Python backend)

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
