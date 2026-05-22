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
        live.innerHTML=`<div class="live-head"><span>실시간 매매 기회</span><b>+${edgeNum.toFixed(2)}%</b></div>
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
   K-EDGE 회원/로그인 UX
   - Supabase 설정이 있으면 Supabase 사용
   - 설정이 없거나 실패하면 브라우저 저장 방식으로 테스트 가능
========================= */

const KEDGE_AUTH_KEY = "kedge_local_user";
const KEDGE_USERS_KEY = "kedge_local_users";

/*
  Supabase를 실제로 쓸 경우 아래 2개만 채우면 됩니다.
  예)
  const SUPABASE_URL = "https://xxxx.supabase.co";
  const SUPABASE_ANON_KEY = "ey....";
*/
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

function setMsg(id, text, type="error"){
  const el = qs(id);
  if(!el) return;
  el.textContent = text;
  el.className = "auth-msg " + type;
}

function getLocalUsers(){
  try { return JSON.parse(localStorage.getItem(KEDGE_USERS_KEY) || "{}"); }
  catch(e){ return {}; }
}

function saveLocalUsers(users){
  localStorage.setItem(KEDGE_USERS_KEY, JSON.stringify(users));
}

function getLocalUser(){
  try { return JSON.parse(localStorage.getItem(KEDGE_AUTH_KEY) || "null"); }
  catch(e){ return null; }
}

function setLocalUser(user){
  localStorage.setItem(KEDGE_AUTH_KEY, JSON.stringify(user));
}

function clearLocalUser(){
  localStorage.removeItem(KEDGE_AUTH_KEY);
}

function friendlyAuthError(err){
  const msg = String((err && err.message) || err || "").toLowerCase();

  if(msg.includes("invalid login") || msg.includes("invalid credentials")) {
    return "❌ 이메일 또는 비밀번호가 틀렸습니다.";
  }
  if(msg.includes("email not confirmed")) {
    return "❌ 이메일 인증이 필요합니다. 메일함을 확인해주세요.";
  }
  if(msg.includes("user already registered") || msg.includes("already")) {
    return "❌ 이미 가입된 이메일입니다. 로그인해주세요.";
  }
  if(msg.includes("password")) {
    return "❌ 비밀번호 형식이 올바르지 않습니다.";
  }
  if(msg.includes("email")) {
    return "❌ 이메일 형식이 올바르지 않습니다.";
  }
  return "❌ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

async function signupUser(){
  const email = (qs("signupEmail")?.value || "").trim();
  const password = qs("signupPassword")?.value || "";
  const confirm = qs("signupPasswordConfirm")?.value || "";
  const telegram = (qs("signupTelegram")?.value || "").trim();

  if(!email) return setMsg("signupMsg", "❌ 이메일을 입력해주세요.");
  if(!email.includes("@")) return setMsg("signupMsg", "❌ 이메일 형식이 올바르지 않습니다.");
  if(!password) return setMsg("signupMsg", "❌ 비밀번호를 입력해주세요.");
  if(password.length < 6) return setMsg("signupMsg", "❌ 비밀번호는 6자리 이상으로 입력해주세요.");
  if(password !== confirm) return setMsg("signupMsg", "❌ 비밀번호가 일치하지 않습니다.");

  if(kedgeSupabase){
    try{
      const { data, error } = await kedgeSupabase.auth.signUp({
        email,
        password,
        options: { data: { telegram, plan: "FREE" } }
      });
      if(error) return setMsg("signupMsg", friendlyAuthError(error));
      setMsg("signupMsg", "✅ 회원가입 완료. 로그인 페이지로 이동합니다.", "success");
      setTimeout(()=> location.href="./login.html", 900);
      return;
    }catch(e){
      setMsg("signupMsg", friendlyAuthError(e));
      return;
    }
  }

  const users = getLocalUsers();
  if(users[email]) return setMsg("signupMsg", "❌ 이미 가입된 이메일입니다. 로그인해주세요.");

  users[email] = { email, password, telegram: telegram || "미등록", plan: "FREE" };
  saveLocalUsers(users);

  setMsg("signupMsg", "✅ 회원가입 완료. 로그인 페이지로 이동합니다.", "success");
  setTimeout(()=> location.href="./login.html", 900);
}

async function loginUser(){
  const email = (qs("loginEmail")?.value || "").trim();
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
        plan: meta.plan || "FREE"
      });

      setMsg("loginMsg", "✅ 로그인 완료. 메인으로 이동합니다.", "success");
      updateAuthUI();
      setTimeout(()=> location.href="./index.html", 800);
      return;
    }catch(e){
      setMsg("loginMsg", friendlyAuthError(e));
      return;
    }
  }

  const users = getLocalUsers();
  if(!users[email]) return setMsg("loginMsg", "❌ 존재하지 않는 계정입니다. 회원가입을 먼저 해주세요.");
  if(users[email].password !== password) return setMsg("loginMsg", "❌ 비밀번호가 틀렸습니다.");

  setLocalUser({
    email: users[email].email,
    telegram: users[email].telegram || "미등록",
    plan: users[email].plan || "FREE"
  });

  setMsg("loginMsg", "✅ 로그인 완료. 메인으로 이동합니다.", "success");
  updateAuthUI();
  setTimeout(()=> location.href="./index.html", 800);
}

async function resetPassword(){
  const email = (qs("loginEmail")?.value || "").trim();

  if(!email) return setMsg("loginMsg", "❌ 비밀번호 찾기를 하려면 이메일을 먼저 입력해주세요.");

  if(kedgeSupabase){
    try{
      const { error } = await kedgeSupabase.auth.resetPasswordForEmail(email, {
        redirectTo: location.origin + "/login.html"
      });
      if(error) return setMsg("loginMsg", friendlyAuthError(error));
      setMsg("loginMsg", "✅ 비밀번호 재설정 메일을 보냈습니다.", "success");
      return;
    }catch(e){
      setMsg("loginMsg", friendlyAuthError(e));
      return;
    }
  }

  const users = getLocalUsers();
  if(!users[email]) return setMsg("loginMsg", "❌ 존재하지 않는 이메일입니다.");
  setMsg("loginMsg", "✅ 테스트 모드: 가입된 이메일입니다. 실제 메일 발송은 Supabase 연결 후 가능합니다.", "success");
}

async function logoutUser(){
  try{
    if(kedgeSupabase) await kedgeSupabase.auth.signOut();
  }catch(e){}
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
          plan: meta.plan || "FREE"
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
          <span class="plan-badge">${plan}</span>
          <a class="login" href="./mypage.html">내정보</a>
          <button onclick="logoutUser()">로그아웃</button>
        </div>
      `;
    }else{
      top.innerHTML = `
        <a class="login" href="./login.html">로그인</a>
        <a class="join" href="./join.html">회원가입</a>
      `;
    }
  }

  const status = qs("authStatus");
  if(status){
    if(user){
      status.innerHTML = `<b>✅ 로그인 중</b><p>${user.email || "-"} / ${user.plan || "FREE"}</p>`;
    }else{
      status.innerHTML = `<b>로그인이 필요합니다.</b><p>회원 기능은 로그인 후 이용할 수 있습니다.</p>`;
    }
  }

  if(qs("myEmail")) qs("myEmail").textContent = user?.email || "-";
  if(qs("myPlan")) qs("myPlan").textContent = user?.plan || "FREE";
  if(qs("myTelegram")) qs("myTelegram").textContent = user?.telegram || "미등록";

  const loggedIn = qs("mypageLoggedIn");
  const loggedOut = qs("mypageLoggedOut");
  if(loggedIn && loggedOut){
    loggedIn.style.display = user ? "grid" : "none";
    loggedOut.style.display = user ? "none" : "grid";
  }
}

document.addEventListener("DOMContentLoaded",()=>{
  loadLiveDashboard();
  setInterval(loadLiveDashboard,10000);
  updateAuthUI();

  const page = document.body?.dataset?.page;
  if(page){
    document.querySelectorAll("[data-nav]").forEach(a=>{
      if(a.dataset.nav === page) a.classList.add("active");
    });
  }
});
