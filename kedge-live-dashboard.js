(function(){
  const $ = (id) => document.getElementById(id);
  const fmtNum = (n) => Number(n || 0).toLocaleString('ko-KR');
  const fmtPct = (n) => {
    const v = Number(n || 0);
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  };
  const fmtTime = (v) => {
    if(!v) return '-';
    try{
      // 봇이 KST 문자열을 Supabase timestamptz에 넣으면 DB가 UTC로 해석해서
      // 브라우저에서 +9시간 밀려 보인다. 그래서 화면에는 UTC 시각 그대로 표시한다.
      const d = new Date(v);
      if(!isNaN(d.getTime())){
        const h = String(d.getUTCHours()).padStart(2, '0');
        const m = String(d.getUTCMinutes()).padStart(2, '0');
        const sec = String(d.getUTCSeconds()).padStart(2, '0');
        const ap = Number(h) < 12 ? '오전' : '오후';
        const hh12 = Number(h) % 12 || 12;
        return `${ap} ${String(hh12).padStart(2, '0')}:${m}:${sec}`;
      }
      return String(v);
    }catch(e){return String(v);}
  };

  const fmtKrwShort = (n) => {
    const v = Number(n || 0);
    if(!v) return '0원';
    if(v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '억';
    if(v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '만';
    return fmtNum(v) + '원';
  };



  function firstNumber(row, keys){
    if(!row) return null;
    for(const k of keys){
      if(Object.prototype.hasOwnProperty.call(row, k)){
        const raw = row[k];
        if(raw !== null && raw !== undefined && raw !== ''){
          const n = Number(raw);
          if(Number.isFinite(n)) return n;
        }
      }
    }
    return null;
  }

  function valueOrDash(v){
    return (v === null || v === undefined || !Number.isFinite(Number(v))) ? '-' : fmtPct(v);
  }

  function getRealEdge(row){
    return firstNumber(row, [
      'real_edge_per',
      'real_edge_percent', 'real_edge', 'edge_percent', 'edge',
      'actual_edge_percent', 'actual_edge', 'net_edge_percent', 'net_edge'
    ]);
  }

  function getCoinGap(row){
    return firstNumber(row, [
      'coin_gap_percent', 'coin_gap',
      'price_gap_percent', 'price_gap',
      'price_premium_percent', 'price_premium',
      'premium_percent', 'premium',
      'basis_percent', 'basis',
      'coin_basis_percent', 'coin_basis',
      'gap_percent', 'gap',
      'kimchi_premium_percent', 'kimchi_premium'
    ]);
  }

  function getBtcGap(row){
    return firstNumber(row, [
      'btc_gap_percent', 'btc_gap',
      'btc_basis_percent', 'btc_basis',
      'btc_premium_percent', 'btc_premium',
      'market_gap_percent', 'market_gap',
      'btc_impact_percent', 'btc_impact'
    ]);
  }

  function getExecutableKrw(row){
    return firstNumber(row, [
      'executable_kr',
      'executable_krw', 'final_entry_krw', 'entry_krw', 'amount_krw',
      'domestic_entry_krw', 'foreign_entry_krw', 'krw'
    ]) || 0;
  }

  function setStatus(text, ok){
    const el = $('kedgeLiveStatus');
    if(!el) return;
    el.textContent = text;
    el.className = 'kedge-live-status' + (ok ? '' : ' off');
  }

  function kstDateKey(v){
    try{
      return new Date(v).toLocaleDateString('sv-SE', { timeZone:'Asia/Seoul' });
    }catch(e){ return ''; }
  }

  function isToday(v){
    if(!v) return false;
    return kstDateKey(v) === kstDateKey(new Date());
  }

  function eventType(row){
    return String((row && (row.event_type || row.status)) || '').toUpperCase();
  }

  function isEntryEvent(row){
    const t = eventType(row);
    return t === 'ENTRY_SUCCESS' || t === 'AUTO_ENTRY_SUCCESS' || t === 'ENTRY_OPEN' || t === 'OPEN_SUCCESS';
  }

  function isTpEvent(row){
    const t = eventType(row);
    return (
      t === 'TP_SUCCESS' ||
      t === 'AUTO_CLOSED' ||
      t === 'TAKE_PROFIT' ||
      t === 'TAKE_PROFIT_SUCCESS' ||
      t === 'PROFIT_CLOSED' ||
      t === 'CLOSE_SUCCESS'
    );
  }

  function renderSummary(row, rows){
    const list = Array.isArray(rows) ? rows : [];
    const todayRows = list.filter(r => isToday(r.created_at));
    const entryCountFromEvents = todayRows.filter(isEntryEvent).length;
    const tpCountFromEvents = todayRows.filter(isTpEvent).length;

    if($('liveBotStatus')) $('liveBotStatus').textContent = (row && row.bot_status) || 'RUNNING';
    if($('liveTodayEntries')) {
      const v = Math.max(Number((row && row.today_entries) || 0), entryCountFromEvents);
      $('liveTodayEntries').textContent = fmtNum(v) + '건';
    }
    if($('liveTodayTp')) {
      const v = Math.max(Number((row && row.today_tp) || 0), tpCountFromEvents);
      $('liveTodayTp').textContent = fmtNum(v) + '건';
    }
    if($('liveLastScan')) $('liveLastScan').textContent = fmtTime((row && (row.last_scan_at || row.updated_at)) || (list[0] && list[0].created_at));
  }

  function renderTopStats(summary, rows){
    const cards = document.querySelectorAll('.stats-panel article');
    if(!cards || cards.length < 4) return;

    const list = Array.isArray(rows) ? rows : [];
    const todayRows = list.filter(r => isToday(r.created_at));
    const publicTodayRows = todayRows.filter(isPublicEvent);
    const candidateCount = todayRows.filter(r => eventType(r) === 'CANDIDATE').length;
    const tpCountFromEvents = todayRows.filter(isTpEvent).length;

    const edgeSource = (publicTodayRows.length ? publicTodayRows : list.filter(isPublicEvent));
    let maxEdge = 0;
    edgeSource.forEach(r => { maxEdge = Math.max(maxEdge, getRealEdge(r) || 0); });

    const latestPublic = list.find(isPublicEvent) || null;
    const latestKrw = latestPublic ? getExecutableKrw(latestPublic) : 0;
    const todayTp = Number((summary && summary.today_tp) || 0) || tpCountFromEvents;

    const items = [
      { title:'오늘 후보', value:fmtNum(candidateCount) + '건', sub:'실시간 감지 누적' },
      { title:'최고 엣지', value:fmtPct(maxEdge), sub:'오늘 공개 이벤트 기준' },
      { title:'최근 실체결', value:fmtKrwShort(latestKrw), sub:'호가벽 기반 가능금액' },
      { title:'오늘 익절', value:fmtNum(todayTp) + '건', sub:'청산 완료 기준' }
    ];

    cards.forEach((card, i) => {
      const item = items[i];
      if(!item) return;
      const p = card.querySelector('p');
      const b = card.querySelector('b');
      const small = card.querySelector('small');
      if(p) p.textContent = item.title;
      if(b) b.textContent = item.value;
      if(small) small.textContent = item.sub;
    });
  }

  function statusText(s){
    const m = {
      CANDIDATE:'후보', ENTRY_SUCCESS:'진입성공', ENTRY_FAIL:'진입실패', TP_SUCCESS:'익절완료', AUTO_CLOSED:'익절완료', TAKE_PROFIT:'익절완료', TAKE_PROFIT_SUCCESS:'익절완료', CLOSE_SUCCESS:'청산완료', SL_WARNING:'위험경고', STOPPED:'정지'
    };
    return m[s] || s || '-';
  }

  function statusClass(s){
    if(String(s).includes('SUCCESS') || s === 'CANDIDATE') return 'up';
    if(String(s).includes('FAIL') || String(s).includes('STOP')) return 'bad';
    return 'warn';
  }

  // 공개 홈페이지에는 후보/진입성공/익절완료만 표시한다.
  // ENTRY_FAIL 등 운영 로그는 Supabase DB에는 저장하되 화면에서는 숨긴다.
  const PUBLIC_EVENT_TYPES = new Set(['CANDIDATE', 'ENTRY_SUCCESS', 'TP_SUCCESS', 'AUTO_CLOSED', 'TAKE_PROFIT', 'TAKE_PROFIT_SUCCESS', 'CLOSE_SUCCESS']);

  function isPublicEvent(row){
    return PUBLIC_EVENT_TYPES.has(eventType(row));
  }

  function renderHeroCandidate(rows){
    const list = Array.isArray(rows) ? rows : [];
    const latest = list.find(r => eventType(r) === 'CANDIDATE') || list.find(isPublicEvent);
    if(!latest) return;

    const symbol = latest.symbol || latest.coin || '-';
    const domestic = latest.domestic_exchange || latest.domestic_exch || latest.domestic || '-';
    const foreign = latest.foreign_exchange || latest.foreign_excha || latest.foreign || '-';
    let realEdge = getRealEdge(latest);
    let coinGap = getCoinGap(latest);
    let btcGap = getBtcGap(latest);
    const executable = getExecutableKrw(latest);

    // real_edge = 가격괴리 - BTC괴리. 저장 필드가 하나 빠진 경우 화면에서 역산해 보강한다.
    if(coinGap === null && realEdge !== null && btcGap !== null) coinGap = realEdge + btcGap;
    if(btcGap === null && coinGap !== null && realEdge !== null) btcGap = coinGap - realEdge;
    if(realEdge === null && coinGap !== null && btcGap !== null) realEdge = coinGap - btcGap;
    if(realEdge === null) realEdge = 0;

    const setText = (id, value) => { const el = $(id); if(el) el.textContent = value; };
    setText('liveHeroLabel', statusText(eventType(latest) || 'CANDIDATE'));
    setText('liveHeroEdge', fmtPct(realEdge));
    setText('liveHeroTitle', `⚖️ ${symbol} 양방 자동 후보`);
    setText('liveHeroRoute', `${domestic} ↔ ${foreign}`);
    setText('liveHeroRealEdge', fmtPct(realEdge));
    setText('liveHeroExecutable', fmtKrwShort(executable));
  }

  function renderRows(rows){
    const wrap = $('kedgeLiveRows');
    if(!wrap) return;
    const publicRows = (Array.isArray(rows) ? rows : []).filter(isPublicEvent).slice(0, 12);
    if(!publicRows.length){
      wrap.innerHTML = '<div class="kedge-live-empty">아직 표시할 공개 LIVE 이벤트가 없습니다.</div>';
      return;
    }
    wrap.innerHTML = `
      <div class="kedge-live-row head"><span>시간</span><span>코인</span><span>국내</span><span>해외</span><span>실제엣지</span><span>실체결</span><span>상태</span></div>
      ${publicRows.map(r => `
        <div class="kedge-live-row">
          <span>${fmtTime(r.created_at)}</span>
          <span>${r.symbol || r.coin || '-'}</span>
          <span>${r.domestic_exchange || r.domestic_exch || r.domestic || '-'}</span>
          <span>${r.foreign_exchange || r.foreign_excha || r.foreign || '-'}</span>
          <span class="${(getRealEdge(r) || 0) >= 2 ? 'up' : 'warn'}">${fmtPct(getRealEdge(r) || 0)}</span>
          <span>${fmtNum(getExecutableKrw(r))}원</span>
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
      let summary = null;
      const { data: summaryRows, error: sErr } = await db.from('kedge_live_summary').select('*').limit(10);
      if(!sErr && Array.isArray(summaryRows) && summaryRows.length){
        summary =
          summaryRows.find(r => String(r.id) === 'main') ||
          summaryRows.find(r => String(r.id) === '1') ||
          summaryRows[0];
      }

      const { data: events, error: eErr } = await db.from('kedge_live_events').select('*').order('created_at', {ascending:false}).limit(200);
      if(eErr) throw eErr;
      renderSummary(summary, events || []);
      renderTopStats(summary, events || []);
      renderHeroCandidate(events || []);
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
