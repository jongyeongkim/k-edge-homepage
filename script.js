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


/* =========================
   K-EDGE 운영자 로그인 최종 패치
   admin.html의 onclick="loginAdmin()" 대응
========================= */

const KEDGE_ADMIN_CODE_FINAL = "0517";

function kedgeOpenAdminPanel(){
  const loginBox = document.getElementById("adminLoginBox");
  const adminApp =
    document.getElementById("adminApp") ||
    document.getElementById("adminPanel");

  if(loginBox) loginBox.style.display = "none";
  if(adminApp) adminApp.style.display = "block";

  if(typeof renderAdminDashboard === "function"){
    renderAdminDashboard();
  }
}

function loginAdmin(){
  const input =
    document.getElementById("adminPin") ||
    document.getElementById("adminCode") ||
    document.getElementById("adminPassword");

  const code = String(input?.value || "").replace(/\s/g, "");
  const savedCode = localStorage.getItem("kedge_admin_pin") || KEDGE_ADMIN_CODE_FINAL;

  if(code !== savedCode){
    const msg = document.getElementById("adminLoginMsg");
    if(msg) msg.textContent = "❌ 관리자 코드가 틀렸습니다.";
    return;
  }

  sessionStorage.setItem("kedge_admin_ok", "1");
  kedgeOpenAdminPanel();
}

function adminLogin(){
  loginAdmin();
}

function checkAdminPin(){
  loginAdmin();
}

function adminLogout(){
  sessionStorage.removeItem("kedge_admin_ok");
  location.reload();
}

document.addEventListener("DOMContentLoaded", function(){
  const input =
    document.getElementById("adminPin") ||
    document.getElementById("adminCode") ||
    document.getElementById("adminPassword");

  if(input){
    input.addEventListener("keydown", function(e){
      if(e.key === "Enter") loginAdmin();
    });
  }

  if(sessionStorage.getItem("kedge_admin_ok") === "1"){
    kedgeOpenAdminPanel();
  }
});
