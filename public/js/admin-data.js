/* =========================================================
   ARAB ADMIN — admin-data.js
   منطق تنقّل لوحة التحكم + كل البيانات حقيقية من السيرفر
   (ولا قيمة وهمية متبقية — كل قسم متصل بـ /api/admin/*)
   ========================================================= */

const SECTION_TITLES = {
  dashboard:"الرئيسية", orders:"الطلبات", deposits:"الإيداعات",
  users:"المستخدمون", "discount-tiers":"المستويات", products:"المنتجات",
  "smart-admin":"الإدارة الذكية", backup:"النسخ الاحتياطي",
};

const SECTION_LOADERS = {
  dashboard: ()=>Promise.all([loadDashboard(), loadProfits(), loadSettings(), loadAdmins(), loadWebAdmins()]),

  orders: ()=>Promise.all([loadOrders("all"), loadShopOrders()]),
  deposits: ()=>Promise.all([loadDeposits(), loadDepositMethods()]),
  users: loadUsers,
  "discount-tiers": loadDiscountTiers,
  products: ()=>Promise.all([loadProducts(), loadSections()]),
  "smart-admin": ()=>Promise.all([loadProviders(), loadPricing()]),
  backup: ()=>Promise.all([loadBackups(), loadSnaps()]),
};
async function changeAdminPassword(){
  const cur = document.getElementById("admCurPw").value, nw = document.getElementById("admNewPw").value;
  if(!cur || nw.length < 8){ toast("أدخل الحالية والجديدة (8+ أحرف)", "error"); return; }
  try{
    const r = await adminFetch("/admin/password", { method:"POST", body: JSON.stringify({ current: cur, new: nw }) });
    toast(r.message); document.getElementById("admCurPw").value = ""; document.getElementById("admNewPw").value = "";
  }catch(err){ toast(err.message, "error"); }
}
async function loadSnaps(){
  const body = document.getElementById("snapsTableBody");
  if(!body) return;
  try{
    const data = await adminFetch("/admin/snapshots");
    body.innerHTML = data.map(s=>`<tr><td>${s.reason}</td><td>${s.created_at}</td><td>${s.size_kb} KB</td>
      <td class="row-actions"><button class="btn-sm primary" onclick="restoreSnap('${s.id}')">استرجاع</button>
      <button class="btn-sm danger" onclick="deleteSnap('${s.id}')">حذف</button></td></tr>`).join("")
      || `<tr><td colspan="4">لا توجد نسخ تلقائية بعد</td></tr>`;
  }catch(err){ body.innerHTML = `<tr><td colspan="4">${err.message}</td></tr>`; }
}
async function restoreSnap(id){
  if(!confirm("استرجاع هذه النسخة؟ سيتم استبدال البيانات الحالية.")) return;
  try{ const r = await adminFetch(`/admin/snapshots/${encodeURIComponent(id)}/restore`, { method:"POST" }); toast(r.message); setTimeout(()=>location.reload(), 1000); }
  catch(err){ toast(err.message, "error"); }
}
async function deleteSnap(id){
  try{ await adminFetch(`/admin/snapshots/${encodeURIComponent(id)}`, { method:"DELETE" }); loadSnaps(); }
  catch(err){ toast(err.message, "error"); }
}
function downloadJsonBackup(){
  const token = localStorage.getItem("admin_token") || "";
  const a = document.createElement("a");
  a.href = "/api/admin/backup-json?token=" + encodeURIComponent(token);
  a.download = "arab-store-backup.json";
  document.body.appendChild(a); a.click(); a.remove();
  toast("جاري تنزيل النسخة…");
}
async function restoreJsonBackup(input){
  const f = input.files && input.files[0];
  if(!f) return;
  if(!confirm("استرجاع هذا الملف؟ سيتم استبدال البيانات الحالية (تُؤخذ نسخة أمان أولاً).")){ input.value=""; return; }
  const fd = new FormData(); fd.append("file", f);
  try{ const r = await adminFetch("/admin/restore-json", { method:"POST", body: fd }); toast(r.message); setTimeout(()=>location.reload(), 1200); }
  catch(err){ toast(err.message, "error"); }
  input.value = "";
}

function goSection(name, navEl){
  document.querySelectorAll(".admin-section").forEach(s=>s.classList.remove("active"));
  document.getElementById("sec-"+name)?.classList.add("active");
  document.querySelectorAll(".admin-nav-item").forEach(n=>n.classList.remove("active"));
  if(navEl) navEl.classList.add("active");
  document.getElementById("sectionTitle").textContent = SECTION_TITLES[name] || name;
  toggleSidebar(false);
  window.scrollTo({ top:0, behavior:"smooth" });
  SECTION_LOADERS[name]?.().catch(err=> toast(err.message, "error"));
}

function toggleSidebar(open){
  document.getElementById("adminSidebar").classList.toggle("open", open);
  document.getElementById("adminOverlay").classList.toggle("show", open);
}

/* ===== أداة استدعاء API بصلاحية الأدمن ===== */
async function adminFetch(path, opts={}){
  const token = localStorage.getItem("admin_token");
  const headers = Object.assign({ "Accept":"application/json" }, opts.headers || {});
  if(token) headers["Authorization"] = "Bearer " + token;
  if(opts.body && !(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(API_BASE + path, Object.assign({}, opts, { headers }));
  const data = await res.json().catch(()=>null);
  if(res.status === 401){ adminLogout(); throw new Error("انتهت الجلسة"); }
  if(!res.ok) throw new Error((data && data.message) || "حدث خطأ");
  return data;
}

let lastCatalogBatchId = "";
async function importCatalogCsv(){
  const input = document.getElementById("catalogCsvInput");
  const result = document.getElementById("catalogImportResult");
  const file = input?.files?.[0];
  if(!file){ toast("اختر ملف CSV أولاً", "error"); return; }
  const fd = new FormData(); fd.append("file", file);
  if(result) result.textContent = "جارِ الاستيراد، يرجى الانتظار...";
  try{
    const data = await adminFetch("/admin/catalog/import-csv", { method:"POST", body:fd });
    lastCatalogBatchId = data.batch_id || "";
    if(result) result.textContent = `${data.message}. تم تجاهل ${data.skipped_unknown} منتج غير معروف و${data.skipped_duplicate} مكرر.`;
    document.getElementById("catalogRollbackBtn").style.display = lastCatalogBatchId ? "inline-flex" : "none";
    toast("تم استيراد المنتجات ✅");
    loadProducts(); loadSections();
  }catch(err){ if(result) result.textContent = err.message; toast(err.message, "error"); }
}
async function rollbackCatalogImport(){
  if(!lastCatalogBatchId || !confirm("هل تريد حذف آخر دفعة مستوردة؟")) return;
  try{
    const data = await adminFetch(`/admin/catalog/import/${encodeURIComponent(lastCatalogBatchId)}`, { method:"DELETE" });
    toast(data.message); lastCatalogBatchId = "";
    document.getElementById("catalogRollbackBtn").style.display = "none";
    document.getElementById("catalogImportResult").textContent = data.message;
    loadProducts(); loadSections();
  }catch(err){ toast(err.message, "error"); }
}
async function clearCatalogProducts(){
  if(!confirm("سيتم حذف كل المنتجات والباقات نهائياً. متابعة؟")) return;
  try{
    const data = await adminFetch("/admin/catalog/clear", { method:"POST" });
    toast(data.message); loadProducts(); loadSections();
  }catch(err){ toast(err.message, "error"); }
}
async function brandAllImages(){
  try{
    toast("جاري توليد الصور… ⏳");
    const data = await adminFetch("/admin/catalog/brand-images", { method:"POST" });
    toast(data.message); loadProducts();
  }catch(err){ toast(err.message, "error"); }
}

const STATUS_LABEL = { processing:"قيد التنفيذ", completed:"مكتمل", failed:"فشل", pending:"بإنتظار المراجعة" };

/* ===== رفع الصور (أقسام / منتجات / فئات) ===== */
let pendingUploadTarget = null;
function pickImage(kind, id){
  pendingUploadTarget = { kind, id };
  document.getElementById("globalImageInput").value = "";
  document.getElementById("globalImageInput").click();
}
document.addEventListener("DOMContentLoaded", ()=>{
  document.getElementById("globalImageInput")?.addEventListener("change", async (e)=>{
    const file = e.target.files[0];
    if(!file || !pendingUploadTarget) return;
    const { kind, id } = pendingUploadTarget;
    const endpoints = {
      section:`/admin/sections/${id}/image`, product:`/admin/products/${id}/image`,
      category:`/admin/categories/${id}/image`, banner:`/admin/settings/banner-image`,
      logo:`/admin/settings/logo`, subsection:`/admin/subsections/${id}/image`,
      manual_method:`/admin/deposit-methods/manual/${id}/image`, auto_method:`/admin/deposit-methods/auto/${id}/image`,
      app_icon:`/admin/settings/app-icon`, dev_logo:`/admin/settings/dev-logo`,
    };
    const fd = new FormData();
    fd.append("file", file);
    try{
      await adminFetch(endpoints[kind], { method:"POST", body: fd });
      toast("تم رفع الصورة ✅");
      if(kind === "section") loadSections();
      if(kind === "product") loadProducts();
      if(kind === "category") loadCategories();
      if(kind === "subsection") loadSubsections();
      if(kind === "banner" || kind === "logo" || kind === "app_icon" || kind === "dev_logo") loadSettings();
      if(kind === "manual_method" || kind === "auto_method") loadDepositMethods();
    }catch(err){ toast(err.message, "error"); }
  });
});

async function renderTables(){
  await loadDashboard().catch(err=> toast(err.message, "error"));
  loadAdminAlerts();
  askAdminNotificationPermission();
  setInterval(loadAdminAlerts, 30000);
}

/* ===== زر التنبيهات بهيدر لوحة الأدمن ===== */
const ADMIN_NOTIF_SEEN_KEY = "adminLastNotifId";
let adminNotifBootstrapped = false;

function askAdminNotificationPermission(){
  if(!("Notification" in window)) return;
  if(Notification.permission === "default"){
    Notification.requestPermission().then((permission)=>{ if(permission === "granted") enableAdminWebPush(); }).catch(()=>{});
  } else if(Notification.permission === "granted") enableAdminWebPush();
}

function adminPushKeyBytes(base64){
  const padding = "=".repeat((4 - base64.length % 4) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map(ch => ch.charCodeAt(0)));
}

async function enableAdminWebPush(){
  if(!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try{
    const keyRes = await fetch(API_BASE + "/push/public-key");
    const keyData = await keyRes.json();
    if(!keyData.enabled || !keyData.public_key || Notification.permission !== "granted") return;
    const registration = await navigator.serviceWorker.register("/sw.js");
    let subscription = await registration.pushManager.getSubscription();
    if(!subscription){
      subscription = await registration.pushManager.subscribe({ userVisibleOnly:true, applicationServerKey:adminPushKeyBytes(keyData.public_key) });
    }
    await adminFetch("/admin/push/subscribe", { method:"POST", body:JSON.stringify(subscription.toJSON()) });
  }catch(err){ /* إشعارات الخلفية اختيارية */ }
}

function showAdminSystemNotification(n){
  if(!("Notification" in window) || Notification.permission !== "granted") return;
  try{
    const note = new Notification(n.title || "تنبيه جديد", { body:n.message || "", icon:"/site-icon", tag:"arab-admin-" + n.id });
    note.onclick = ()=>{ window.focus(); };
  }catch(e){}
}

async function loadAdminAlerts(){
  try{
    const [a, n] = await Promise.all([
      adminFetch("/admin/alerts-count"),
      adminFetch("/admin/notifications")
    ]);
    const badge = document.getElementById("adminAlertsBadge");
    if(a.total > 0){
      badge.style.display = "flex";
      badge.textContent = a.total > 99 ? "99+" : a.total;
    } else {
      badge.style.display = "none";
    }
    const list = document.getElementById("adminAlertsList");
    const items = (n.items || []).map(x => `<div class="admin-alert-item"><i class="fa-solid fa-bell"></i><span><b>${x.title}</b><br><small>${x.message || ""}</small></span></div>`);
    if(a.pending_deposits > 0) items.push(`<div class="admin-alert-item" onclick="goSection('deposits', document.querySelector('[data-section=deposits]')); toggleAdminAlerts(false);"><i class="fa-solid fa-credit-card"></i> ${a.pending_deposits} طلب إيداع بانتظار المراجعة</div>`);
    if(a.pending_shop_orders > 0) items.push(`<div class="admin-alert-item" onclick="goSection('orders', document.querySelector('[data-section=orders]')); toggleAdminAlerts(false);"><i class="fa-solid fa-bolt"></i> ${a.pending_shop_orders} طلب يدوي بانتظار المراجعة</div>`);
    list.innerHTML = items.join("") || `<div class="admin-alert-item empty">لا توجد تنبيهات جديدة 👍</div>`;
    const ids = (n.items || []).map(x => Number(x.id) || 0);
    const maxId = ids.length ? Math.max(...ids) : 0;
    const lastSeen = Number(localStorage.getItem(ADMIN_NOTIF_SEEN_KEY) || 0);
    if(!adminNotifBootstrapped && !lastSeen){
      localStorage.setItem(ADMIN_NOTIF_SEEN_KEY, String(maxId));
      adminNotifBootstrapped = true;
    } else {
      adminNotifBootstrapped = true;
      (n.items || []).filter(x => Number(x.id) > lastSeen).slice(0, 3).forEach(showAdminSystemNotification);
      if(maxId > lastSeen) localStorage.setItem(ADMIN_NOTIF_SEEN_KEY, String(maxId));
    }
  }catch(err){ /* تجاهل */ }
}

function toggleAdminAlerts(force){
  const panel = document.getElementById("adminAlertsPanel");
  const show = force !== undefined ? force : panel.style.display === "none";
  panel.style.display = show ? "block" : "none";
  if(show){
    adminFetch("/admin/notifications/mark-read", { method:"POST" }).catch(()=>{});
    document.getElementById("adminAlertsBadge").style.display = "none";
  }
}
document.addEventListener("click", (e)=>{
  const panel = document.getElementById("adminAlertsPanel");
  if(!panel || panel.style.display === "none") return;
  if(!e.target.closest("#adminAlertsPanel") && !e.target.closest(".icon-btn")) toggleAdminAlerts(false);
});

/* ===== 1) لوحة المعلومات ===== */
async function loadDashboard(){
  const stats = await adminFetch("/admin/stats");
  document.getElementById("kpiUsers").textContent = stats.total_users.toLocaleString();
  document.getElementById("kpiOrders").textContent = stats.total_orders.toLocaleString();
  document.getElementById("kpiBalance").textContent = Math.round(stats.total_balance_syp).toLocaleString() + " ل.س";
  document.getElementById("kpiRate").textContent = "1$ = " + stats.exchange_rate.toLocaleString() + " ل.س";
  document.getElementById("kpiTodaySales").textContent = "$" + stats.today_sales_usd.toFixed(2);
  document.getElementById("kpiTodayOrders").textContent = stats.today_orders.toLocaleString();
  document.getElementById("kpiTodayProfit").textContent = "$" + stats.today_profit_usd.toFixed(2);
  document.getElementById("kpiTodayMargin").textContent = stats.today_margin_percent + "%";

  const orders = await adminFetch("/admin/orders");
  document.getElementById("dashOrdersBody").innerHTML = orders.slice(0,5).map(o=>`
    <tr><td>#${o.id}</td><td>${o.user_id}</td><td>${o.product_name}</td><td>${Math.round(o.price_syp).toLocaleString()} ل.س</td>
    <td><span class="status-badge ${o.status}">${STATUS_LABEL[o.status]||o.status}</span></td><td>${o.date}</td></tr>`).join("")
    || `<tr><td colspan="6" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات بعد</td></tr>`;

  const deposits = await adminFetch("/admin/deposits");
  const pending = deposits.filter(d=>d.status==="pending");
  document.getElementById("dashDepositsBody").innerHTML = pending.slice(0,5).map(d=>`
    <tr><td>#${d.id}</td><td>${d.full_name||d.user_id}</td><td>${d.method_title}</td><td>$${d.amount_usd}</td>
    <td style="font-family:'Orbitron',monospace; font-size:10px;">${d.code}</td>
    <td><button class="btn-sm primary" onclick="acceptDeposit(${d.id})">قبول</button></td></tr>`).join("")
    || `<tr><td colspan="6" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات إيداع معلّقة</td></tr>`;
}

/* ===== 1.5) الأرباح ===== */
const PROFIT_SOURCE_LABEL = { shop:"يدوي", api:"مزوّد API" };
async function loadProfits(){
  const start = document.getElementById("profitsStart").value;
  const end = document.getElementById("profitsEnd").value;
  let path = "/admin/profits";
  const qs = [];
  if(start) qs.push("start="+start);
  if(end) qs.push("end="+end);
  if(qs.length) path += "?" + qs.join("&");

  const data = await adminFetch(path);
  const s = data.summary;
  document.getElementById("profitOrdersCount").textContent = s.total_orders.toLocaleString();
  document.getElementById("profitSales").textContent = "$" + s.total_sales_usd.toFixed(2);
  document.getElementById("profitCost").textContent = "$" + s.total_cost_usd.toFixed(2);
  document.getElementById("profitNet").textContent = "$" + s.total_profit_usd.toFixed(2);

  document.getElementById("profitsTableBody").innerHTML = data.orders.map(o=>`
    <tr>
      <td>#${o.id}</td>
      <td>${PROFIT_SOURCE_LABEL[o.source]||o.source}</td>
      <td>${o.product_name}</td>
      <td>${o.category_name}</td>
      <td>$${o.price_usd.toFixed(2)}</td>
      <td>$${o.cost_usd.toFixed(2)}</td>
      <td style="color:${o.profit_usd>=0?'var(--success)':'var(--danger)'}; font-weight:700;">$${o.profit_usd.toFixed(2)}</td>
      <td>${o.created_at}</td>
    </tr>`).join("")
    || `<tr><td colspan="8" class="text-muted" style="text-align:center; padding:16px;">لا توجد مبيعات مكتملة بهذه الفترة</td></tr>`;
}
function resetProfitsFilter(){
  document.getElementById("profitsStart").value = "";
  document.getElementById("profitsEnd").value = "";
  loadProfits();
}

/* ===== 2) الطلبات ===== */
let allOrdersCache = [];
async function loadOrders(filter){
  allOrdersCache = await adminFetch("/admin/orders");
  renderOrdersTable(filter);
}
function renderOrdersTable(filter){
  const items = allOrdersCache.filter(o => filter==="all" || o.status===filter);
  document.getElementById("ordersTableBody").innerHTML = items.map(o=>`
    <tr><td>#${o.ref||o.id}<br><small style="color:var(--muted)">${o.source||''}</small></td><td>${o.user_id}</td><td>${o.product_name}</td><td>${o.player_id||'-'}</td>
    <td>${Math.round(o.price_syp).toLocaleString()} ل.س</td>
    <td><span class="status-badge ${o.status}">${STATUS_LABEL[o.status]||o.status}</span></td>
    <td>
      ${(o.status==='accepted'||o.status==='rejected') ? '—' : `
        <button class="btn-sm primary" onclick="setOrderStatus('${o.ref||('S'+o.id)}','accept')">✅ قبول</button>
        <button class="btn-sm danger" onclick="setOrderStatus('${o.ref||('S'+o.id)}','reject')">❌ رفض</button>`}
    </td></tr>`).join("")
    || `<tr><td colspan="7" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات</td></tr>`;
}
async function setOrderStatus(ref, action){
  if(!confirm(action==='accept' ? "تأكيد قبول الطلب؟" : "تأكيد رفض الطلب واسترجاع رصيد العميل؟")) return;
  try{
    await adminFetch(`/admin/orders/${ref}/status`, { method:"POST", body: JSON.stringify({ action }) });
    toast(action==='accept' ? "تم قبول الطلب ✅" : "تم رفض الطلب واسترجاع الرصيد");
    loadOrders("all");
  }catch(err){ toast(err.message, "error"); }
}
function filterAdminOrders(status, btn){
  document.querySelectorAll("#sec-orders .tab-btn").forEach(b=>b.classList.remove("active"));
  btn.classList.add("active");
  renderOrdersTable(status);
}

/* ===== 3) طلبات الإيداع ===== */
async function loadDeposits(){
  const deposits = await adminFetch("/admin/deposits");
  document.getElementById("depositsTableBody").innerHTML = deposits.map(d=>`
    <tr><td>#${d.id}</td><td>${d.full_name||d.user_id}</td><td>${d.method_title}</td><td>$${d.amount_usd}</td>
    <td>${Math.round(d.amount_syp).toLocaleString()} ل.س</td>
    <td style="font-family:'Orbitron',monospace; font-size:10px;">${d.code}</td>
    <td>${d.status==="pending"
      ? `<button class="btn-sm primary" onclick="acceptDeposit(${d.id})">قبول</button> <button class="btn-sm danger" onclick="rejectDeposit(${d.id})">رفض</button>`
      : `<span class="status-badge ${d.status==='accepted'?'completed':'failed'}">${d.status==='accepted'?'مقبول':'مرفوض'}</span>`}</td></tr>`).join("")
    || `<tr><td colspan="7" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات إيداع</td></tr>`;
}
async function acceptDeposit(id){
  try{ await adminFetch(`/admin/deposits/${id}/accept`, { method:"POST" }); toast("تم قبول الإيداع ✅"); loadDeposits(); }
  catch(err){ toast(err.message, "error"); }
}
async function rejectDeposit(id){
  try{ await adminFetch(`/admin/deposits/${id}/reject`, { method:"POST" }); toast("تم رفض الإيداع"); loadDeposits(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 4) المستخدمون ===== */
let ALL_DISCOUNT_TIERS = [];

let ALL_USERS_ROWS = [];
let topBalancesChartInstance = null;
let tierDistributionChartInstance = null;

async function loadUsers(){
  const [users, tiers, stats] = await Promise.all([
    adminFetch("/admin/users"), adminFetch("/admin/discount-tiers"), adminFetch("/admin/stats")
  ]);
  ALL_DISCOUNT_TIERS = tiers;
  ALL_USERS_ROWS = users;

  // ===== بطاقات الإحصائيات =====
  const rate = stats.exchange_rate || 1;
  const totalBalanceUsd = users.reduce((s,u)=> s + (u.balance_syp/rate), 0);
  const avgBalanceUsd = users.length ? totalBalanceUsd / users.length : 0;
  document.getElementById("usersKpiAvgBalance").textContent = "$" + avgBalanceUsd.toFixed(2);
  document.getElementById("usersKpiOrders").textContent = stats.total_orders.toLocaleString();
  document.getElementById("usersKpiTotalBalance").textContent = "$" + totalBalanceUsd.toFixed(2);
  document.getElementById("usersKpiTotal").textContent = users.length.toLocaleString();

  // ===== فلتر المستويات =====
  const tierSelect = document.getElementById("usersFilterTier");
  tierSelect.innerHTML = `<option value="">كل المستويات</option>` +
    tiers.map(t => `<option value="${t.id}">${t.name}</option>`).join("");

  // ===== رسم: أعلى 5 مستخدمين رصيداً =====
  const top5 = [...users].sort((a,b)=> b.balance_syp - a.balance_syp).slice(0,5);
  renderChart("topBalancesChart", "topBalances", top5.map(u=>u.name), top5.map(u=> Number((u.balance_syp/rate).toFixed(2))), "#e0a83a");

  // ===== رسم: توزيع المستويات =====
  const tierCounts = tiers.map(t => users.filter(u=>u.discount_tier_id===t.id).length);
  const noTierCount = users.filter(u=>!u.discount_tier_id).length;
  renderChart("tierDistributionChart", "tierDist",
    [...tiers.map(t=>t.name), "بدون رتبة"], [...tierCounts, noTierCount], "#e63946");

  renderUsersTable();
}

function renderChart(canvasId, kind, labels, data, color){
  if(typeof Chart === "undefined") return; // لو تعذّر تحميل مكتبة الرسوم من CDN (بدون إنترنت مثلاً)
  const ctx = document.getElementById(canvasId);
  if(!ctx) return;
  const existing = kind === "topBalances" ? topBalancesChartInstance : tierDistributionChartInstance;
  if(existing) existing.destroy();
  const instance = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data, backgroundColor: color, borderRadius: 6 }] },
    options: {
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9aa3b2", font: { size: 10 } }, grid: { display:false } },
        y: { ticks: { color: "#9aa3b2", font: { size: 10 } }, grid: { color: "rgba(255,255,255,.05)" } },
      },
    },
  });
  if(kind === "topBalances") topBalancesChartInstance = instance;
  else tierDistributionChartInstance = instance;
}

function renderUsersTable(){
  const apiFilter = document.getElementById("usersFilterApi").value;
  const tierFilter = document.getElementById("usersFilterTier").value;
  const search = document.getElementById("usersSearchInput").value.trim().toLowerCase();

  const tierOptions = (selectedId) => `
    <option value="0" ${!selectedId ? 'selected' : ''}>بدون رتبة</option>
    ${ALL_DISCOUNT_TIERS.map(t => `<option value="${t.id}" ${t.id === selectedId ? 'selected' : ''}>${t.name} (${t.percent}%)</option>`).join("")}`;

  const filtered = ALL_USERS_ROWS.filter(u => {
    if(apiFilter === "enabled" && !u.api_enabled) return false;
    if(apiFilter === "disabled" && u.api_enabled) return false;
    if(tierFilter && String(u.discount_tier_id) !== tierFilter) return false;
    if(search && !(u.name.toLowerCase().includes(search) || u.email.toLowerCase().includes(search))) return false;
    return true;
  });

  document.getElementById("usersTableBody").innerHTML = filtered.map(u=>`
    <tr>
    <td style="cursor:pointer;" onclick="openUserDetails(${u.web_id})"><i class="fa-solid fa-circle-info" style="color:var(--accent); margin-left:4px;"></i>${u.name}</td>
    <td>${u.email}</td><td>${Math.round(u.balance_syp).toLocaleString()} ل.س</td>
    <td><select onchange="setUserDiscountTier(${u.web_id}, this.value)" style="padding:6px 8px; border-radius:8px; border:1px solid var(--border); background:var(--card-soft); color:var(--text); font-size:11px;">${tierOptions(u.discount_tier_id)}</select></td>
    <td>${u.blocked ? '<span class="status-badge failed">محظور</span>' : '<span class="status-badge completed">نشط</span>'}</td>
    <td>${u.api_enabled
        ? `<span class="status-badge completed" title="${u.api_key}" style="cursor:pointer;" onclick="navigator.clipboard?.writeText('${u.api_key}'); toast('تم نسخ المفتاح')">مفعّل <i class="fa-solid fa-copy"></i></span>`
        : '<span class="status-badge pending">غير مفعّل</span>'}</td>
    <td style="display:flex; gap:6px; flex-wrap:wrap;">
      <button class="btn-sm" style="background:var(--gold); color:#000;" onclick="openBalanceAdjust(${u.web_id}, '${u.name.replace(/'/g,"")}')"><i class="fa-solid fa-coins"></i> الرصيد</button>
      <button class="btn-sm ${u.blocked?'primary':'danger'}" onclick="${u.blocked?'unblockUser':'blockUser'}(${u.web_id})">${u.blocked?'رفع الحظر':'حظر'}</button>
      ${u.api_enabled
        ? `<button class="btn-sm danger" onclick="disableUserApi(${u.web_id})">تعطيل API</button>
           <button class="btn-sm primary" onclick="regenerateUserApi(${u.web_id})">تجديد المفتاح</button>`
        : `<button class="btn-sm primary" onclick="enableUserApi(${u.web_id})">فتح API</button>`}
    </td></tr>`).join("")
    || `<tr><td colspan="7" class="text-muted" style="text-align:center; padding:16px;">لا يوجد مستخدمون مطابقون</td></tr>`;
}

function exportUsersCsv(){
  const rows = [["الاسم","البريد","الرصيد (ل.س)","الرتبة","الحالة","API"]];
  ALL_USERS_ROWS.forEach(u => rows.push([
    u.name, u.email, Math.round(u.balance_syp), u.discount_tier_name || "بدون رتبة",
    u.blocked ? "محظور" : "نشط", u.api_enabled ? "مفعّل" : "غير مفعّل"
  ]));
  downloadCsv(rows, "users-export.csv");
}

function downloadCsv(rows, filename){
  const csv = rows.map(r => r.map(cell => `"${String(cell).replace(/"/g,'""')}"`).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ===== مودال تفاصيل المستخدم المتقدمة ===== */
let CURRENT_USER_DETAILS = null;
async function openUserDetails(webId){
  try{
    const d = await adminFetch(`/admin/users/${webId}/details`);
    CURRENT_USER_DETAILS = d;
    document.getElementById("userDetailsName").innerHTML = `<i class="fa-solid fa-user"></i> ${d.name} — ${d.email}`;
    document.getElementById("udRProfit").textContent = "$" + d.total_profit_usd.toFixed(4);
    document.getElementById("udOrders").textContent = d.total_orders.toLocaleString();
    document.getElementById("udSpent").textContent = "$" + d.total_spent_usd.toFixed(2);
    document.getElementById("udBalance").textContent = "$" + d.balance_usd.toFixed(2);
    document.getElementById("userDetailsOrdersBody").innerHTML = d.recent_orders.map(o=>`
      <tr><td>#${o.id}</td><td>${o.product_name||'-'}</td><td>${o.qty}</td><td>$${Number(o.price_usd).toFixed(4)}</td>
      <td><span class="status-badge ${o.status}">${STATUS_LABEL[o.status]||o.status}</span></td><td>${o.date}</td></tr>`).join("")
      || `<tr><td colspan="6" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات</td></tr>`;
    document.getElementById("userDetailsModal").style.display = "flex";
  }catch(err){ toast(err.message, "error"); }
}
function closeUserDetailsModal(){ document.getElementById("userDetailsModal").style.display = "none"; }
function exportUserOrdersCsv(){
  if(!CURRENT_USER_DETAILS) return;
  const rows = [["ID","المنتج","الكمية","السعر (USD)","الحالة","التاريخ"]];
  CURRENT_USER_DETAILS.recent_orders.forEach(o => rows.push([o.id, o.product_name||"-", o.qty, o.price_usd, o.status, o.date]));
  downloadCsv(rows, `user-${CURRENT_USER_DETAILS.email}-orders.csv`);
}

let balanceModalWebId = null;
function openBalanceAdjust(webId, userName){
  balanceModalWebId = webId;
  document.getElementById("balanceModalUser").textContent = userName;
  document.getElementById("balanceModalAmount").value = "";
  document.getElementById("balanceModal").style.display = "flex";
}
function closeBalanceModal(){
  document.getElementById("balanceModal").style.display = "none";
  balanceModalWebId = null;
}
async function submitBalanceAdjust(action){
  const amount = Number(document.getElementById("balanceModalAmount").value || 0);
  if(!amount || amount <= 0){ toast("أدخل مبلغ صحيح أكبر من صفر", "error"); return; }
  try{
    await adminFetch(`/admin/users/${balanceModalWebId}/balance`, { method:"POST", body: JSON.stringify({ action, amount }) });
    toast(action === "add" ? "✅ تمت إضافة الرصيد" : "✅ تم خصم الرصيد");
    closeBalanceModal();
    loadUsers();
  }catch(err){ toast(err.message, "error"); }
}
async function setUserDiscountTier(webId, tierId){
  try{
    await adminFetch(`/admin/users/${webId}/discount-tier`, { method:"POST", body: JSON.stringify({ tier_id: Number(tierId) }) });
    toast(Number(tierId) === 0 ? "تمت إزالة رتبة المستخدم" : "تم تعيين الرتبة ✅");
  }catch(err){ toast(err.message, "error"); loadUsers(); }
}

/* ===== الرتب والخصومات ===== */
async function loadDiscountTiers(){
  const tiers = await adminFetch("/admin/discount-tiers");
  ALL_DISCOUNT_TIERS = tiers;
  document.getElementById("tiersTableBody").innerHTML = tiers.map(t => `
    <tr>
      <td><input type="text" value="${t.name}" onchange="updateDiscountTier(${t.id}, {name:this.value})" style="padding:6px 8px; border-radius:8px; border:1px solid var(--border); background:var(--card-soft); color:var(--text); font-size:11px; width:100px;"></td>
      <td><input type="number" value="${t.percent}" min="0" max="100" step="0.5" onchange="updateDiscountTier(${t.id}, {percent:Number(this.value)})" style="padding:6px 8px; border-radius:8px; border:1px solid var(--border); background:var(--card-soft); color:var(--text); font-size:11px; width:70px;"> %</td>
      <td><input type="number" value="${t.sort_order}" onchange="updateDiscountTier(${t.id}, {sort_order:Number(this.value)})" style="padding:6px 8px; border-radius:8px; border:1px solid var(--border); background:var(--card-soft); color:var(--text); font-size:11px; width:60px;"></td>
      <td><button class="btn-sm danger" onclick="deleteDiscountTier(${t.id})">حذف</button></td>
    </tr>`).join("")
    || `<tr><td colspan="4" class="text-muted" style="text-align:center; padding:16px;">لا توجد رتب بعد، أضف أول رتبة فوق</td></tr>`;
}
async function addDiscountTier(){
  const name = document.getElementById("newTierName").value.trim();
  const percent = Number(document.getElementById("newTierPercent").value || 0);
  const sort_order = Number(document.getElementById("newTierSort").value || 0);
  if(!name){ toast("أدخل اسم الرتبة", "error"); return; }
  if(percent < 0 || percent > 100){ toast("نسبة الخصم يجب أن تكون بين 0 و100", "error"); return; }
  try{
    await adminFetch("/admin/discount-tiers", { method:"POST", body: JSON.stringify({ name, percent, sort_order }) });
    toast("تمت إضافة الرتبة ✅");
    document.getElementById("newTierName").value = "";
    document.getElementById("newTierPercent").value = "";
    document.getElementById("newTierSort").value = "0";
    loadDiscountTiers();
  }catch(err){ toast(err.message, "error"); }
}
async function updateDiscountTier(tierId, changes){
  try{
    await adminFetch(`/admin/discount-tiers/${tierId}`, { method:"PUT", body: JSON.stringify(changes) });
    toast("تم الحفظ ✅");
  }catch(err){ toast(err.message, "error"); loadDiscountTiers(); }
}
async function deleteDiscountTier(tierId){
  if(!confirm("حذف هذه الرتبة؟ كل المستخدمين المعيّنين لها سيرجعون لحالة بدون رتبة (0% خصم).")) return;
  try{ await adminFetch(`/admin/discount-tiers/${tierId}`, { method:"DELETE" }); toast("تم الحذف"); loadDiscountTiers(); }
  catch(err){ toast(err.message, "error"); }
}
async function blockUser(webId){
  try{ await adminFetch(`/admin/users/${webId}/block`, { method:"POST" }); toast("تم حظر المستخدم"); loadUsers(); }
  catch(err){ toast(err.message, "error"); }
}
async function unblockUser(webId){
  try{ await adminFetch(`/admin/users/${webId}/unblock`, { method:"POST" }); toast("تم رفع الحظر"); loadUsers(); }
  catch(err){ toast(err.message, "error"); }
}
async function enableUserApi(webId){
  if(!confirm("هل تريد تفعيل API لهذا المستخدم؟ سيتمكن من إنشاء طلبات خارجية عبر مفتاحه.")) return;
  try{ await adminFetch(`/admin/users/${webId}/api/enable`, { method:"POST" }); toast("تم تفعيل API ✅"); loadUsers(); }
  catch(err){ toast(err.message, "error"); }
}
async function disableUserApi(webId){
  if(!confirm("هل تريد تعطيل API لهذا المستخدم؟ مفتاحه سيتوقف عن العمل فوراً.")) return;
  try{ await adminFetch(`/admin/users/${webId}/api/disable`, { method:"POST" }); toast("تم تعطيل API"); loadUsers(); }
  catch(err){ toast(err.message, "error"); }
}
async function regenerateUserApi(webId){
  if(!confirm("توليد مفتاح جديد سيلغي المفتاح القديم فوراً. متابعة؟")) return;
  try{ await adminFetch(`/admin/users/${webId}/api/regenerate`, { method:"POST" }); toast("تم توليد مفتاح جديد ✅"); loadUsers(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 5) المنتجات والفئات ===== */
let currentProductId = null;
let sectionsCache = [];
let productsCache = [];
async function loadProducts(){
  sectionsCache = await adminFetch("/admin/sections");
  const sel = document.getElementById("newProductSection");
  sel.innerHTML = sectionsCache.map(s=>`<option value="${s.name}" data-id="${s.id}">${s.name}</option>`).join("") || `<option value="">لا يوجد أقسام بعد</option>`;
  await onProductSectionChange();

  productsCache = await adminFetch("/admin/products");
  renderProductsTable(productsCache);
}
function renderProductsTable(products){
  document.getElementById("productsTableBody").innerHTML = products.map(p=>`
    <tr>
      <td>${p.image ? `<img src="${p.image}" style="width:30px; height:30px; border-radius:8px; object-fit:cover; vertical-align:middle; margin-left:6px;">` : ''}${p.name}</td>
      <td>${p.category}</td>
      <td>${p.subsection_name || '<span class="text-muted">—</span>'}</td>
      <td>${p.categories_count}</td>
      <td>
        <button class="btn-sm" onclick="pickImage('product', ${p.id})"><i class="fa-solid fa-camera"></i></button>
        <button class="btn-sm" onclick="openAiImage('product', ${p.id}, '${p.name.replace(/'/g,"")}')" title="إنشاء صورة بالذكاء الاصطناعي"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
        <button class="btn-sm" onclick="openEdit('product', ${p.id}, '${p.name.replace(/'/g,"")}', {name:'${p.name.replace(/'/g,"")}', emoji:'${p.emoji||''}'})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-sm" onclick="openCategories(${p.id}, '${p.name.replace(/'/g,"")}')">الفئات</button>
        <button class="btn-sm danger" onclick="deleteProduct(${p.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="5" class="text-muted" style="text-align:center; padding:16px;">${productsCache.length ? 'لا توجد نتائج مطابقة' : 'لا توجد منتجات بعد'}</td></tr>`;
}
function searchProducts(q){
  q = (q || "").trim().toLowerCase();
  if(!q){ renderProductsTable(productsCache); return; }
  renderProductsTable(productsCache.filter(p =>
    p.name.toLowerCase().includes(q) ||
    (p.category || "").toLowerCase().includes(q) ||
    (p.subsection_name || "").toLowerCase().includes(q)
  ));
}
async function onProductSectionChange(){
  const sel = document.getElementById("newProductSection");
  const opt = sel.options[sel.selectedIndex];
  const sectionId = opt ? opt.dataset.id : null;
  const wrap = document.getElementById("newProductSubsectionWrap");
  const subSel = document.getElementById("newProductSubsection");
  if(!sectionId){ wrap.style.display = "none"; return; }
  try{
    const subs = await adminFetch(`/admin/sections/${sectionId}/subsections`);
    if(subs.length){
      subSel.innerHTML = `<option value="">— بدون قسم فرعي —</option>` + subs.map(s=>`<option value="${s.id}">${s.name}</option>`).join("");
      wrap.style.display = "block";
    }else{
      wrap.style.display = "none";
    }
  }catch(err){ wrap.style.display = "none"; }
}
async function addProduct(){
  const name = document.getElementById("newProductName").value.trim();
  const category = document.getElementById("newProductSection").value;
  const emoji = document.getElementById("newProductEmoji").value.trim();
  const subsection_id = document.getElementById("newProductSubsection").value || null;
  if(!name || !category){ toast("أدخل اسم المنتج واختر القسم", "error"); return; }
  try{
    await adminFetch("/admin/products", { method:"POST", body: JSON.stringify({ name, category, emoji, subsection_id }) });
    toast("تمت إضافة المنتج ✅");
    document.getElementById("newProductName").value = "";
    document.getElementById("newProductEmoji").value = "";
    loadProducts();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteProduct(id){
  try{ await adminFetch(`/admin/products/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadProducts(); }
  catch(err){ toast(err.message, "error"); }
}
async function openCategories(productId, productName){
  currentProductId = productId;
  document.getElementById("categoriesPanel").style.display = "block";
  document.getElementById("categoriesPanelTitle").textContent = "فئات: " + productName;
  document.getElementById("categoriesPanel").scrollIntoView({ behavior:"smooth", block:"center" });
  await loadCategories();
}
async function loadCategories(){
  const cats = await adminFetch(`/admin/products/${currentProductId}/categories`);
  document.getElementById("categoriesTableBody").innerHTML = cats.map(c=>`
    <tr>
      <td>${c.image ? `<img src="${c.image}" style="width:26px; height:26px; border-radius:7px; object-fit:cover; vertical-align:middle; margin-left:6px;">` : ''}${c.name}</td>
      <td>$${c.price_usd}</td>
      <td>${c.stock_qty === null || c.stock_qty === undefined ? '<span style="color:var(--muted);">غير محدود</span>' : (c.stock_qty > 0 ? c.stock_qty : '<span style="color:var(--danger);">نفدت</span>')}</td>
      <td>
        <button class="btn-sm" onclick="pickImage('category', ${c.id})"><i class="fa-solid fa-camera"></i></button>
        <button class="btn-sm" onclick="openAiImage('category', ${c.id}, '${c.name.replace(/'/g,"")}')" title="إنشاء صورة بالذكاء الاصطناعي"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
        <button class="btn-sm" onclick="openLinkModal(${c.id}, '${c.name.replace(/'/g,"")}')" title="ربط بمزوّد API"><i class="fa-solid fa-link"></i></button>
        <button class="btn-sm" onclick="openEdit('category', ${c.id}, '${c.name.replace(/'/g,"")}', {name:'${c.name.replace(/'/g,"")}', price:${c.price_usd}, unit_qty:${c.unit_qty||1}, min_qty:${c.min_qty}, max_qty:${c.max_qty}, stock_qty:${c.stock_qty === null || c.stock_qty === undefined ? 'null' : c.stock_qty}, requires_id:${c.requires_id === false ? 0 : 1}})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-sm danger" onclick="deleteCategory(${c.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="4" class="text-muted" style="text-align:center; padding:12px;">لا توجد فئات بعد</td></tr>`;
}
async function addCategory(){
  const name = document.getElementById("newCategoryName").value.trim();
  const price = Number(document.getElementById("newCategoryPrice").value || 0);
  const type = document.getElementById("newCategoryType").value;
  const unit_qty = Math.max(1, Number(document.getElementById("newCategoryUnitQty").value || 1));
  const min_qty = Math.max(1, Number(document.getElementById("newCategoryMinQty").value || 1));
  const max_qty = Math.max(min_qty, Number(document.getElementById("newCategoryMaxQty").value || min_qty));
  const stockRaw = document.getElementById("newCategoryStock")?.value ?? "";
  const stock_qty = stockRaw.trim() === "" ? null : Number(stockRaw);
  const requires_id = document.getElementById("newCategoryRequiresId") ? document.getElementById("newCategoryRequiresId").checked : true;
  if(!name || price <= 0){ toast("أدخل اسم الفئة وسعر صحيح", "error"); return; }
  try{
    await adminFetch(`/admin/products/${currentProductId}/categories`, { method:"POST", body: JSON.stringify({ name, price, type, unit_qty, min_qty, max_qty, stock_qty, requires_id }) });
    toast("تمت إضافة الفئة ✅");
    document.getElementById("newCategoryName").value = "";
    document.getElementById("newCategoryPrice").value = "";
    if(document.getElementById("newCategoryStock")) document.getElementById("newCategoryStock").value = "";
    loadCategories(); loadProducts();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteCategory(id){
  try{ await adminFetch(`/admin/categories/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadCategories(); loadProducts(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 6) الأقسام ===== */
let sectionsListCache = [];
async function loadSections(){
  sectionsListCache = await adminFetch("/admin/sections");
  renderSectionsTable();
}
function renderSectionsTable(){
  const sections = sectionsListCache;
  document.getElementById("sectionsTableBody").innerHTML = sections.map((s, idx)=>`
    <tr>
      <td>
        <button class="btn-sm" ${idx===0?'disabled':''} onclick="moveSection(${s.id}, -1)"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="btn-sm" ${idx===sections.length-1?'disabled':''} onclick="moveSection(${s.id}, 1)"><i class="fa-solid fa-arrow-down"></i></button>
      </td>
      <td>${s.image ? `<img src="${s.image}" style="width:26px; height:26px; border-radius:7px; object-fit:cover; vertical-align:middle; margin-left:6px;">` : (s.emoji||'')} ${s.name}</td>
      <td>${s.products_count}</td>
      <td>${s.active ? '<span class="status-badge completed">مفعّل</span>' : '<span class="status-badge pending">معطّل</span>'}</td>
      <td>
        <button class="btn-sm" onclick="pickImage('section', ${s.id})"><i class="fa-solid fa-camera"></i></button>
        <button class="btn-sm" onclick="openAiImage('section', ${s.id}, '${s.name.replace(/'/g,"")}')" title="إنشاء صورة بالذكاء الاصطناعي"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
        <button class="btn-sm" onclick="openEdit('section', ${s.id}, '${s.name.replace(/'/g,"")}', {name:'${s.name.replace(/'/g,"")}', emoji:'${s.emoji||''}', active:${s.active}})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-sm" onclick="openSubsections(${s.id}, '${s.name.replace(/'/g,"")}')"><i class="fa-solid fa-layer-group"></i> الأقسام الفرعية (${s.subsections_count||0})</button>
        <button class="btn-sm danger" onclick="deleteSection(${s.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="5" class="text-muted" style="text-align:center; padding:16px;">لا توجد أقسام بعد</td></tr>`;
}
async function moveSection(id, dir){
  const idx = sectionsListCache.findIndex(s=>s.id===id);
  const swapIdx = idx + dir;
  if(idx<0 || swapIdx<0 || swapIdx>=sectionsListCache.length) return;
  [sectionsListCache[idx], sectionsListCache[swapIdx]] = [sectionsListCache[swapIdx], sectionsListCache[idx]];
  renderSectionsTable();
  try{
    await adminFetch("/admin/sections/reorder", { method:"POST", body: JSON.stringify({ ids: sectionsListCache.map(s=>s.id) }) });
  }catch(err){ toast(err.message, "error"); loadSections(); }
}
async function addSection(){
  const name = document.getElementById("newSectionName").value.trim();
  const emoji = document.getElementById("newSectionEmoji").value.trim();
  if(!name){ toast("أدخل اسم القسم", "error"); return; }
  try{
    await adminFetch("/admin/sections", { method:"POST", body: JSON.stringify({ name, emoji }) });
    toast("تمت إضافة القسم ✅");
    document.getElementById("newSectionName").value = "";
    document.getElementById("newSectionEmoji").value = "";
    loadSections();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteSection(id){
  try{ await adminFetch(`/admin/sections/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadSections(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== الأقسام الفرعية ===== */
let currentSectionId = null;
let subsectionsListCache = [];
async function openSubsections(sectionId, sectionName){
  currentSectionId = sectionId;
  document.getElementById("subsectionsPanel").style.display = "block";
  document.getElementById("subsectionsPanelTitle").textContent = "الأقسام الفرعية لـ: " + sectionName;
  document.getElementById("subsectionsPanel").scrollIntoView({ behavior:"smooth", block:"center" });
  await loadSubsections();
}
async function loadSubsections(){
  subsectionsListCache = await adminFetch(`/admin/sections/${currentSectionId}/subsections`);
  renderSubsectionsTable();
}
function renderSubsectionsTable(){
  const subs = subsectionsListCache;
  document.getElementById("subsectionsTableBody").innerHTML = subs.map((s, idx)=>`
    <tr>
      <td>
        <button class="btn-sm" ${idx===0?'disabled':''} onclick="moveSubsection(${s.id}, -1)"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="btn-sm" ${idx===subs.length-1?'disabled':''} onclick="moveSubsection(${s.id}, 1)"><i class="fa-solid fa-arrow-down"></i></button>
      </td>
      <td>${s.image ? `<img src="${s.image}" style="width:26px; height:26px; border-radius:7px; object-fit:cover; vertical-align:middle; margin-left:6px;">` : (s.emoji||'')} ${s.name}</td>
      <td>${s.products_count}</td>
      <td>${s.active ? '<span class="status-badge completed">مفعّل</span>' : '<span class="status-badge pending">معطّل</span>'}</td>
      <td>
        <button class="btn-sm" onclick="pickImage('subsection', ${s.id})"><i class="fa-solid fa-camera"></i></button>
        <button class="btn-sm" onclick="openAiImage('subsection', ${s.id}, '${s.name.replace(/'/g,"")}')" title="إنشاء صورة بالذكاء الاصطناعي"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
        <button class="btn-sm" onclick="openEdit('subsection', ${s.id}, '${s.name.replace(/'/g,"")}', {name:'${s.name.replace(/'/g,"")}', emoji:'${s.emoji||''}', active:${s.active}})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-sm danger" onclick="deleteSubsection(${s.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="5" class="text-muted" style="text-align:center; padding:16px;">لا توجد أقسام فرعية بعد</td></tr>`;
}
async function moveSubsection(id, dir){
  const idx = subsectionsListCache.findIndex(s=>s.id===id);
  const swapIdx = idx + dir;
  if(idx<0 || swapIdx<0 || swapIdx>=subsectionsListCache.length) return;
  [subsectionsListCache[idx], subsectionsListCache[swapIdx]] = [subsectionsListCache[swapIdx], subsectionsListCache[idx]];
  renderSubsectionsTable();
  try{
    await adminFetch(`/admin/sections/${currentSectionId}/subsections/reorder`, { method:"POST", body: JSON.stringify({ ids: subsectionsListCache.map(s=>s.id) }) });
  }catch(err){ toast(err.message, "error"); loadSubsections(); }
}
async function addSubsection(){
  const name = document.getElementById("newSubsectionName").value.trim();
  const emoji = document.getElementById("newSubsectionEmoji").value.trim();
  if(!name){ toast("أدخل اسم القسم الفرعي", "error"); return; }
  try{
    await adminFetch(`/admin/sections/${currentSectionId}/subsections`, { method:"POST", body: JSON.stringify({ name, emoji }) });
    toast("تمت الإضافة ✅");
    document.getElementById("newSubsectionName").value = "";
    document.getElementById("newSubsectionEmoji").value = "";
    loadSubsections();
    loadSections(); // لتحديث عداد الأقسام الفرعية بجدول الأقسام
  }catch(err){ toast(err.message, "error"); }
}
async function deleteSubsection(id){
  try{ await adminFetch(`/admin/subsections/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadSubsections(); loadSections(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 7) طرق الإيداع ===== */
async function loadDepositMethods(){
  const m = await adminFetch("/admin/deposit-methods");
  document.getElementById("autoMethodsBody").innerHTML = m.auto.map(a=>`
    <tr>
      <td><img src="${a.image || ''}" onerror="this.style.visibility='hidden'" style="width:34px; height:34px; border-radius:8px; object-fit:cover; background:var(--card-soft); display:${a.image?'block':'none'};"></td>
      <td>${a.title} ${a.gateway_type==='invoice' ? '<span class="badge-sm" style="background:var(--success);">فاتورة</span>' : '<span class="badge-sm">تحقق</span>'}</td><td style="font-family:'Orbitron',monospace; font-size:10px;">${a.api_url}</td>
      <td style="display:flex; gap:6px;">
        <button class="btn-sm" onclick="pickImage('auto_method', ${a.id})"><i class="fa-solid fa-image"></i> صورة</button>
        <button class="btn-sm danger" onclick="deleteAutoMethod(${a.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="4" class="text-muted" style="text-align:center; padding:12px;">لا توجد طرق تلقائية بعد</td></tr>`;
  document.getElementById("manualMethodsBody").innerHTML = m.manual.map(a=>`
    <tr>
      <td><img src="${a.image || ''}" onerror="this.style.visibility='hidden'" style="width:34px; height:34px; border-radius:8px; object-fit:cover; background:var(--card-soft); display:${a.image?'block':'none'};"></td>
      <td>${a.title}</td>
      <td style="display:flex; gap:6px;">
        <button class="btn-sm" onclick="pickImage('manual_method', ${a.id})"><i class="fa-solid fa-image"></i> صورة</button>
        <button class="btn-sm danger" onclick="deleteManualMethod(${a.id})">حذف</button>
      </td>
    </tr>`).join("")
    || `<tr><td colspan="3" class="text-muted" style="text-align:center; padding:12px;">لا توجد طرق يدوية بعد</td></tr>`;
}
async function addAutoMethod(){
  const title = document.getElementById("autoMethodTitle").value.trim();
  const description = document.getElementById("autoMethodDescription").value.trim();
  const api_token = document.getElementById("autoMethodToken").value.trim();
  const api_url = document.getElementById("autoMethodUrl").value.trim();
  const gateway_type = document.getElementById("autoMethodGatewayType")?.value || "verify";
  const input_currency = document.getElementById("autoMethodCurrency")?.value || "usd";
  if(!title || !api_token || !api_url){ toast("عبّي كل الحقول", "error"); return; }
  try{
    await adminFetch("/admin/deposit-methods/auto", { method:"POST", body: JSON.stringify({ title, description, api_token, api_url, gateway_type, input_currency }) });
    toast("تمت الإضافة ✅");
    ["autoMethodTitle","autoMethodDescription","autoMethodToken","autoMethodUrl"].forEach(id=> document.getElementById(id).value = "");
    loadDepositMethods();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteAutoMethod(id){
  try{ await adminFetch(`/admin/deposit-methods/auto/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadDepositMethods(); }
  catch(err){ toast(err.message, "error"); }
}
async function addManualMethod(){
  const title = document.getElementById("manualMethodTitle").value.trim();
  const code = document.getElementById("manualMethodCode").value.trim();
  const description = document.getElementById("manualMethodDescription")?.value.trim() || "";
  const input_currency = document.getElementById("manualMethodCurrency")?.value || "usd";
  if(!title){ toast("أدخل اسم الطريقة", "error"); return; }
  try{
    await adminFetch("/admin/deposit-methods/manual", { method:"POST", body: JSON.stringify({ title, code, description, input_currency }) });
    toast("تمت الإضافة ✅");
    document.getElementById("manualMethodTitle").value = "";
    document.getElementById("manualMethodCode").value = "";
    if(document.getElementById("manualMethodDescription")) document.getElementById("manualMethodDescription").value = "";
    loadDepositMethods();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteManualMethod(id){
  try{ await adminFetch(`/admin/deposit-methods/manual/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadDepositMethods(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 8) مزوّدو API ===== */
/* ===== التسعير الذكي ===== */
let ALL_PRICING_ROWS = [];

async function loadPricing(){
  ALL_PRICING_ROWS = await adminFetch("/admin/categories/all-pricing");
  document.getElementById("pricingSelectAll").checked = false;
  renderPricingTable();
}

function renderPricingTable(){
  const box = document.getElementById("pricingTableBody");
  box.innerHTML = ALL_PRICING_ROWS.map(c => `
    <tr>
      <td><input type="checkbox" class="pricing-row-check" data-id="${c.id}" onchange="updatePricingSelectedCount()"></td>
      <td>${c.product_name}</td>
      <td>${c.name}</td>
      <td>${c.linked ? c.provider_name : '<span class="text-muted">غير مربوطة</span>'}</td>
      <td>${c.cost_usd != null ? "$"+Number(c.cost_usd).toFixed(4) : "—"}</td>
      <td>${c.margin_percent != null ? c.margin_percent+"%" : '<span class="text-muted">يدوي</span>'}</td>
      <td>$${Number(c.price_usd).toFixed(4)}</td>
    </tr>`).join("")
    || `<tr><td colspan="7" class="text-muted" style="text-align:center; padding:16px;">لا توجد فئات بعد — أضف منتجات وفئات من قسم "المنتجات والفئات" أولاً</td></tr>`;
  updatePricingSelectedCount();
}

function toggleSelectAllPricing(checkbox){
  document.querySelectorAll(".pricing-row-check").forEach(c => c.checked = checkbox.checked);
  updatePricingSelectedCount();
}

function updatePricingSelectedCount(){
  const n = document.querySelectorAll(".pricing-row-check:checked").length;
  document.getElementById("pricingSelectedCount").textContent = `${n} فئة محددة`;
}

function getSelectedPricingIds(){
  return Array.from(document.querySelectorAll(".pricing-row-check:checked")).map(c => Number(c.dataset.id));
}

async function applyMarginToSelected(){
  const ids = getSelectedPricingIds();
  const margin = Number(document.getElementById("pricingMarginInput").value);
  if(!ids.length){ toast("حدد فئة واحدة على الأقل من الجدول", "error"); return; }
  if(isNaN(margin) || margin < 0){ toast("أدخل نسبة هامش صحيحة", "error"); return; }
  try{
    const res = await adminFetch("/admin/categories/apply-margin", {
      method: "POST",
      body: JSON.stringify({ category_ids: ids, margin_percent: margin })
    });
    toast(res.message);
    loadPricing();
  }catch(err){ toast(err.message, "error"); }
}

async function loadProviders(){
  const providers = await adminFetch("/admin/providers");
  document.getElementById("providersTableBody").innerHTML = providers.map(p=>`
    <tr><td>${p.name}</td><td style="font-family:'Orbitron',monospace; font-size:10px;">${p.api_url}</td><td>${p.linked_products}</td>
    <td><input type="number" id="importMargin_${p.id}" placeholder="10" min="0" step="0.5" style="width:70px; padding:7px; border-radius:8px; border:1px solid var(--border); background:var(--card-soft); color:var(--text); font-size:11px;"></td>
    <td style="display:flex; gap:6px; flex-wrap:wrap;">
      <button class="btn-sm primary" onclick="importProviderCatalog(${p.id}, '${p.name.replace(/'/g,"")}')"><i class="fa-solid fa-cloud-arrow-down"></i> استيراد الكل</button>
      <button class="btn-sm" onclick="exportProviderProducts(${p.id}, '${p.name.replace(/'/g,"")}')"><i class="fa-solid fa-file-arrow-down"></i> تحميل قائمة المنتجات</button>
      <button class="btn-sm danger" onclick="deleteProvider(${p.id})">حذف</button>
    </td></tr>`).join("")
    || `<tr><td colspan="5" class="text-muted" style="text-align:center; padding:16px;">لا يوجد مزوّدون بعد</td></tr>`;
}

async function exportProviderProducts(providerId, providerName){
  toast("جاري تجهيز ملف المنتجات ⏳");
  try{
    const token = localStorage.getItem("admin_token");
    const res = await fetch(`${API_BASE}/admin/providers/${providerId}/products/export`, {
      headers: token ? { "Authorization": "Bearer " + token } : {}
    });
    if(!res.ok){
      const data = await res.json().catch(()=>null);
      throw new Error((data && data.message) || "تعذّر تحميل الملف");
    }
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `products_${providerName || providerId}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    toast("تم تحميل قائمة المنتجات ✅");
  }catch(err){ toast(err.message, "error"); }
}

/* ===== إنشاء صور بالذكاء الاصطناعي ===== */
let aiImageTarget = null;
let aiImageUrl = null;
function openAiImage(kind, id, name){
  aiImageTarget = { kind, id, name };
  aiImageUrl = null;
  document.getElementById("aiImageTitle").textContent = "إنشاء صورة لـ: " + name;
  document.getElementById("aiImagePreview").style.display = "none";
  document.getElementById("aiImageConfirm").disabled = true;
  document.getElementById("aiImageStatus").textContent = "اضغط «إنشاء صورة» ليبدأ التوليد التلقائي حسب الاسم.";
  document.getElementById("aiImageModal").style.display = "flex";
}
function closeAiImage(){ document.getElementById("aiImageModal").style.display = "none"; aiImageTarget = null; }
async function generateAiImage(){
  if(!aiImageTarget) return;
  const status = document.getElementById("aiImageStatus");
  status.textContent = "جاري إنشاء الصورة... ⏳";
  document.getElementById("aiImageConfirm").disabled = true;
  try{
    const res = await adminFetch("/admin/ai-image/generate", {
      method: "POST",
      body: JSON.stringify({ kind: aiImageTarget.kind, name: aiImageTarget.name })
    });
    aiImageUrl = res.url;
    const img = document.getElementById("aiImagePreview");
    img.src = res.url;
    img.style.display = "block";
    document.getElementById("aiImageConfirm").disabled = false;
    status.textContent = "الصورة جاهزة — أكّدها أو أعد الإنشاء.";
  }catch(err){
    status.textContent = err.message;
    toast(err.message, "error");
  }
}
async function confirmAiImage(){
  if(!aiImageTarget || !aiImageUrl) return;
  try{
    await adminFetch("/admin/ai-image/apply", {
      method: "POST",
      body: JSON.stringify({ kind: aiImageTarget.kind, id: aiImageTarget.id, url: aiImageUrl })
    });
    toast("تم اعتماد الصورة ✅");
    const kind = aiImageTarget.kind;
    closeAiImage();
    if(kind === "product") loadProducts();
    if(kind === "category") loadCategories();
    if(kind === "section") loadSections();
    if(kind === "subsection") loadSubsections();
  }catch(err){ toast(err.message, "error"); }
}

async function importProviderCatalog(providerId, providerName){
  const marginInput = document.getElementById(`importMargin_${providerId}`);
  const margin = Number(marginInput.value);
  if(isNaN(margin) || margin < 0){ toast("حدد هامش ربح صحيح بالخانة جنب زر الاستيراد", "error"); return; }
  if(!confirm(`رح يتم سحب كل كتالوج "${providerName}" (كل الأقسام والمنتجات) وإضافته لموقعك بهامش ربح ${margin}%.\nهاي عملية دفعة وحدة، متابع؟`)) return;
  toast("جاري الاستيراد... قد ياخد لحظات حسب حجم كتالوج المزوّد ⏳");
  try{
    const res = await adminFetch(`/admin/providers/${providerId}/import-catalog`, {
      method: "POST", body: JSON.stringify({ margin_percent: margin })
    });
    toast("✅ " + res.message);
    loadProviders();
  }catch(err){ toast(err.message, "error"); }
}
async function importProviderFile(){
  const input = document.getElementById("impFileInput");
  const result = document.getElementById("impFileResult");
  const file = input && input.files && input.files[0];
  if(!file){ toast("اختر ملف CSV أولاً", "error"); return; }
  const text = await file.text();
  const lines = text.split(/\r?\n/);
  const header = lines[0] || "";
  const body = lines.slice(1).filter(l => l.trim() !== "");
  if(!body.length){ toast("الملف فارغ", "error"); return; }
  const CHUNK = 100;
  let imported = 0, skipped = 0, dups = 0, sections = [], n = 0;
  for(let i = 0; i < body.length; i += CHUNK){
    n++;
    const chunkText = header + "\n" + body.slice(i, i + CHUNK).join("\n");
    const fd = new FormData();
    fd.append("file", new Blob([chunkText], { type: "text/csv" }), file.name);
    fd.append("name", document.getElementById("impFileName").value.trim() || "Shams");
    fd.append("token", document.getElementById("impFileToken").value.trim());
    fd.append("url", document.getElementById("impFileUrl").value.trim());
    fd.append("margin", document.getElementById("impFileMargin").value || "15");
    fd.append("grouping", document.getElementById("impFileGrouping").value || "sections");
    if(result) result.textContent = `⏳ جاري الاستيراد… الدفعة ${n} من ${Math.ceil(body.length / CHUNK)}`;
    try{
      const res = await adminFetch("/admin/providers/import-file", { method:"POST", body: fd });
      imported += res.imported || 0; skipped += res.skipped || 0; dups += res.duplicates || 0;
      (res.sections || []).forEach(s => { if(!sections.includes(s)) sections.push(s); });
    }catch(err){ if(result) result.textContent = "توقفت عند الدفعة " + n + ": " + err.message; toast(err.message, "error"); return; }
  }
  if(result) result.textContent = `✅ تم استيراد وربط ${imported} منتج (تخطّي ${skipped}، مكرر ${dups}) | الأقسام: ${sections.join("، ")}`;
  toast(`✅ تم استيراد ${imported} منتج`);
  loadProviders(); if(typeof loadSections === "function") loadSections(); if(typeof loadProducts === "function") loadProducts();
}
async function addProvider(){
  const name = document.getElementById("providerName").value.trim();
  const api_token = document.getElementById("providerToken").value.trim();
  const api_url = document.getElementById("providerUrl").value.trim();
  if(!name || !api_token || !api_url){ toast("عبّي كل الحقول", "error"); return; }
  try{
    await adminFetch("/admin/providers", { method:"POST", body: JSON.stringify({ name, api_token, api_url }) });
    toast("تمت إضافة المزوّد ✅");
    ["providerName","providerToken","providerUrl"].forEach(id=> document.getElementById(id).value = "");
    loadProviders();
  }catch(err){ toast(err.message, "error"); }
}
async function deleteProvider(id){
  try{ await adminFetch(`/admin/providers/${id}`, { method:"DELETE" }); toast("تم الحذف"); loadProviders(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== إعدادات عامة ===== */
async function loadSettings(){
  const s = await adminFetch("/admin/settings");
  document.getElementById("settingsRate").value = s.exchange_rate;
  document.getElementById("settingsWelcome").value = s.welcome_message;
  document.getElementById("settingsSupport").value = s.support_username;
  document.getElementById("settingsPopupEnabled").checked = !!s.welcome_popup_enabled;
  document.getElementById("settingsPopupText").value = s.welcome_popup_text || "";
  if(document.getElementById("settingsAiUrl")){
    document.getElementById("settingsAiUrl").value = s.ai_image_api_url || "";
    document.getElementById("settingsAiKey").value = s.ai_image_api_key || "";
    document.getElementById("settingsAiPrompt").value = s.ai_image_prompt_template || "";
  }
  const setVal = (id, v)=>{ const el = document.getElementById(id); if(el) el.value = v || ""; };
  setVal("settingsAiPromptProduct", s.ai_image_prompt_product);
  setVal("settingsAiPromptSection", s.ai_image_prompt_section);
  setVal("settingsAdminChatIds", s.admin_notify_chat_ids);
  const c = s.contact || {};
  setVal("settingsWaNumber", c.whatsapp_number);
  setVal("settingsWaUrl", c.whatsapp_url);
  setVal("settingsTgUrl", c.telegram_url);
  setVal("settingsWaChannel", c.whatsapp_channel_url);
  setVal("settingsTgChannel", c.telegram_channel_url);
  const devWrap = document.getElementById("devLogoPreviewWrap");
  if(devWrap){
    if(s.dev_logo){
      document.getElementById("devLogoPreview").src = s.dev_logo;
      document.getElementById("devLogoPreview").onerror = ()=>{ devWrap.style.display = "none"; };
      devWrap.style.display = "block";
    }
    else devWrap.style.display = "none";
  }

  const grid = document.getElementById("bannerPreviewGrid");
  const images = s.banner_images || [];
  grid.innerHTML = images.map(b => `
    <div style="position:relative; display:inline-block; margin:4px;">
      <img src="${b.image}" style="width:120px; height:64px; object-fit:cover; border-radius:10px; border:1px solid var(--border); display:block;">
      <button class="btn-sm danger" style="position:absolute; top:-6px; left:-6px; padding:2px 7px; border-radius:50%;" onclick="removeBannerImage(${b.id})"><i class="fa-solid fa-xmark"></i></button>
    </div>`).join("") || `<div class="text-muted" style="font-size:11.5px;">لا توجد صور بعد — أضف حتى 5 صور للسلايدر</div>`;
  document.getElementById("bannerCountHint").textContent = `${images.length} / 5 صور`;
  document.getElementById("bannerAddBtn").disabled = images.length >= 5;

  const logoWrap = document.getElementById("logoPreviewWrap");
  if(s.logo_image){
    document.getElementById("logoPreview").src = s.logo_image;
    document.getElementById("logoPreview").onerror = ()=>{ logoWrap.style.display = "none"; };
    logoWrap.style.display = "block";
  }else{ logoWrap.style.display = "none"; }

  const iconWrap = document.getElementById("appIconPreviewWrap");
  if(s.app_icon){
    document.getElementById("appIconPreview").src = s.app_icon;
    document.getElementById("appIconPreview").onerror = ()=>{ iconWrap.style.display = "none"; };
    iconWrap.style.display = "block";
  }else{ iconWrap.style.display = "none"; }

  loadMaintenanceStatus();
}

function fmtHMS(sec){
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s2 = sec%60;
  return `${h} ساعة ${m} دقيقة ${s2} ثانية`;
}

let _adminMaintenanceInterval = null;
async function loadMaintenanceStatus(){
  try{
    const m = await adminFetch("/admin/maintenance");
    const box = document.getElementById("maintenanceStatusBox");
    if(_adminMaintenanceInterval) clearInterval(_adminMaintenanceInterval);
    if(m.enabled){
      box.style.display = "flex";
      let remaining = m.seconds_left;
      document.getElementById("maintenanceRemaining").textContent = fmtHMS(remaining);
      _adminMaintenanceInterval = setInterval(()=>{
        remaining -= 1;
        if(remaining <= 0){ clearInterval(_adminMaintenanceInterval); box.style.display = "none"; return; }
        document.getElementById("maintenanceRemaining").textContent = fmtHMS(remaining);
      }, 1000);
    } else {
      box.style.display = "none";
    }
  }catch(err){ /* تجاهل */ }
}

async function enableMaintenance(){
  const hours = Number(document.getElementById("maintenanceHours").value || 0);
  if(!hours || hours <= 0){ toast("حدد عدد ساعات صحيح", "error"); return; }
  try{
    await adminFetch("/admin/maintenance", { method:"POST", body: JSON.stringify({ enabled: true, hours }) });
    toast("✅ تم تفعيل وضع الصيانة");
    loadMaintenanceStatus();
  }catch(err){ toast(err.message, "error"); }
}

async function disableMaintenance(){
  try{
    await adminFetch("/admin/maintenance", { method:"POST", body: JSON.stringify({ enabled: false }) });
    toast("✅ تم إيقاف وضع الصيانة");
    loadMaintenanceStatus();
  }catch(err){ toast(err.message, "error"); }
}

async function removeBannerImage(imageId){
  try{ await adminFetch(`/admin/settings/banner-image/${imageId}`, { method:"DELETE" }); toast("تمت إزالة الصورة"); loadSettings(); }
  catch(err){ toast(err.message, "error"); }
}
async function clearAllBanners(){
  if(!confirm("سيتم حذف كل صور البنرات. متابعة؟")) return;
  try{ await adminFetch("/admin/banners/all", { method:"DELETE" }); toast("تم حذف كل البنرات ✅"); loadSettings(); }
  catch(err){ toast(err.message, "error"); }
}
async function removeLogo(){
  try{ await adminFetch("/admin/settings/logo", { method:"DELETE" }); toast("تمت إزالة اللوغو"); loadSettings(); location.reload(); }
  catch(err){ toast(err.message, "error"); }
}

async function removeDevLogo(){
  try{ await adminFetch("/admin/settings/dev-logo", { method:"DELETE" }); toast("تمت إزالة لوغو المطوّر"); loadSettings(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== تثبيت التطبيق (PWA) ===== */
let _deferredPwaPrompt = null;
window.addEventListener("beforeinstallprompt", (e)=>{
  e.preventDefault();
  _deferredPwaPrompt = e;
  const hint = document.getElementById("pwaHint");
  if(hint) hint.textContent = "التطبيق جاهز للتثبيت — اضغط الزر تحت.";
});
async function installPwa(){
  if(!_deferredPwaPrompt){
    toast("إذا كنت على آيفون: افتح مشاركة ← إضافة إلى الشاشة الرئيسية. أو التطبيق مثبّت مسبقاً.", "error");
    return;
  }
  _deferredPwaPrompt.prompt();
  const { outcome } = await _deferredPwaPrompt.userChoice;
  _deferredPwaPrompt = null;
  toast(outcome === "accepted" ? "تم تثبيت التطبيق ✅" : "تم إلغاء التثبيت");
}

async function removeAppIcon(){
  try{ await adminFetch("/admin/settings/app-icon", { method:"DELETE" }); toast("تمت إزالة أيقونة التطبيق"); loadSettings(); }
  catch(err){ toast(err.message, "error"); }
}

function previewWelcomePopup(){
  window.open("/store.html?preview_popup=1", "_blank");
}
async function saveSettings(){
  const exchange_rate = Number(document.getElementById("settingsRate").value || 0);
  const welcome_message = document.getElementById("settingsWelcome").value.trim();
  const support_username = document.getElementById("settingsSupport").value.trim();
  const welcome_popup_enabled = document.getElementById("settingsPopupEnabled").checked;
  const welcome_popup_text = document.getElementById("settingsPopupText").value.trim();
  const ai_image_api_url = document.getElementById("settingsAiUrl") ? document.getElementById("settingsAiUrl").value.trim() : "";
  const ai_image_api_key = document.getElementById("settingsAiKey") ? document.getElementById("settingsAiKey").value.trim() : "";
  const ai_image_prompt_template = document.getElementById("settingsAiPrompt") ? document.getElementById("settingsAiPrompt").value.trim() : "";
  const getVal = (id)=>{ const el = document.getElementById(id); return el ? el.value.trim() : ""; };
  const payload = {
    exchange_rate, welcome_message, support_username, welcome_popup_enabled, welcome_popup_text,
    ai_image_api_url, ai_image_api_key, ai_image_prompt_template,
    ai_image_prompt_product: getVal("settingsAiPromptProduct"),
    ai_image_prompt_section: getVal("settingsAiPromptSection"),
    support_whatsapp_number: getVal("settingsWaNumber"),
    support_whatsapp_url: getVal("settingsWaUrl"),
    support_telegram_url: getVal("settingsTgUrl"),
    whatsapp_channel_url: getVal("settingsWaChannel"),
    telegram_channel_url: getVal("settingsTgChannel"),
  };
  try{
    await adminFetch("/admin/settings", { method:"POST", body: JSON.stringify(payload) });
    toast("تم حفظ الإعدادات ✅");
  }catch(err){ toast(err.message, "error"); }
}

/* ===== 11) صلاحيات الأدمن ===== */
async function loadAdmins(){
  const admins = await adminFetch("/admin/admins");
  document.getElementById("adminsTableBody").innerHTML = admins.map(a=>`
    <tr><td style="font-family:'Orbitron',monospace;">${a.user_id}</td>
    <td>${a.main ? '<span class="status-badge completed">مشرف رئيسي</span>' : '<span class="status-badge pending">مشرف</span>'}</td>
    <td>${a.main ? '—' : `<button class="btn-sm danger" onclick="removeAdminUser(${a.user_id})">إزالة</button>`}</td></tr>`).join("");
}
async function addAdminUser(){
  const idVal = document.getElementById("newAdminId").value.trim();
  if(!idVal || isNaN(Number(idVal))){ toast("أدخل آيدي تيليجرام صحيح (أرقام فقط)", "error"); return; }
  try{
    await adminFetch("/admin/admins", { method:"POST", body: JSON.stringify({ user_id: Number(idVal) }) });
    toast("تمت إضافة المشرف ✅");
    document.getElementById("newAdminId").value = "";
    loadAdmins();
  }catch(err){ toast(err.message, "error"); }
}
async function removeAdminUser(userId){
  try{ await adminFetch(`/admin/admins/${userId}`, { method:"DELETE" }); toast("تمت الإزالة"); loadAdmins(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== 11-b) أدمن الموقع (Web Admins) — صلاحية كاملة للوحة ===== */
async function loadWebAdmins(){
  try{
    const data = await adminFetch("/admin/web-admins");
    const isOwner = !!data.is_owner;
    document.getElementById("webAdminsAddRow").style.display = isOwner ? "" : "none";
    document.getElementById("webAdminsTableBody").innerHTML = (data.admins || []).map(a=>`
      <tr>
        <td style="font-family:monospace;">${a.email}</td>
        <td>${a.owner ? '<span class="status-badge completed">المالك</span>' : '<span class="status-badge pending">أدمن</span>'}</td>
        <td>${a.added_at || '—'}</td>
        <td>${(a.removable && isOwner) ? `<button class="btn-sm danger" onclick="removeWebAdmin('${a.email.replace(/'/g,"\\'")}')">إزالة</button>` : '—'}</td>
      </tr>`).join("");
  }catch(err){ /* silent — قد لا تكون النقطة متاحة */ }
}
async function addWebAdmin(){
  const email = (document.getElementById("newWebAdminEmail").value || "").trim().toLowerCase();
  if(!email || !email.includes("@")){ toast("أدخل بريد إلكتروني صحيح", "error"); return; }
  try{
    await adminFetch("/admin/web-admins", { method:"POST", body: JSON.stringify({ email }) });
    toast("تمت إضافة الأدمن ✅");
    document.getElementById("newWebAdminEmail").value = "";
    loadWebAdmins();
  }catch(err){ toast(err.message, "error"); }
}
async function removeWebAdmin(email){
  if(!confirm("إزالة صلاحية الأدمن عن: " + email + "؟")) return;
  try{
    await adminFetch(`/admin/web-admins/${encodeURIComponent(email)}`, { method:"DELETE" });
    toast("تمت الإزالة"); loadWebAdmins();
  }catch(err){ toast(err.message, "error"); }
}


/* ===== 3) تعديل عام (modal ديناميكي) ===== */
let editTarget = null;
function openEdit(kind, id, title, fields){
  editTarget = { kind, id };
  document.getElementById("editModalTitle").textContent = "تعديل: " + title;
  const body = document.getElementById("editModalBody");
  const labels = { name:"الاسم", emoji:"الإيموجي", price:"السعر $", unit_qty:"السعر لكل كمية", min_qty:"الحد الأدنى للكمية", max_qty:"الحد الأقصى للكمية", stock_qty:"كمية المخزون (فارغ = غير محدود)", requires_id:"يطلب ايدي اللاعب (1 = نعم / 0 = لا)", active:"الحالة", exchange_rate:"سعر الصرف", api_token:"API Token", api_url:"API URL", description:"الوصف" };
  body.innerHTML = Object.entries(fields).map(([k,v])=>{
    if(k === "active") return `<div class="field"><label>${labels[k]||k}</label><select id="ef_${k}" style="padding:11px;border-radius:11px;border:1px solid var(--border);background:var(--card-soft);color:var(--text);"><option value="1" ${v?"selected":""}>مفعّل</option><option value="0" ${!v?"selected":""}>معطّل</option></select></div>`;
    return `<div class="field"><label>${labels[k]||k}</label><input type="${typeof v==='number'?'number':'text'}" id="ef_${k}" value="${v??''}" step="${(k.includes('price')||k.includes('rate'))?'0.01':'1'}" style="padding:11px;border-radius:11px;border:1px solid var(--border);background:var(--card-soft);color:var(--text);"></div>`;
  }).join("");
  document.getElementById("editModal").style.display = "flex";
}
async function saveEdit(){
  if(!editTarget) return;
  const { kind, id } = editTarget;
  const eps = { product:`/admin/products/${id}`, category:`/admin/categories/${id}`, section:`/admin/sections/${id}`, subsection:`/admin/subsections/${id}`, manual_method:`/admin/deposit-methods/manual/${id}`, auto_method:`/admin/deposit-methods/auto/${id}` };
  const inputs = document.querySelectorAll("#editModalBody input, #editModalBody select");
  const b = {};
  inputs.forEach(el=>{
    const k=el.id.replace("ef_","");
    if(k === "stock_qty"){ b[k] = el.value.trim()===""? null : Number(el.value); return; }
    b[k]=el.type==="number"?Number(el.value):el.value;
  });
  if("active" in b) b.active = b.active==="1"||b.active===1;
  try{
    await adminFetch(eps[kind], { method:"PUT", body: JSON.stringify(b) });
    toast("تم التعديل ✅"); closeEdit();
    if(kind==="product") loadProducts();
    if(kind==="category") loadCategories();
    if(kind==="section") loadSections();
    if(kind==="subsection") loadSubsections();
    if(kind.includes("method")) loadDepositMethods();
  }catch(err){ toast(err.message, "error"); }
}
function closeEdit(){ document.getElementById("editModal").style.display="none"; editTarget=null; }

/* ===== طلبات المتجر اليدوية (قبول / رفض / شحن عبر مزوّد) ===== */
async function loadShopOrders(){
  const orders = await adminFetch("/admin/shop-orders");
  const STATUS_LABEL = { pending:"بإنتظار المراجعة", accepted:"مقبول/مكتمل", rejected:"مرفوض" };
  document.getElementById("shopOrdersBody").innerHTML = orders.map(o=>`
    <tr>
      <td>#${o.id}</td>
      <td>${o.user_id}</td>
      <td>${o.product_name}<br><small style="color:var(--muted)">${o.category_name}</small></td>
      <td>${o.player_id||'-'}</td>
      <td>${Math.round(o.price_syp).toLocaleString()} ل.س</td>
      <td><span class="status-badge ${o.status==='pending'?'pending':o.status==='accepted'?'completed':'failed'}">${STATUS_LABEL[o.status]||o.status}</span></td>
      <td>
        ${o.status==='pending' ? `
          <button class="btn-sm primary" onclick="acceptShopOrder(${o.id})">✅ قبول</button>
          <button class="btn-sm danger" onclick="rejectShopOrder(${o.id})">❌ رفض</button>
          <button class="btn-sm" onclick="openExecuteModal(${o.id}, '${o.product_name.replace(/'/g,'')}', '${o.player_id||''}', ${o.qty||1})"><i class="fa-solid fa-bolt"></i> شحن</button>
        ` : '—'}
      </td>
    </tr>`).join("")
  || `<tr><td colspan="7" class="text-muted" style="text-align:center; padding:16px;">لا توجد طلبات يدوية</td></tr>`;
}

async function acceptShopOrder(id){
  try{ await adminFetch(`/admin/shop-orders/${id}/accept`, { method:"POST" }); toast("تم القبول وإشعار العميل ✅"); loadShopOrders(); }
  catch(err){ toast(err.message, "error"); }
}
async function rejectShopOrder(id){
  try{ await adminFetch(`/admin/shop-orders/${id}/reject`, { method:"POST" }); toast("تم الرفض واسترجاع الرصيد"); loadShopOrders(); }
  catch(err){ toast(err.message, "error"); }
}

/* ===== Modal تنفيذ الطلب عبر مزوّد ===== */
let executeOrderId = null;
async function openExecuteModal(orderId, productName, playerId, qty){
  executeOrderId = orderId;
  document.getElementById("executeOrderInfo").textContent = `${productName} • آيدي: ${playerId} • كمية: ${qty}`;
  document.getElementById("executeApiProductId").value = "";
  document.getElementById("executeCostUsd").value = "";
  document.getElementById("executeProviderProducts").innerHTML = "";
  document.getElementById("executeModal").style.display = "flex";

  // تحميل المزودين
  const providers = await adminFetch("/admin/providers").catch(()=>[]);
  const sel = document.getElementById("executeProviderSel");
  sel.innerHTML = `<option value="">— اختر المزوّد —</option>` + providers.map(p=>`<option value="${p.id}">${p.name}</option>`).join("");
}
function closeExecuteModal(){ document.getElementById("executeModal").style.display="none"; executeOrderId=null; }

async function loadProviderProducts(){
  const pid = document.getElementById("executeProviderSel").value;
  if(!pid) return;
  const box = document.getElementById("executeProviderProducts");
  box.innerHTML = `<div style="font-size:11px; color:var(--muted); padding:8px;">⏳ جاري جلب منتجات المزوّد...</div>`;
  try{
    const prods = await adminFetch(`/admin/providers/${pid}/products`);
    if(!prods.length){ box.innerHTML = `<div style="font-size:11px; color:var(--muted); padding:8px;">لا توجد منتجات</div>`; return; }
    box.innerHTML = `<div style="font-size:10.5px; color:var(--muted); margin-bottom:6px;">اضغط على المنتج لاختياره:</div>` +
      prods.slice(0,40).map(p=>`<button class="btn-sm" style="margin:3px; font-size:10px;" onclick="document.getElementById('executeApiProductId').value='${p.id}'; if(${JSON.stringify(p.price||0)}){document.getElementById('executeCostUsd').value=${JSON.stringify(p.price||0)};} this.style.background='var(--accent)'; this.style.color='#fff';">${p.name} (${p.id})</button>`).join("");
  }catch(err){ box.innerHTML = `<div style="font-size:11px; color:var(--danger);">${err.message}</div>`; }
}

async function confirmExecute(){
  if(!executeOrderId) return;
  const provider_id = document.getElementById("executeProviderSel").value;
  const api_product_id = document.getElementById("executeApiProductId").value.trim();
  const cost_usd = Number(document.getElementById("executeCostUsd").value || 0);
  if(!provider_id || !api_product_id){ toast("اختر المزوّد وآيدي المنتج", "error"); return; }
  const btn = document.getElementById("executeConfirmBtn");
  btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
  try{
    const r = await adminFetch(`/admin/shop-orders/${executeOrderId}/execute`, { method:"POST", body: JSON.stringify({ provider_id: Number(provider_id), api_product_id, cost_usd }) });
    toast("✅ " + r.message); closeExecuteModal(); loadShopOrders();
  }catch(err){ toast(err.message, "error"); }
  btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-bolt"></i> تنفيذ الشحن الآن';
}

/* ===== ربط فئة بمزوّد API بشكل دائم (من لوحة تحكم الموقع مباشرة) ===== */
let linkCategoryId = null;
async function openLinkModal(categoryId, categoryName){
  linkCategoryId = categoryId;
  document.getElementById("linkCategoryInfo").textContent = categoryName;
  document.getElementById("linkApiProductId").value = "";
  document.getElementById("linkProviderProducts").innerHTML = "";
  document.getElementById("linkCurrentStatus").innerHTML = "";
  document.getElementById("linkModal").style.display = "flex";

  const providers = await adminFetch("/admin/providers").catch(()=>[]);
  const sel = document.getElementById("linkProviderSel");
  sel.innerHTML = `<option value="">— اختر المزوّد —</option>` + providers.map(p=>`<option value="${p.id}">${p.name}</option>`).join("");

  try{
    const status = await adminFetch(`/admin/categories/${categoryId}/link`);
    if(status.linked){
      document.getElementById("linkCurrentStatus").innerHTML =
        `<div class="info-banner" style="font-size:11px; border-color:var(--success);"><i class="fa-solid fa-circle-check" style="color:var(--success);"></i> مربوطة حالياً — آيدي المزوّد: <b>${status.api_product_id}</b></div>`;
      sel.value = status.provider_id;
      document.getElementById("linkApiProductId").value = status.api_product_id;
    }
  }catch(err){ /* لا يوجد ربط سابق، تجاهل */ }
}
function closeLinkModal(){ document.getElementById("linkModal").style.display="none"; linkCategoryId=null; }

async function loadLinkProviderProducts(){
  const pid = document.getElementById("linkProviderSel").value;
  if(!pid) return;
  const box = document.getElementById("linkProviderProducts");
  box.innerHTML = `<div style="font-size:11px; color:var(--muted); padding:8px;">⏳ جاري جلب منتجات المزوّد...</div>`;
  try{
    const prods = await adminFetch(`/admin/providers/${pid}/products`);
    if(!prods.length){ box.innerHTML = `<div style="font-size:11px; color:var(--muted); padding:8px;">لا توجد منتجات</div>`; return; }
    box.innerHTML = `<div style="font-size:10.5px; color:var(--muted); margin-bottom:6px;">اضغط على المنتج لاختياره:</div>` +
      prods.slice(0,40).map(p=>`<button class="btn-sm" style="margin:3px; font-size:10px;" onclick="document.getElementById('linkApiProductId').value='${p.id}'; this.style.background='var(--accent)'; this.style.color='#fff';">${p.name} (${p.id})</button>`).join("");
  }catch(err){ box.innerHTML = `<div style="font-size:11px; color:var(--danger);">${err.message}</div>`; }
}

async function confirmLink(){
  if(!linkCategoryId) return;
  const provider_id = document.getElementById("linkProviderSel").value;
  const api_product_id = document.getElementById("linkApiProductId").value.trim();
  if(!provider_id || !api_product_id){ toast("اختر المزوّد وآيدي المنتج", "error"); return; }
  const btn = document.getElementById("linkConfirmBtn");
  btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
  try{
    const r = await adminFetch(`/admin/categories/${linkCategoryId}/link`, { method:"POST", body: JSON.stringify({ provider_id: Number(provider_id), api_product_id }) });
    toast("✅ " + r.message); closeLinkModal(); loadCategories();
  }catch(err){ toast(err.message, "error"); }
  btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-link"></i> حفظ الربط';
}

async function unlinkCurrentCategory(){
  if(!linkCategoryId) return;
  if(!confirm("متأكد من إلغاء ربط هذه الفئة بالمزوّد؟")) return;
  try{
    await adminFetch(`/admin/categories/${linkCategoryId}/link`, { method:"DELETE" });
    toast("تم إلغاء الربط"); closeLinkModal(); loadCategories();
  }catch(err){ toast(err.message, "error"); }
}


/* =========================================================
   النسخ الاحتياطي / الاسترجاع / حذف كل البيانات
   ========================================================= */
async function loadBackups(){
  const body = document.getElementById("backupsTableBody");
  if(!body) return;
  try{
    const data = await adminFetch("/admin/backups");
    const token = localStorage.getItem("admin_token") || "";
    if(!data.backups.length){
      body.innerHTML = `<tr><td colspan="4">لا توجد نسخ احتياطية بعد</td></tr>`;
      return;
    }
    body.innerHTML = data.backups.map(b=>`
      <tr>
        <td style="font-family:monospace; font-size:11px;">${b.name}</td>
        <td>${b.size_kb} KB</td>
        <td>${b.created_at}</td>
        <td class="row-actions">
          <a class="btn-sm" href="${API_BASE}${b.download_url}?token=${encodeURIComponent(token)}"><i class="fa-solid fa-download"></i> تنزيل</a>
          <button class="btn-sm" onclick="restoreBackup('${b.name}', this)"><i class="fa-solid fa-rotate-left"></i> استرجاع</button>
          <button class="btn-sm danger" onclick="deleteBackup('${b.name}')"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>`).join("");
  }catch(err){
    body.innerHTML = `<tr><td colspan="4">${err.message}</td></tr>`;
  }
}

async function createBackup(btn){
  if(btn) btn.disabled = true;
  try{
    const r = await adminFetch("/admin/backups", { method:"POST" });
    toast(r.message);
    loadBackups();
  }catch(err){ toast(err.message, "error"); }
  if(btn) btn.disabled = false;
}

async function deleteBackup(name){
  if(!confirm("حذف هذه النسخة الاحتياطية؟")) return;
  try{
    const r = await adminFetch("/admin/backups/" + encodeURIComponent(name), { method:"DELETE" });
    toast(r.message);
    loadBackups();
  }catch(err){ toast(err.message, "error"); }
}

async function restoreBackup(name, btn){
  if(!confirm("سيتم استبدال كل البيانات الحالية بمحتوى هذه النسخة. متابعة؟")) return;
  if(btn) btn.disabled = true;
  const fd = new FormData();
  fd.append("name", name);
  try{
    const r = await adminFetch("/admin/restore", { method:"POST", body: fd });
    toast(r.message);
    setTimeout(()=> location.reload(), 1200);
  }catch(err){ toast(err.message, "error"); }
  if(btn) btn.disabled = false;
}

async function restoreFromUpload(btn){
  const input = document.getElementById("restoreFileInput");
  const file = input && input.files[0];
  if(!file) return toast("اختر ملف نسخة احتياطية أولاً", "error");
  if(!confirm("سيتم استبدال كل البيانات الحالية بمحتوى هذا الملف. متابعة؟")) return;
  if(btn) btn.disabled = true;
  const fd = new FormData();
  fd.append("file", file);
  try{
    const r = await adminFetch("/admin/restore", { method:"POST", body: fd });
    toast(r.message);
    setTimeout(()=> location.reload(), 1200);
  }catch(err){ toast(err.message, "error"); }
  if(btn) btn.disabled = false;
}

async function wipeAllData(btn){
  const confirmText = (document.getElementById("wipeConfirm").value || "").trim();
  const scope = document.getElementById("wipeScope").value;
  if(confirmText !== "حذف") return toast("اكتب كلمة (حذف) للتأكيد", "error");
  if(!confirm("تأكيد أخير: سيتم حذف البيانات نهائياً. متابعة؟")) return;
  if(btn) btn.disabled = true;
  try{
    const r = await adminFetch("/admin/wipe-data", { method:"POST", body: JSON.stringify({ confirm: confirmText, scope }) });
    toast(r.message);
    document.getElementById("wipeConfirm").value = "";
    loadBackups();
  }catch(err){ toast(err.message, "error"); }
  if(btn) btn.disabled = false;
}
