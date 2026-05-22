async function loadLiveDashboard(){
  try{
    const stats=await (await fetch("./data/stats.json?t="+Date.now())).json();
    const cards=document.querySelectorAll(".stats-panel article b");
    if(cards[0]) cards[0].textContent=(stats.today||0)+"건";
    if(cards[1]) cards[1].textContent="+"+Number(stats.avg_edge||0).toFixed(2)+"%";
    if(cards[2]) cards[2].textContent=(stats.vip||0)+"건";
    if(cards[3]) cards[3].textContent="+"+Number(stats.max_edge||0).toFixed(2)+"%";

    const rows=await (await fetch("./data/signals.json?t="+Date.now())).json();
    if(Array.isArray(rows) && rows.length){
      const last=rows[0];
      const live=document.querySelector(".live-edge-card");
      const edgeNum = Number(last.real_edge || 0);
      if(live){
        live.innerHTML=`<div class="live-head"><span>실시간 추가 수익 기회</span><b>+${edgeNum.toFixed(2)}%</b></div>
        <h3>🚨 ${last.coin || "-"} 양방 후보</h3>
        <p>국내: ${last.domestic_exchange || last.domestic || "-"} · 해외선물: ${last.foreign_exchange || last.foreign || "-"}</p>
        <div class="live-metrics">
          <div><small>가격 차이</small><strong>+${Number(last.coin_gap || 0).toFixed(2)}%</strong></div>
          <div><small>시장 영향</small><strong>${Number(last.btc_gap || 0).toFixed(2)}%</strong></div>
          <div><small>실체결</small><strong>${Number(last.krw || last.executable_krw || 0).toLocaleString()}원</strong></div>
          <div><small>기준</small><strong>최근 감지</strong></div>
        </div>
        <a class="btn primary full" href="./payment.html">서비스 시작</a>`;
      }
    }
  }catch(e){
    console.log(e);
  }
}

/* =========================
   K-EDGE 회원/로그인/등록 UX
========================= */
const KEDGE_AUTH_KEY = "kedge_local_user";
const KEDGE_USERS_KEY = "kedge_local_users";
const KEDGE_REQUESTS_KEY = "kedge_vip_requests";

const SUPABASE_URL = window.KEDGE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = window.KEDGE_SUPABASE_ANON_KEY || "";
let kedgeSupabase = null;

try {
  if (window.supabase && SUPABASE_URL && SUPABASE_ANON_KEY) {
    kedgeSupabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
} catch (e) {
  console.log("Supabase init skipped", e);
}

function qs(id){ return document.getElementById(id); }
function val(id){ return (qs(id)?.value || "").trim(); }

function setMsg(id, text, type="error"){
  const el = qs(id);
  if(!el) return;
  el.textContent = text;
  el.className = (el.classList.contains("form-msg") ? "form-msg " : "auth-msg ") + type;
}

function getLocalUsers(){
  try { return JSON.parse(localStorage.getItem(KEDGE_USERS_KEY) || "{}"); }
  catch(e){ return {}; }
}
function saveLocalUsers(users){ localStorage.setItem(KEDGE_USERS_KEY, JSON.stringify(users)); }
function getLocalUser(){
  try { return JSON.parse(localStorage.getItem(KEDGE_AUTH_KEY) || "null"); }
  catch(e){ return null; }
}
function setLocalUser(user){ localStorage.setItem(KEDGE_AUTH_KEY, JSON.stringify(user)); }
function clearLocalUser(){ localStorage.removeItem(KEDGE_AUTH_KEY); }
function getRequests(){
  try { return JSON.parse(localStorage.getItem(KEDGE_REQUESTS_KEY) || "[]"); }
  catch(e){ return []; }
}
function saveRequests(rows){ localStorage.setItem(KEDGE_REQUESTS_KEY, JSON.stringify(rows)); }

function maskValue(v){
  if(!v) return "미등록";
  if(v.length <= 8) return "••••";
  return v.slice(0,4) + "••••" + v.slice(-4);
}
function planLabel(plan){
  const map = { FREE:"FREE", VIP:"VIP 👑", SEMI:"VIP Lite 🤖", AUTO:"VIP Pro 🚀" };
  return map[plan] || plan || "FREE";
}
function isBotPlan(plan){ return plan === "SEMI" || plan === "AUTO"; }
function isAutoPlan(plan){ return plan === "AUTO"; }

function friendlyAuthError(err){
  const msg = String((err && err.message) || err || "").toLowerCase();
  if(msg.includes("invalid login") || msg.includes("invalid credentials")) return "❌ 이메일 또는 비밀번호가 틀렸습니다.";
  if(msg.includes("email not confirmed")) return "❌ 이메일 인증이 필요합니다. 메일함을 확인해주세요.";
  if(msg.includes("user already registered") || msg.includes("already")) return "❌ 이미 가입된 이메일입니다. 로그인해주세요.";
  if(msg.includes("password")) return "❌ 비밀번호 형식이 올바르지 않습니다.";
  if(msg.includes("email")) return "❌ 이메일 형식이 올바르지 않습니다.";
  return "❌ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

function togglePassword(inputId, btn){
  const input = qs(inputId);
  if(!input) return;
  const hidden = input.type === "password";
  input.type = hidden ? "text" : "password";
  if(btn) btn.textContent = hidden ? "🙈" : "👁";
}

function getSignupExtra(){
  const plan = val("signupPlan") || "FREE";
  return {
    plan,
    tg_bot_token: val("signupBotToken"),
    tg_chat_id: val("signupChatId"),
    exchange: val("signupExchange") || "MEXC",
    api_key: val("signupApiKey"),
    api_secret: val("signupApiSecret")
  };
}

function syncPlanFields(){
  const plan = val("signupPlan") || val("productSelect") || "FREE";
  const isBot = isBotPlan(plan);
  const isAuto = isAutoPlan(plan);

  document.querySelectorAll("[data-plan-field='bot']").forEach(el=> el.style.display = isBot ? "block" : "none");
  document.querySelectorAll("[data-plan-field='auto']").forEach(el=> el.style.display = isAuto ? "block" : "none");
  document.querySelectorAll("[data-product-field='bot']").forEach(el=> el.style.display = isBot ? "block" : "none");
  document.querySelectorAll("[data-product-field='auto']").forEach(el=> el.style.display = isAuto ? "block" : "none");
}

async function signupUser(){
  const email = val("signupEmail");
  const password = qs("signupPassword")?.value || "";
  const confirm = qs("signupPasswordConfirm")?.value || "";
  const telegram = val("signupTelegram");
  const extra = getSignupExtra();

  if(!email) return setMsg("signupMsg", "❌ 이메일을 입력해주세요.");
  if(!email.includes("@")) return setMsg("signupMsg", "❌ 이메일 형식이 올바르지 않습니다.");
  if(!password) return setMsg("signupMsg", "❌ 비밀번호를 입력해주세요.");
  if(password.length < 6) return setMsg("signupMsg", "❌ 비밀번호는 6자리 이상으로 입력해주세요.");
  if(password !== confirm) return setMsg("signupMsg", "❌ 비밀번호가 일치하지 않습니다.");
  if(isBotPlan(extra.plan) && (!extra.tg_bot_token || !extra.tg_chat_id)) return setMsg("signupMsg", "❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
  if(isAutoPlan(extra.plan) && (!extra.api_key || !extra.api_secret)) return setMsg("signupMsg", "❌ 자동은 API KEY와 SECRET이 필요합니다.");

  if(kedgeSupabase){
    try{
      const { error } = await kedgeSupabase.auth.signUp({
        email,
        password,
        options: { data: { telegram, ...extra } }
      });
      if(error) return setMsg("signupMsg", friendlyAuthError(error));
      setMsg("signupMsg", "✅ 회원가입 완료. 로그인 페이지로 이동합니다.", "success");
      setTimeout(()=> location.href="./login.html", 900);
      return;
    }catch(e){ return setMsg("signupMsg", friendlyAuthError(e)); }
  }

  const users = getLocalUsers();
  if(users[email]) return setMsg("signupMsg", "❌ 이미 가입된 이메일입니다. 로그인해주세요.");

  users[email] = { email, password, telegram: telegram || "미등록", ...extra };
  saveLocalUsers(users);
  setLocalUser({ email, telegram: telegram || "미등록", ...extra });
  setMsg("signupMsg", "✅ 회원가입 완료. 내정보로 이동합니다.", "success");
  setTimeout(()=> location.href="./mypage.html", 900);
}

async function loginUser(){
  const email = val("loginEmail");
  const password = qs("loginPassword")?.value || "";
  if(!email) return setMsg("loginMsg", "❌ 이메일을 입력해주세요.");
  if(!password) return setMsg("loginMsg", "❌ 비밀번호를 입력해주세요.");

  if(kedgeSupabase){
    try{
      const { data, error } = await kedgeSupabase.auth.signInWithPassword({ email, password });
      if(error) return setMsg("loginMsg", friendlyAuthError(error));
      const user = data.user || {};
      const meta = user.user_metadata || {};
      setLocalUser({
        email: user.email || email,
        telegram: meta.telegram || "미등록",
        plan: meta.plan || "FREE",
        tg_bot_token: meta.tg_bot_token || "",
        tg_chat_id: meta.tg_chat_id || "",
        exchange: meta.exchange || "",
        api_key: meta.api_key || "",
        api_secret: meta.api_secret || ""
      });
      setMsg("loginMsg", "✅ 로그인 완료. 메인으로 이동합니다.", "success");
      updateAuthUI();
      setTimeout(()=> location.href="./index.html", 800);
      return;
    }catch(e){ return setMsg("loginMsg", friendlyAuthError(e)); }
  }

  const users = getLocalUsers();
  if(!users[email]) return setMsg("loginMsg", "❌ 존재하지 않는 계정입니다. 회원가입을 먼저 해주세요.");
  if(users[email].password !== password) return setMsg("loginMsg", "❌ 비밀번호가 틀렸습니다.");

  const { password: _pw, ...safeUser } = users[email];
  setLocalUser(safeUser);
  setMsg("loginMsg", "✅ 로그인 완료. 메인으로 이동합니다.", "success");
  updateAuthUI();
  setTimeout(()=> location.href="./index.html", 800);
}

async function resetPassword(){
  const email = val("loginEmail");
  if(!email) return setMsg("loginMsg", "❌ 비밀번호 찾기를 하려면 이메일을 먼저 입력해주세요.");
  if(kedgeSupabase){
    try{
      const { error } = await kedgeSupabase.auth.resetPasswordForEmail(email, { redirectTo: location.origin + "/login.html" });
      if(error) return setMsg("loginMsg", friendlyAuthError(error));
      setMsg("loginMsg", "✅ 비밀번호 재설정 메일을 보냈습니다.", "success");
      return;
    }catch(e){ return setMsg("loginMsg", friendlyAuthError(e)); }
  }
  const users = getLocalUsers();
  if(!users[email]) return setMsg("loginMsg", "❌ 존재하지 않는 이메일입니다.");
  setMsg("loginMsg", "✅ 테스트 모드: 가입된 이메일입니다. 실제 메일 발송은 Supabase 연결 후 가능합니다.", "success");
}

async function logoutUser(){
  try{ if(kedgeSupabase) await kedgeSupabase.auth.signOut(); }catch(e){}
  clearLocalUser();
  updateAuthUI();
  location.href = "./index.html";
}

async function getCurrentUser(){
  if(kedgeSupabase){
    try{
      const { data } = await kedgeSupabase.auth.getUser();
      if(data && data.user){
        const meta = data.user.user_metadata || {};
        const user = {
          email: data.user.email || "-",
          telegram: meta.telegram || "미등록",
          plan: meta.plan || "FREE",
          tg_bot_token: meta.tg_bot_token || "",
          tg_chat_id: meta.tg_chat_id || "",
          exchange: meta.exchange || "",
          api_key: meta.api_key || "",
          api_secret: meta.api_secret || ""
        };
        setLocalUser(user);
        return user;
      }
    }catch(e){}
  }
  return getLocalUser();
}

async function updateAuthUI(){
  const user = await getCurrentUser();
  const top = qs("topAuthArea");
  if(top){
    if(user){
      const plan = user.plan || "FREE";
      top.innerHTML = `
        <div class="user-mini">
          <span class="user-name">${user.email || "회원"}</span>
          <span class="plan-badge plan-${plan.toLowerCase()}">${planLabel(plan)}</span>
          <a class="login" href="./mypage.html">내정보</a>
          <button onclick="logoutUser()">로그아웃</button>
        </div>`;
    }else{
      top.innerHTML = `<a class="login" href="./login.html">로그인</a><a class="join" href="./join.html">회원가입</a>`;
    }
  }

  const status = qs("authStatus");
  if(status){
    status.innerHTML = user
      ? `<b>✅ 로그인 중</b><p>${user.email || "-"} / ${planLabel(user.plan || "FREE")}</p>`
      : `<b>로그인이 필요합니다.</b><p>회원 기능은 로그인 후 이용할 수 있습니다.</p>`;
  }

  if(qs("myEmail")) qs("myEmail").textContent = user?.email || "-";
  if(qs("myPlan")) qs("myPlan").textContent = planLabel(user?.plan || "FREE");
  if(qs("myTelegram")) qs("myTelegram").textContent = user?.telegram || "미등록";
  if(qs("myBotToken")) qs("myBotToken").textContent = maskValue(user?.tg_bot_token || "");
  if(qs("myChatId")) qs("myChatId").textContent = user?.tg_chat_id || "미등록";
  if(qs("myExchange")) qs("myExchange").textContent = user?.exchange || "미등록";
  if(qs("myApiKey")) qs("myApiKey").textContent = maskValue(user?.api_key || "");
  if(qs("myApiSecret")) qs("myApiSecret").textContent = maskValue(user?.api_secret || "");

  document.querySelectorAll("[data-my-bot]").forEach(el=> el.style.display = user && isBotPlan(user.plan) ? "block" : "none");
  document.querySelectorAll("[data-my-auto]").forEach(el=> el.style.display = user && isAutoPlan(user.plan) ? "block" : "none");

  const loggedIn = qs("mypageLoggedIn");
  const loggedOut = qs("mypageLoggedOut");
  if(loggedIn && loggedOut){
    loggedIn.style.display = user ? "grid" : "none";
    loggedOut.style.display = user ? "none" : "grid";
  }
}

const PRODUCT_INFO = {
  VIP: { title:"🔥 VIP", price:"35,000원", desc:"전체 유료 정보 알림 제공", list:["김프/역프 전체 알림", "양방 후보", "입출금·고래·상장·DEX·BTC Wave"] },
  SEMI: { title:"🤖 VIP Lite (반자동)", price:"70,000원", desc:"VIP 전체 기능 + 승인형 진입 준비", list:["VIP 전체 기능", "텔레그램 BOT TOKEN 저장", "CHAT ID 저장", "향후 [진입] 버튼 연동"] },
  AUTO: { title:"🚀 VIP Pro (자동)", price:"100,000원", desc:"VIP 전체 기능 + 자동매매 연동 준비", list:["VIP 전체 기능", "텔레그램 BOT TOKEN 저장", "거래소 API 저장", "자동 진입/청산 연동 준비"] }
};
const PAY_INFO = {
  BANK: `<h4>국내 계좌</h4><p>관리자에게 계좌 안내를 받은 뒤 입금자명을 입력하세요.</p><small>확인 후 수동 승인됩니다.</small>`,
  USDT: `<h4>USDT 테더</h4><p>관리자에게 입금 주소를 받은 뒤 TxID를 입력하세요.</p><small>네트워크 오입금에 주의하세요.</small>`,
  CARD: `<h4>신용카드</h4><p>카드 결제는 준비중입니다.</p><small>현재는 국내 계좌 또는 USDT 등록을 이용해주세요.</small>`
};

function changeProductInfo(){
  const product = val("productSelect") || "VIP";
  const info = PRODUCT_INFO[product] || PRODUCT_INFO.VIP;
  const box = qs("productInfo");
  if(box){
    box.innerHTML = `<h4>${info.title}</h4><strong>${info.price}</strong><p>${info.desc}</p><ul>${info.list.map(x=>`<li>${x}</li>`).join("")}</ul>`;
  }
  syncPlanFields();
}
function changePayInfo(){
  const pay = val("payType") || "USDT";
  const box = qs("payInfo");
  if(box) box.innerHTML = PAY_INFO[pay] || PAY_INFO.USDT;
}

function collectPaymentExtra(product){
  return {
    tg_bot_token: val("payBotToken"),
    tg_chat_id: val("payChatId"),
    exchange: val("payExchange") || "MEXC",
    api_key: val("payApiKey"),
    api_secret: val("payApiSecret")
  };
}

async function submitVipRequest(){
  const user = await getCurrentUser();
  if(!user) return setMsg("vipRequestMsg", "❌ 로그인 후 등록 신청할 수 있습니다.");

  const product = val("productSelect") || "VIP";
  const payType = val("payType") || "USDT";
  const payName = val("payName");
  const memo = val("txidInput");
  const extra = collectPaymentExtra(product);

  if(!payName) return setMsg("vipRequestMsg", "❌ 입금자명 또는 보내는 사람 이름을 입력해주세요.");
  if(!memo) return setMsg("vipRequestMsg", "❌ TxID / 입금 메모 / 확인용 내용을 입력해주세요.");
  if(isBotPlan(product) && (!extra.tg_bot_token || !extra.tg_chat_id)) return setMsg("vipRequestMsg", "❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
  if(isAutoPlan(product) && (!extra.api_key || !extra.api_secret)) return setMsg("vipRequestMsg", "❌ 자동은 거래소 API KEY와 SECRET이 필요합니다.");

  const request = {
    id: "REQ-" + Date.now(),
    created_at: new Date().toISOString(),
    email: user.email,
    telegram: user.telegram || "미등록",
    product,
    payType,
    payName,
    memo,
    status:"PENDING",
    ...extra
  };

  const rows = getRequests();
  rows.unshift(request);
  saveRequests(rows);

  // 테스트/프론트 단독 모드에서는 신청 즉시 내 계정에 입력값을 반영해 확인 가능하게 처리
  const users = getLocalUsers();
  if(users[user.email]){
    users[user.email] = { ...users[user.email], plan: product, ...extra };
    saveLocalUsers(users);
  }
  setLocalUser({ ...user, plan: product, ...extra });
  updateAuthUI();

  setMsg("vipRequestMsg", "✅ 등록 신청 완료. 관리자 확인 후 승인됩니다.", "success");
}

document.addEventListener("DOMContentLoaded",()=>{
  loadLiveDashboard();
  setInterval(loadLiveDashboard,10000);
  updateAuthUI();
  changeProductInfo();
  changePayInfo();
  syncPlanFields();

  qs("signupPlan")?.addEventListener("change", syncPlanFields);
  qs("productSelect")?.addEventListener("change", changeProductInfo);
  qs("payType")?.addEventListener("change", changePayInfo);

  const page = document.body?.dataset?.page;
  if(page){
    document.querySelectorAll("[data-nav]").forEach(a=>{
      if(a.dataset.nav === page) a.classList.add("active");
    });
  }
});


/* =========================================================
   K-EDGE 관리자/승인 시스템 v1
   - 프론트 단독 테스트: localStorage 기반
   - 실제 운영: Supabase/서버 DB로 교체 권장
========================================================= */

const KEDGE_ADMIN_SESSION_KEY = "kedge_admin_logged_in";
const KEDGE_ADMIN_PIN_KEY = "kedge_admin_pin";
const KEDGE_DEFAULT_ADMIN_PIN = "0517";

/* 승인 후 고객에게 안내할 링크 */
const KEDGE_LINKS = {
  VIP: "https://t.me/listing0517",
  SEMI: "https://t.me/listing0517",
  AUTO: "https://t.me/listing0517"
};

function nowText(){
  try{
    return new Date().toLocaleString("ko-KR", { hour12:false });
  }catch(e){
    return new Date().toISOString();
  }
}

function productLabel(product){
  const map = {
    VIP: "VIP 👑",
    SEMI: "VIP Lite 반자동 🤖",
    AUTO: "VIP Pro 자동 🚀"
  };
  return map[product] || product || "-";
}

function statusLabel(status){
  const map = {
    PENDING: "승인대기",
    APPROVED: "승인완료",
    REJECTED: "거절"
  };
  return map[status] || status || "-";
}

function maskSecret(v){
  if(!v) return "미등록";
  const s = String(v);
  if(s.length <= 8) return "••••";
  return s.slice(0,4) + "••••" + s.slice(-4);
}

function telegramUrl(id){
  if(!id) return "https://t.me/listing0517";
  const clean = String(id).replace("@","").trim();
  if(!clean) return "https://t.me/listing0517";
  return "https://t.me/" + clean;
}

function getAdminPin(){
  return localStorage.getItem(KEDGE_ADMIN_PIN_KEY) || KEDGE_DEFAULT_ADMIN_PIN;
}

function isAdminLoggedIn(){
  return sessionStorage.getItem(KEDGE_ADMIN_SESSION_KEY) === "Y";
}

function adminLogin(){
  const pin = val("adminPin");
  const msg = qs("adminLoginMsg");
  if(pin === getAdminPin()){
    sessionStorage.setItem(KEDGE_ADMIN_SESSION_KEY, "Y");
    if(msg) msg.textContent = "✅ 관리자 로그인 완료";
    renderAdminPage();
    return;
  }
  if(msg) msg.textContent = "❌ 관리자 코드가 틀렸습니다.";
}

function adminLogout(){
  sessionStorage.removeItem(KEDGE_ADMIN_SESSION_KEY);
  renderAdminPage();
}

function adminChangePin(){
  const oldPin = val("oldAdminPin");
  const newPin = val("newAdminPin");
  const msg = qs("adminSettingMsg");
  if(oldPin !== getAdminPin()){
    if(msg) msg.textContent = "❌ 기존 관리자 코드가 틀렸습니다.";
    return;
  }
  if(!newPin || newPin.length < 4){
    if(msg) msg.textContent = "❌ 새 코드는 4자리 이상 입력하세요.";
    return;
  }
  localStorage.setItem(KEDGE_ADMIN_PIN_KEY, newPin);
  if(msg) msg.textContent = "✅ 관리자 코드 변경 완료";
}

function getRequestById(id){
  return getRequests().find(x => x.id === id);
}

function updateRequest(id, patch){
  const rows = getRequests();
  const idx = rows.findIndex(x => x.id === id);
  if(idx < 0) return null;
  rows[idx] = { ...rows[idx], ...patch };
  saveRequests(rows);
  return rows[idx];
}

/* 기존 submitVipRequest 덮어쓰기: 신청만 저장, 승인 전 plan 변경 없음 */
async function submitVipRequest(){
  const user = await getCurrentUser();
  if(!user) return setMsg("vipRequestMsg", "❌ 로그인 후 등록 신청할 수 있습니다.");

  const product = val("productSelect") || "VIP";
  const payType = val("payType") || "USDT";
  const payName = val("payName");
  const memo = val("txidInput");
  const extra = collectPaymentExtra(product);

  if(!payName) return setMsg("vipRequestMsg", "❌ 입금자명 또는 보내는 사람 이름을 입력해주세요.");
  if(!memo) return setMsg("vipRequestMsg", "❌ TxID / 입금 메모 / 확인용 내용을 입력해주세요.");
  if(isBotPlan(product) && (!extra.tg_bot_token || !extra.tg_chat_id)) return setMsg("vipRequestMsg", "❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
  if(isAutoPlan(product) && (!extra.api_key || !extra.api_secret)) return setMsg("vipRequestMsg", "❌ 자동은 거래소 API KEY와 SECRET이 필요합니다.");

  const request = {
    id: "REQ-" + Date.now(),
    created_at: new Date().toISOString(),
    created_text: nowText(),
    email: user.email,
    telegram: user.telegram || "미등록",
    current_plan: user.plan || "FREE",
    product,
    payType,
    payName,
    memo,
    status:"PENDING",
    approved_at:"",
    rejected_at:"",
    admin_note:"",
    ...extra
  };

  const rows = getRequests();
  rows.unshift(request);
  saveRequests(rows);

  setMsg("vipRequestMsg", "✅ 등록 신청 완료. 관리자 승인 후 이용 가능합니다.", "success");
  if(qs("payName")) qs("payName").value = "";
  if(qs("txidInput")) qs("txidInput").value = "";
}

/* 기존 updateAuthUI 덮어쓰기: 승인상태/연동정보 표시 보강 */
async function updateAuthUI(){
  const user = await getCurrentUser();
  const top = qs("topAuthArea");
  if(top){
    if(user){
      const plan = user.plan || "FREE";
      top.innerHTML = `
        <div class="user-mini">
          <span class="user-name">${user.email || "회원"}</span>
          <span class="plan-badge plan-${plan.toLowerCase()}">${planLabel(plan)}</span>
          <a class="login" href="./mypage.html">내정보</a>
          <button onclick="logoutUser()">로그아웃</button>
        </div>`;
    }else{
      top.innerHTML = `<a class="login" href="./login.html">로그인</a><a class="join" href="./join.html">회원가입</a>`;
    }
  }

  const status = qs("authStatus");
  if(status){
    status.innerHTML = user
      ? `<b>✅ 로그인 중</b><p>${user.email || "-"} / ${planLabel(user.plan || "FREE")}</p>`
      : `<b>로그인이 필요합니다.</b><p>회원 기능은 로그인 후 이용할 수 있습니다.</p>`;
  }

  const rows = getRequests();
  const myRows = user ? rows.filter(r => r.email === user.email) : [];
  const pending = myRows.find(r => r.status === "PENDING");
  const latest = myRows[0];

  if(qs("myEmail")) qs("myEmail").textContent = user?.email || "-";
  if(qs("myPlan")) qs("myPlan").textContent = planLabel(user?.plan || "FREE");
  if(qs("myTelegram")) qs("myTelegram").textContent = user?.telegram || "미등록";
  if(qs("myApproval")) qs("myApproval").textContent = pending ? "승인 대기중" : (latest ? statusLabel(latest.status) : "신청 없음");
  if(qs("myLastRequest")) qs("myLastRequest").textContent = latest ? `${productLabel(latest.product)} / ${statusLabel(latest.status)}` : "신청 내역 없음";
  if(qs("myInviteLink")){
    const link = user && user.plan && user.plan !== "FREE" ? (KEDGE_LINKS[user.plan] || KEDGE_LINKS.VIP) : "";
    qs("myInviteLink").innerHTML = link ? `<a href="${link}" target="_blank">텔레그램 입장/문의 링크</a>` : "승인 후 표시";
  }

  if(qs("myBotToken")) qs("myBotToken").textContent = maskValue(user?.tg_bot_token || "");
  if(qs("myChatId")) qs("myChatId").textContent = user?.tg_chat_id || "미등록";
  if(qs("myExchange")) qs("myExchange").textContent = user?.exchange || "미등록";
  if(qs("myApiKey")) qs("myApiKey").textContent = maskValue(user?.api_key || "");
  if(qs("myApiSecret")) qs("myApiSecret").textContent = maskValue(user?.api_secret || "");

  document.querySelectorAll("[data-my-bot]").forEach(el=> el.style.display = user && isBotPlan(user.plan) ? "block" : "none");
  document.querySelectorAll("[data-my-auto]").forEach(el=> el.style.display = user && isAutoPlan(user.plan) ? "block" : "none");

  const loggedIn = qs("mypageLoggedIn");
  const loggedOut = qs("mypageLoggedOut");
  if(loggedIn && loggedOut){
    loggedIn.style.display = user ? "grid" : "none";
    loggedOut.style.display = user ? "none" : "grid";
  }
}

function approveRequest(id){
  const req = getRequestById(id);
  if(!req) return alert("신청 내역을 찾을 수 없습니다.");

  const users = getLocalUsers();
  const oldUser = users[req.email] || { email:req.email, password:"", telegram:req.telegram || "미등록" };

  users[req.email] = {
    ...oldUser,
    email:req.email,
    telegram:req.telegram || oldUser.telegram || "미등록",
    plan:req.product,
    tg_bot_token:req.tg_bot_token || oldUser.tg_bot_token || "",
    tg_chat_id:req.tg_chat_id || oldUser.tg_chat_id || "",
    exchange:req.exchange || oldUser.exchange || "",
    api_key:req.api_key || oldUser.api_key || "",
    api_secret:req.api_secret || oldUser.api_secret || "",
    approved_at:new Date().toISOString(),
    status:"ACTIVE"
  };
  saveLocalUsers(users);

  updateRequest(id, {
    status:"APPROVED",
    approved_at:new Date().toISOString(),
    approved_text:nowText(),
    admin_note: val("adminNote-" + id)
  });

  const current = getLocalUser();
  if(current && current.email === req.email){
    setLocalUser({
      ...current,
      plan:req.product,
      tg_bot_token:req.tg_bot_token || "",
      tg_chat_id:req.tg_chat_id || "",
      exchange:req.exchange || "",
      api_key:req.api_key || "",
      api_secret:req.api_secret || ""
    });
  }

  renderAdminPage();
}

function rejectRequest(id){
  const req = getRequestById(id);
  if(!req) return alert("신청 내역을 찾을 수 없습니다.");

  updateRequest(id, {
    status:"REJECTED",
    rejected_at:new Date().toISOString(),
    rejected_text:nowText(),
    admin_note: val("adminNote-" + id)
  });

  renderAdminPage();
}

function deleteRequest(id){
  if(!confirm("이 신청 내역을 삭제할까요?")) return;
  saveRequests(getRequests().filter(x => x.id !== id));
  renderAdminPage();
}

function setUserPlan(email, plan){
  const users = getLocalUsers();
  if(!users[email]) return alert("회원 정보를 찾을 수 없습니다.");
  users[email].plan = plan;
  saveLocalUsers(users);

  const current = getLocalUser();
  if(current && current.email === email){
    setLocalUser({ ...current, plan });
  }
  renderAdminPage();
}

function suspendUser(email){
  if(!confirm(email + " 회원을 정지 처리할까요?")) return;
  const users = getLocalUsers();
  if(!users[email]) return alert("회원 정보를 찾을 수 없습니다.");
  users[email].plan = "FREE";
  users[email].status = "SUSPENDED";
  saveLocalUsers(users);
  renderAdminPage();
}

function copyText(text){
  if(navigator.clipboard){
    navigator.clipboard.writeText(text).then(()=>alert("복사 완료"));
  }else{
    prompt("복사하세요", text);
  }
}

function makeApprovalMessage(req){
  const link = KEDGE_LINKS[req.product] || KEDGE_LINKS.VIP;
  return `[K-EDGE 승인 완료]\n\n상품: ${productLabel(req.product)}\n텔레그램 링크: ${link}\n\n반자동/자동 회원은 입력하신 BOT/API 정보 기준으로 연동 준비됩니다.\n문의: @listing0517`;
}

function renderAdminStats(){
  const rows = getRequests();
  const users = Object.values(getLocalUsers());
  const pending = rows.filter(x=>x.status==="PENDING").length;
  const approved = rows.filter(x=>x.status==="APPROVED").length;
  const rejected = rows.filter(x=>x.status==="REJECTED").length;
  const vip = users.filter(x=>x.plan==="VIP").length;
  const semi = users.filter(x=>x.plan==="SEMI").length;
  const auto = users.filter(x=>x.plan==="AUTO").length;

  const box = qs("adminStats");
  if(!box) return;
  box.innerHTML = `
    <article><b>${pending}</b><span>승인 대기</span></article>
    <article><b>${approved}</b><span>승인 완료</span></article>
    <article><b>${rejected}</b><span>거절</span></article>
    <article><b>${vip}</b><span>VIP</span></article>
    <article><b>${semi}</b><span>반자동</span></article>
    <article><b>${auto}</b><span>자동</span></article>
  `;
}

function renderAdminRequests(){
  const wrap = qs("adminRequestList");
  if(!wrap) return;

  const status = val("adminStatusFilter") || "ALL";
  const keyword = val("adminSearch").toLowerCase();
  let rows = getRequests();

  if(status !== "ALL") rows = rows.filter(x => x.status === status);
  if(keyword){
    rows = rows.filter(x => JSON.stringify(x).toLowerCase().includes(keyword));
  }

  if(!rows.length){
    wrap.innerHTML = `<div class="admin-empty">신청 내역이 없습니다.</div>`;
    return;
  }

  wrap.innerHTML = rows.map(req => {
    const statusClass = (req.status || "PENDING").toLowerCase();
    const msg = makeApprovalMessage(req).replaceAll("`","").replaceAll("${","");

    return `
      <article class="admin-request-card status-${statusClass}">
        <div class="admin-card-top">
          <div>
            <b>${productLabel(req.product)}</b>
            <p>${req.email || "-"} · ${req.telegram || "미등록"}</p>
          </div>
          <span class="admin-status ${statusClass}">${statusLabel(req.status)}</span>
        </div>

        <div class="admin-detail-grid">
          <p><small>신청시간</small><strong>${req.created_text || req.created_at || "-"}</strong></p>
          <p><small>결제방식</small><strong>${req.payType || "-"}</strong></p>
          <p><small>입금자명</small><strong>${req.payName || "-"}</strong></p>
          <p><small>TxID/메모</small><strong>${req.memo || "-"}</strong></p>
          <p><small>BOT TOKEN</small><strong>${maskSecret(req.tg_bot_token)}</strong></p>
          <p><small>CHAT ID</small><strong>${req.tg_chat_id || "미등록"}</strong></p>
          <p><small>거래소</small><strong>${req.exchange || "미등록"}</strong></p>
          <p><small>API KEY</small><strong>${maskSecret(req.api_key)}</strong></p>
          <p><small>SECRET</small><strong>${maskSecret(req.api_secret)}</strong></p>
        </div>

        <textarea id="adminNote-${req.id}" class="admin-note" placeholder="관리자 메모">${req.admin_note || ""}</textarea>

        <div class="admin-actions">
          <button class="ok" onclick="approveRequest('${req.id}')">승인</button>
          <button class="danger" onclick="rejectRequest('${req.id}')">거절</button>
          <a class="admin-link" href="${telegramUrl(req.telegram)}" target="_blank">텔레그램 열기</a>
          <button onclick="copyText(\`${msg}\`)">승인문구 복사</button>
          <button class="ghost-admin" onclick="deleteRequest('${req.id}')">삭제</button>
        </div>
      </article>
    `;
  }).join("");
}

function renderAdminUsers(){
  const wrap = qs("adminUserList");
  if(!wrap) return;

  const users = Object.values(getLocalUsers());
  const keyword = val("adminUserSearch").toLowerCase();
  let rows = users;
  if(keyword) rows = rows.filter(x => JSON.stringify(x).toLowerCase().includes(keyword));

  if(!rows.length){
    wrap.innerHTML = `<div class="admin-empty">회원 정보가 없습니다.</div>`;
    return;
  }

  wrap.innerHTML = rows.map(u => `
    <article class="admin-user-row">
      <div>
        <b>${u.email || "-"}</b>
        <p>${u.telegram || "미등록"} · ${planLabel(u.plan || "FREE")} · ${u.status || "NORMAL"}</p>
      </div>
      <select data-user-plan="${u.email}">
        <option value="FREE" ${u.plan==="FREE"?"selected":""}>FREE</option>
        <option value="VIP" ${u.plan==="VIP"?"selected":""}>VIP</option>
        <option value="SEMI" ${u.plan==="SEMI"?"selected":""}>반자동</option>
        <option value="AUTO" ${u.plan==="AUTO"?"selected":""}>자동</option>
      </select>
      <button onclick="setUserPlan('${u.email}', this.parentElement.querySelector('[data-user-plan]').value)">등급변경</button>
      <button class="danger" onclick="suspendUser('${u.email}')">정지</button>
    </article>
  `).join("");
}

function exportAdminData(){
  const data = {
    exported_at:new Date().toISOString(),
    users:getLocalUsers(),
    requests:getRequests()
  };
  const blob = new Blob([JSON.stringify(data,null,2)], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "k-edge-admin-backup.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function renderAdminPage(){
  const loginBox = qs("adminLoginBox");
  const app = qs("adminApp");
  if(!loginBox || !app) return;

  if(!isAdminLoggedIn()){
    loginBox.style.display = "block";
    app.style.display = "none";
    return;
  }

  loginBox.style.display = "none";
  app.style.display = "block";
  renderAdminStats();
  renderAdminRequests();
  renderAdminUsers();
}

document.addEventListener("DOMContentLoaded",()=>{
  renderAdminPage();

  qs("adminStatusFilter")?.addEventListener("change", renderAdminRequests);
  qs("adminSearch")?.addEventListener("input", renderAdminRequests);
  qs("adminUserSearch")?.addEventListener("input", renderAdminUsers);
});
