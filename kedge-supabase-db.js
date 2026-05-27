/* K-EDGE Supabase DB Bridge FINAL
   - AUTO 전용
   - 등록 신청 전 기본 검증
   - BANK는 TxID 필수 아님 / USDT는 TxID 필수
   - 빗썸 + 해외선물 API 입력 검증
   - 관리자 승인 시 텔레그램 테스트 메시지 발송 후 승인
*/
(function(){
  const SUPABASE_URL = "https://qakhbihueonefzifrmct.supabase.co";
  const SUPABASE_ANON_KEY = "sb_publishable_XboBFueAITcieSL75B2S5g_qlm4XmOm";

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

  async function getUserSafe(){
    if(typeof window.getCurrentUser === "function"){
      try{
        const u = await window.getCurrentUser();
        if(u && u.email) return u;
      }catch(e){}
    }

    const d = getDb();
    if(d){
      try{
        const { data } = await d.auth.getUser();
        if(data && data.user){
          return {
            email: data.user.email,
            telegram: data.user.user_metadata?.telegram || "미등록"
          };
        }
      }catch(e){}
    }

    try{
      return JSON.parse(localStorage.getItem("kedge_local_user") || "null");
    }catch(e){
      return null;
    }
  }

  function readApi(checkboxId, keyId, secretId){
    return {
      enabled: !!qs(checkboxId)?.checked,
      api_key: val(keyId),
      api_secret: val(secretId)
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

  function collectApis(){
    return {
      domestic_apis:{
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

  function getReferralUidData(){
    return {
      mexc: { enabled: !!qs("refMexcUse")?.checked, uid: val("refMexcUid") },
      bitget: { enabled: !!qs("refBitgetUse")?.checked, uid: val("refBitgetUid") },
      bingx: { enabled: !!qs("refBingxUse")?.checked, uid: val("refBingxUid") },
      gate: { enabled: !!qs("refGateUse")?.checked, uid: val("refGateUid") }
    };
  }

  function getReferralCount(){
    return Math.min(Object.values(getReferralUidData()).filter(x => x.enabled && x.uid).length, 4);
  }

  function validateTelegramInput(token, chatId){
    if(!token) return "❌ BOT TOKEN을 입력해주세요.";
    if(!/^\d{6,}:[A-Za-z0-9_-]{20,}$/.test(token)){
      return "❌ BOT TOKEN 형식이 올바르지 않습니다.";
    }
    if(!chatId) return "❌ CHAT ID를 입력해주세요.";
    if(!/^-?\d+$/.test(chatId)){
      return "❌ CHAT ID는 숫자 형식이어야 합니다. 개인 DM chat_id를 입력해주세요.";
    }
    return "";
  }

  function validateApiBasic(apis){
    if(!hasValidEnabledApi(apis.domestic_apis)){
      return "❌ 빗썸 API KEY와 SECRET을 입력해주세요.";
    }
    if(!hasValidEnabledApi(apis.foreign_apis)){
      return "❌ 해외 거래소 API를 1개 이상 입력해주세요.";
    }
    if(hasInvalidEnabledApi(apis.domestic_apis)){
      return "❌ 체크된 국내 거래소는 KEY와 SECRET을 모두 입력해야 합니다.";
    }
    if(hasInvalidEnabledApi(apis.foreign_apis)){
      return "❌ 체크된 해외 거래소는 KEY와 SECRET을 모두 입력해야 합니다.";
    }

    const all = [...enabledList(apis.domestic_apis), ...enabledList(apis.foreign_apis)];
    for(const [name, v] of all){
      if(String(v.api_key).length < 4 || String(v.api_secret).length < 4){
        return `❌ ${name.toUpperCase()} API KEY 또는 SECRET이 너무 짧습니다.`;
      }
    }
    return "";
  }

  function mask(v){
    const s = String(v || "");
    if(!s) return "미등록";
    if(s.length <= 8) return "••••";
    return s.slice(0,4) + "••••" + s.slice(-4);
  }

  function productLabel(p){
    return ({AUTO:"K-EDGE AUTO 🚀"})[p] || p || "-";
  }

  function statusLabel(s){
    return ({PENDING:"승인대기",APPROVED:"승인완료",REJECTED:"거절"})[s] || s || "-";
  }

  function apiSummary(apiObj){
    const labels = { bithumb:"빗썸", mexc:"MEXC", gate:"Gate.io", bitget:"Bitget", bingx:"BingX" };
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

  async function sendTelegramTest(botToken, chatId, mode){
    const text = mode === "approval"
      ? "🎉 K-EDGE AUTO 승인 완료\n\n텔레그램 알람이 활성화되었습니다.\n\n현재 상태\n알람 : ON\n자동매매 : OFF\n\n홈페이지 AUTO 설정에서 운용금액 / 분할 / 자동매매 ON/OFF를 설정해주세요."
      : "✅ K-EDGE 텔레그램 연결 테스트 성공\n\nBOT TOKEN / CHAT ID 연결이 확인되었습니다.";

    const url = `https://api.telegram.org/bot${encodeURIComponent(botToken)}/sendMessage`;
    try{
      const res = await fetch(url, {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ chat_id: chatId, text })
      });
      const data = await res.json().catch(()=>null);
      if(!res.ok || !data || data.ok !== true){
        return { ok:false, error:(data && data.description) ? data.description : "Telegram sendMessage failed" };
      }
      return { ok:true };
    }catch(e){
      return { ok:false, error:e.message || String(e) };
    }
  }

  async function insertRequest(payload){
    const d = getDb();
    if(!d) return { error:{ message:"Supabase 연결 실패" } };

    // 1차: 확장 컬럼 포함 저장
    let res = await d.from("kedge_requests").insert(payload);
    if(!res.error) return res;

    // 스키마 컬럼이 아직 없으면 최소 컬럼으로 재시도
    const msg = String(res.error.message || "");
    if(msg.includes("schema cache") || msg.includes("column")){
      const minimal = {
        email: payload.email,
        telegram: payload.telegram,
        product: payload.product,
        pay_type: payload.pay_type,
        pay_name: payload.pay_name,
        memo: payload.memo,
        status: payload.status,
        tg_bot_token: payload.tg_bot_token,
        tg_chat_id: payload.tg_chat_id,
        domestic_apis: payload.domestic_apis,
        foreign_apis: payload.foreign_apis
      };
      return await d.from("kedge_requests").insert(minimal);
    }

    return res;
  }

  // payment.html 등록 신청
  window.submitVipRequest = async function(){
    const user = await getUserSafe();
    if(!user || !user.email){
      return msg("vipRequestMsg", "❌ 로그인 후 등록 신청할 수 있습니다.");
    }

    const product = "AUTO";
    const payType = val("payType") || "USDT";
    const payName = val("payName");
    const memo = val("txidInput");
    const tgBotToken = val("payBotToken");
    const tgChatId = val("payChatId");
    const telegramId = val("payTelegramId");
    const apis = collectApis();

    if(!payName) return msg("vipRequestMsg", "❌ 입금자명 또는 보내는 사람 이름을 입력해주세요.");
    if(payType !== "BANK" && !memo) return msg("vipRequestMsg", "❌ TxID / 입금 메모 / 확인용 내용을 입력해주세요.");

    const tgErr = validateTelegramInput(tgBotToken, tgChatId);
    if(tgErr) return msg("vipRequestMsg", tgErr);

    const apiErr = validateApiBasic(apis);
    if(apiErr) return msg("vipRequestMsg", apiErr);

    msg("vipRequestMsg", "🔄 신청 정보 확인 중...", "success");

    const referral_count = getReferralCount();
    const referral_discount_percent = referral_count * 10;
    const base_price_krw = 200000;
    const final_price_krw = base_price_krw * (100 - referral_discount_percent) / 100;

    const payload = {
      email: user.email,
      telegram: telegramId || user.telegram || "미등록",
      product,
      pay_type: payType,
      pay_name: payName,
      memo: payType === "BANK" ? "" : memo,
      status: "PENDING",
      tg_bot_token: tgBotToken,
      tg_chat_id: tgChatId,
      domestic_apis: apis.domestic_apis,
      foreign_apis: apis.foreign_apis,
      referral_uids: getReferralUidData(),
      referral_count,
      referral_discount_percent,
      base_price_krw,
      final_price_krw
    };

    const { error } = await insertRequest(payload);
    if(error){
      console.error(error);
      return msg("vipRequestMsg", "❌ 신청 저장 실패: " + error.message);
    }

    msg("vipRequestMsg", "✅ AUTO 신청 완료. 관리자 승인 후 텔레그램 알람이 활성화됩니다.", "success");
    if(qs("payName")) qs("payName").value = "";
    if(qs("txidInput")) qs("txidInput").value = "";
  };

  async function loadRequestsFromDb(){
    const d = getDb();
    if(!d) return [];
    const { data, error } = await d
      .from("kedge_requests")
      .select("*")
      .order("created_at", { ascending:false });
    if(error){
      console.error(error);
      return [];
    }
    return data || [];
  }

  window.renderAdminStats = async function(){
    const box = qs("adminStats");
    if(!box) return;
    const rows = await loadRequestsFromDb();

    const pending = rows.filter(x=>x.status==="PENDING").length;
    const approved = rows.filter(x=>x.status==="APPROVED").length;
    const rejected = rows.filter(x=>x.status==="REJECTED").length;
    const auto = rows.filter(x=>x.status==="APPROVED" && x.product==="AUTO").length;

    box.innerHTML = `
      <article><b>${pending}</b><span>승인 대기</span></article>
      <article><b>${approved}</b><span>승인 완료</span></article>
      <article><b>${rejected}</b><span>거절</span></article>
      <article><b>${auto}</b><span>AUTO</span></article>
    `;
  };

  window.renderAdminRequests = async function(){
    const wrap = qs("adminRequestList");
    if(!wrap) return;

    const status = val("adminStatusFilter") || "ALL";
    const keyword = val("adminSearch").toLowerCase();
    let rows = await loadRequestsFromDb();

    if(status !== "ALL") rows = rows.filter(x => x.status === status);
    if(keyword) rows = rows.filter(x => JSON.stringify(x).toLowerCase().includes(keyword));

    if(!rows.length){
      wrap.innerHTML = `<div class="admin-empty">신청 내역이 없습니다.</div>`;
      return;
    }

    wrap.innerHTML = rows.map(req => {
      const statusClass = String(req.status || "PENDING").toLowerCase();
      const price = req.final_price_krw ? Number(req.final_price_krw).toLocaleString("ko-KR") + "원" : "-";
      const discount = req.referral_discount_percent ? req.referral_discount_percent + "%" : "0%";
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
            <p><small>최종금액</small><strong>${price}</strong></p>
            <p><small>추천인 할인</small><strong>${discount}</strong></p>
            <p><small>BOT TOKEN</small><strong>${mask(req.tg_bot_token)}</strong></p>
            <p><small>CHAT ID</small><strong>${req.tg_chat_id || "미등록"}</strong></p>
            <p><small>국내 API</small><strong>${apiSummary(req.domestic_apis)}</strong></p>
            <p><small>해외 API</small><strong>${apiSummary(req.foreign_apis)}</strong></p>
          </div>

          <textarea id="adminNote-${req.id}" class="admin-note" placeholder="관리자 메모">${req.admin_note || ""}</textarea>

          <div class="admin-actions">
            <button class="ok" onclick="approveRequest('${req.id}')">승인 + 텔레그램 테스트</button>
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
    if(keyword) rows = rows.filter(x=>JSON.stringify(x).toLowerCase().includes(keyword));

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
    const d = getDb();
    if(!d) return;
    const note = val("adminNote-" + id);

    const { data, error:readError } = await d
      .from("kedge_requests")
      .select("*")
      .eq("id", id)
      .limit(1);

    if(readError || !data || !data.length){
      console.error(readError);
      return alert("신청 내역을 찾을 수 없습니다.");
    }

    const req = data[0];

    const tgErr = validateTelegramInput(req.tg_bot_token, req.tg_chat_id);
    if(tgErr){
      return alert("승인 불가: " + tgErr);
    }

    const test = await sendTelegramTest(req.tg_bot_token, req.tg_chat_id, "approval");
    if(!test.ok){
      return alert("승인 불가: 텔레그램 연결 실패\n" + test.error);
    }

    const { error } = await d
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

    alert("승인 완료 + 텔레그램 알림 발송 완료");
    await window.renderAdminPage();
  };

  window.rejectRequest = async function(id){
    const d = getDb();
    if(!d) return;
    const note = val("adminNote-" + id);

    const { error } = await d
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
