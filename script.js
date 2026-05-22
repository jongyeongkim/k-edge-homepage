
const SUPABASE_URL = "https://ilkkwbnxxzkmqhdoscep.supabase.co";
const SUPABASE_KEY = "sb_publishable_Fegb-Q-M98BReiYp1LV9sQ_7CW7e8T_";
const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

const stat = document.querySelector('.stats b');
setInterval(() => {
  if (!stat) return;
  stat.textContent = (20 + Math.floor(Math.random() * 9)) + '건';
}, 3000);

document.querySelectorAll('.copy-text').forEach((el) => {
  el.title = '클릭하면 복사됩니다';
  el.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(el.textContent.trim());
      const old = el.textContent;
      el.textContent = '복사 완료!';
      setTimeout(() => (el.textContent = old), 900);
    } catch(e) {}
  });
});

function setMsg(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
}

async function signupUser() {
  const email = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value.trim();
  const telegram = document.getElementById('signupTelegram').value.trim();

  if (!email || !password) {
    setMsg('signupMsg', '이메일과 비밀번호를 입력하세요.');
    return;
  }

  const { data, error } = await supabaseClient.auth.signUp({
    email,
    password,
    options: {
      data: {
        telegram_id: telegram || '',
        plan: 'FREE'
      }
    }
  });

  if (error) {
    setMsg('signupMsg', '가입 실패: ' + error.message);
    return;
  }

  localStorage.setItem('kedge_telegram', telegram || '');
  setMsg('signupMsg', '가입 완료. 이메일 인증이 켜져 있으면 메일 확인 후 로그인하세요.');
  await checkUser();
}

async function loginUser() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value.trim();

  if (!email || !password) {
    setMsg('loginMsg', '이메일과 비밀번호를 입력하세요.');
    return;
  }

  const { data, error } = await supabaseClient.auth.signInWithPassword({
    email,
    password
  });

  if (error) {
    setMsg('loginMsg', '로그인 실패: ' + error.message);
    return;
  }

  setMsg('loginMsg', '로그인 성공');
  await checkUser();
}

async function logoutUser() {
  await supabaseClient.auth.signOut();
  localStorage.removeItem('kedge_telegram');
  await checkUser();
}


function planLabel(plan) {
  plan = String(plan || "FREE").toUpperCase();
  const map = { FREE:"FREE", VIP:"VIP", SEMI:"VIP Lite", AUTO:"VIP Pro" };
  return map[plan] || plan;
}
function statusLabel(status) {
  status = String(status || "PENDING").toUpperCase();
  if (status === "APPROVED") return "승인완료";
  if (status === "REJECTED") return "거절";
  return "승인 확인중";
}
function formatDate(v) {
  if (!v) return "-";
  try { return new Date(v).toLocaleString("ko-KR"); } catch(e) { return v; }
}
function maskValue(v) {
  v = String(v || "");
  if (!v) return "미등록";
  if (v.length <= 8) return "••••";
  return v.slice(0,4) + "••••" + v.slice(-4);
}
function showEl(id, show) {
  const el = document.getElementById(id);
  if (el) el.style.display = show ? "" : "none";
}
function renderTopAuth(user) {
  const area = document.getElementById("topAuthArea");
  if (!area) return;
  if (!user) {
    area.innerHTML = '<a class="login" href="./login.html">로그인</a><a class="join" href="./join.html">회원가입</a>';
  } else {
    area.innerHTML = '<a class="login" href="./mypage.html">내정보</a><a class="join" href="javascript:logoutUser()">로그아웃</a>';
  }
}
async function safeLatestRequest(email) {
  try {
    const { data, error } = await supabaseClient
      .from("kedge_requests")
      .select("*")
      .eq("email", email)
      .order("created_at", { ascending:false })
      .limit(1);
    if (error) return null;
    return Array.isArray(data) && data.length ? data[0] : null;
  } catch(e) { return null; }
}
async function safeUserRow(email) {
  try {
    const { data, error } = await supabaseClient
      .from("kedge_users")
      .select("*")
      .eq("email", email)
      .limit(1);
    if (error) return null;
    return Array.isArray(data) && data.length ? data[0] : null;
  } catch(e) { return null; }
}

async function checkUser() {
  const status = document.getElementById('authStatus');
  const emailEl = document.getElementById('myEmail');
  const planEl = document.getElementById('myPlan');
  const telEl = document.getElementById('myTelegram');
  const approvalEl = document.getElementById('myApproval');
  const lastReqEl = document.getElementById('myLastRequest');
  const inviteEl = document.getElementById('myInviteLink');
  const isMypage = document.body && document.body.dataset.page === "mypage";

  const { data } = await supabaseClient.auth.getUser();
  const user = data?.user;

  renderTopAuth(user);

  if (!user) {
    if (status) {
      status.className = 'auth-status warn';
      status.innerHTML = '<b>로그인 전</b> — 회원가입 또는 로그인을 진행하세요.';
    }
    if (isMypage) {
      showEl("mypageLoggedOut", true);
      showEl("mypageLoggedIn", false);
    }
    if (emailEl) emailEl.textContent = '-';
    if (planEl) planEl.textContent = 'FREE';
    if (telEl) telEl.textContent = '미등록';
    if (approvalEl) approvalEl.textContent = '확인중';
    if (lastReqEl) lastReqEl.textContent = '신청 내역 없음';
    if (inviteEl) inviteEl.textContent = '승인 후 표시';
    return;
  }

  const meta = user.user_metadata || {};
  const email = user.email || "";
  const telegramMeta = meta.telegram_id || localStorage.getItem('kedge_telegram') || '미등록';

  if (!isMypage) {
    if (status) {
      status.className = 'auth-status ok';
      status.innerHTML = '<b>로그인 완료</b> — K-EDGE 회원으로 연결되었습니다.';
    }
    if (emailEl) emailEl.textContent = email || '-';
    if (planEl) planEl.textContent = meta.plan || 'FREE';
    if (telEl) telEl.textContent = telegramMeta;
    return;
  }

  showEl("mypageLoggedOut", false);
  showEl("mypageLoggedIn", true);

  const request = await safeLatestRequest(email);
  const userRow = await safeUserRow(email);
  const requestStatus = String(request?.status || "").toUpperCase();
  const requestEnabled = request?.service_enabled === true;
  const userApproved = userRow?.approved === true;
  const requestApproved = requestStatus === "APPROVED" && requestEnabled;
  const approved = userApproved || requestApproved;
  const requestPlan = String(request?.product || "").toUpperCase();
  const userPlan = String(userRow?.plan || "").toUpperCase();
  const activePlan = approved ? (userPlan || requestPlan || "FREE") : "FREE";
  const pendingPlan = requestPlan && !approved && requestStatus !== "REJECTED" ? requestPlan : "";
  const telegram = request?.telegram || userRow?.telegram || telegramMeta;

  if (status) {
    if (approved) {
      status.className = 'auth-status ok';
      status.innerHTML = `<b>승인 완료</b> — ${planLabel(activePlan)} 서비스가 활성화되었습니다.`;
    } else if (request) {
      status.className = 'auth-status warn';
      status.innerHTML = `<b>승인 확인중</b> — ${planLabel(requestPlan)} 신청 접수. 관리자 승인 후 이용 가능합니다.`;
    } else {
      status.className = 'auth-status ok';
      status.innerHTML = '<b>로그인 완료</b> — 아직 신청 내역이 없습니다.';
    }
  }

  if (emailEl) emailEl.textContent = email || '-';
  if (planEl) planEl.textContent = approved ? `${planLabel(activePlan)} 이용중` : (pendingPlan ? `승인대기 (${planLabel(pendingPlan)} 신청)` : 'FREE');
  if (telEl) telEl.textContent = telegram || '미등록';
  if (approvalEl) approvalEl.textContent = approved ? '승인완료' : (request ? statusLabel(requestStatus) : '신청 전');
  if (lastReqEl) lastReqEl.textContent = request ? `${planLabel(requestPlan)} / ${statusLabel(requestStatus)} / ${formatDate(request.created_at)}` : '신청 내역 없음';
  if (inviteEl) {
    if (!approved) inviteEl.textContent = '승인 후 표시';
    else if (activePlan === 'SEMI') inviteEl.textContent = '개인 텔레그램 봇에서 반자동 버튼 활성화';
    else if (activePlan === 'AUTO') inviteEl.textContent = '자동 설정 완료 후 개인 텔레그램 봇에서 활성화';
    else inviteEl.innerHTML = '<a href="https://t.me/listing0517" target="_blank">VIP방 입장</a>';
  }

  const botBox = document.querySelector('[data-my-bot]');
  const autoBox = document.querySelector('[data-my-auto]');
  const showDetail = Boolean(request && ['SEMI','AUTO'].includes(requestPlan));
  if (botBox) botBox.style.display = showDetail ? '' : 'none';
  if (autoBox) autoBox.style.display = showDetail ? '' : 'none';

  const botTokenEl = document.getElementById('myBotToken');
  const chatIdEl = document.getElementById('myChatId');
  const exchangeEl = document.getElementById('myExchange');
  const apiKeyEl = document.getElementById('myApiKey');
  const apiSecretEl = document.getElementById('myApiSecret');

  if (botTokenEl) botTokenEl.textContent = maskValue(request?.tg_bot_token || userRow?.tg_bot_token || '');
  if (chatIdEl) chatIdEl.textContent = request?.tg_chat_id || userRow?.tg_chat_id || '미등록';
  if (exchangeEl) exchangeEl.textContent = request?.foreign_exchange || request?.exchange || userRow?.foreign_exchange || userRow?.exchange || '미등록';
  if (apiKeyEl) apiKeyEl.textContent = maskValue(request?.foreign_api_key || request?.api_key || userRow?.foreign_api_key || userRow?.api_key || '');
  if (apiSecretEl) apiSecretEl.textContent = maskValue(request?.foreign_api_secret || request?.api_secret || userRow?.foreign_api_secret || userRow?.api_secret || '');
}

checkUser();
