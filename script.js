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

async function resolveApprovedPlan(user){
  if(!user || !user.email) return user?.plan || "FREE";

  // 1) Supabase 승인 신청 우선 확인
  if(kedgeSupabase){
    try{
      const { data, error } = await kedgeSupabase
        .from("kedge_requests")
        .select("product,status,created_at")
        .eq("email", user.email)
        .eq("status", "APPROVED")
        .order("created_at", { ascending:false })
        .limit(1);

      if(!error && Array.isArray(data) && data.length){
        return data[0].product || user.plan || "FREE";
      }
    }catch(e){
      console.log("approved plan supabase skipped", e);
    }
  }

  // 2) 프론트 단독/localStorage 승인 신청 확인
  try{
    const rows = getRequests() || [];
    const mine = rows
      .filter(x => x && x.email === user.email && x.status === "APPROVED")
      .sort((a,b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));

    if(mine.length){
      return mine[0].product || user.plan || "FREE";
    }
  }catch(e){
    console.log("approved plan local skipped", e);
  }

  return user.plan || "FREE";
}


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
  const productSelect = qs("productSelect");
  const signupPlan = qs("signupPlan");

  const plan = productSelect
    ? val("productSelect")
    : (signupPlan ? val("signupPlan") : "FREE");

  const isBot = plan === "SEMI" || plan === "AUTO";
  const isAuto = plan === "AUTO";

  document.querySelectorAll("[data-plan-field='bot']")
    .forEach(el=> el.style.display = isBot ? "block" : "none");

  document.querySelectorAll("[data-plan-field='auto']")
    .forEach(el=> el.style.display = isAuto ? "block" : "none");

  document.querySelectorAll("[data-product-field='bot']")
    .forEach(el=> el.style.display = isBot ? "block" : "none");

  document.querySelectorAll("[data-product-field='auto']")
    .forEach(el=> el.style.display = isAuto ? "block" : "none");

  document.querySelectorAll("[data-product-field='api']")
    .forEach(el=> el.style.display = isBot ? "block" : "none");
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
  const approvedPlan = user ? await resolveApprovedPlan(user) : "FREE";
  const displayUser = user ? { ...user, plan: approvedPlan } : null;

  const top = qs("topAuthArea");
  if(top){
    if(displayUser){
      const plan = displayUser.plan || "FREE";
      top.innerHTML = `
        <div class="user-mini">
          <span class="user-name">${displayUser.email || "회원"}</span>
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
    status.innerHTML = displayUser
      ? `<b>✅ 로그인 중</b><p>${displayUser.email || "-"} / ${planLabel(displayUser.plan || "FREE")}</p>`
      : `<b>로그인이 필요합니다.</b><p>회원 기능은 로그인 후 이용할 수 있습니다.</p>`;
  }

  if(qs("myEmail")) qs("myEmail").textContent = displayUser?.email || "-";
  if(qs("myPlan")) qs("myPlan").textContent = planLabel(displayUser?.plan || "FREE");
  if(qs("myTelegram")) qs("myTelegram").textContent = displayUser?.telegram || "미등록";
  if(qs("myBotToken")) qs("myBotToken").textContent = maskValue(displayUser?.tg_bot_token || "");
  if(qs("myChatId")) qs("myChatId").textContent = displayUser?.tg_chat_id || "미등록";
  if(qs("myExchange")) qs("myExchange").textContent = displayUser?.exchange || "미등록";
  if(qs("myApiKey")) qs("myApiKey").textContent = maskValue(displayUser?.api_key || "");
  if(qs("myApiSecret")) qs("myApiSecret").textContent = maskValue(displayUser?.api_secret || "");

  document.querySelectorAll("[data-my-bot]").forEach(el=> el.style.display = displayUser && isBotPlan(displayUser.plan) ? "block" : "none");
  document.querySelectorAll("[data-my-auto]").forEach(el=> el.style.display = displayUser && isAutoPlan(displayUser.plan) ? "block" : "none");

  const loggedIn = qs("mypageLoggedIn");
  const loggedOut = qs("mypageLoggedOut");
  if(loggedIn && loggedOut){
    loggedIn.style.display = displayUser ? "grid" : "none";
    loggedOut.style.display = displayUser ? "none" : "grid";
  }
}

const PRODUCT_INFO = {
  VIP: { title:"🔥 VIP", price:"35,000원", desc:"전체 유료 정보 알림 제공", list:["김프/역프 전체 알림", "양방 후보", "입출금·고래·상장·DEX·BTC Wave"] },
  SEMI: { title:"🤖 VIP Lite (반자동)", price:"70,000원", desc:"VIP 전체 기능 + 승인형 진입 준비", list:["VIP 전체 기능", "텔레그램 BOT TOKEN 저장", "CHAT ID 저장", "국내/해외 API 개별 저장", "향후 [진입] 버튼 연동"] },
  AUTO: { title:"🚀 VIP Pro (자동)", price:"100,000원", desc:"VIP 전체 기능 + 자동매매 연동 준비", list:["VIP 전체 기능", "텔레그램 BOT TOKEN 저장", "국내/해외 API 개별 저장", "자동 진입/청산 연동 준비"] }
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
  const domestic_apis = {
    upbit:{
      enabled: !!qs("payUpbitUse")?.checked,
      api_key: val("payUpbitApiKey"),
      api_secret: val("payUpbitApiSecret")
    },
    bithumb:{
      enabled: !!qs("payBithumbUse")?.checked,
      api_key: val("payBithumbApiKey"),
      api_secret: val("payBithumbApiSecret")
    }
  };

  const foreign_apis = {
    mexc:{
      enabled: !!qs("payMexcUse")?.checked,
      api_key: val("payMexcApiKey"),
      api_secret: val("payMexcApiSecret")
    },
    gate:{
      enabled: !!qs("payGateUse")?.checked,
      api_key: val("payGateApiKey"),
      api_secret: val("payGateApiSecret")
    },
    bitget:{
      enabled: !!qs("payBitgetUse")?.checked,
      api_key: val("payBitgetApiKey"),
      api_secret: val("payBitgetApiSecret")
    },
    bingx:{
      enabled: !!qs("payBingxUse")?.checked,
      api_key: val("payBingxApiKey"),
      api_secret: val("payBingxApiSecret")
    }
  };

  return {
    tg_bot_token: val("payBotToken"),
    tg_chat_id: val("payChatId"),
    domestic_apis,
    foreign_apis
  };
}

function enabledApiList(apiObj){
  return Object.entries(apiObj || {}).filter(([_, v]) => v && v.enabled);
}

function hasValidEnabledApi(apiObj){
  return enabledApiList(apiObj).some(([_, v]) => v.api_key && v.api_secret);
}

function hasInvalidEnabledApi(apiObj){
  return enabledApiList(apiObj).some(([_, v]) => !v.api_key || !v.api_secret);
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
  if(isBotPlan(product)){
    if(!hasValidEnabledApi(extra.domestic_apis)) return setMsg("vipRequestMsg", "❌ 국내 거래소 API를 1개 이상 입력해주세요.");
    if(!hasValidEnabledApi(extra.foreign_apis)) return setMsg("vipRequestMsg", "❌ 해외 거래소 API를 1개 이상 입력해주세요.");
    if(hasInvalidEnabledApi(extra.domestic_apis)) return setMsg("vipRequestMsg", "❌ 체크된 국내 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
    if(hasInvalidEnabledApi(extra.foreign_apis)) return setMsg("vipRequestMsg", "❌ 체크된 해외 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
  }

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
  if(isBotPlan(product)){
    if(!hasValidEnabledApi(extra.domestic_apis)) return setMsg("vipRequestMsg", "❌ 국내 거래소 API를 1개 이상 입력해주세요.");
    if(!hasValidEnabledApi(extra.foreign_apis)) return setMsg("vipRequestMsg", "❌ 해외 거래소 API를 1개 이상 입력해주세요.");
    if(hasInvalidEnabledApi(extra.domestic_apis)) return setMsg("vipRequestMsg", "❌ 체크된 국내 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
    if(hasInvalidEnabledApi(extra.foreign_apis)) return setMsg("vipRequestMsg", "❌ 체크된 해외 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
  }

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

/* =========================================================
   K-EDGE AUTO SETTINGS SIMPLE OVERRIDE
   - 유저 설정: 운용방식 / 빗썸 총 운용금액 / 분할 수 / 자동매매 ON-OFF
   - 시스템 고정: 실제엣지 +1.5%, 익절 +0.3%, 손절/필터/청산 내부 기준
========================================================= */
(function(){
  const SIMPLE_DEFAULT = {
    alert_enabled: "ON",
    auto_entry_enabled: "OFF",
    auto_exit_enabled: "ON",
    capital_mode: "fixed",
    capital_krw: 2000000,
    split_count: 20,
    min_edge_percent: 1.5,
    take_profit_percent: 0.3,
    stop_loss_percent: 8,
    reentry_enabled: "OFF",
    use_bithumb: true,
    use_mexc: true,
    use_gate: true,
    use_bitget: true,
    use_bingx: true
  };

  function q(id){ return document.getElementById(id); }
  function getNum(id, fallback){
    const n = Number(q(id)?.value);
    return Number.isFinite(n) ? n : fallback;
  }
  function db(){
    if(!window.supabase) return null;
    return window.supabase.createClient(
      window.KEDGE_SUPABASE_URL || "https://qakhbihueonefzifrmct.supabase.co",
      window.KEDGE_SUPABASE_ANON_KEY || "sb_publishable_XboBFueAITcieSL75B2S5g_qlm4XmOm"
    );
  }
  function msg(text, type){
    const el = q("autoSettingMsg");
    if(!el) return alert(text);
    el.textContent = text;
    el.className = "form-msg " + (type || "error");
  }

  window.calcAutoEntryAmount = function(){
    const capital = getNum("autoCapitalKrw", SIMPLE_DEFAULT.capital_krw);
    const split = Math.max(1, getNum("autoSplitCount", SIMPLE_DEFAULT.split_count));
    const entry = Math.floor(capital / split);
    if(q("autoEntryAmountText")) q("autoEntryAmountText").textContent = entry.toLocaleString("ko-KR") + "원";
  };

  async function getApproved(user){
    const client = db();
    if(!client || !user?.email) return null;
    const { data, error } = await client
      .from("kedge_requests")
      .select("*")
      .eq("email", user.email)
      .eq("status", "APPROVED")
      .order("created_at", { ascending:false })
      .limit(1);
    if(error || !data || !data.length) return null;
    return data[0];
  }

  async function getSaved(user){
    const client = db();
    if(!client || !user?.email) return null;
    const { data, error } = await client
      .from("auto_settings")
      .select("*")
      .eq("email", user.email)
      .limit(1);
    if(error || !data || !data.length) return null;
    return data[0];
  }

  function applySettings(saved){
    const s = {...SIMPLE_DEFAULT, ...(saved || {})};
    const mode = document.querySelector(`input[name="capitalMode"][value="${s.capital_mode || "fixed"}"]`);
    if(mode) mode.checked = true;
    if(q("autoCapitalKrw")) q("autoCapitalKrw").value = s.capital_krw;
    if(q("autoSplitCount")) q("autoSplitCount").value = s.split_count;
    if(q("autoEntryEnabled")) q("autoEntryEnabled").value = s.auto_entry_enabled || "OFF";
    window.calcAutoEntryAmount();
  }

  function collect(user){
    const mode = document.querySelector('input[name="capitalMode"]:checked')?.value || "fixed";
    return {
      email: user.email,

      alert_enabled: "ON",
      auto_entry_enabled: q("autoEntryEnabled")?.value || "OFF",
      auto_exit_enabled: "ON",

      capital_mode: mode,
      capital_krw: getNum("autoCapitalKrw", SIMPLE_DEFAULT.capital_krw),
      split_count: Math.max(1, getNum("autoSplitCount", SIMPLE_DEFAULT.split_count)),

      max_positions: 0,
      max_daily_entries: 0,

      min_edge_percent: 1.5,
      take_profit_percent: 0.3,
      stop_loss_percent: 8,

      reentry_enabled: "OFF",

      use_bithumb: true,
      use_mexc: true,
      use_gate: true,
      use_bitget: true,
      use_bingx: true,

      updated_at: new Date().toISOString()
    };
  }

  window.initAutoSettingsPage = async function(){
    if(document.body?.dataset?.page !== "auto") return;

    const user = await (window.getCurrentUser ? window.getCurrentUser() : null);
    if(!user){
      if(q("autoSettingStatus")) q("autoSettingStatus").innerHTML = "<b>로그인이 필요합니다.</b><p>AUTO 설정은 로그인 후 이용할 수 있습니다.</p>";
      if(q("autoSettingLocked")) q("autoSettingLocked").style.display = "block";
      if(q("autoSettingForm")) q("autoSettingForm").style.display = "none";
      return;
    }

    const approved = await getApproved(user);
    if(!approved){
      if(q("autoSettingStatus")) q("autoSettingStatus").innerHTML = "<b>🔒 관리자 승인 필요</b><p>승인 완료 후 AUTO 설정을 저장할 수 있습니다.</p>";
      if(q("autoSettingLocked")) q("autoSettingLocked").style.display = "block";
      if(q("autoSettingForm")) q("autoSettingForm").style.display = "none";
      return;
    }

    if(q("autoSettingStatus")) q("autoSettingStatus").innerHTML = "<b>✅ K-EDGE AUTO 승인 완료</b><p>알람 수신은 ON 상태입니다. 자동매매 시작 전 빗썸 총자산 기준 운용금액과 분할 수를 설정해주세요.</p>";
    if(q("autoSettingLocked")) q("autoSettingLocked").style.display = "none";
    if(q("autoSettingForm")) q("autoSettingForm").style.display = "block";

    applySettings(await getSaved(user));
  };

  window.saveAutoSettings = async function(){
    const client = db();
    if(!client) return msg("❌ Supabase 연결 실패");

    const user = await (window.getCurrentUser ? window.getCurrentUser() : null);
    if(!user) return msg("❌ 로그인 후 저장할 수 있습니다.");

    const approved = await getApproved(user);
    if(!approved) return msg("❌ 관리자 승인 후 AUTO 설정을 저장할 수 있습니다.");

    const payload = collect(user);
    const { error } = await client
      .from("auto_settings")
      .upsert(payload, { onConflict:"email" });

    if(error){
      console.error(error);
      return msg("❌ 설정 저장 실패: " + error.message);
    }

    msg("✅ AUTO 설정 저장 완료. 빗썸 총자산 기준 운용금액과 분할 수가 반영됩니다.", "success");
    if(window.updateAuthUI) window.updateAuthUI();
  };

  document.addEventListener("DOMContentLoaded", function(){
    if(document.body?.dataset?.page === "auto"){
      setTimeout(function(){
        window.initAutoSettingsPage();
        window.calcAutoEntryAmount();
      }, 80);
    }
  });
})();
