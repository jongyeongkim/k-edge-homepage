/* K-EDGE Supabase DB Bridge
   localStorage 신청/관리자 문제 방지용.
   payment/admin 화면은 유지하고 신청/승인 데이터만 Supabase kedge_requests로 통일합니다.
*/
(function(){
  const SUPABASE_URL = "https://ilkkwbnxxzkmqhdoscep.supabase.co";
  const SUPABASE_ANON_KEY = "sb_publishable_Fegb-Q-M98BReiYp1LV9sQ_7CW7e8T_";

  let db = null;

  function qs(id){ return document.getElementById(id); }
  function val(id){ return (qs(id)?.value || "").trim(); }

  function msg(id, text, type){
    const el = qs(id);
    if(!el) return alert(text);
    el.textContent = text;
    el.className = (el.classList.contains("form-msg") ? "form-msg " : "auth-msg ") + (type || "error");
  }

  function getDb(){
    if(db) return db;
    if(!window.supabase){
      alert("Supabase 라이브러리가 아직 로드되지 않았습니다.");
      return null;
    }
    db = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    return db;
  }

  function getLocalUserSafe(){
    try{
      return JSON.parse(localStorage.getItem("kedge_local_user") || "null");
    }catch(e){
      return null;
    }
  }

  async function getUserSafe(){
    if(typeof window.getCurrentUser === "function"){
      try{
        const u = await window.getCurrentUser();
        if(u) return u;
      }catch(e){}
    }
    return getLocalUserSafe();
  }

  function isBotProduct(product){
    return product === "SEMI" || product === "AUTO";
  }

  function readApi(checkboxId, keyId, secretId){
    return {
      enabled: !!qs(checkboxId)?.checked,
      api_key: val(keyId),
      api_secret: val(secretId)
    };
  }

  function collectApis(){
    return {
      domestic_apis:{
        upbit: readApi("payUpbitUse", "payUpbitApiKey", "payUpbitApiSecret"),
        bithumb: readApi("payBithumbUse", "payBithumbApiKey", "payBithumbApiSecret")
      },
      foreign_apis:{
        mexc: readApi("payMexcUse", "payMexcApiKey", "payMexcApiSecret"),
        gate: readApi("payGateUse", "payGateApiKey", "payGateApiSecret"),
        bitget: readApi("payBitgetUse", "payBitgetApiKey", "payBitgetApiSecret"),
        bingx: readApi("payBingxUse", "payBingxApiKey", "payBingxApiSecret")
      }
    };
  }

  function enabledList(obj){
    return Object.entries(obj || {}).filter(([_, v]) => v && v.enabled);
  }

  function hasValidEnabledApi(obj){
    return enabledList(obj).some(([_, v]) => v.api_key && v.api_secret);
  }

  function hasInvalidEnabledApi(obj){
    return enabledList(obj).some(([_, v]) => !v.api_key || !v.api_secret);
  }

  function mask(v){
    const s = String(v || "");
    if(!s) return "미등록";
    if(s.length <= 8) return "••••";
    return s.slice(0,4) + "••••" + s.slice(-4);
  }

  function productLabel(p){
    return ({VIP:"VIP 👑",SEMI:"VIP Lite 반자동 🤖",AUTO:"VIP Pro 자동 🚀"})[p] || p || "-";
  }

  function statusLabel(s){
    return ({PENDING:"승인대기",APPROVED:"승인완료",REJECTED:"거절"})[s] || s || "-";
  }

  function apiSummary(apiObj){
    const labels = {
      upbit:"업비트",
      bithumb:"빗썸",
      mexc:"MEXC",
      gate:"Gate.io",
      bitget:"Bitget",
      bingx:"BingX"
    };
    const rows = Object.entries(apiObj || {})
      .filter(([_, v]) => v && v.enabled)
      .map(([k, v]) => `${labels[k] || k}: ${mask(v.api_key)} / ${mask(v.api_secret)}`);
    return rows.length ? rows.join("<br>") : "미등록";
  }

  function dateText(v){
    if(!v) return "-";
    try{ return new Date(v).toLocaleString("ko-KR"); }
    catch(e){ return v; }
  }

  // payment.html 등록 신청: Supabase kedge_requests에 저장
  window.submitVipRequest = async function(){
    const db = getDb();
    if(!db) return;

    const user = await getUserSafe();
    if(!user || !user.email){
      return msg("vipRequestMsg", "❌ 로그인 후 등록 신청할 수 있습니다.");
    }

    const product = val("productSelect") || "VIP";
    const payType = val("payType") || "USDT";
    const payName = val("payName");
    const memo = val("txidInput");
    const tgBotToken = val("payBotToken");
    const tgChatId = val("payChatId");
    const apis = collectApis();

    if(!payName) return msg("vipRequestMsg", "❌ 입금자명 또는 보내는 사람 이름을 입력해주세요.");
    if(!memo) return msg("vipRequestMsg", "❌ TxID / 입금 메모 / 확인용 내용을 입력해주세요.");

    if(isBotProduct(product)){
      if(!tgBotToken || !tgChatId){
        return msg("vipRequestMsg", "❌ 반자동/자동은 BOT TOKEN과 CHAT ID가 필요합니다.");
      }
      if(!hasValidEnabledApi(apis.domestic_apis)){
        return msg("vipRequestMsg", "❌ 국내 거래소 API를 1개 이상 입력해주세요.");
      }
      if(!hasValidEnabledApi(apis.foreign_apis)){
        return msg("vipRequestMsg", "❌ 해외 거래소 API를 1개 이상 입력해주세요.");
      }
      if(hasInvalidEnabledApi(apis.domestic_apis)){
        return msg("vipRequestMsg", "❌ 체크된 국내 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
      }
      if(hasInvalidEnabledApi(apis.foreign_apis)){
        return msg("vipRequestMsg", "❌ 체크된 해외 거래소는 KEY와 SECRET을 모두 입력해야 합니다.");
      }
    }

    const payload = {
      email: user.email,
      telegram: user.telegram || "미등록",
      product,
      pay_type: payType,
      pay_name: payName,
      memo,
      status: "PENDING",
      tg_bot_token: isBotProduct(product) ? tgBotToken : "",
      tg_chat_id: isBotProduct(product) ? tgChatId : "",
      domestic_apis: isBotProduct(product) ? apis.domestic_apis : {},
      foreign_apis: isBotProduct(product) ? apis.foreign_apis : {}
    };

    const { error } = await db.from("kedge_requests").insert(payload);
    if(error){
      console.error(error);
      return msg("vipRequestMsg", "❌ 신청 저장 실패: " + error.message);
    }

    msg("vipRequestMsg", "✅ 등록 신청 완료. 관리자 승인 후 이용 가능합니다.", "success");
    if(qs("payName")) qs("payName").value = "";
    if(qs("txidInput")) qs("txidInput").value = "";
  };

  async function loadRequestsFromDb(){
    const db = getDb();
    if(!db) return [];
    const { data, error } = await db
      .from("kedge_requests")
      .select("*")
      .order("created_at", { ascending:false });
    if(error){
      console.error(error);
      return [];
    }
    return data || [];
  }

  // admin.html 통계
  window.renderAdminStats = async function(){
    const box = qs("adminStats");
    if(!box) return;
    const rows = await loadRequestsFromDb();

    const pending = rows.filter(x=>x.status==="PENDING").length;
    const approved = rows.filter(x=>x.status==="APPROVED").length;
    const rejected = rows.filter(x=>x.status==="REJECTED").length;
    const vip = rows.filter(x=>x.status==="APPROVED" && x.product==="VIP").length;
    const semi = rows.filter(x=>x.status==="APPROVED" && x.product==="SEMI").length;
    const auto = rows.filter(x=>x.status==="APPROVED" && x.product==="AUTO").length;

    box.innerHTML = `
      <article><b>${pending}</b><span>승인 대기</span></article>
      <article><b>${approved}</b><span>승인 완료</span></article>
      <article><b>${rejected}</b><span>거절</span></article>
      <article><b>${vip}</b><span>VIP</span></article>
      <article><b>${semi}</b><span>반자동</span></article>
      <article><b>${auto}</b><span>자동</span></article>
    `;
  };

  // admin.html 신청 목록
  window.renderAdminRequests = async function(){
    const wrap = qs("adminRequestList");
    if(!wrap) return;

    const status = val("adminStatusFilter") || "ALL";
    const keyword = val("adminSearch").toLowerCase();
    let rows = await loadRequestsFromDb();

    if(status !== "ALL") rows = rows.filter(x => x.status === status);
    if(keyword){
      rows = rows.filter(x => JSON.stringify(x).toLowerCase().includes(keyword));
    }

    if(!rows.length){
      wrap.innerHTML = `<div class="admin-empty">신청 내역이 없습니다.</div>`;
      return;
    }

    wrap.innerHTML = rows.map(req => {
      const statusClass = String(req.status || "PENDING").toLowerCase();
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
            <p><small>신청시간</small><strong>${dateText(req.created_at)}</strong></p>
            <p><small>결제방식</small><strong>${req.pay_type || "-"}</strong></p>
            <p><small>입금자명</small><strong>${req.pay_name || "-"}</strong></p>
            <p><small>TxID/메모</small><strong>${req.memo || "-"}</strong></p>
            <p><small>BOT TOKEN</small><strong>${mask(req.tg_bot_token)}</strong></p>
            <p><small>CHAT ID</small><strong>${req.tg_chat_id || "미등록"}</strong></p>
            <p><small>국내 API</small><strong>${apiSummary(req.domestic_apis)}</strong></p>
            <p><small>해외 API</small><strong>${apiSummary(req.foreign_apis)}</strong></p>
          </div>

          <textarea id="adminNote-${req.id}" class="admin-note" placeholder="관리자 메모">${req.admin_note || ""}</textarea>

          <div class="admin-actions">
            <button class="ok" onclick="approveRequest('${req.id}')">승인</button>
            <button class="danger" onclick="rejectRequest('${req.id}')">거절</button>
            <button onclick="copyText('${req.email || ""}')">이메일 복사</button>
          </div>
        </article>
      `;
    }).join("");
  };

  window.renderAdminUsers = async function(){
    const wrap = qs("adminUserList");
    if(!wrap) return;

    let rows = await loadRequestsFromDb();
    rows = rows.filter(x=>x.status==="APPROVED");

    const keyword = val("adminUserSearch").toLowerCase();
    if(keyword){
      rows = rows.filter(x=>JSON.stringify(x).toLowerCase().includes(keyword));
    }

    if(!rows.length){
      wrap.innerHTML = `<div class="admin-empty">회원 정보가 없습니다.</div>`;
      return;
    }

    wrap.innerHTML = rows.map(u=>`
      <article class="admin-user-row">
        <div>
          <b>${u.email || "-"}</b>
          <p>${u.telegram || "미등록"} · ${productLabel(u.product)} · 승인일 ${dateText(u.approved_at)}</p>
        </div>
        <button onclick="copyText('${u.email || ""}')">이메일 복사</button>
      </article>
    `).join("");
  };

  window.approveRequest = async function(id){
    const db = getDb();
    if(!db) return;
    const note = val("adminNote-" + id);

    const { error } = await db
      .from("kedge_requests")
      .update({
        status:"APPROVED",
        approved_at:new Date().toISOString(),
        rejected_at:null,
        admin_note:note
      })
      .eq("id", id);

    if(error){
      console.error(error);
      return alert("승인 실패: " + error.message);
    }

    alert("승인 완료");
    await window.renderAdminPage();
  };

  window.rejectRequest = async function(id){
    const db = getDb();
    if(!db) return;
    const note = val("adminNote-" + id);

    const { error } = await db
      .from("kedge_requests")
      .update({
        status:"REJECTED",
        rejected_at:new Date().toISOString(),
        admin_note:note
      })
      .eq("id", id);

    if(error){
      console.error(error);
      return alert("거절 실패: " + error.message);
    }

    alert("거절 완료");
    await window.renderAdminPage();
  };

  window.exportAdminData = async function(){
    const rows = await loadRequestsFromDb();
    const blob = new Blob([JSON.stringify(rows,null,2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "kedge_requests_backup.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  window.renderAdminPage = async function(){
    const loginBox = qs("adminLoginBox");
    const app = qs("adminApp");
    if(!loginBox || !app) return;

    if(typeof window.isAdminLoggedIn === "function" && !window.isAdminLoggedIn()){
      loginBox.style.display = "block";
      app.style.display = "none";
      return;
    }

    loginBox.style.display = "none";
    app.style.display = "block";

    await window.renderAdminStats();
    await window.renderAdminRequests();
    await window.renderAdminUsers();
  };

  document.addEventListener("DOMContentLoaded", ()=>{
    const page = document.body?.dataset?.page;
    if(page === "admin"){
      setTimeout(()=>window.renderAdminPage && window.renderAdminPage(), 150);
      qs("adminStatusFilter")?.addEventListener("change", window.renderAdminRequests);
      qs("adminSearch")?.addEventListener("input", window.renderAdminRequests);
      qs("adminUserSearch")?.addEventListener("input", window.renderAdminUsers);
    }
  });
})();
