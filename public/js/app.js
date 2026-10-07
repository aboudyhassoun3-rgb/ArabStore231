/* =========================================================
   ARAB STORE — app.js
   أدوات مشتركة بين كل صفحات الموقع
   ⚠️ API_BASE حالياً عنوان مؤقت — رح نربطه بالـ backend الحقيقي
   لما نبني سيرفر الـ API (المرحلة الجاية).
   ========================================================= */
const API_BASE = "/api"; // TODO: استبدلها بعنوان السيرفر الحقيقي بعد نشر الـ backend

const Store = {
  token(){ return localStorage.getItem("token"); },
  setToken(t){ localStorage.setItem("token", t); },
  clearToken(){ localStorage.removeItem("token"); },
  user(){ try{ return JSON.parse(localStorage.getItem("user")||"null"); }catch(e){ return null; } },
  setUser(u){ localStorage.setItem("user", JSON.stringify(u)); },
};

/* ===== العملة المعروضة (USD / SYP) — متزامنة بكل صفحات الموقع ===== */
const Currency = {
  get(){ return localStorage.getItem("displayCurrency") || "USD"; },
  set(c){ localStorage.setItem("displayCurrency", c); },
  async save(c){
    this.set(c);
    if(Store.token()) await apiFetch("/auth/currency", { method:"POST", body:JSON.stringify({ currency:c }) });
  },
  toggle(){ this.set(this.get() === "USD" ? "SYP" : "USD"); return this.get(); },
  rate(){ return parseFloat(localStorage.getItem("exchangeRate") || "0") || 0; },
  setRate(r){ if(r) localStorage.setItem("exchangeRate", r); },
  /* يحوّل سعر بالدولار لنص جاهز للعرض حسب العملة المختارة حالياً */
  format(usd){
    usd = Number(usd) || 0;
    if(this.get() === "SYP"){
      const syp = usd * this.rate();
      return Math.round(syp).toLocaleString() + " ل.س";
    }
    return "$" + usd.toFixed(2);
  }
};

/* ===== اللغة (عربي / إنكليزي) ===== */
const Lang = {
  get(){ return localStorage.getItem("lang") || "ar"; },
  set(l){ localStorage.setItem("lang", l); },
};
function applyTranslations(){
  const lang = Lang.get();
  document.documentElement.lang = lang === "en" ? "en" : "ar";
  document.documentElement.dir = lang === "en" ? "ltr" : "rtl";
  document.querySelectorAll("[data-ar]").forEach(el=>{
    const text = lang === "en" ? (el.dataset.en || el.dataset.ar) : el.dataset.ar;
    if(el.hasAttribute("data-attr-placeholder")) el.setAttribute("placeholder", text);
    else el.textContent = text;
  });
}
function toggleLanguage(){
  Lang.set(Lang.get() === "en" ? "ar" : "en");
  applyTranslations();
}
(function initTheme(){
  const saved = localStorage.getItem("theme");
  if(saved) document.documentElement.dataset.theme = saved;
})();
function toggleTheme(){
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "light" ? "dark" : "light";
  localStorage.setItem("theme", html.dataset.theme);
}

/* ===== Drawer ===== */
function toggleDrawer(open){
  const d = document.getElementById("drawer");
  const o = document.getElementById("overlay");
  if(!d || !o) return;
  d.classList.toggle("open", open);
  o.classList.toggle("show", open);
  document.body.style.overflow = open ? "hidden" : "";
}
document.addEventListener("click", (e)=>{
  if(!e.target.closest(".drawer") && !e.target.closest(".menu-btn")){
    toggleDrawer(false);
  }
});

/* ===== Toast ===== */
function toast(msg, type="success"){
  let el = document.getElementById("appToast");
  if(!el){
    el = document.createElement("div");
    el.id = "appToast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  const icon = type === "error" ? "fa-circle-xmark" : "fa-circle-check";
  el.className = `toast show ${type}`;
  el.innerHTML = `<i class="fa-solid ${icon}"></i><span>${msg}</span>`;
  clearTimeout(el._t);
  el._t = setTimeout(()=> el.classList.remove("show"), 2600);
}

/* ===== API helper (جاهز للربط مع backend لاحقاً) ===== */
async function apiFetch(path, opts={}){
  const headers = Object.assign({ "Accept":"application/json" }, opts.headers || {});
  const token = Store.token();
  if(token) headers["Authorization"] = "Bearer " + token;
  if(opts.body && !(opts.body instanceof FormData)){
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(API_BASE + path, Object.assign({}, opts, { headers }));
  let data = null;
  try{ data = await res.json(); }catch(e){ /* لا يوجد body */ }
  if(!res.ok){
    const err = new Error((data && (data.message||data.error)) || "حدث خطأ، حاول مرة ثانية");
    err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

/* ===== الدرج: تحديث حالة المستخدم (زائر / مسجل) ===== */
function renderAuthState(){
  const user = Store.user();
  const nameEl = document.getElementById("drawerUserName");
  const emailEl = document.getElementById("drawerUserEmail");
  const authButtons = document.getElementById("drawerAuthButtons");
  const logoutBox = document.getElementById("logoutBox");
  const balancePill = document.getElementById("balancePillValue");
  const guestOnlyEls = document.querySelectorAll(".guest-hide");
  const apiMenuItem = document.getElementById("apiMenuItem");

  if(!user){
    if(nameEl) nameEl.textContent = "زائر";
    if(emailEl) emailEl.textContent = "سجّل دخولك للاستفادة من المحفظة والطلبات";
    if(authButtons) authButtons.style.display = "flex";
    if(logoutBox) logoutBox.style.display = "none";
    if(balancePill) balancePill.textContent = "$0.00";
    guestOnlyEls.forEach(el => el.style.display = "none");
    if(apiMenuItem) apiMenuItem.style.display = "none";
    return;
  }
  if(nameEl){
    if(user.discount_tier_name){
      nameEl.innerHTML = `<span class="badge-vip"><i class="fa-solid fa-crown"></i> ${user.discount_tier_name}</span> ${user.name || "مستخدم"}`;
    } else {
      nameEl.textContent = user.name || "مستخدم";
    }
  }
  if(emailEl) emailEl.textContent = user.email || "";
  if(authButtons) authButtons.style.display = "none";
  if(logoutBox) logoutBox.style.display = "block";
  if(balancePill) balancePill.textContent = Currency.format(user.balance||0);
  guestOnlyEls.forEach(el => el.style.display = "");
  if(apiMenuItem) apiMenuItem.style.display = user.api_enabled ? "" : "none";
  const ownerAdminItem = document.getElementById("ownerAdminMenuItem");
  // إظهار لوحة الأدمن لأي حساب صلاحياته أدمن (المالك أو أي بريد مضاف من لوحة الأدمن)
  if(ownerAdminItem) ownerAdminItem.style.display = user.is_admin ? "" : "none";
}

function logoutUser(e){
  if(e) e.stopPropagation();
  Store.clearToken();
  localStorage.removeItem("user");
  toggleDrawer(false);
  setTimeout(()=>{ window.location.href = "/store.html"; }, 150);
}

function goLogin(e){ if(e) e.stopPropagation(); toggleDrawer(false); setTimeout(()=> window.location.href="/login.html", 120); }
function goRegister(e){ if(e) e.stopPropagation(); toggleDrawer(false); setTimeout(()=> window.location.href="/register.html", 120); }

/* ===== الفاب العائم ===== */
function setupFab(){
  const fab = document.getElementById("fabMainBtn");
  const opts = document.getElementById("fabOptions");
  if(!fab || !opts) return;
  fab.addEventListener("click", (e)=>{ e.stopPropagation(); opts.classList.toggle("open"); });
  document.addEventListener("click", (e)=>{
    if(!e.target.closest(".fab-stack")) opts.classList.remove("open");
  });
}

/* ===== إعدادات الموقع العامة (لوغو المطوّر + روابط التواصل) ===== */
let SITE_SETTINGS = null;

async function loadSiteBranding(){
  try{
    const res = await fetch(API_BASE + "/store/settings");
    SITE_SETTINGS = await res.json();
  }catch(e){ return; }
  applyDevLogo();
  applyContactLinks();
}

function applyDevLogo(){
  const url = SITE_SETTINGS && SITE_SETTINGS.dev_logo;
  if(!url) return;
  document.querySelectorAll(".dev-logo").forEach(img=>{
    img.src = url;
    img.onerror = ()=>{ img.style.display = "none"; };
    img.style.display = "";
  });
}

function applyContactLinks(){
  const opts = document.getElementById("fabOptions");
  const c = (SITE_SETTINGS && SITE_SETTINGS.contact) || {};
  if(!opts) return;
  const links = [
    { url: c.telegram_url, icon: "fa-brands fa-telegram", title: "الدعم على تيليجرام" },
    { url: c.whatsapp_url, icon: "fa-brands fa-whatsapp", title: "الدعم على واتساب" },
    { url: c.whatsapp_channel_url, icon: "fa-solid fa-bullhorn", title: "قناة أخبار واتساب" },
    { url: c.telegram_channel_url, icon: "fa-solid fa-tower-broadcast", title: "قناة أخبار تيليجرام" },
  ].filter(l => l.url);
  if(!links.length) return; // نخلي الروابط الافتراضية بالصفحة
  opts.innerHTML = links.map(l =>
    `<a href="${l.url}" target="_blank" rel="noopener" class="fab-option" title="${l.title}"><i class="${l.icon}"></i></a>`
  ).join("");
}

/* ===== إشعارات فعلية بالخلفية مع صوت رنين ===== */
const NOTIF_SEEN_KEY = "lastNotifId";
let _notifBootstrapped = false;

function playNotifSound(){
  try{
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if(!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    [880, 1174].forEach((freq, i)=>{
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + i*0.18);
      gain.gain.exponentialRampToValueAtTime(0.25, now + i*0.18 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i*0.18 + 0.16);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(now + i*0.18); osc.stop(now + i*0.18 + 0.2);
    });
    setTimeout(()=>{ try{ ctx.close(); }catch(e){} }, 900);
  }catch(e){}
}

function askNotifPermission(){
  if(!("Notification" in window)) return;
  if(Notification.permission === "default"){
    const ask = ()=>{
      Notification.requestPermission().then((permission)=>{ if(permission === "granted") enableWebPush(); }).catch(()=>{});
      document.removeEventListener("click", ask);
    };
    document.addEventListener("click", ask, { once:true });
  } else if(Notification.permission === "granted") {
    enableWebPush();
  }
}

function pushKeyBytes(base64){
  const padding = "=".repeat((4 - base64.length % 4) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map(ch => ch.charCodeAt(0)));
}

async function enableWebPush(){
  if(!Store.token() || !("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try{
    const keyRes = await fetch(API_BASE + "/push/public-key");
    const keyData = await keyRes.json();
    if(!keyData.enabled || !keyData.public_key || Notification.permission !== "granted") return;
    const registration = await navigator.serviceWorker.register("/sw.js");
    let subscription = await registration.pushManager.getSubscription();
    if(!subscription){
      subscription = await registration.pushManager.subscribe({ userVisibleOnly:true, applicationServerKey:pushKeyBytes(keyData.public_key) });
    }
    await apiFetch("/push/subscribe", { method:"POST", body:JSON.stringify(subscription.toJSON()) });
  }catch(err){ /* إشعارات الخلفية اختيارية ولا تعطل الموقع */ }
}

function showSystemNotification(n){
  try{
    if(!("Notification" in window) || Notification.permission !== "granted") return;
    const note = new Notification(n.title || "إشعار جديد", {
      body: n.message || "",
      icon: "/site-icon",
      tag: "arab-store-" + n.id,
    });
    note.onclick = ()=>{ window.focus(); location.href = "/activity.html"; };
  }catch(e){}
}

function handleIncomingNotifications(items){
  if(!items || !items.length) return;
  const ids = items.map(n => Number(n.id) || 0);
  const maxId = Math.max.apply(null, ids);
  const lastSeen = Number(localStorage.getItem(NOTIF_SEEN_KEY) || 0);
  if(!_notifBootstrapped && !lastSeen){
    localStorage.setItem(NOTIF_SEEN_KEY, String(maxId));
    _notifBootstrapped = true;
    return;
  }
  _notifBootstrapped = true;
  const fresh = items.filter(n => Number(n.id) > lastSeen);
  if(!fresh.length) return;
  localStorage.setItem(NOTIF_SEEN_KEY, String(maxId));
  playNotifSound();
  fresh.slice(0, 3).forEach(showSystemNotification);
  if(typeof toast === "function") toast("🔔 " + (fresh[0].title || "لديك إشعار جديد"));
}

/* ===== تفعيل عنصر التنقل السفلي الحالي ===== */
function setActiveNav(){
  const path = location.pathname;
  document.querySelectorAll(".nav-item").forEach(item=>{
    const href = item.getAttribute("href");
    if(href && path.includes(href)) item.classList.add("active");
  });
}

/* ===== مزامنة بيانات المستخدم مع السيرفر (لو الأدمن غيّر شي مثل تفعيل API) ===== */
async function syncUserState(){
  if(!Store.token()) return;
  try{
    const data = await apiFetch("/auth/me");
    Store.setUser(Object.assign(data.user, { balance: data.user.balance_usd }));
    if(data.user.preferred_currency) Currency.set(data.user.preferred_currency);
    renderAuthState();
  }catch(err){
    if(err.status === 401){ Store.clearToken(); localStorage.removeItem("user"); renderAuthState(); }
  }
}

/* ===== جرس الإشعارات (موحّد بكل الصفحات) ===== */
const NOTIF_ICONS = { success:"fa-circle-check", danger:"fa-circle-xmark", info:"fa-circle-info" };

function ensureNotifPanel(){
  let panel = document.getElementById("notifPanel");
  if(panel) return panel;
  panel = document.createElement("div");
  panel.id = "notifPanel";
  panel.className = "notif-panel";
  panel.innerHTML = `<div class="notif-panel-head">الإشعارات</div><div id="notifPanelBody"></div>`;
  document.body.appendChild(panel);
  document.addEventListener("click", (e)=>{
    if(!e.target.closest("#notifPanel") && !e.target.closest("#notifBellBtn")){
      panel.classList.remove("show");
    }
  });
  return panel;
}

function timeAgo(iso){
  try{
    const diffMs = Date.now() - new Date(iso.replace(" ","T")+"Z").getTime();
    const mins = Math.floor(diffMs/60000);
    if(mins < 1) return "الآن";
    if(mins < 60) return `منذ ${mins} د`;
    const hrs = Math.floor(mins/60);
    if(hrs < 24) return `منذ ${hrs} س`;
    const days = Math.floor(hrs/24);
    return `منذ ${days} يوم`;
  }catch(e){ return ""; }
}

async function loadNotifications(){
  const badge = document.getElementById("notifBadge");
  if(!Store.token()){ if(badge) badge.style.display = "none"; return; }
  try{
    const data = await apiFetch("/notifications");
    if(badge){
      if(data.unread > 0){ badge.textContent = data.unread > 9 ? "9+" : data.unread; badge.style.display = "flex"; }
      else{ badge.style.display = "none"; }
    }
    handleIncomingNotifications(data.items);
    const body = document.getElementById("notifPanelBody");
    if(body){
      if(!data.items.length){
        body.innerHTML = `<div class="notif-empty"><i class="fa-solid fa-bell-slash" style="font-size:20px; margin-bottom:8px; display:block;"></i>ما في إشعارات بعد</div>`;
      } else {
        body.innerHTML = data.items.map(n => `
          <div class="notif-item ${n.kind}">
            <i class="fa-solid ${NOTIF_ICONS[n.kind] || 'fa-circle-info'}"></i>
            <div style="flex:1;">
              <div class="t">${n.title}</div>
              <div class="m">${n.message || ""}</div>
              <div class="d">${timeAgo(n.created_at)}</div>
            </div>
          </div>`).join("");
      }
    }
  }catch(err){ /* تجاهل بهدوء */ }
}

function setupNotifBell(){
  const btn = document.getElementById("notifBellBtn");
  if(!btn) return;
  const panel = ensureNotifPanel();
  btn.addEventListener("click", async (e)=>{
    e.stopPropagation();
    panel.classList.toggle("show");
    if(panel.classList.contains("show")){
      await loadNotifications();
      const badge = document.getElementById("notifBadge");
      if(badge && badge.style.display !== "none"){
        try{ await apiFetch("/notifications/mark-read", { method:"POST" }); badge.style.display = "none"; }catch(e){}
      }
    }
  });
}

/* ===== وضع الصيانة ===== */
let _maintenanceInterval = null;

function formatMaintenanceCountdown(sec){
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return [h, m, s].map(n => String(n).padStart(2, "0")).join(" / ");
}

function showMaintenanceScreen(secondsLeft){
  if(document.getElementById("maintenanceOverlay")) return;
  const overlay = document.createElement("div");
  overlay.id = "maintenanceOverlay";
  overlay.style.cssText = "position:fixed; inset:0; z-index:99999; background:var(--bg,#0b0d14); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; text-align:center; padding:24px;";
  overlay.innerHTML = `
    <i class="fa-solid fa-screwdriver-wrench" style="font-size:42px; color:var(--accent,#e63946);"></i>
    <div style="font-size:16px; font-weight:800; color:var(--text,#fff); max-width:320px; line-height:1.6;">
      عذراً الموقع في فترة الصيانة<br>نعمل على تحديثات أفضل
    </div>
    <div id="maintenanceCountdown" style="font-family:'Orbitron',sans-serif; font-size:22px; font-weight:800; color:var(--accent,#e63946); letter-spacing:1px;">
      ${formatMaintenanceCountdown(secondsLeft)}
    </div>`;
  document.documentElement.appendChild(overlay);
  document.body.style.overflow = "hidden";

  let remaining = secondsLeft;
  _maintenanceInterval = setInterval(()=>{
    remaining -= 1;
    if(remaining <= 0){
      clearInterval(_maintenanceInterval);
      location.reload();
      return;
    }
    const el = document.getElementById("maintenanceCountdown");
    if(el) el.textContent = formatMaintenanceCountdown(remaining);
  }, 1000);
}

async function checkMaintenanceMode(){
  // لوحة تحكم الأدمن وصفحة تسجيل الدخول لازم تبقى وصولة دايماً عشان الأدمن يقدر يسجّل دخول ويوقف الصيانة
  if(location.pathname.includes("admin.html") || location.pathname.includes("login.html")) return;
  try{
    const res = await fetch(API_BASE + "/maintenance-status");
    const data = await res.json();
    if(data.enabled){
      showMaintenanceScreen(data.seconds_left);
    }
  }catch(err){ /* تجاهل أي خطأ شبكة هون، ما منوقف الموقع لأجل هيك */ }
}

document.addEventListener("DOMContentLoaded", ()=>{
  applyTranslations();
  renderAuthState();
  setupFab();
  loadSiteBranding();
  askNotifPermission();
  setActiveNav();
  setupNotifBell();
  syncUserState();
  loadNotifications();
  checkMaintenanceMode();
  setTimeout(enableWebPush, 900);
  // تحديث الرصيد كل 30 ثانية بشكل صامت (يستخدم syncUserState الموجودة أصلاً)
  setInterval(syncUserState, 30000);
  setInterval(loadNotifications, 30000);
});
