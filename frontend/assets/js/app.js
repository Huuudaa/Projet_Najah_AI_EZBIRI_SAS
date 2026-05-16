/* ═══════════════════════════════════════════════════
   NAJAH-AI — Shared JS utilities
═══════════════════════════════════════════════════ */

const API = "http://localhost:5000/api";

// ── HTTP ─────────────────────────────────────────────
function getToken() {
  return localStorage.getItem("najah_token") || "";
}
function setToken(t) {
  if (t) localStorage.setItem("najah_token", t);
}
function clearToken() {
  localStorage.removeItem("najah_token");
  localStorage.removeItem("najah_user");
}

async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": "Bearer " + token } : {}),
    ...(options.headers || {})
  };
  const cfg = { credentials: "include", ...options, headers };
  try {
    const r = await fetch(`${API}${endpoint}`, cfg);
    if (r.status === 401) {
      clearToken();
      window.location.href = "/login.html";
      return null;
    }
    return await r.json();
  } catch(e) {
    console.error("apiFetch error:", e);
    return null;
  }
}
async function apiPost(ep, body) {
  return apiFetch(ep, { method: "POST", body: JSON.stringify(body) });
}

// ── Auth ──────────────────────────────────────────────
async function requireAuth(expectedRole) {
  const token = getToken();
  if (!token) { window.location.href = "/login.html"; return null; }
  const d = await apiFetch("/auth/me");
  if (!d || !d.authenticated) {
    clearToken();
    window.location.href = "/login.html";
    return null;
  }
  if (expectedRole && d.role !== expectedRole) {
    window.location.href = d.role === "professeur" ? "/dashboard_prof.html" : "/dashboard_etu.html";
    return null;
  }
  return d;
}
async function logout() {
  await apiPost("/auth/logout", {});
  clearToken();
  window.location.href = "/login.html";
}

// ── Toast ──────────────────────────────────────────────
function toast(msg, type = "success") {
  let el = document.getElementById("__toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "__toast"; el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(el.__timer);
  el.__timer = setTimeout(() => el.classList.remove("show"), 3000);
}

// ── Sidebar ────────────────────────────────────────────
function buildSidebar(role, activePage, user) {
  const initials = ((user.prenom || "?")[0] + (user.nom || "?")[0]).toUpperCase();
  const profNav = [
    { label: "Tableau de bord", page: "/dashboard_prof.html", icon: svgGrid() },
    { label: "Étudiants",       page: "/etudiants.html",      icon: svgUsers() },
    { label: "Alertes",         page: "/alertes.html",        icon: svgBell() },
    { section: "Éthique & Données" },
    { label: "Consentements",   page: "/consentements.html",  icon: svgShield() },
    { label: "Journal d'audit", page: "/audit.html",          icon: svgLog() },
    { section: "Compte" },
    { label: "Mon profil",      page: "/profil.html",         icon: svgUser() },
  ];
  const stuNav = [
    { label: "Tableau de bord",   page: "/dashboard_etu.html",      icon: svgGrid() },
    { label: "Mon engagement",    page: "/mon_engagement.html",      icon: svgChart() },
    { section: "Éthique" },
    { label: "Mes consentements", page: "/mes_consentements.html",   icon: svgShield() },
    { section: "Compte" },
    { label: "Mon profil",        page: "/profil.html",              icon: svgUser() },
  ];
  const nav = role === "professeur" ? profNav : stuNav;

  const navHtml = nav.map(item => {
    if (item.section) return `<div class="nav-section"><div class="nav-section-label">${item.section}</div>`;
    const active = activePage === item.page ? " active" : "";
    return `<a href="${item.page}" class="nav-item${active}">${item.icon}<span>${item.label}</span></a>`;
  }).join("") + "</div>";

  const roleLabel = role === "professeur" ? "Professeur" : "Étudiant";

  return `
    <div class="sidebar-brand">
      <span class="brand-logo">Najah-AI</span>
      <span class="brand-sub">UCA · AI2S · ENSA</span>
    </div>
    <div class="nav-section">
      ${navHtml}
    </div>
    <div class="sidebar-user">
      <div class="user-card">
        <div class="user-avatar">${initials}</div>
        <div>
          <div class="user-name">${user.prenom} ${user.nom}</div>
          <div class="user-role">${roleLabel}</div>
        </div>
      </div>
      <button onclick="logout()" class="btn btn-secondary btn-sm" style="width:100%;margin-top:10px;justify-content:center">
        ${svgLogout()} Déconnexion
      </button>
    </div>`;
}

// ── Helpers ────────────────────────────────────────────
function labelBadge(label) {
  const map = { "Engagé": "badge-sage", "Modéré": "badge-amber", "À risque": "badge-red" };
  return `<span class="badge ${map[label]||'badge-beige'}">${label||'—'}</span>`;
}
function severityBadge(sev) {
  const map = { "critique": "badge-red", "elevee": "badge-amber", "normale": "badge-blue" };
  const labels = { "critique": "Critique", "elevee": "Élevée", "normale": "Normale" };
  return `<span class="badge ${map[sev]||'badge-beige'}">${labels[sev]||sev}</span>`;
}
function progressBar(val, cls="blue") {
  return `<div class="progress"><div class="progress-bar ${cls}" style="width:${Math.min(100,val)}%"></div></div>`;
}
function scoreColor(score) {
  if (score >= 68) return "var(--sage)";
  if (score >= 38) return "var(--amber)";
  return "var(--red)";
}
function consentLabel(type) {
  const map = { analytics: "Analyse d'engagement", personalization: "Personnalisation", data_sharing: "Partage de données" };
  return map[type] || type;
}
function consentDesc(type) {
  const map = {
    analytics: "Autoriser l'analyse de votre comportement d'apprentissage (temps passé, interactions, scores).",
    personalization: "Autoriser la personnalisation des contenus selon votre profil pédagogique.",
    data_sharing: "Autoriser le partage anonymisé de vos données à des fins de recherche académique."
  };
  return map[type] || "";
}

// ── SVG Icons ─────────────────────────────────────────
function svgGrid()   { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" stroke-width="1.7"/><rect x="14" y="3" width="7" height="7" rx="1" stroke-width="1.7"/><rect x="3" y="14" width="7" height="7" rx="1" stroke-width="1.7"/><rect x="14" y="14" width="7" height="7" rx="1" stroke-width="1.7"/></svg>`; }
function svgUsers()  { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4" stroke-width="1.7"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>`; }
function svgBell()   { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></svg>`; }
function svgShield() { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`; }
function svgLog()    { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><line x1="16" y1="13" x2="8" y2="13" stroke-width="1.7" stroke-linecap="round"/><line x1="16" y1="17" x2="8" y2="17" stroke-width="1.7" stroke-linecap="round"/><polyline points="10 9 9 9 8 9" stroke-width="1.7" stroke-linecap="round"/></svg>`; }
function svgUser()   { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4" stroke-width="1.7"/></svg>`; }
function svgChart()  { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"/></svg>`; }
function svgLogout() { return `<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>`; }
function svgRefresh(){ return `<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>`; }
function svgCheck()  { return `<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>`; }
function svgSearch() { return `<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" stroke-width="1.7"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke-linecap="round" stroke-width="1.7"/></svg>`; }
function svgML() { return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>`; }
