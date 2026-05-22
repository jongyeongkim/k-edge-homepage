const SUPABASE_URL = "https://ilkkwbnxxzkmqhdoscep.supabase.co";
const SUPABASE_KEY = "sb_publishable_Fegb-Q-M98BReiYp1LV9sQ_7CW7e8T_";
const supabaseClient = window.supabase ? supabase.createClient(SUPABASE_URL, SUPABASE_KEY) : null;

function $(id){ return document.getElementById(id); }
function setMsg(id, msg) { const el = $(id); if (el) el.textContent = msg; }
function val(id){ const el = $(id); return el ? String(el.value || '').trim() : ''; }

function togglePassword(id, btn){
  const input = $(id);
  if(!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
  if(btn) btn.textContent = input.type === 'password' ? '👁' : '🙈';
}

async function getCurrentUser(){
  if(!supabaseClient) return null;
  const { data } = await supabaseClient.auth.getUser();
  return data?.user || null;
}

async function signupUser() {
  const email = val('signupEmail');
  const password = val('signupPassword');
  const confirm = val('signupPasswordConfirm');
  const telegram = val('signupTelegram');

  if (!email || !password) return setMsg('signupMsg', '이메일과 비밀번호를 입력하세요.');
  if (password.length < 6) return setMsg('signupMsg', '비밀번호는 6자리 이상 입력하세요.');
  if (confirm && password !== confirm) return setMsg('signupMsg', '비밀번호 확인이 일치하지 않습니다.');
  if (!supabaseClient) return setMsg('signupMsg', 'Supabase 연결 실패. 새로고침 후 다시 시도하세요.');

  const { error } = await supabaseClient.auth.signUp({
    email,
    password,
    options: { data: { telegram_id: telegram || '', plan: 'FREE' } }
  });

  if (error) return setMsg('signupMsg', '가입 실패: ' + error.message);
  localStorage.setItem('kedge_telegram', telegram || '');
  setMsg('signupMsg', '가입 완료. 로그인 페이지로 이동합니다.');
  setTimeout(()=>{ window.location.href = './login.html?v=' + Date.now(); }, 700);
}

async function loginUser() {
  const email = val('loginEmail');
  const password = val('loginPassword');
  if (!email || !password) return setMsg('loginMsg', '이메일과 비밀번호를 입력하세요.');
  if (!supabaseClient) return setMsg('loginMsg', 'Supabase 연결 실패. 새로고침 후 다시 시도하세요.');

  const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
  if (error) return setMsg('loginMsg', '로그인 실패: ' + error.message);

  setMsg('loginMsg', '로그인 성공. 홈으로 이동합니다.');
  setTimeout(()=>{ window.location.href = './index.html?v=' + Date.now(); }, 500);
}

async function logoutUser() {
  if(supabaseClient) await supabaseClient.auth.signOut();
  localStorage.removeItem('kedge_telegram');
  window.location.href = './index.html?v=' + Date.now();
}

async function resetPassword(){
  const email = val('loginEmail');
  if(!email) return setMsg('loginMsg','비밀번호 재설정 받을 이메일을 입력하세요.');
  const { error } = await supabaseClient.auth.resetPasswordForEmail(email, { redirectTo: location.origin + '/k-edge-homepage/login.html' });
  setMsg('loginMsg', error ? ('재설정 실패: '+error.message) : '비밀번호 재설정 메일을 발송했습니다.');
}

function planLabel(p){ return ({FREE:'FREE',VIP:'VIP',SEMI:'VIP Lite (반자동)',AUTO:'VIP Pro (자동)'})[p] || p || 'FREE'; }
function approvalLabel(s){ return s === 'APPROVED' ? '승인완료' : s === 'REJECTED' ? '거절' : '승인 확인중'; }
function mask(v){ v=String(v||''); if(!v) return '미등록'; if(v.length<=8) return '••••'; return v.slice(0,4)+'••••'+v.slice(-4); }

async function checkUser() {
  const page = document.body?.dataset?.page || '';
  const user = await getCurrentUser();

  const top = $('topAuthArea');
  if(top){
    top.innerHTML = user
      ? `<a class="login" href="./mypage.html">내정보</a><button type="button" class="join" onclick="logoutUser()">로그아웃</button>`
      : `<a class="login" href="./login.html">로그인</a><a class="join" href="./join.html">회원가입</a>`;
  }

  if(page !== 'mypage') return;

  const status = $('authStatus');
  const loggedOut = $('mypageLoggedOut');
  const loggedIn = $('mypageLoggedIn');

  if (!user) {
    if(status){ status.className='auth-status warn'; status.innerHTML='<b>로그인 전</b> — 회원가입 또는 로그인을 진행하세요.'; }
    if(loggedOut) loggedOut.style.display='grid';
    if(loggedIn) loggedIn.style.display='none';
    return;
  }

  if(loggedOut) loggedOut.style.display='none';
  if(loggedIn) loggedIn.style.display='grid';

  const meta = user.user_metadata || {};
  const telegram = meta.telegram_id || localStorage.getItem('kedge_telegram') || '미등록';
  if($('myEmail')) $('myEmail').textContent = user.email || '-';
  if($('myTelegram')) $('myTelegram').textContent = telegram;

  let req = null;
  try{
    const { data } = await supabaseClient
      .from('kedge_requests')
      .select('*')
      .eq('email', user.email)
      .order('created_at', { ascending:false })
      .limit(1);
    req = data && data[0] ? data[0] : null;
  }catch(e){ console.log(e); }

  const approved = req && req.status === 'APPROVED' && req.service_enabled === true;
  const product = req?.product || 'FREE';
  if($('myPlan')) $('myPlan').textContent = approved ? planLabel(product) : (req ? planLabel(product) + ' 신청중' : 'FREE');
  if($('myApproval')) $('myApproval').textContent = req ? approvalLabel(req.status) : '신청 내역 없음';
  if($('myLastRequest')) $('myLastRequest').textContent = req ? `${planLabel(product)} / ${approvalLabel(req.status)}` : '신청 내역 없음';
  if($('myInviteLink')) $('myInviteLink').textContent = approved ? '승인 완료 — 텔레그램 안내 확인' : '승인 후 표시';

  document.querySelectorAll('[data-my-bot]').forEach(el=>{ el.style.display = approved && (product==='SEMI'||product==='AUTO') ? 'block':'none'; });
  document.querySelectorAll('[data-my-auto]').forEach(el=>{ el.style.display = approved && (product==='SEMI'||product==='AUTO') ? 'block':'none'; });
  if($('myBotToken')) $('myBotToken').textContent = mask(req?.tg_bot_token);
  if($('myChatId')) $('myChatId').textContent = req?.tg_chat_id || '미등록';
  if($('myExchange')) $('myExchange').textContent = req?.foreign_exchange || req?.exchange || '미등록';
  if($('myApiKey')) $('myApiKey').textContent = mask(req?.foreign_api_key || req?.api_key);
  if($('myApiSecret')) $('myApiSecret').textContent = mask(req?.foreign_api_secret || req?.api_secret);

  if(status){
    status.className = approved ? 'auth-status ok' : 'auth-status warn';
    status.innerHTML = approved ? '<b>승인 완료</b> — 서비스 이용 가능 상태입니다.' : '<b>승인 확인중</b> — 관리자 승인 후 이용 가능합니다.';
  }
}

const PRODUCT_TEXT = {
  VIP: `<h4>VIP</h4><p>정보방/알림 서비스 기본 상품입니다.</p><p><b>가격:</b> 35,000원</p>`,
  SEMI: `<h4>VIP Lite (반자동)</h4><p>텔레그램 버튼으로 직접 진입/청산하는 반자동 상품입니다.</p><p><b>가격:</b> 70,000원</p>`,
  AUTO: `<h4>VIP Pro (자동)</h4><p>승인 후 자동 설정을 완료하면 자동 운용되는 상품입니다.</p><p><b>가격:</b> 100,000원</p>`
};
const PAY_TEXT = {
  USDT: `<h4>USDT 테더</h4><p>입금 후 TxID를 입력하세요.</p>`,
  BANK: `<h4>국내 계좌</h4><p>입금자명을 정확히 입력하세요.</p>`,
  CARD: `<h4>신용카드</h4><p>현재 준비중입니다.</p>`
};

function changeProductInfo(){
  const product = val('productSelect') || 'VIP';
  if($('productInfo')) $('productInfo').innerHTML = PRODUCT_TEXT[product] || '';
  const needBotApi = product === 'SEMI' || product === 'AUTO';
  document.querySelectorAll('[data-product-field="bot"],[data-product-field="api"]').forEach(el=>{
    el.style.display = needBotApi ? 'block' : 'none';
  });
}
function changePayInfo(){
  const pay = val('payType') || 'USDT';
  if($('payInfo')) $('payInfo').innerHTML = PAY_TEXT[pay] || '';
}

async function submitVipRequest(){
  if(!supabaseClient) return setMsg('vipRequestMsg','Supabase 연결 실패. 새로고침 후 다시 시도하세요.');
  const user = await getCurrentUser();
  if(!user){
    setMsg('vipRequestMsg','로그인 후 등록 신청이 가능합니다. 로그인 페이지로 이동합니다.');
    setTimeout(()=>{ window.location.href='./login.html?v='+Date.now(); }, 700);
    return;
  }

  const product = val('productSelect') || 'VIP';
  const needBotApi = product === 'SEMI' || product === 'AUTO';
  const payType = val('payType') || 'USDT';
  const payName = val('payName');
  const memo = val('txidInput');
  const telegram = user.user_metadata?.telegram_id || localStorage.getItem('kedge_telegram') || '';

  if(!payName) return setMsg('vipRequestMsg','입금자명 또는 보내는 사람 이름을 입력하세요.');
  if(!memo) return setMsg('vipRequestMsg','TxID / 입금 메모 / 확인용 내용을 입력하세요.');
  if(needBotApi){
    const required = ['payBotToken','payChatId','payDomesticApiKey','payDomesticApiSecret','payForeignApiKey','payForeignApiSecret'];
    for(const id of required){ if(!val(id)) return setMsg('vipRequestMsg','반자동/자동은 BOT TOKEN, CHAT ID, 국내/해외 API를 모두 입력해야 합니다.'); }
  }

  const payload = {
    email: user.email,
    telegram,
    product,
    pay_type: payType,
    pay_name: payName,
    memo,
    status: 'PENDING',
    tg_bot_token: needBotApi ? val('payBotToken') : '',
    tg_chat_id: needBotApi ? val('payChatId') : '',
    domestic_exchange: needBotApi ? val('payDomesticExchange') : '',
    domestic_api_key: needBotApi ? val('payDomesticApiKey') : '',
    domestic_api_secret: needBotApi ? val('payDomesticApiSecret') : '',
    foreign_exchange: needBotApi ? val('payForeignExchange') : '',
    foreign_api_key: needBotApi ? val('payForeignApiKey') : '',
    foreign_api_secret: needBotApi ? val('payForeignApiSecret') : '',
    service_enabled: false,
    running: false,
    auto_config_done: false,
    domestic_percent: 20,
    trade_mode: 'fixed',
    stop_loss_percent: 4,
    active_coins: []
  };

  const { error } = await supabaseClient.from('kedge_requests').insert(payload);
  if(error){
    console.log(error);
    return setMsg('vipRequestMsg','등록 실패: '+error.message);
  }
  setMsg('vipRequestMsg','등록 신청 완료. 관리자 승인 후 이용 가능합니다.');
}

function initPage(){
  const stat = document.querySelector('.stats b');
  if(stat){ setInterval(()=>{ stat.textContent = (20 + Math.floor(Math.random() * 9)) + '건'; }, 3000); }
  document.querySelectorAll('.copy-text').forEach((el) => {
    el.title = '클릭하면 복사됩니다';
    el.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(el.textContent.trim()); const old=el.textContent; el.textContent='복사 완료!'; setTimeout(()=>el.textContent=old,900); } catch(e) {}
    });
  });
  if(document.body?.dataset?.page === 'payment'){
    changeProductInfo();
    changePayInfo();
  }
  checkUser();
}

window.addEventListener('DOMContentLoaded', initPage);
