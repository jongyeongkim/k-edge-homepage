
const SUPABASE_URL = "https://ilkkwbnxxzkmqhdoscep.supabase.co";
const SUPABASE_KEY = "sb_publishable_Fegb-Q-M98BReiYp1LV9sQ_7CW7e8T_";
const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

let USD_KRW_RATE = 1400;

const PRODUCTS = {
  VIP: {
    title: "🔥 VIP",
    price: 26,
    db: "VIP",
    html: `
      <strong>월 26 USD</strong>
      <ul>
        <li>실시간 김프 / 역프 실체결 감지</li>
        <li>현물-선물 양방 헤지 감지</li>
        <li>초고속 입출금 공지</li>
        <li>입출금 후 시장 분석</li>
        <li>고래 입금 및 후속효과 추적</li>
        <li>상장 기대감 탐지</li>
        <li>DEX 선행 매집 및 생존 추적</li>
        <li>BTC 기술적 패턴 분석</li>
      </ul>`
  },
  SEMI: {
    title: "🤖 VIP + 반자동",
    price: 49,
    db: "VIP_SEMI_AUTO",
    html: `
      <strong>월 49 USD</strong>
      <ul>
        <li>VIP 정보방 전체 기능 포함</li>
        <li>텔레그램 [진입] 버튼</li>
        <li>사용자 승인 후 주문 실행</li>
        <li>API 연동</li>
        <li>일부 자동 청산 지원</li>
        <li>기본 리스크 관리</li>
      </ul>`
  },
  AUTO: {
    title: "🚀 VIP + 자동",
    price: 70,
    db: "VIP_FULL_AUTO",
    html: `
      <strong>월 70 USD</strong>
      <ul>
        <li>VIP 정보방 전체 기능 포함</li>
        <li>자동 매매 실행</li>
        <li>자동 포지션 청산</li>
        <li>24시간 무인 운영</li>
        <li>고급 리스크 관리</li>
        <li>개인방 운영 지원</li>
      </ul>`
  }
};

function setMsg(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
}

function formatKRW(n) {
  return Math.round(n).toLocaleString("ko-KR") + "원";
}

async function loadUsdKrwRate() {
  try {
    const res = await fetch("https://open.er-api.com/v6/latest/USD");
    const data = await res.json();
    const rate = data?.rates?.KRW;
    if (rate) USD_KRW_RATE = rate;
  } catch (e) {}

  const rateText = document.getElementById("usdKrwText");
  if (rateText) rateText.textContent = formatKRW(USD_KRW_RATE);

  document.querySelectorAll("[data-usd-price]").forEach((el) => {
    const usd = Number(el.dataset.usdPrice || "0");
    el.textContent = `월 ${usd} USD / 약 ${formatKRW(usd * USD_KRW_RATE)}`;
  });

  document.querySelectorAll("[data-usd-single]").forEach((el) => {
    const usd = Number(el.dataset.usdSingle || "0");
    el.textContent = `/ 약 ${formatKRW(usd * USD_KRW_RATE)}`;
  });

  changeProductInfo();
}

function initActiveNav() {
  const page = document.body.dataset.page;
  document.querySelectorAll("[data-nav]").forEach(a => {
    if (a.dataset.nav === page) a.classList.add("active");
    else a.classList.remove("active");
  });
}

function initStats() {
  const stat = document.querySelector(".stats-panel article:first-child b");
  setInterval(() => {
    if (!stat) return;
    stat.textContent = (20 + Math.floor(Math.random() * 9)) + "건";
  }, 3000);
}

function bindCopyText() {
  document.querySelectorAll(".copy-text").forEach((el) => {
    if (el.dataset.copyBound === "1") return;
    el.dataset.copyBound = "1";
    el.title = "클릭하면 복사됩니다";
    el.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(el.textContent.trim());
        const old = el.textContent;
        el.textContent = "복사 완료!";
        setTimeout(() => (el.textContent = old), 900);
      } catch(e) {}
    });
  });
}

function changeProductInfo() {
  const select = document.getElementById("productSelect");
  const box = document.getElementById("productInfo");
  if (!select || !box) return;

  const item = PRODUCTS[select.value] || PRODUCTS.VIP;
  const krw = formatKRW(item.price * USD_KRW_RATE);
  box.innerHTML = `<h4>${item.title}</h4>${item.html}<p class="price-note">실시간 환율 기준 약 ${krw}</p>`;
}

function changePayInfo() {
  const payType = document.getElementById("payType");
  const box = document.getElementById("payInfo");
  if (!payType || !box) return;

  if (payType.value === "USDT") {
    box.innerHTML = `
      <h4>USDT 테더 결제</h4>
      <p>체인: Polygon</p>
      <p class="copy-text dynamic-copy">USDT 주소 등록 전</p>
      <small>주소가 확정되면 이 부분에 넣으면 됩니다. 클릭하면 복사됩니다.</small>`;
  } else if (payType.value === "BANK") {
    box.innerHTML = `
      <h4>국내 계좌 결제</h4>
      <p class="copy-text dynamic-copy">계좌 등록 전</p>
      <small>은행 / 계좌번호 / 예금주가 확정되면 이 부분에 넣으면 됩니다. 클릭하면 복사됩니다.</small>`;
  } else {
    box.innerHTML = `
      <h4>신용카드 결제</h4>
      <p>준비 중</p>
      <small>현재는 USDT 또는 국내 계좌 방식으로 먼저 운영합니다.</small>`;
  }
  bindCopyText();
}

function applyQueryProduct() {
  const select = document.getElementById("productSelect");
  if (!select) return;
  const params = new URLSearchParams(location.search);
  const product = params.get("product");
  if (product && PRODUCTS[product]) {
    select.value = product;
  }
}

async function signupUser() {
  const email = document.getElementById("signupEmail")?.value.trim();
  const password = document.getElementById("signupPassword")?.value.trim();
  const telegram = document.getElementById("signupTelegram")?.value.trim();

  if (!email || !password) {
    setMsg("signupMsg", "이메일과 비밀번호를 입력하세요.");
    return;
  }

  const { error } = await supabaseClient.auth.signUp({
    email,
    password,
    options: { data: { telegram_id: telegram || "", plan: "FREE" } }
  });

  if (error) {
    setMsg("signupMsg", "가입 실패: " + error.message);
    return;
  }

  localStorage.setItem("kedge_telegram", telegram || "");
  setMsg("signupMsg", "가입 완료. 이메일 인증이 켜져 있으면 메일 확인 후 로그인하세요.");
  await checkUser();
}

async function loginUser() {
  const email = document.getElementById("loginEmail")?.value.trim();
  const password = document.getElementById("loginPassword")?.value.trim();

  if (!email || !password) {
    setMsg("loginMsg", "이메일과 비밀번호를 입력하세요.");
    return;
  }

  const { error } = await supabaseClient.auth.signInWithPassword({ email, password });

  if (error) {
    setMsg("loginMsg", "로그인 실패: " + error.message);
    return;
  }

  setMsg("loginMsg", "로그인 성공");
  await checkUser();

  setTimeout(() => {
    location.href = "./index.html";
  }, 450);
}

async function logoutUser() {
  await supabaseClient.auth.signOut();
  localStorage.removeItem("kedge_telegram");
  await checkUser();
}

async function checkUser() {
  const status = document.getElementById("authStatus");
  const emailEl = document.getElementById("myEmail");
  const planEl = document.getElementById("myPlan");
  const telEl = document.getElementById("myTelegram");
  const topAuth = document.getElementById("topAuthArea");

  const { data } = await supabaseClient.auth.getUser();
  const user = data?.user;

  if (!user) {
    if (topAuth) {
      topAuth.innerHTML = `
        <a class="login" href="./login.html">로그인</a>
        <a class="join" href="./login.html">회원가입</a>`;
    }
    if (status) {
      status.className = "auth-status warn";
      status.innerHTML = "<b>로그인 전</b> — 회원가입 또는 로그인을 진행하세요.";
    }
    if (emailEl) emailEl.textContent = "-";
    if (planEl) planEl.textContent = "FREE";
    if (telEl) telEl.textContent = "미등록";
    return;
  }

  const meta = user.user_metadata || {};
  const telegram = meta.telegram_id || localStorage.getItem("kedge_telegram") || "미등록";
  const plan = meta.plan || "FREE";
  const name = (user.email || "회원").split("@")[0];

  if (topAuth) {
    topAuth.innerHTML = `
      <div class="user-mini">
        <span class="user-name">${name}님</span>
        <span class="plan-badge">${plan}</span>
        <button type="button" onclick="logoutUser()">로그아웃</button>
      </div>`;
  }

  if (status) {
    status.className = "auth-status ok";
    status.innerHTML = "<b>로그인 완료</b> — K-EDGE 회원으로 연결되었습니다.";
  }
  if (emailEl) emailEl.textContent = user.email || "-";
  if (planEl) planEl.textContent = plan;
  if (telEl) telEl.textContent = telegram || "미등록";
}

async function getCurrentUserForForm() {
  const { data } = await supabaseClient.auth.getUser();
  return data?.user || null;
}

async function submitVipRequest() {
  const user = await getCurrentUserForForm();
  if (!user) {
    setMsg("vipRequestMsg", "로그인 후 등록 신청할 수 있습니다.");
    location.href = "./login.html";
    return;
  }

  const productKey = document.getElementById("productSelect")?.value || "VIP";
  const product = PRODUCTS[productKey] || PRODUCTS.VIP;
  const payType = document.getElementById("payType")?.value || "USDT";
  const payName = document.getElementById("payName")?.value.trim() || "";
  const txid = document.getElementById("txidInput")?.value.trim() || "";
  const meta = user.user_metadata || {};
  const telegram = meta.telegram_id || localStorage.getItem("kedge_telegram") || "";

  if (!payName && !txid) {
    setMsg("vipRequestMsg", "입금자명 또는 TxID/메모 중 하나는 입력하세요.");
    return;
  }

  const payload = {
    email: user.email,
    telegram,
    product: product.db,
    pay_type: payType,
    pay_name: payName,
    txid,
    usd_price: product.price,
    krw_estimate: Math.round(product.price * USD_KRW_RATE),
    usd_krw_rate: USD_KRW_RATE,
    status: "pending",
    created_at: new Date().toISOString()
  };

  const { error } = await supabaseClient.from("vip_requests").insert(payload);
  if (error) {
    setMsg("vipRequestMsg", "DB 저장 실패: vip_requests 테이블/RLS 설정을 확인하세요.");
    return;
  }

  setMsg("vipRequestMsg", "등록 신청 완료. 확인 후 승인됩니다.");
}

async function submitSupportTicket() {
  const user = await getCurrentUserForForm();
  if (!user) {
    setMsg("ticketMsg", "로그인 후 문의 등록할 수 있습니다.");
    location.href = "./login.html";
    return;
  }

  const category = document.getElementById("ticketCategory")?.value || "ETC";
  const telegramInput = document.getElementById("ticketTelegram")?.value.trim() || "";
  const message = document.getElementById("ticketMessage")?.value.trim() || "";
  const meta = user.user_metadata || {};
  const telegram = telegramInput || meta.telegram_id || localStorage.getItem("kedge_telegram") || "";

  if (!message) {
    setMsg("ticketMsg", "문의 내용을 입력하세요.");
    return;
  }

  const payload = {
    email: user.email,
    telegram,
    category,
    message,
    status: "open",
    created_at: new Date().toISOString()
  };

  const { error } = await supabaseClient.from("support_tickets").insert(payload);
  if (error) {
    setMsg("ticketMsg", "DB 저장 실패: support_tickets 테이블/RLS 설정을 확인하세요.");
    return;
  }

  setMsg("ticketMsg", "문의 등록 완료. 관리자가 확인합니다.");
  const textarea = document.getElementById("ticketMessage");
  if (textarea) textarea.value = "";
}

document.addEventListener("DOMContentLoaded", async () => {
  initActiveNav();
  initStats();
  bindCopyText();
  applyQueryProduct();
  changeProductInfo();
  changePayInfo();
  await loadUsdKrwRate();
  await checkUser();
});
