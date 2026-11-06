// Mjenzi Cloud — shared header, footer and small helpers
(function () {
  const page = document.body.dataset.page || "home";
  const logo = `
    <svg class="logo-mark" viewBox="0 0 40 40" aria-hidden="true">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#2ee6c5"/><stop offset=".55" stop-color="#7b8cff"/><stop offset="1" stop-color="#ffb547"/></linearGradient></defs>
      <rect x="1" y="1" width="38" height="38" rx="11" fill="url(#lg)"/>
      <path d="M10 28V13l10 9 10-9v15" fill="none" stroke="#070b14" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;

  const links = [
    ["home", "index.html#services", "Services"],
    ["ai", "index.html#ai", "Mjenzi AI"],
    ["fde", "index.html#fde", "FDE"],
    ["network", "index.html#network", "Network"],
    ["assessment", "assessment.html", "Assessment"],
    ["sizing", "sizing.html", "Server Sizing"],
    ["cloud", "cloud-config.html", "Cloud Config"],
  ];

  const header = document.createElement("header");
  header.className = "site-header";
  header.innerHTML = `
    <div class="wrap nav">
      <a class="logo" href="index.html" aria-label="Mjenzi Cloud home">${logo}<span>Mjenzi<small>Cloud</small></span></a>
      <nav class="nav-links" id="navLinks" aria-label="Main">
        ${links.map(([k, h, t]) => `<a href="${h}" class="${k === page ? "active" : ""}">${t}</a>`).join("")}
      </nav>
      <div class="nav-cta">
        <a class="btn btn-ghost btn-sm" href="tel:+611300998025">+61 1300 998 025</a>
        <a class="btn btn-primary btn-sm" href="index.html#contact">Talk to us</a>
        <button class="menu-btn" aria-label="Open menu" aria-expanded="false" id="menuBtn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
        </button>
      </div>
    </div>`;
  document.body.prepend(header);

  const footer = document.createElement("footer");
  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="wrap">
      <div class="footer-grid">
        <div>
          <a class="logo" href="index.html">${logo}<span>Mjenzi<small>Cloud</small></span></a>
          <p style="margin-top:14px;max-width:340px">Sovereign cloud, AI and infrastructure built for Africa and Australia. Points of presence in Nairobi, Johannesburg, Gaborone, Sydney and Canberra.</p>
          <p style="margin:0"><a href="tel:+611300998025">+61 1300 998 025</a> · <a href="mailto:cloud@mjenzi.com">cloud@mjenzi.com</a></p>
        </div>
        <div>
          <h4>Platform</h4>
          <ul>
            <li><a href="index.html#services">Infrastructure-as-a-Service</a></li>
            <li><a href="index.html#ai">Mjenzi AI</a></li>
            <li><a href="index.html#fde">Forward Deployed Engineering</a></li>
            <li><a href="index.html#services">Enterprise SOC</a></li>
            <li><a href="index.html#services">Servers &amp; Hardware</a></li>
          </ul>
        </div>
        <div>
          <h4>Tools</h4>
          <ul>
            <li><a href="assessment.html">Cloud &amp; AI Rapid Assessment</a></li>
            <li><a href="sizing.html">Server Sizing &amp; Spec Sheet</a></li>
            <li><a href="cloud-config.html">Cloud Configuration Sheet</a></li>
          </ul>
        </div>
        <div>
          <h4>Company</h4>
          <ul>
            <li><a href="index.html#network">Locations</a></li>
            <li><a href="index.html#customers">Customers</a></li>
            <li><a href="index.html#contact">Contact</a></li>
            <li><a href="privacy.html">Privacy Policy</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span>© ${new Date().getFullYear()} Mjenzi Technologies. All rights reserved.</span>
        <span>Offices: Australia · Kenya · Botswana</span>
      </div>
    </div>`;
  document.body.append(footer);

  const btn = document.getElementById("menuBtn");
  const nl = document.getElementById("navLinks");
  btn.addEventListener("click", () => {
    const open = nl.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  nl.addEventListener("click", (e) => { if (e.target.tagName === "A") nl.classList.remove("open"); });

  // Reveal on scroll
  const io = "IntersectionObserver" in window ? new IntersectionObserver((es) => {
    es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { threshold: 0.12 }) : null;
  document.querySelectorAll(".reveal").forEach((el) => io ? io.observe(el) : el.classList.add("in"));
})();

// Shared helpers
window.Mjenzi = {
  fmt(n, d = 0) { return Number(n).toLocaleString("en-AU", { maximumFractionDigits: d, minimumFractionDigits: d }); },
  download(name, text, type = "text/csv") {
    const blob = new Blob([text], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  },
  csv(rows) { return rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n"); },
  esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); },
  ref(prefix) { const d = new Date(); return `${prefix}-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`; },

  // Form backend. Set window.MJENZI_API before common.js loads if the API lives on another host.
  API: window.MJENZI_API || "/api/submit",

  // POST a submission. Resolves {ok:true} or {ok:false, error, offline}.
  async submit(payload) {
    if (location.protocol === "file:") return { ok: false, offline: true, error: "Form server not reachable." };
    try {
      const res = await fetch(this.API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) return { ok: true, id: body.id };
      return { ok: false, offline: res.status >= 500 || res.status === 404, error: body.error || "Something went wrong. Please try again." };
    } catch (e) {
      return { ok: false, offline: true, error: "Form server not reachable." };
    }
  },

  mailto(subject, body) {
    location.href = `mailto:cloud@mjenzi.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  },

  // Modal that collects contact details, then submits a tool result.
  // opts: { type, title, intro, reference, summary: () => string, data: () => object }
  leadDialog(opts) {
    let dlg = document.getElementById("leadDlg");
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.id = "leadDlg";
      dlg.className = "lead-dlg";
      document.body.appendChild(dlg);
    }
    dlg.innerHTML = `
      <form method="dialog" class="lead-form" novalidate>
        <button type="button" class="dlg-x" aria-label="Close">✕</button>
        <h3>${this.esc(opts.title)}</h3>
        <p>${this.esc(opts.intro || "Leave your details and a Mjenzi engineer will get back to you, usually within one business day.")}</p>
        <div class="field-row">
          <div class="field"><label for="ld-name">Name</label><input id="ld-name" name="name" required autocomplete="name"></div>
          <div class="field"><label for="ld-company">Company</label><input id="ld-company" name="company" autocomplete="organization"></div>
        </div>
        <div class="field-row">
          <div class="field"><label for="ld-email">Work email</label><input id="ld-email" name="email" type="email" required autocomplete="email"></div>
          <div class="field"><label for="ld-phone">Phone</label><input id="ld-phone" name="phone" type="tel" autocomplete="tel"></div>
        </div>
        <div class="field"><label for="ld-msg">Anything else we should know? (optional)</label><textarea id="ld-msg" name="message" rows="3"></textarea></div>
        <div class="hp" aria-hidden="true"><label for="ld-web">Website</label><input id="ld-web" name="website" tabindex="-1" autocomplete="off"></div>
        <p class="form-status" role="status" aria-live="polite"></p>
        <div class="actions"><button type="submit" class="btn btn-primary">Send to Mjenzi</button><button type="button" class="btn btn-ghost dlg-cancel">Cancel</button></div>
        <p class="hint">${opts.reference ? `Reference ${this.esc(opts.reference)} · ` : ""}We use your details only to respond to you. See our <a href="privacy.html" target="_blank" style="text-decoration:underline">Privacy Policy</a>.</p>
      </form>`;
    const form = dlg.querySelector("form");
    const close = () => dlg.close();
    dlg.querySelector(".dlg-x").onclick = close;
    dlg.querySelector(".dlg-cancel").onclick = close;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(form);
      const payload = {
        type: opts.type, reference: opts.reference,
        name: f.get("name"), company: f.get("company"), email: f.get("email"), phone: f.get("phone"),
        message: f.get("message"), website: f.get("website"),
        summary: opts.summary(), data: opts.data ? opts.data() : null,
      };
      const done = await this.handleSubmit(form, payload, `${opts.title} ${opts.reference || ""}`.trim());
      if (done) setTimeout(close, 2200);
    });
    dlg.showModal();
    dlg.querySelector("#ld-name").focus();
  },

  // Shared submit flow: validate, post, show status; offer email if the server is unreachable.
  async handleSubmit(form, payload, mailSubject) {
    const status = form.querySelector(".form-status");
    const btn = form.querySelector('button[type="submit"]');
    status.className = "form-status";
    if (!String(payload.name || "").trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(payload.email || "").trim())) {
      status.textContent = "Please enter your name and a valid email address.";
      status.classList.add("err");
      return false;
    }
    btn.disabled = true; const label = btn.textContent; btn.textContent = "Sending…";
    const r = await this.submit(payload);
    btn.disabled = false; btn.textContent = label;
    if (r.ok) {
      status.textContent = "Thanks! We've received it and will be in touch shortly.";
      status.classList.add("ok");
      form.reset();
      return true;
    }
    status.classList.add("err");
    if (r.offline) {
      status.innerHTML = `We couldn't reach our server. <a href="#" class="mail-fallback">Send it by email instead</a>.`;
      status.querySelector(".mail-fallback").onclick = (e) => {
        e.preventDefault();
        const body = [`Name: ${payload.name}`, `Company: ${payload.company || "-"}`, `Email: ${payload.email}`, `Phone: ${payload.phone || "-"}`,
          payload.topic ? `Topic: ${payload.topic}` : "", "", payload.message || "", payload.summary ? "\n" + payload.summary : ""].filter((x) => x !== "").join("\n");
        this.mailto(mailSubject, body);
      };
    } else status.textContent = r.error;
    return false;
  },
};
