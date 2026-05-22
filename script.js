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
  }catch(e){ console.log(e); }
}

/* =========================
   K-EDGE Supabase 운영용 최종본
   - service_role key 절대 사용 금지
   - anon public key만 사용
========================= */
const KEDGE_AUTH_KEY = "kedge_local_user";
const KEDGE_USERS_KEY = "kedge_local_users";
const KEDGE_REQUESTS_KEY = "kedge_vip_requests";

const SUPABASE_URL = "https://qakhbihueonefzifrmct.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_XboBFueAITcieSL75B2S5g_qlm4XmOm";

let kedgeSupabase = null;

try{
  if(window.supabase && SUPABASE_URL && SUPABASE_ANON_KEY){
    kedgeSupabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
}catch(e){
  console.log("Supabase init failed", e);
}

function qs(id){ return document.getElementById(id); }
function val(id){ return (qs(id)?.value || "").trim(); }

function setMsg(id,text,type="error"){
  const el=qs(id);
  if(!el) return;
  el.textContent=text;
  el.className=(el.classList.contains("form-msg") ? "form-msg " : "auth-msg ") + type;
}

function getLocalUsers(){
  try{return JSON.parse(localStorage.getItem(KEDGE_USERS_KEY)||"{}");}
  catch(e){return {};}
}
function saveLocalUsers(users){ localStorage.setItem(KEDGE_USERS_KEY,JSON.stringify(users)); }
function getLocalUser(){
  try{return JSON.parse(localStorage.getItem(KEDGE_AUTH_KEY)||"null");}
  catch(e){return null;}
}
function setLocalUser(user){ localStorage.setItem(KEDGE_AUTH_KEY,JSON.stringify(user)); }
function clearLocalUser(){ localStorage.removeItem(KEDGE_AUTH_KEY); }
function getRequests(){
  try{return JSON.parse(localStorage.getItem(KEDGE_REQUESTS_KEY)||"[]");}
  catch(e){return [];}
}
function saveRequests(rows){ localStorage.setItem(KEDGE_REQUESTS_KEY,JSON.stringify(rows)); }

function maskValue(v){
  v=String(v||"");
  if(!v) return "미등록";
  if(v.length<=8) return "••••";
  return v.slice(0,4)+"••••"+v.slice(-4);
}
function planLabel(plan){
  const map={FREE:"FREE",VIP:"VIP 👑",SEMI:"VIP Lite 🤖",AUTO:"VIP Pro 🚀"};
  return map[plan] || plan || "FREE";
}
function isBotPlan(plan){ return plan==="SEMI" || plan==="AUTO"; }
function isAutoPlan(plan){ return plan==="AUTO"; }
function formatDate(v){
  if(!v) return "-";
  try{return new Date(v).toLocaleString("ko-KR");}
  catch(e){return v;}
}

function friendlyAuthError(err){
  const msg=String((err&&err.message)||err||"").toLowerCase();
  if(msg.includes("invalid login")||msg.includes("invalid credentials")) return "❌ 이메일 또는 비밀번호가 틀렸습니다.";
  if(msg.includes("email not confirmed")) return "❌ 이메일 인증이 필요합니다. 메일함을 확인해주세요.";
  if(msg.includes("already")) return "❌ 이미 가입된 이메일입니다. 로그인해주세요.";
  if(msg.includes("password")) return "❌ 비밀번호 형식이 올바르지 않습니다.";
  if(msg.includes("email")) return "❌ 이메일 형식이 올바르지 않습니다.";
  if(msg.includes("row-level security")||msg.includes("rls")) return "❌ Supabase RLS 정책 때문에 저장이 막혔습니다. 테이블 RLS를 끄거나 정책을 추가해주세요.";
  return "❌ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

/* =========================
   Supabase DB 함수
========================= */
async function dbInsertUser(user){
  if(!kedgeSupabase) throw new Error("Supabase 미연결");
  const payload={
    email:user.email,
    telegram:user.telegram || "미등록",
    plan:user.plan || "FREE",
    tg_bot_token:user.tg_bot_token || "",
    tg_chat_id:user.tg_chat_id || "",
    exchange:user.exchange || "",
    api_key:user.api_key || "",
    api_secret:user.api_secret || "",
    approved:!!user.approved,
    expire_at:user.expire_at || null
  };
  const {data,error}=await kedgeSupabase
    .from("kedge_users")
    .upsert(payload,{onConflict:"email"})
    .select()
    .single();
  if(error) throw error;
  return data;
}

async function dbGetUserByEmail(email){
  if(!kedgeSupabase || !email) return null;
  const {data,error}=await kedgeSupabase
    .from("kedge_users")
    .select("*")
    .eq("email",email)
    .maybeSingle();
  if(error) throw error;
  return data;
}

async function dbInsertRequest(req){
  if(!kedgeSupabase) throw new Error("Supabase 미연결");
  const payload={
    email:req.email,
    telegram:req.telegram || "미등록",
    product:req.product,
    pay_type:req.payType || req.pay_type || "USDT",
    pay_name:req.payName || req.pay_name || "",
    memo:req.memo || "",
    status:req.status || "PENDING",
    tg_bot_token:req.tg_bot_token || "",
    tg_chat_id:req.tg_chat_id || "",
    exchange:req.exchange || "",
    api_key:req.api_key || "",
    api_secret:req.api_secret || ""
  };
  const {data,error}=await kedgeSupabase
    .from("kedge_requests")
    .insert(payload)
    .select()
    .single();
  if(error) throw error;
  return data;
}

async function dbLoadRequests(){
  if(!kedgeSupabase) return getRequests();
  const {data,error}=await kedgeSupabase
    .from("kedge_requests")
    .select("*")
    .order("created_at",{ascending:false});
  if(error) throw error;
  return data || [];
}

async function dbUpdateRequestStatus(id,status){
  if(!kedgeSupabase) throw new Error("Supabase 미연결");
  const {data,error}=await kedgeSupabase
    .from("kedge_requests")
    .update({status})
    .eq("id",id)
    .select()
    .single();
  if(error) throw error;
  return data;
}

async function dbApproveUserFromRequest(req){
  if(!kedgeSupabase || !req) throw new Error("승인 데이터 없음");
  const plan=req.product || "VIP";
  const expire=new Date();
  expire.setMonth(expire.getMonth()+1);

  const payload={
    email:req.email,
    telegram:req.telegram || "미등록",
    plan,
    tg_bot_token:req.tg_bot_token || "",
    tg_chat_id:req.tg_chat_id || "",
    exchange:req.exchange || "",
    api_key:req.api_key || "",
    api_secret:req.api_secret || "",
    approved:true,
    expire_at:expire.toISOString()
  };

  const {data,error}=await kedgeSupabase
    .from("kedge_users")
    .upsert(payload,{onConflict:"email"})
    .select()
    .single();
  if(error) throw error;

  const amountMap={VIP:35000,SEMI:70000,AUTO:100000};
  await kedgeSupabase.from("kedge_sales").insert({
    email:req.email,
    product:plan,
    amount:amountMap[plan] || 0
  });

  return data;
}

async function dbLoadUsers(){
  if(!kedgeSupabase) return Object.values(getLocalUsers());
  const {data,error}=await kedgeSupabase
    .from("kedge_users")
    .select("*")
    .order("created_at",{ascending:false});
  if(error) throw error;
  return data || [];
}

async function dbLoadSales(){
  if(!kedgeSupabase) return [];
  const {data,error}=await kedgeSupabase
    .from("kedge_sales")
    .select("*")
    .order("created_at",{ascending:false});
  if(error) throw error;
  return data || [];
}

/* =========================
   회원/로그인
========================= */
function togglePassword(inputId,btn){
  const input=qs(inputId);
  if(!input) return;
  const hidden=input.type==="password";
  input.type=hidden ? "text" : "password";
  if(btn){
    btn.textContent=hidden ? "🙈" : "👁";
    btn.classList.toggle("show",hidden);
  }
}

function getSignupExtra(){
  const plan=val("signupPlan") || "FREE";
  return {
    plan,
    tg_bot_token:val("signupBotToken"),
    tg_chat_id:val("signupChatId"),
    exchange:val("signupExchange") || "MEXC",
    api_key:val("signupApiKey"),
    api_secret:val("signupApiSecret")
  };
}

function syncPlanFields(){
  const plan=val("signupPlan") || val("productSelect") || "FREE";
  const isBot=isBotPlan(plan);
  const isAuto=isAutoPlan(plan);
  document.querySelectorAll("[data-plan-field='bot']").forEach(el=>el.style.display=isBot?"block":"none");
  document.querySelectorAll("[data-plan-field='auto']").forEach(el=>el.style.display=isAuto?"block":"none");
  document.querySelectorAll("[data-product-field='bot']").forEach(el=>el.style.display=isBot?"block":"none");
  document.querySelectorAll("[data-product-field='auto']").forEach(el=>el.style.display=isAuto?"block":"none");
}

async function signupUser(){
  const email=val("signupEmail");
  const password=qs("signupPassword")?.value || "";
  const confirm=qs("signupPasswordConfirm")?.value || "";
  const telegram=val("signupTelegram");
  const extra=getSignupExtra();

  if(!email) return setMsg("signupMsg","❌ 이메일을 입력해주세요.");
  if(!email.includes("@")) return setMsg("signupMsg","❌ 이메일 형식이 올바르지 않습니다.");
  if(!password) return setMsg("signupMsg","❌ 비밀번호를 입력해주세요.");
  if(password.length<6) return setMsg("signupMsg","❌ 비밀번호는 6자리 이상으로 입력해주세요.");
  if(password!==confirm) return setMsg("signupMsg","❌ 비밀번호가 일치하지 않습니다.");
  if(isBotPlan(extra.plan)&&(!extra.tg_bot_token||!extra.tg_chat_id)) return setMsg("signupMsg","❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
  if(isAutoPlan(extra.plan)&&(!extra.api_key||!extra.api_secret)) return setMsg("signupMsg","❌ 자동은 API KEY와 SECRET이 필요합니다.");

  const localUser={email,password,telegram:telegram||"미등록",...extra,approved:extra.plan==="FREE"};
  const users=getLocalUsers();
  if(users[email]) return setMsg("signupMsg","❌ 이미 가입된 이메일입니다. 로그인해주세요.");

  if(kedgeSupabase){
    try{
      const {error}=await kedgeSupabase.auth.signUp({
        email,
        password,
        options:{data:{telegram,...extra}}
      });

      // 이미 Auth 계정이 있어도 DB 회원 저장은 시도
      if(error && !String(error.message||"").toLowerCase().includes("already")){
        console.log(error);
      }

      await dbInsertUser(localUser);
    }catch(e){
      console.log(e);
      return setMsg("signupMsg",friendlyAuthError(e));
    }
  }

  users[email]=localUser;
  saveLocalUsers(users);
  const {password:_pw,...safeUser}=localUser;
  setLocalUser(safeUser);
  setMsg("signupMsg","✅ 회원가입 완료. 내정보로 이동합니다.","success");
  setTimeout(()=>location.href="./mypage.html",900);
}

async function loginUser(){
  const email=val("loginEmail");
  const password=qs("loginPassword")?.value || "";
  if(!email) return setMsg("loginMsg","❌ 이메일을 입력해주세요.");
  if(!password) return setMsg("loginMsg","❌ 비밀번호를 입력해주세요.");

  const users=getLocalUsers();
  if(users[email] && users[email].password===password){
    let safeUser={...users[email]};
    delete safeUser.password;

    if(kedgeSupabase){
      try{
        const dbUser=await dbGetUserByEmail(email);
        if(dbUser) safeUser={...safeUser,...dbUser};
      }catch(e){ console.log(e); }
    }

    setLocalUser(safeUser);
    setMsg("loginMsg","✅ 로그인 완료. 메인으로 이동합니다.","success");
    updateAuthUI();
    setTimeout(()=>location.href="./index.html",800);
    return;
  }

  // localStorage에 없으면 Supabase Auth 로그인 시도
  if(kedgeSupabase){
    try{
      const {data,error}=await kedgeSupabase.auth.signInWithPassword({email,password});
      if(error) return setMsg("loginMsg",friendlyAuthError(error));
      const user=data.user || {};
      const meta=user.user_metadata || {};
      const dbUser=await dbGetUserByEmail(user.email || email);
      setLocalUser({
        email:user.email || email,
        telegram:dbUser?.telegram || meta.telegram || "미등록",
        plan:dbUser?.plan || meta.plan || "FREE",
        tg_bot_token:dbUser?.tg_bot_token || meta.tg_bot_token || "",
        tg_chat_id:dbUser?.tg_chat_id || meta.tg_chat_id || "",
        exchange:dbUser?.exchange || meta.exchange || "",
        api_key:dbUser?.api_key || meta.api_key || "",
        api_secret:dbUser?.api_secret || meta.api_secret || "",
        approved:dbUser?.approved || false,
        expire_at:dbUser?.expire_at || ""
      });
      setMsg("loginMsg","✅ 로그인 완료. 메인으로 이동합니다.","success");
      updateAuthUI();
      setTimeout(()=>location.href="./index.html",800);
      return;
    }catch(e){
      return setMsg("loginMsg",friendlyAuthError(e));
    }
  }

  if(!users[email]) return setMsg("loginMsg","❌ 존재하지 않는 계정입니다. 회원가입을 먼저 해주세요.");
  return setMsg("loginMsg","❌ 비밀번호가 틀렸습니다.");
}

async function resetPassword(){
  const email=val("loginEmail");
  if(!email) return setMsg("loginMsg","❌ 비밀번호 찾기를 하려면 이메일을 먼저 입력해주세요.");
  if(kedgeSupabase){
    try{
      const {error}=await kedgeSupabase.auth.resetPasswordForEmail(email,{redirectTo:location.origin+"/login.html"});
      if(error) return setMsg("loginMsg",friendlyAuthError(error));
      setMsg("loginMsg","✅ 비밀번호 재설정 메일을 보냈습니다.","success");
      return;
    }catch(e){ return setMsg("loginMsg",friendlyAuthError(e)); }
  }
  setMsg("loginMsg","✅ 테스트 모드: Supabase 연결 후 메일 발송 가능합니다.","success");
}

async function logoutUser(){
  try{ if(kedgeSupabase) await kedgeSupabase.auth.signOut(); }catch(e){}
  clearLocalUser();
  updateAuthUI();
  location.href="./index.html";
}

async function getCurrentUser(){
  let user=getLocalUser();

  if(kedgeSupabase){
    try{
      const {data}=await kedgeSupabase.auth.getUser();
      if(data && data.user){
        const meta=data.user.user_metadata || {};
        const dbUser=await dbGetUserByEmail(data.user.email || "");
        user={
          email:data.user.email || user?.email || "-",
          telegram:dbUser?.telegram || meta.telegram || user?.telegram || "미등록",
          plan:dbUser?.plan || meta.plan || user?.plan || "FREE",
          tg_bot_token:dbUser?.tg_bot_token || meta.tg_bot_token || user?.tg_bot_token || "",
          tg_chat_id:dbUser?.tg_chat_id || meta.tg_chat_id || user?.tg_chat_id || "",
          exchange:dbUser?.exchange || meta.exchange || user?.exchange || "",
          api_key:dbUser?.api_key || meta.api_key || user?.api_key || "",
          api_secret:dbUser?.api_secret || meta.api_secret || user?.api_secret || "",
          approved:dbUser?.approved || user?.approved || false,
          expire_at:dbUser?.expire_at || user?.expire_at || ""
        };
        setLocalUser(user);
      }else if(user?.email){
        const dbUser=await dbGetUserByEmail(user.email);
        if(dbUser){
          user={...user,...dbUser};
          setLocalUser(user);
        }
      }
    }catch(e){ console.log(e); }
  }

  return user;
}

async function updateAuthUI(){
  const user=await getCurrentUser();
  const top=qs("topAuthArea");
  if(top){
    if(user){
      const plan=user.plan || "FREE";
      top.innerHTML=`
        <div class="user-mini">
          <span class="user-name">${user.email || "회원"}</span>
          <span class="plan-badge plan-${String(plan).toLowerCase()}">${planLabel(plan)}</span>
          <a class="login" href="./mypage.html">내정보</a>
          <button onclick="logoutUser()">로그아웃</button>
        </div>`;
    }else{
      top.innerHTML=`<a class="login" href="./login.html">로그인</a><a class="join" href="./join.html">회원가입</a>`;
    }
  }

  const status=qs("authStatus");
  if(status){
    status.innerHTML=user
      ? `<b>✅ 로그인 중</b><p>${user.email || "-"} / ${planLabel(user.plan || "FREE")}</p>`
      : `<b>로그인이 필요합니다.</b><p>회원 기능은 로그인 후 이용할 수 있습니다.</p>`;
  }

  if(qs("myEmail")) qs("myEmail").textContent=user?.email || "-";
  if(qs("myPlan")) qs("myPlan").textContent=planLabel(user?.plan || "FREE");
  if(qs("myTelegram")) qs("myTelegram").textContent=user?.telegram || "미등록";
  if(qs("myBotToken")) qs("myBotToken").textContent=maskValue(user?.tg_bot_token || "");
  if(qs("myChatId")) qs("myChatId").textContent=user?.tg_chat_id || "미등록";
  if(qs("myExchange")) qs("myExchange").textContent=user?.exchange || "미등록";
  if(qs("myApiKey")) qs("myApiKey").textContent=maskValue(user?.api_key || "");
  if(qs("myApiSecret")) qs("myApiSecret").textContent=maskValue(user?.api_secret || "");

  document.querySelectorAll("[data-my-bot]").forEach(el=>el.style.display=user&&isBotPlan(user.plan)?"block":"none");
  document.querySelectorAll("[data-my-auto]").forEach(el=>el.style.display=user&&isAutoPlan(user.plan)?"block":"none");

  const loggedIn=qs("mypageLoggedIn");
  const loggedOut=qs("mypageLoggedOut");
  if(loggedIn && loggedOut){
    loggedIn.style.display=user?"grid":"none";
    loggedOut.style.display=user?"none":"grid";
  }
}

/* =========================
   결제/등록 신청
========================= */
const PRODUCT_INFO={
  VIP:{title:"🔥 VIP",price:"35,000원",desc:"전체 유료 정보 알림 제공",list:["김프/역프 전체 알림","양방 후보","입출금·고래·상장·DEX·BTC Wave"]},
  SEMI:{title:"🤖 VIP Lite (반자동)",price:"70,000원",desc:"VIP 전체 기능 + 승인형 진입 준비",list:["VIP 전체 기능","텔레그램 BOT TOKEN 저장","CHAT ID 저장","향후 [진입] 버튼 연동"]},
  AUTO:{title:"🚀 VIP Pro (자동)",price:"100,000원",desc:"VIP 전체 기능 + 자동매매 연동 준비",list:["VIP 전체 기능","텔레그램 BOT TOKEN 저장","거래소 API 저장","자동 진입/청산 연동 준비"]}
};
const PAY_INFO={
  BANK:`<h4>국내 계좌</h4><p>관리자에게 계좌 안내를 받은 뒤 입금자명을 입력하세요.</p><small>확인 후 수동 승인됩니다.</small>`,
  USDT:`<h4>USDT 테더</h4><p>관리자에게 입금 주소를 받은 뒤 TxID를 입력하세요.</p><small>네트워크 오입금에 주의하세요.</small>`,
  CARD:`<h4>신용카드</h4><p>카드 결제는 준비중입니다.</p><small>현재는 국내 계좌 또는 USDT 등록을 이용해주세요.</small>`
};

function changeProductInfo(){
  const product=val("productSelect") || "VIP";
  const info=PRODUCT_INFO[product] || PRODUCT_INFO.VIP;
  const box=qs("productInfo");
  if(box){
    box.innerHTML=`<h4>${info.title}</h4><strong>${info.price}</strong><p>${info.desc}</p><ul>${info.list.map(x=>`<li>${x}</li>`).join("")}</ul>`;
  }
  syncPlanFields();
}
function changePayInfo(){
  const pay=val("payType") || "USDT";
  const box=qs("payInfo");
  if(box) box.innerHTML=PAY_INFO[pay] || PAY_INFO.USDT;
}
function collectPaymentExtra(){
  return {
    tg_bot_token:val("payBotToken"),
    tg_chat_id:val("payChatId"),
    exchange:val("payExchange") || "MEXC",
    api_key:val("payApiKey"),
    api_secret:val("payApiSecret")
  };
}

async function submitVipRequest(){
  const user=await getCurrentUser();
  if(!user) return setMsg("vipRequestMsg","❌ 로그인 후 등록 신청할 수 있습니다.");

  const product=val("productSelect") || "VIP";
  const payType=val("payType") || "USDT";
  const payName=val("payName");
  const memo=val("txidInput");
  const extra=collectPaymentExtra();

  if(!payName) return setMsg("vipRequestMsg","❌ 입금자명 또는 보내는 사람 이름을 입력해주세요.");
  if(!memo) return setMsg("vipRequestMsg","❌ TxID / 입금 메모 / 확인용 내용을 입력해주세요.");
  if(isBotPlan(product)&&(!extra.tg_bot_token||!extra.tg_chat_id)) return setMsg("vipRequestMsg","❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
  if(isAutoPlan(product)&&(!extra.api_key||!extra.api_secret)) return setMsg("vipRequestMsg","❌ 자동은 거래소 API KEY와 SECRET이 필요합니다.");

  const request={
    id:"REQ-"+Date.now(),
    created_at:new Date().toISOString(),
    email:user.email,
    telegram:user.telegram || "미등록",
    product,
    payType,
    payName,
    memo,
    status:"PENDING",
    ...extra
  };

  try{
    if(kedgeSupabase){
      await dbInsertRequest(request);
    }else{
      const rows=getRequests();
      rows.unshift(request);
      saveRequests(rows);
    }

    // 내정보에서도 신청값이 보이도록 현재 브라우저 상태 갱신
    const users=getLocalUsers();
    if(users[user.email]){
      users[user.email]={...users[user.email],plan:product,...extra};
      saveLocalUsers(users);
    }
    setLocalUser({...user,plan:product,...extra});
    updateAuthUI();

    setMsg("vipRequestMsg","✅ 등록 신청 완료. 관리자 확인 후 승인됩니다.","success");
  }catch(e){
    console.log(e);
    setMsg("vipRequestMsg",friendlyAuthError(e));
  }
}

/* =========================
   관리자 페이지
========================= */
const KEDGE_ADMIN_CODE="0517";
const VIP_INVITE_LINK="https://t.me/listing0517";
const SEMI_GUIDE_LINK="https://t.me/listing0517";
const AUTO_GUIDE_LINK="https://t.me/listing0517";

function adminLogin(){
  const code=String(qs("adminPin")?.value || qs("adminCode")?.value || "").replace(/\s/g,"");
  if(code!==KEDGE_ADMIN_CODE){
    const m=qs("adminLoginMsg");
    if(m) m.textContent="❌ 관리자 코드가 틀렸습니다.";
    return;
  }
  sessionStorage.setItem("kedge_admin_ok","1");
  initAdminPage();
}
function adminLogout(){
  sessionStorage.removeItem("kedge_admin_ok");
  location.reload();
}
function adminBadge(status){
  const s=status || "PENDING";
  const label=s==="APPROVED" ? "승인" : s==="REJECTED" ? "거절" : "대기";
  return `<span class="admin-status ${String(s).toLowerCase()}">${label}</span>`;
}
async function initAdminPage(){
  const loginBox=qs("adminLoginBox");
  const panel=qs("adminApp") || qs("adminPanel");
  if(!loginBox && !panel) return;

  if(sessionStorage.getItem("kedge_admin_ok")!=="1"){
    if(loginBox) loginBox.style.display="block";
    if(panel) panel.style.display="none";
    return;
  }

  if(loginBox) loginBox.style.display="none";
  if(panel) panel.style.display="block";
  await renderAdminDashboard();
}
async function renderAdminDashboard(){
  let requests=[],users=[],sales=[];
  try{
    requests=await dbLoadRequests();
    users=await dbLoadUsers();
    sales=await dbLoadSales();
  }catch(e){
    console.log(e);
    if(qs("adminRequestList")) qs("adminRequestList").innerHTML=`<div class="admin-empty">DB 로딩 실패. Supabase 테이블/RLS를 확인하세요.</div>`;
    return;
  }

  const pending=requests.filter(r=>r.status==="PENDING").length;
  const active=users.filter(u=>u.approved || u.plan!=="FREE").length;
  const semi=users.filter(u=>u.plan==="SEMI").length;
  const auto=users.filter(u=>u.plan==="AUTO").length;
  const revenue=sales.reduce((a,b)=>a+Number(b.amount||0),0);

  if(qs("adminTodayCount")) qs("adminTodayCount").textContent=requests.length+"건";
  if(qs("adminPendingCount")) qs("adminPendingCount").textContent=pending+"건";
  if(qs("adminActiveCount")) qs("adminActiveCount").textContent=active+"명";
  if(qs("adminSemiCount")) qs("adminSemiCount").textContent=semi+"명";
  if(qs("adminAutoCount")) qs("adminAutoCount").textContent=auto+"명";
  if(qs("adminRevenue")) qs("adminRevenue").textContent=revenue.toLocaleString()+"원";

  renderAdminRequests(requests);
  renderAdminUsers(users);
}
function renderAdminRequests(rows){
  const box=qs("adminRequestList");
  if(!box) return;

  const q=(val("adminSearch")||"").toLowerCase();
  const f=val("adminStatusFilter") || val("adminFilter") || "ALL";

  let list=rows || [];
  if(f!=="ALL") list=list.filter(r=>r.status===f || r.product===f);
  if(q) list=list.filter(r=>
    String(r.email||"").toLowerCase().includes(q) ||
    String(r.telegram||"").toLowerCase().includes(q) ||
    String(r.pay_name||"").toLowerCase().includes(q) ||
    String(r.product||"").toLowerCase().includes(q)
  );

  if(!list.length){
    box.innerHTML=`<div class="admin-empty">신청 내역이 없습니다.</div>`;
    return;
  }

  box.innerHTML=list.map(r=>`
    <article class="admin-row">
      <div>
        <h3>${planLabel(r.product)} ${adminBadge(r.status)}</h3>
        <p><b>이메일</b> ${r.email || "-"}</p>
        <p><b>텔레그램</b> ${r.telegram || "-"}</p>
        <p><b>결제</b> ${r.pay_type || "-"} / ${r.pay_name || "-"}</p>
        <p><b>메모</b> ${r.memo || "-"}</p>
        <p><b>신청시간</b> ${formatDate(r.created_at)}</p>
        ${(r.product==="SEMI"||r.product==="AUTO") ? `<p><b>BOT</b> ${maskValue(r.tg_bot_token)} / CHAT ${r.tg_chat_id || "-"}</p>` : ""}
        ${r.product==="AUTO" ? `<p><b>API</b> ${r.exchange || "-"} / ${maskValue(r.api_key)} / ${maskValue(r.api_secret)}</p>` : ""}
      </div>
      <div class="admin-actions">
        <button onclick="approveRequest('${r.id}')">승인</button>
        <button class="danger" onclick="rejectRequest('${r.id}')">거절</button>
        <button class="ghost" onclick="copyVipLink('${r.product}')">링크 복사</button>
        ${(r.product==="SEMI"||r.product==="AUTO") ? `<button class="ghost" onclick="testUserBot('${r.tg_bot_token || ""}','${r.tg_chat_id || ""}')">BOT 테스트</button>` : ""}
        ${r.product==="AUTO" ? `<button class="ghost" onclick="testExchangeApi('${r.exchange || ""}','${r.api_key || ""}','${r.api_secret || ""}')">API 테스트</button>` : ""}
      </div>
    </article>
  `).join("");
}
function renderAdminUsers(rows){
  const box=qs("adminUserList");
  if(!box) return;
  if(!rows || !rows.length){
    box.innerHTML=`<div class="admin-empty">회원 데이터가 없습니다.</div>`;
    return;
  }
  box.innerHTML=rows.map(u=>`
    <article class="admin-row compact">
      <div>
        <h3>${u.email || "-"} <span class="plan-badge plan-${String(u.plan||"FREE").toLowerCase()}">${planLabel(u.plan)}</span></h3>
        <p><b>텔레그램</b> ${u.telegram || "미등록"}</p>
        <p><b>승인</b> ${u.approved ? "승인됨" : "미승인"} / <b>만료</b> ${formatDate(u.expire_at)}</p>
        ${(u.plan==="SEMI"||u.plan==="AUTO") ? `<p><b>BOT</b> ${maskValue(u.tg_bot_token)} / CHAT ${u.tg_chat_id || "-"}</p>` : ""}
        ${u.plan==="AUTO" ? `<p><b>API</b> ${u.exchange || "-"} / ${maskValue(u.api_key)}</p>` : ""}
      </div>
      <div class="admin-actions">
        <button class="ghost" onclick="copyText('${u.email || ""}')">이메일 복사</button>
      </div>
    </article>
  `).join("");
}
async function approveRequest(id){
  try{
    const rows=await dbLoadRequests();
    const req=rows.find(r=>String(r.id)===String(id));
    if(!req) return alert("신청 정보를 찾을 수 없습니다.");
    await dbUpdateRequestStatus(id,"APPROVED");
    await dbApproveUserFromRequest(req);
    alert("승인 완료");
    await renderAdminDashboard();
  }catch(e){
    console.log(e);
    alert("승인 실패. Supabase 테이블/RLS를 확인하세요.");
  }
}
async function rejectRequest(id){
  try{
    await dbUpdateRequestStatus(id,"REJECTED");
    alert("거절 처리 완료");
    await renderAdminDashboard();
  }catch(e){
    console.log(e);
    alert("거절 실패");
  }
}
function copyText(t){
  navigator.clipboard?.writeText(t || "");
  alert("복사 완료");
}
function copyVipLink(product){
  let link=VIP_INVITE_LINK;
  if(product==="SEMI") link=SEMI_GUIDE_LINK;
  if(product==="AUTO") link=AUTO_GUIDE_LINK;
  copyText(link);
}
async function testUserBot(token,chatId){
  if(!token || !chatId) return alert("BOT TOKEN 또는 CHAT ID가 없습니다.");
  const msg=encodeURIComponent("✅ K-EDGE BOT 연결 테스트 성공");
  try{
    const res=await fetch(`https://api.telegram.org/bot${token}/sendMessage?chat_id=${chatId}&text=${msg}`);
    const data=await res.json();
    alert(data.ok ? "BOT 테스트 전송 성공" : "BOT 테스트 실패");
  }catch(e){
    alert("BOT 테스트 실패");
  }
}
function testExchangeApi(exchange,apiKey,apiSecret){
  if(!apiKey || !apiSecret) return alert("API KEY 또는 SECRET이 없습니다.");
  alert(`${exchange || "거래소"} API 입력값은 확인됨. 실제 잔고/주문 테스트는 서버 프록시 연결 후 가능합니다.`);
}

/* =========================
   초기 실행
========================= */
document.addEventListener("DOMContentLoaded",()=>{
  loadLiveDashboard();
  setInterval(loadLiveDashboard,10000);

  updateAuthUI();
  changeProductInfo();
  changePayInfo();
  syncPlanFields();
  initAdminPage();

  qs("signupPlan")?.addEventListener("change",syncPlanFields);
  qs("productSelect")?.addEventListener("change",changeProductInfo);
  qs("payType")?.addEventListener("change",changePayInfo);
  qs("adminPin")?.addEventListener("keydown",(e)=>{ if(e.key==="Enter") adminLogin(); });
  qs("adminSearch")?.addEventListener("input",renderAdminDashboard);
  qs("adminStatusFilter")?.addEventListener("change",renderAdminDashboard);
  qs("adminFilter")?.addEventListener("change",renderAdminDashboard);

  const page=document.body?.dataset?.page;
  if(page){
    document.querySelectorAll("[data-nav]").forEach(a=>{
      if(a.dataset.nav===page) a.classList.add("active");
    });
  }
});
