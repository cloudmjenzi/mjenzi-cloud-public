#!/usr/bin/env python3
"""
Mjenzi Cloud - website form backend.

Handles every form on the site with one endpoint:

    POST /api/submit   JSON body:
        {
          "type":    "contact" | "assessment" | "sizing" | "cloud",
          "name", "email", "phone", "company", "topic", "message",
          "reference": "MJZ-SZ-...",          (tool sheets only)
          "summary":   "plain-text summary",   (tool sheets only)
          "data":      { ...full tool output } (tool sheets only)
          "website":   ""                      (honeypot - must stay empty)
        }

Every submission is saved to a SQLite database, then emailed to the sales
inbox (Reply-To is set to the customer so you can answer straight away).

Admin export (needs ADMIN_TOKEN set):
    GET /api/leads.csv     header  Authorization: Bearer <ADMIN_TOKEN>

Uses only the Python standard library. Settings come from environment
variables (see deploy/form.env.example).

Local test (also serves the website):
    STATIC_DIR=.. python3 form_server.py
"""
from __future__ import annotations

import csv
from contextlib import closing
import hmac
import io
import json
import os
import re
import smtplib
import sqlite3
import ssl
import sys
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8082"))
STATIC_DIR = os.environ.get("STATIC_DIR")  # only for local testing
DB_FILE = Path(os.environ.get("LEADS_DB", "leads.sqlite3"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
# ssl (port 465), starttls (587) or none (local relay only)
SMTP_SECURITY = os.environ.get("SMTP_SECURITY", "ssl" if SMTP_PORT == 465 else "starttls").lower()
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)
MAIL_TO = [a.strip() for a in os.environ.get("MAIL_TO", "cloudmjenzi@gmail.com").split(",") if a.strip()]

TYPES = {"contact": "Website enquiry", "assessment": "Cloud & AI assessment",
         "sizing": "Server sizing quote request", "cloud": "Cloud configuration pricing request"}
MAX_BODY = 200_000
RATE_LIMIT = 8          # submissions ...
RATE_WINDOW = 15 * 60   # ... per 15 minutes per IP
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", file=sys.stderr, flush=True)


def db() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received TEXT NOT NULL, type TEXT NOT NULL, reference TEXT,
        name TEXT, email TEXT, phone TEXT, company TEXT, topic TEXT,
        message TEXT, summary TEXT, data TEXT, ip TEXT, emailed INTEGER DEFAULT 0)""")
    return con


def rate_limited(ip: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        limited = len(recent) >= RATE_LIMIT
        if not limited:
            recent.append(now)
        _hits[ip] = recent
        return limited


def save(entry: dict) -> int:
    with _lock, closing(db()) as con, con:
        cur = con.execute(
            "INSERT INTO leads (received,type,reference,name,email,phone,company,topic,message,summary,data,ip)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (entry["received"], entry["type"], entry["reference"], entry["name"], entry["email"],
             entry["phone"], entry["company"], entry["topic"], entry["message"], entry["summary"],
             json.dumps(entry["data"], ensure_ascii=False) if entry["data"] else None, entry["ip"]))
        return cur.lastrowid


def mark_emailed(lead_id: int) -> None:
    with _lock, closing(db()) as con, con:
        con.execute("UPDATE leads SET emailed=1 WHERE id=?", (lead_id,))


def send_email(lead_id: int, e: dict) -> bool:
    if not (SMTP_HOST and MAIL_TO):
        log(f"Lead #{lead_id} saved. Email not configured (SMTP_HOST empty).")
        return False
    msg = EmailMessage()
    subject = TYPES[e["type"]] + (f" {e['reference']}" if e["reference"] else "")
    msg["Subject"] = f"{subject}: {e['name']}" + (f" ({e['company']})" if e["company"] else "")
    msg["From"] = formataddr(("Mjenzi Cloud website", MAIL_FROM))
    msg["To"] = ", ".join(MAIL_TO)
    msg["Reply-To"] = formataddr((e["name"], e["email"]))
    lines = [f"New {TYPES[e['type']].lower()} from mjenzi.cloud (lead #{lead_id})", "",
             f"Name:     {e['name']}", f"Email:    {e['email']}", f"Phone:    {e['phone'] or '-'}",
             f"Company:  {e['company'] or '-'}"]
    if e["topic"]:
        lines.append(f"Topic:    {e['topic']}")
    if e["reference"]:
        lines.append(f"Ref:      {e['reference']}")
    lines.append(f"Received: {e['received']}")
    if e["message"]:
        lines += ["", "Message:", e["message"]]
    if e["summary"]:
        lines += ["", "-" * 60, e["summary"]]
    msg.set_content("\n".join(lines) + "\n")
    if e["data"]:
        msg.add_attachment(json.dumps(e["data"], indent=2, ensure_ascii=False).encode(),
                           maintype="application", subtype="json",
                           filename=f"{e['reference'] or 'lead-' + str(lead_id)}.json")
    ctx = ssl.create_default_context()
    if SMTP_SECURITY == "ssl":
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    with smtp as s:
        if SMTP_SECURITY == "starttls":
            s.starttls(context=ctx)
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    return True


def clean(v, n: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()[:n]


class Handler(BaseHTTPRequestHandler):
    server_version = "Mjenzi"

    def log_message(self, fmt, *args):
        log(f"{self.client_ip()} {fmt % args}")

    def client_ip(self) -> str:
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_body(self, status: int, data: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, body: dict) -> None:
        self.send_body(status, json.dumps(body).encode(), "application/json")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- API ----
    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") != "/api/submit":
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self.send_json(400, {"error": "Invalid request"})
        try:
            d = json.loads(self.rfile.read(length))
            if not isinstance(d, dict):
                raise ValueError
        except ValueError:
            return self.send_json(400, {"error": "Invalid request"})

        if clean(d.get("website"), 200):  # honeypot filled in: pretend success, drop it
            log(f"{self.client_ip()} honeypot triggered, submission dropped")
            return self.send_json(200, {"ok": True})

        ftype = clean(d.get("type"), 20)
        if ftype not in TYPES:
            return self.send_json(400, {"error": "Unknown form type"})
        data = d.get("data") if isinstance(d.get("data"), (dict, list)) else None
        entry = {
            "received": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": ftype,
            "reference": clean(d.get("reference"), 40),
            "name": clean(d.get("name"), 200),
            "email": clean(d.get("email"), 200),
            "phone": clean(d.get("phone"), 50),
            "company": clean(d.get("company"), 200),
            "topic": clean(d.get("topic"), 120),
            "message": clean(d.get("message"), 5000),
            "summary": clean(d.get("summary"), 20000),
            "data": data,
            "ip": self.client_ip(),
        }
        if not entry["name"] or not EMAIL_RE.match(entry["email"]):
            return self.send_json(400, {"error": "Please give your name and a valid email address."})
        if ftype == "contact" and not entry["message"]:
            return self.send_json(400, {"error": "Please write a message."})
        if rate_limited(entry["ip"]):
            return self.send_json(429, {"error": "Too many submissions. Please try again in a few minutes."})

        try:
            lead_id = save(entry)
        except (OSError, sqlite3.Error) as e:
            log(f"Could not save lead: {e!r}")
            return self.send_json(500, {"error": "Sorry, we couldn't save that. Please email cloudmjenzi@gmail.com."})
        log(f"Lead #{lead_id} saved ({ftype}, {entry['email']})")

        def mail():  # don't make the visitor wait for SMTP
            try:
                if send_email(lead_id, entry):
                    mark_emailed(lead_id)
            except Exception as e:  # lead is saved, so just log it
                log(f"Email for lead #{lead_id} failed: {e!r}")
        threading.Thread(target=mail, daemon=True).start()
        return self.send_json(200, {"ok": True, "id": lead_id})

    # ---- GET: health, admin export, static files (local testing only) ----
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self.send_json(200, {"ok": True})
        if path == "/api/leads.csv":
            auth = self.headers.get("Authorization", "")
            if not ADMIN_TOKEN or not hmac.compare_digest(auth, f"Bearer {ADMIN_TOKEN}"):
                return self.send_json(401, {"error": "Unauthorised"})
            with _lock, closing(db()) as con, con:
                rows = con.execute("SELECT id,received,type,reference,name,email,phone,company,topic,"
                                   "message,summary,emailed FROM leads ORDER BY id DESC").fetchall()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "received", "type", "reference", "name", "email", "phone", "company",
                        "topic", "message", "summary", "emailed"])
            # neutralise spreadsheet formulas in visitor-supplied text
            w.writerows([[(f"'{c}" if isinstance(c, str) and c and c[0] in "=+-@" else c) for c in r] for r in rows])
            return self.send_body(200, buf.getvalue().encode(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="mjenzi-leads.csv"'})
        if path.startswith("/api/"):
            return self.send_json(404, {"error": "Not found"})
        if not STATIC_DIR:
            return self.send_json(404, {"error": "Not found"})
        root = Path(STATIC_DIR).resolve()
        target = (root / path.lstrip("/")).resolve()
        if target.is_dir():
            target = target / "index.html"
        if (root not in target.parents) or not target.is_file() or "api" in target.relative_to(root).parts:
            return self.send_body(404, b"Not found", "text/plain")
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain"}
        self.send_body(200, target.read_bytes(), types.get(target.suffix, "application/octet-stream"))


if __name__ == "__main__":
    db().close()
    log(f"Mjenzi form server on http://{HOST}:{PORT}  db={DB_FILE.resolve()}  "
        f"email to: {', '.join(MAIL_TO) if SMTP_HOST else 'not configured (saving only)'}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
