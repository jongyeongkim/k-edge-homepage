
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

async function checkUser() {
  const status = document.getElementById('authStatus');
  const emailEl = document.getElementById('myEmail');
  const planEl = document.getElementById('myPlan');
  const telEl = document.getElementById('myTelegram');

  const { data } = await supabaseClient.auth.getUser();
  const user = data?.user;

  if (!user) {
    if (status) {
      status.className = 'auth-status warn';
      status.innerHTML = '<b>로그인 전</b> — 회원가입 또는 로그인을 진행하세요.';
    }
    if (emailEl) emailEl.textContent = '-';
    if (planEl) planEl.textContent = 'FREE';
    if (telEl) telEl.textContent = '미등록';
    return;
  }

  const meta = user.user_metadata || {};
  const telegram = meta.telegram_id || localStorage.getItem('kedge_telegram') || '미등록';
  const plan = meta.plan || 'FREE';

  if (status) {
    status.className = 'auth-status ok';
    status.innerHTML = '<b>로그인 완료</b> — K-EDGE 회원으로 연결되었습니다.';
  }
  if (emailEl) emailEl.textContent = user.email || '-';
  if (planEl) planEl.textContent = plan;
  if (telEl) telEl.textContent = telegram || '미등록';
}

checkUser();
