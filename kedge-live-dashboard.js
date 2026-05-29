(function(){
  const $ = (id) => document.getElementById(id);
  const fmtNum = (n) => Number(n || 0).toLocaleString('ko-KR');
  const fmtPct = (n) => {
    const v = Number(n || 0);
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  };
  const fmtTime = (v) => {
    if(!v) return '-';
    try{return new Date(v).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit', second:'2-digit'});}catch(e){return String(v);}
  };

  function setStatus(text, ok){
    const el = $('kedgeLiveStatus');
    if(!el) return;
    el.textContent = text;
    el.className = 'kedge-live-status' + (ok ? '' : ' off');
  }

  function renderSummary(row){
    if(!row) return;
    if($('liveBotStatus')) $('liveBotStatus').textContent = row.bot_status || '대기';
    if($('liveTodayEntries')) $('liveTodayEntries').textContent = fmtNum(row.today_entries) + '건';
    if($('liveTodayTp')) $('liveTodayTp').textContent = fmtNum(row.today_tp) + '건';
    if($('liveLastScan')) $('liveLastScan').textContent = fmtTime(row.last_scan_at || row.updated_at);
  }

  function statusText(s){
    const m = {
      CANDIDATE:'후보', ENTRY_SUCCESS:'진입성공', ENTRY_FAIL:'진입실패', TP_SUCCESS:'익절완료', TP_FAIL:'익절실패', SL_WARNING:'위험경고', SL_STRONG_WARNING:'강경고', STOPPED:'정지'
    };
    return m[s] || s || '-';
  }

  function statusClass(s){
    if(String(s).includes('SUCCESS') || s === 'CANDIDATE') return 'up';
    if(String(s).includes('FAIL') || String(s).includes('STOP')) return 'bad';
    return 'warn';
  }

  function renderRows(rows){
    const wrap = $('kedgeLiveRows');
    if(!wrap) return;
    if(!rows || !rows.length){
      wrap.innerHTML = '<div class="kedge-live-empty">아직 표시할 실시간 이벤트가 없습니다.</div>';
      return;
    }
    wrap.innerHTML = `
      <div class="kedge-live-row head"><span>시간</span><span>코인</span><span>국내</span><span>해외</span><span>실제엣지</span><span>실체결</span><span>상태</span></div>
      ${rows.map(r => `
        <div class="kedge-live-row">
          <span>${fmtTime(r.created_at)}</span>
          <span>${r.symbol || '-'}</span>
          <span>${r.domestic_exchange || '-'}</span>
          <span>${r.foreign_exchange || '-'}</span>
          <span class="${Number(r.real_edge_percent || 0) >= 2 ? 'up' : 'warn'}">${fmtPct(r.real_edge_percent)}</span>
          <span>${fmtNum(r.executable_krw)}원</span>
          <span class="${statusClass(r.event_type || r.status)}">${statusText(r.event_type || r.status)}</span>
        </div>
      `).join('')}
    `;
  }

  async function loadLive(){
    if(!window.supabase){ setStatus('Supabase 로드 실패', false); return; }
    const url = window.KEDGE_SUPABASE_URL;
    const key = window.KEDGE_SUPABASE_ANON_KEY;
    if(!url || !key){ setStatus('연동 설정 없음', false); return; }
    const db = window.supabase.createClient(url, key);

    try{
      const { data: summary, error: sErr } = await db.from('kedge_live_summary').select('*').eq('id','main').maybeSingle();
      if(!sErr && summary) renderSummary(summary);

      const { data: events, error: eErr } = await db.from('kedge_live_events').select('*').order('created_at', {ascending:false}).limit(12);
      if(eErr) throw eErr;
      renderRows(events || []);
      setStatus('실시간 연동 ON', true);
    }catch(err){
      console.warn('[K-EDGE LIVE] table not ready or read failed:', err.message || err);
      setStatus('DB 테이블 대기', false);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    if(!$('kedgeLiveRows')) return;
    loadLive();
    setInterval(loadLive, 10000);
  });
})();
