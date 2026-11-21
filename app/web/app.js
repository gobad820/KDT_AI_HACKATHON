/* 남는 돈 비교: 화면 3단계. 바닐라 JS. 서버 문자열은 모두 textContent로만 넣는다(innerHTML 사용 안 함). */
(function () {
  'use strict';

  var params = new URLSearchParams(location.search);
  var MOCK = params.has('mock');
  var MAX_CHARS = 8000;

  var SCENARIOS = [
    { id: 'none', label: '감면 없음' },
    { id: 'current_law', label: '현행법' },
    { id: 'proposal_base', label: '정부안(우대지역 아님)' },
    { id: 'proposal_pref', label: '정부안(우대지역으로 지정될 때)' }
  ];
  var EMP_OPTS = [['regular', '정규직'], ['contract', '계약직'], ['intern', '인턴'], ['daily', '일용직'], ['unknown', '모름']];
  var SIZE_OPTS = [['sme', '중소기업'], ['mid', '중견기업'], ['large', '대기업'], ['public', '공공기관'], ['unknown', '모름']];
  var STATUS_LABEL = { extracted: '추출됨', inferred: '추정', missing: '없음', user: '직접 입력' };
  var RULE_LABEL = { age: '나이', company_size: '회사 규모', industry: '업종', employment_type: '고용 형태', prior_relief: '감면 이력' };
  var RESULT_LABEL = { pass: '충족', fail: '미충족', unknown: '확인 필요' };
  var TRACE_LABEL = { extract: '읽기', question: '질문', tool_call: '도구 호출', decision: '판단', explain: '설명' };
  var ELIG_LABEL = { likely: '대상일 가능성 높음', uncertain: '불확실', unlikely: '대상 아닐 가능성 높음' };
  var SCOPE_LABEL = { sgg: '최근 6개월 기준', sgg_12m: '최근 12개월 기준', sido: '시도 전체 기준' };

  /* profile 질문 폴백(서버가 질문을 주지 않는 직접 입력 모드용) */
  var FALLBACK_PROFILE_QS = [
    { id: 'p1', postingId: null, field: 'profile.age', text: '근로계약을 맺는 시점의 만 나이를 알려주세요.', inputType: 'number', options: null, required: true },
    { id: 'p2', postingId: null, field: 'profile.militaryServiceMonths', text: '병역을 마쳤다면 복무 기간을 개월 수로 적어 주세요. 해당이 없으면 0입니다.', inputType: 'number', options: null, required: false },
    { id: 'p3', postingId: null, field: 'profile.hireYear', text: '입사 예정 시기를 알려주세요.', inputType: 'select', options: [{ value: 2026, label: '2026년 안' }, { value: 2027, label: '2027년 이후' }], required: true },
    { id: 'p4', postingId: null, field: 'profile.priorRelief', text: '중소기업 취업자 소득세 감면을 받은 적이 있나요?', inputType: 'select', options: [{ value: 'no', label: '없음' }, { value: 'yes', label: '있음' }, { value: 'unknown', label: '모름' }], required: false }
  ];

  var state;
  function freshState() {
    return {
      samples: [], extract: null, manual: false, model: {}, profileQs: [], profileVals: {},
      extraQs: [], earlyTrace: [], horizon: 5, lastReq: null, result: null, names: {}, tab: 'current_law', step: 1,
      skipped: false, assumed: []
    };
  }
  state = freshState();
  var ui = { rows: {}, qsync: {}, housing: {}, nonTaxInput: {} };

  /* ---------- 도우미 ---------- */
  function $(id) { return document.getElementById(id); }
  function h(tag, props, kids) {
    var e = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v === null || v === undefined || v === false) return;
        if (k === 'class') e.className = v;
        else if (k === 'text') e.textContent = v;
        else if (k === 'on') Object.keys(v).forEach(function (ev) { e.addEventListener(ev, v[ev]); });
        else if (k === 'value') e.value = v;
        else if (k === 'checked') e.checked = !!v;
        else if (k === 'disabled') e.disabled = !!v;
        else e.setAttribute(k, v === true ? '' : String(v));
      });
    }
    add(e, kids);
    return e;
  }
  function add(e, kids) {
    if (kids === null || kids === undefined || kids === false) return;
    if (Array.isArray(kids)) { kids.forEach(function (k) { add(e, k); }); return; }
    if (typeof kids === 'string' || typeof kids === 'number') e.appendChild(document.createTextNode(String(kids)));
    else e.appendChild(kids);
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  var nf = new Intl.NumberFormat('ko-KR');
  function won(n) { return nf.format(Math.round(n)) + '원'; }
  function manVal(n) { var v = Math.round(n / 10000); return v === 0 ? 0 : v; }
  function man(n) { return nf.format(manVal(n)) + '만 원'; }
  function money(n, cls) { return h('span', { class: 'num' + (cls ? ' ' + cls : ''), title: won(n), text: man(n) }); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function badge(text, cls) { return h('span', { class: 'badge' + (cls ? ' ' + cls : ''), text: text }); }
  function jobName(id) { var n = state.names[id]; return '공고 ' + id + (n ? '(' + n + ')' : ''); }
  function safeUrl(u) { return typeof u === 'string' && /^https?:\/\//i.test(u) ? u : null; }
  function label(opts, v) { for (var i = 0; i < opts.length; i++) if (opts[i][0] === v) return opts[i][1]; return String(v); }

  function showMsg(id, content, kind) {
    var m = $(id);
    clear(m);
    m.className = 'msg' + (kind ? ' ' + kind : '');
    add(m, content);
    m.hidden = false;
  }
  function hideMsg(id) { var m = $(id); m.hidden = true; clear(m); }
  var busyTimers = {};
  function busy(n, phrases) {
    var b = $('busy' + n);
    var t = b.querySelector ? b.querySelector('.busytext') : null;
    stopBusyTimers(n);
    b.hidden = false;
    var i = 0;
    function set() { if (t) t.textContent = phrases[Math.min(i, phrases.length - 1)] + '…'; }
    set();
    busyTimers[n] = setInterval(function () { i++; set(); }, 6000);
  }
  function stopBusyTimers(n) { if (busyTimers[n]) { clearInterval(busyTimers[n]); busyTimers[n] = null; } }
  function unbusy(n) { stopBusyTimers(n); $('busy' + n).hidden = true; }
  function setButtons(ids, disabled) { ids.forEach(function (id) { $(id).disabled = disabled; }); }

  function setStep(n) {
    state.step = n;
    [1, 2, 3].forEach(function (i) { $('step' + i).hidden = i !== n; });
    var items = $('stepper').children;
    for (var i = 0; i < items.length; i++) {
      items[i].className = (i + 1 === n) ? 'on' : (i + 1 < n ? 'done' : '');
    }
    if (window.scrollTo) window.scrollTo(0, 0);
  }

  /* ---------- API ---------- */
  function api(method, path, body) {
    if (MOCK) {
      return window.MockApi.request(method, path, body).then(function (r) { return { status: r.status, data: r.data }; });
    }
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 70000) : null;
    var opts = { method: method, headers: {} };
    if (ctl) opts.signal = ctl.signal;
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch(path, opts).then(function (res) {
      return res.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        return { status: res.status, data: data };
      });
    }).then(function (r) { if (timer) clearTimeout(timer); return r; }, function (err) {
      if (timer) clearTimeout(timer);
      return { status: 0, data: null, networkError: (err && err.name === 'AbortError') ? 'timeout' : 'network' };
    });
  }
  function netMessage(r) {
    if (r.networkError === 'timeout') return '서버 응답이 너무 오래 걸립니다. 잠시 뒤 다시 시도해 주세요.';
    if (r.networkError) return '서버에 연결하지 못했습니다. 네트워크 상태를 확인하고 다시 시도해 주세요.';
    return '서버 응답을 읽지 못했습니다(HTTP ' + r.status + '). 잠시 뒤 다시 시도해 주세요.';
  }

  /* ---------- 1 입력 ---------- */
  function initStep1() {
    ['A', 'B'].forEach(function (id) {
      var ta = $('text' + id);
      var upd = function () {
        var n = ta.value.length;
        $('count' + id).textContent = nf.format(n);
        $('count' + id).parentNode.className = 'count' + (n >= MAX_CHARS ? ' full' : '');
      };
      ta.addEventListener('input', function () { upd(); if (document.activeElement !== ta) renderPostView(id); });
      ta.addEventListener('blur', function () { renderPostView(id); });
      var view = $('view' + id), edit = function () { view.hidden = true; ta.hidden = false; ta.focus(); };
      view.addEventListener('click', edit);
      view.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); edit(); } });
      upd();
    });
    $('btnStart').addEventListener('click', onStart);
    api('GET', '/api/samples').then(function (r) {
      var box = $('sampleButtons');
      if (r.data && Array.isArray(r.data.samples)) {
        state.samples = r.data.samples;
        state.samples.forEach(function (s) {
          box.appendChild(h('button', { class: 'chip', type: 'button', text: s.title, on: { click: function () { fillSample(s); } } }));
        });
        if (!state.samples.length) box.textContent = '샘플이 없습니다';
      } else {
        box.textContent = '샘플 목록을 불러오지 못했습니다';
      }
    });
  }
  // 입력한 공고 원문을 감열 계산서처럼 정리해 보여 준다. 원문은 textarea에 그대로 있고, 누르면 고칠 수 있다
  var POST_MAX_LINES = 18;
  function renderPostView(id) {
    var ta = $('text' + id), view = $('view' + id), text = ta.value.trim();
    if (!text) { view.hidden = true; ta.hidden = false; return; }
    clear(view);
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var first = /^\[(.+?)\]\s*(.*)$/.exec(lines[0]);
    if (first) {
      view.appendChild(h('div', { class: 'rc-center rc-name', text: first[1] }));
      if (first[2]) view.appendChild(h('div', { class: 'rc-center', text: first[2] }));
      view.appendChild(h('div', { class: 'rc-rule', 'aria-hidden': 'true' }));
      lines = lines.slice(1);
    }
    lines.slice(0, POST_MAX_LINES).forEach(function (l) {
      var kv = /^([^:：]{1,14}?)\s*[:：]\s*(.+)$/.exec(l);
      if (kv && /급여|연봉|임금|월급/.test(kv[1])) view.appendChild(h('div', { class: 'rc-line pay' }, [h('span', { class: 'rc-l', text: kv[1] }), h('span', { class: 'rc-v' }, h('span', { class: 'hlv', text: kv[2] }))]));
      else if (kv) view.appendChild(rcLine(kv[1], kv[2]));
      else view.appendChild(h('div', { class: 'post-line', text: l }));
    });
    if (lines.length > POST_MAX_LINES) view.appendChild(h('div', { class: 'rc-note', text: '··· ' + nf.format(lines.length - POST_MAX_LINES) + '줄 더 있음' }));
    view.appendChild(h('div', { class: 'rc-note post-edit', text: '눌러서 고치기' }));
    view.hidden = false; ta.hidden = true;
  }
  function fillSample(s) {
    s.postings.forEach(function (p) {
      var ta = $('text' + p.id);
      if (ta) { ta.value = p.text; ta.dispatchEvent(new Event('input')); }
    });
    hideMsg('msg1');
    $('samples').classList.remove('flash');
  }
  function onStart() {
    hideMsg('msg1');
    $('samples').classList.remove('flash');
    var a = $('textA').value.trim(), b = $('textB').value.trim();
    if (!a || !b) { showMsg('msg1', '공고 A와 B를 모두 입력해 주세요.'); return; }
    if (a.length > MAX_CHARS || b.length > MAX_CHARS) { showMsg('msg1', '공고는 건당 8,000자까지 입력할 수 있습니다.'); return; }
    setButtons(['btnStart'], true);
    busy(1, ['공고를 읽는 중', '조건을 정리하는 중', '근무지를 찾는 중']);
    api('POST', '/api/extract', { postings: [{ id: 'A', text: a }, { id: 'B', text: b }] }).then(function (r) {
      unbusy(1);
      setButtons(['btnStart'], false);
      if (r.networkError || !r.data) { showMsg('msg1', netMessage(r)); return; }
      if (r.data.error) {
        var er = r.data.error;
        if (er.fallback === 'manual_input') { startManual(er.message); return; }
        showMsg('msg1', er.message || '요청을 처리하지 못했습니다.');
        if (er.fallback === 'sample_mode') {
          $('samples').classList.add('flash');
          $('msg1').appendChild(h('div', { text: '위의 샘플 버튼으로 저장된 예시를 볼 수 있습니다.' }));
        }
        return;
      }
      if (!Array.isArray(r.data.postings) || r.data.postings.length < 2) { showMsg('msg1', '서버 응답 형식이 올바르지 않습니다.'); return; }
      state = Object.assign(freshState(), { samples: state.samples });
      state.extract = r.data;
      state.earlyTrace = (r.data.trace || []).slice();
      buildModel(r.data);
      state.profileQs = (r.data.questions || []).filter(function (q) { return q.postingId === null || q.postingId === undefined; });
      if (!state.profileQs.length) state.profileQs = FALLBACK_PROFILE_QS;
      // 연봉과 근무지 시군구가 두 공고 모두에서 나오면 확인 화면 없이 바로 계산한다(가정은 결과 화면 맨 위에 보여 준다)
      state.skipped = canSkipConfirm();
      if (state.skipped) applyProfileDefaults();
      renderConfirm();
      if (state.skipped) {
        var c = collectRequest(true);
        if (!c.errs.length) {
          state.tab = 'current_law';
          setButtons(['btnStart'], true);
          runCompare(c.req, 1, function () { setButtons(['btnStart'], false); });
          return;
        }
        state.skipped = false;
      }
      setStep(2);
    });
  }

  // 내 정보 기본값: 서비스 대상(취업 준비 청년)의 흔한 경우. 결과 화면에 '가정'으로 밝히고 조건 고치기에서 바꾼다
  var PROFILE_DEFAULTS = { age: 27, militaryServiceMonths: 0, hireYear: 2027, priorRelief: 'no' };
  var PROFILE_LABEL = { age: '만 27세', militaryServiceMonths: '병역 0개월', hireYear: '2027년 이후 입사', priorRelief: '감면 받은 적 없음' };
  function canSkipConfirm() {
    if (state.manual) return false;
    return ['A', 'B'].every(function (pid) {
      var m = state.model[pid];
      return m && isNum(m.f.annualSalary.value) && m.f.annualSalary.value > 0 && /^\d{5}$/.test(m.sggCode || '');
    });
  }
  function applyProfileDefaults() {
    state.assumed = [];
    Object.keys(PROFILE_DEFAULTS).forEach(function (k) {
      if (state.profileVals[k] === undefined) { state.profileVals[k] = PROFILE_DEFAULTS[k]; state.assumed.push(k); }
    });
  }
  // 답을 받지 않고 계산했을 때 실제로 쓴 값
  function skippedAnswer(pid, field) {
    var m = state.model[pid];
    if (field === 'housing.mode') return m.housing.mode === 'dormitory' ? '→ 이용한다고 보고 주거비 0원으로 계산했습니다.' : '→ 이용하지 않는다고 보고 근무지 원룸 월세로 계산했습니다.';
    if (field === 'companySize') { var v = m.f.companySize.value; return !v || v === 'unknown' ? '→ 모름으로 계산했습니다. 그래서 감면 판정이 불확실로 나옵니다.' : '→ ' + optLabel(SIZE_OPTS, v) + '(으)로 계산했습니다.'; }
    if (field === 'proceed') return '→ 같은 조건이 이어진다고 보고 비교했습니다.';
    return '→ 공고에서 읽은 값으로 계산했습니다.';
  }
  function optLabel(opts, v) { var f = (opts || []).filter(function (o) { return o[0] === v; })[0]; return f ? f[1] : String(v); }

  // 결과 화면 맨 위: 확인 없이 계산했을 때 무엇을 가정했는지, AI가 무엇을 되물었는지
  function renderSkipped() {
    var card = h('div', { class: 'card assumed' });
    card.appendChild(h('div', { class: 'assumed-head' }, [
      h('div', null, [h('h2', { text: '확인 단계 없이 바로 계산했습니다' }),
        h('p', { class: 'hint', text: 'AI가 두 공고에서 연봉과 근무지를 찾았습니다. 아래 가정이 다르면 조건을 고쳐 다시 계산하세요.' })]),
      h('button', { type: 'button', class: 'primary', text: '조건 고치기', on: { click: function () { state.skipped = false; renderConfirm(); setStep(2); } } })
    ]));
    var ul = h('ul', { class: 'assumed-list' });
    if (state.assumed.length) ul.appendChild(h('li', null, [h('strong', { text: '내 정보(가정) ' }), state.assumed.map(function (k) { return PROFILE_LABEL[k]; }).join(' · ')]));
    var qs = ((state.extract && state.extract.questions) || []).filter(function (q) { return q.postingId; });
    ['A', 'B'].forEach(function (pid) {
      var asked = {};
      qs.filter(function (q) { return q.postingId === pid; }).forEach(function (q) {
        asked[q.field] = true;
        ul.appendChild(h('li', null, [h('strong', { text: jobName(pid) + ' ' }), badge('AI가 되물은 것', 'accent'), ' ' + q.text,
          h('div', { class: 'assumed-as', text: skippedAnswer(pid, q.field) })]));
      });
      pendingKeys(pid).forEach(function (d) {
        if (asked[d.key]) return;
        var f = state.model[pid].f[d.key];
        var v = f.value === null || f.value === undefined ? '공고에 없어 모름으로 계산' : (d.opts ? optLabel(d.opts, f.value) : (d.money ? won(f.value) : String(f.value))) + ' (AI 추정)';
        ul.appendChild(h('li', null, [h('strong', { text: jobName(pid) + ' ' }), d.label + ': ' + v]));
      });
    });
    if (ul.children.length) card.appendChild(ul);
    return card;
  }

  /* ---------- 2 확인: 모델 ---------- */
  var CORE = [
    { key: 'companyName', label: '회사명', kind: 'text' },
    { key: 'annualSalary', label: '연봉(원)', kind: 'number', money: true },
    { key: 'workLocationText', label: '근무지(공고 표기)', kind: 'text' },
    { key: 'employmentType', label: '고용 형태', kind: 'select', opts: EMP_OPTS },
    { key: 'companySize', label: '회사 규모', kind: 'select', opts: SIZE_OPTS },
    { key: 'industryText', label: '업종(사업 내용)', kind: 'text' },
    { key: 'benefits.mealAllowanceMonthly', label: '식대(월, 원)', kind: 'number', money: true, optional: true },
    { key: 'benefits.dormitory', label: '기숙사 제공', kind: 'bool', optional: true },
    { key: 'benefits.housingSupportMonthly', label: '주거 지원(월, 원)', kind: 'number', money: true, optional: true, noteText: '계산에는 반영되지 않습니다' }
  ];
  var MANUAL_KEYS = ['companyName', 'annualSalary', 'employmentType', 'companySize', 'industryText'];

  function emptyField() { return { value: null, status: 'missing', evidence: null, note: null }; }
  function getSrc(fields, key) {
    if (key.indexOf('benefits.') === 0) return (fields.benefits || {})[key.slice(9)];
    return fields[key];
  }
  function buildModel(ext) {
    state.model = {};
    ext.postings.forEach(function (p) {
      var m = { id: p.id, f: {}, others: [], candidates: [], ambiguous: false, sggCode: '', housing: { mode: 'market_rent', custom: null }, nonTax: 200000 };
      CORE.forEach(function (d) {
        var s = getSrc(p.fields || {}, d.key) || emptyField();
        m.f[d.key] = { value: s.value === undefined ? null : s.value, status: s.status || 'missing', evidence: s.evidence || null, note: s.note || null, confirmed: false };
      });
      m.others = ((p.fields || {}).benefits || {}).others || [];
      var reg = p.region || {};
      m.candidates = reg.candidates || [];
      m.ambiguous = !!reg.ambiguous;
      if (m.candidates.length === 1) m.sggCode = m.candidates[0].sggCode;
      if (m.f['benefits.dormitory'].value === true) m.housing.mode = 'dormitory';
      var meal = m.f['benefits.mealAllowanceMonthly'].value;
      if (isNum(meal) && meal > 0) m.nonTax = meal;
      state.model[p.id] = m;
    });
  }
  function startManual(message) {
    state = Object.assign(freshState(), { samples: state.samples });
    state.manual = true;
    state.extract = { postings: [{ id: 'A', fields: {}, region: { candidates: [] } }, { id: 'B', fields: {}, region: { candidates: [] } }], questions: [], trace: [] };
    buildModel(state.extract);
    state.profileQs = FALLBACK_PROFILE_QS;
    state.manualMessage = message || '공고를 읽지 못했습니다.';
    renderConfirm();
    setStep(2);
  }

  function pendingKeys(pid) {
    var m = state.model[pid], out = [];
    if (state.manual) return out;
    CORE.forEach(function (d) {
      var f = m.f[d.key];
      if (d.key === 'workLocationText' && m.sggCode) return;
      if (d.optional && f.status === 'missing') return;   // 공고에 없는 부가 항목은 확인 없이 넘어간다
      if ((f.status === 'inferred' || f.status === 'missing') && !f.confirmed) out.push(d);
    });
    return out;
  }

  function setField(pid, key, value, source) {
    var f = state.model[pid].f[key];
    f.value = value;
    f.status = 'user';
    f.confirmed = true;
    if (key === 'benefits.mealAllowanceMonthly' && isNum(value) && value >= 0) {
      state.model[pid].nonTax = value;
      var ni = ui.nonTaxInput[pid];
      if (ni && source !== 'assume') ni.value = String(value);
    }
    if (key === 'benefits.dormitory') {
      var hs = state.model[pid].housing;
      if (value === true) hs.mode = 'dormitory';
      else if (hs.mode === 'dormitory') hs.mode = 'market_rent';
      syncHousing(pid);
    }
    refreshRow(pid, key, source);
    if (ui.qsync[pid + '|' + key]) ui.qsync[pid + '|' + key](source);
  }

  /* ---------- 2 확인: 화면 ---------- */
  function renderConfirm() {
    ui = { rows: {}, qsync: {}, housing: {}, nonTaxInput: {} };
    var body = $('confirmBody');
    clear(body);
    hideMsg('msg2');
    if (state.manual) {
      body.appendChild(h('div', { class: 'msg info' }, [state.manualMessage + ' 아래 양식에 직접 입력해 주세요.']));
    } else if (state.extract && state.extract.degraded) {
      body.appendChild(h('div', { class: 'msg info', text: '저장된 예시 결과로 응답했습니다.' }));
    }
    ['A', 'B'].forEach(function (pid) { body.appendChild(renderPosting(pid)); });
    body.appendChild(renderProfile());
    body.appendChild(renderAssumptions());
  }

  function renderPosting(pid) {
    var m = state.model[pid];
    var card = h('div', { class: 'card', 'data-posting': pid });
    card.appendChild(h('h2', { text: '공고 ' + pid + (m.f.companyName.value ? ' · ' + m.f.companyName.value : '') }));
    var tbody = h('tbody');
    CORE.forEach(function (d) {
      if (state.manual && MANUAL_KEYS.indexOf(d.key) < 0) return;
      tbody.appendChild(makeRow(pid, d));
    });
    var tbl = h('table', null, [
      h('thead', null, h('tr', null, [h('th', { text: '항목' }), h('th', { text: '값' }), h('th', { text: '상태' }), h('th', { text: '근거' })])),
      tbody
    ]);
    card.appendChild(h('div', { class: 'scroll' }, tbl));
    if (!state.manual) {
      card.appendChild(h('button', { type: 'button', class: 'chip', 'data-role': 'confirm-all', text: '추정·없음 항목을 모두 이대로 확인', on: { click: function () {
        pendingKeys(pid).forEach(function (d) { m.f[d.key].confirmed = true; refreshRow(pid, d.key, 'init'); });
      } } }));
    }
    if (m.others.length) {
      card.appendChild(h('p', { class: 'small', text: '계산에 넣지 않는 복지: ' + m.others.join(', ') }));
    }
    card.appendChild(renderRegion(pid));
    var qs = (state.extract.questions || []).filter(function (q) { return q.postingId === pid; })
      .concat(state.extraQs.filter(function (q) { return q.postingId === pid; }));
    qs.forEach(function (q) { card.appendChild(renderPostingQuestion(pid, q)); });
    return card;
  }

  function makeRow(pid, d) {
    var f = state.model[pid].f[d.key];
    var control, helper = null;
    if (d.kind === 'text') {
      control = h('input', { type: 'text', value: f.value === null ? '' : String(f.value), 'aria-label': d.label, on: { input: function () { setField(pid, d.key, control.value, 'row'); } } });
    } else if (d.kind === 'number') {
      helper = h('div', { class: 'unit' });
      control = h('input', { type: 'number', inputmode: 'numeric', min: '0', step: '1', value: isNum(f.value) ? String(f.value) : '', 'aria-label': d.label, on: { input: function () {
        var v = control.value === '' ? null : Number(control.value);
        setField(pid, d.key, (v !== null && isFinite(v)) ? v : null, 'row');
      } } });
    } else if (d.kind === 'select') {
      var opts = d.opts.map(function (o) { return h('option', { value: o[0], text: o[1] }); });
      opts.unshift(h('option', { value: '', text: '—' }));
      control = h('select', { 'aria-label': d.label, on: { change: function () { setField(pid, d.key, control.value === '' ? null : control.value, 'row'); } } }, opts);
      control.value = f.value === null || f.value === undefined ? '' : String(f.value);
    } else {
      control = h('select', { 'aria-label': d.label, on: { change: function () {
        setField(pid, d.key, control.value === '' ? null : control.value === 'true', 'row');
      } } }, [h('option', { value: '', text: '—' }), h('option', { value: 'true', text: '예' }), h('option', { value: 'false', text: '아니오' })]);
      control.value = f.value === true ? 'true' : (f.value === false ? 'false' : '');
    }
    var badgeCell = h('td'), evCell = h('td', { class: 'evidence' });
    var chk = h('input', { type: 'checkbox', 'data-role': 'confirm', 'aria-label': d.label + ' 이대로 확인', on: { change: function () { f.confirmed = chk.checked; } } });
    var chkWrap = h('label', { class: 'small' }, [chk, ' 이대로 확인']);
    var row = h('tr', null, [
      h('td', { text: d.label }),
      h('td', { class: 'val' }, [control, helper]),
      badgeCell, evCell
    ]);
    ui.rows[pid + '|' + d.key] = { control: control, helper: helper, badgeCell: badgeCell, evCell: evCell, chkWrap: chkWrap, chk: chk, def: d };
    refreshRow(pid, d.key, 'init');
    return row;
  }

  function refreshRow(pid, key, source) {
    var r = ui.rows[pid + '|' + key];
    if (!r) return;
    var f = state.model[pid].f[key], d = r.def;
    if (source !== 'row') {
      if (d.kind === 'bool') r.control.value = f.value === true ? 'true' : (f.value === false ? 'false' : '');
      else if (d.kind === 'number') r.control.value = isNum(f.value) ? String(f.value) : '';
      else r.control.value = f.value === null || f.value === undefined ? '' : String(f.value);
    }
    if (r.helper) {
      r.helper.textContent = isNum(f.value) ? '= ' + man(f.value) : '';
      if (isNum(f.value)) r.helper.setAttribute('title', won(f.value));
    }
    clear(r.badgeCell);
    r.badgeCell.appendChild(badge(STATUS_LABEL[f.status] || f.status, f.status));
    var needs = !state.manual && (f.status === 'inferred' || f.status === 'missing') && !(d.optional && f.status === 'missing');
    if (needs && !(key === 'workLocationText' && state.model[pid].sggCode)) {
      r.chk.checked = !!f.confirmed;
      r.badgeCell.appendChild(r.chkWrap);
    }
    clear(r.evCell);
    if (f.evidence) r.evCell.appendChild(h('q', { text: f.evidence }));
    if (f.note) r.evCell.appendChild(h('div', { text: f.note }));
    if (d.noteText) r.evCell.appendChild(h('div', { text: d.noteText }));
  }

  function renderRegion(pid) {
    var m = state.model[pid];
    var box = h('div', { class: 'q' });
    box.appendChild(h('label', { class: 't', text: '근무지 시군구' }));
    function flags(c) {
      var out = [];
      if (c.classUncertain) out.push(badge('분류 미확정', 'warn'));
      if (c.prefCandidate) out.push(badge('우대지역 후보(확정 아님)', 'accent'));
      return out;
    }
    if (m.candidates.length === 0) {
      if (!state.manual) box.appendChild(h('p', { text: '지역 표에 없는 근무지입니다. 시군구 코드(5자리)를 직접 입력해 주세요.' }));
      else box.appendChild(h('p', { text: '근무지의 시군구 코드(5자리)를 입력해 주세요. 예: 서울 강남구는 11680' }));
      var inp = h('input', { type: 'text', inputmode: 'numeric', maxlength: '5', placeholder: '시군구 코드', value: m.sggCode, 'data-role': 'sgg', 'aria-label': '시군구 코드', on: { input: function () {
        m.sggCode = inp.value.trim();
        refreshRow(pid, 'workLocationText', 'init');
      } } });
      box.appendChild(h('div', { class: 'row' }, inp));
    } else if (m.candidates.length === 1) {
      var c = m.candidates[0];
      box.appendChild(h('div', null, [h('strong', { text: c.name }), ' ', h('span', { class: 'small', text: '(' + c.sggCode + ')' }), ' ', flags(c)]));
    } else {
      box.appendChild(h('p', { class: 'small', text: '공고의 근무지에 해당하는 시군구가 여럿입니다. 해당하는 곳을 고르세요.' }));
      m.candidates.forEach(function (c) {
        var rd = h('input', { type: 'radio', name: 'region-' + pid, value: c.sggCode, checked: m.sggCode === c.sggCode, 'data-role': 'region', on: { change: function () { m.sggCode = c.sggCode; refreshRow(pid, 'workLocationText', 'init'); } } });
        box.appendChild(h('label', { class: 'radio' }, [rd, c.name + ' (' + c.sggCode + ') ', flags(c)]));
      });
    }
    return box;
  }

  function renderPostingQuestion(pid, q) {
    var m = state.model[pid];
    var pending = state.extraQs.indexOf(q) >= 0;
    var box = h('div', { class: 'q' + (pending ? ' pending' : ''), 'data-qid': q.id });
    box.appendChild(h('label', { class: 't', text: q.text + (q.required ? ' (필수)' : '') }));
    var fld = q.field;
    if (fld === 'companySize') {
      var sel = h('select', { 'data-role': 'q-' + fld, 'aria-label': q.text, on: { change: function () { setField(pid, 'companySize', sel.value === '' ? null : sel.value, 'q'); } } },
        [h('option', { value: '', text: '—' })].concat(optList(q, SIZE_OPTS)));
      var cur = m.f.companySize;
      sel.value = (cur.status === 'user' && cur.value) ? String(cur.value) : '';
      ui.qsync[pid + '|companySize'] = function (src) { if (src !== 'q') sel.value = m.f.companySize.value === null ? '' : String(m.f.companySize.value); };
      box.appendChild(sel);
    } else if (fld === 'annualSalary') {
      var ni = h('input', { type: 'number', inputmode: 'numeric', min: '0', 'aria-label': q.text, 'data-role': 'q-' + fld, value: isNum(m.f.annualSalary.value) && m.f.annualSalary.status === 'user' ? String(m.f.annualSalary.value) : '', on: { input: function () {
        var v = ni.value === '' ? null : Number(ni.value);
        setField(pid, 'annualSalary', (v !== null && isFinite(v)) ? v : null, 'q');
      } } });
      ui.qsync[pid + '|annualSalary'] = function (src) { if (src !== 'q') ni.value = isNum(m.f.annualSalary.value) ? String(m.f.annualSalary.value) : ''; };
      box.appendChild(h('div', { class: 'row' }, [ni, h('span', { class: 'small', text: '원' })]));
    } else if (fld === 'housing.mode' && q.inputType === 'boolean') {
      var bs = h('select', { 'data-role': 'q-housing', 'aria-label': q.text, on: { change: function () {
        if (bs.value === 'true') m.housing.mode = 'dormitory';
        else if (bs.value === 'false' && m.housing.mode === 'dormitory') m.housing.mode = 'market_rent';
        syncHousing(pid);
      } } }, [h('option', { value: '', text: '—' }), h('option', { value: 'true', text: '예' }), h('option', { value: 'false', text: '아니오' })]);
      box.appendChild(bs);
    } else if (fld === 'housing.customMonthly') {
      var hi = h('input', { type: 'number', inputmode: 'numeric', min: '0', 'data-role': 'q-' + fld, 'aria-label': q.text, value: isNum(m.housing.custom) ? String(m.housing.custom) : '', on: { input: function () {
        var v = hi.value === '' ? null : Number(hi.value);
        m.housing.mode = 'custom';
        m.housing.custom = (v !== null && isFinite(v)) ? v : null;
        syncHousing(pid);
      } } });
      box.appendChild(h('div', { class: 'row' }, [hi, h('span', { class: 'small', text: '원 / 월' })]));
    } else {
      box.appendChild(h('p', { class: 'small', text: '표시용 질문입니다. 아래 표와 근무지 항목에서 직접 고칠 수 있습니다.' }));
    }
    return box;
  }
  function optList(q, fallback) {
    if (q.options && q.options.length) return q.options.map(function (o) { return h('option', { value: String(o.value), text: o.label }); });
    return fallback.map(function (o) { return h('option', { value: o[0], text: o[1] }); });
  }

  /* 내 정보: 질문 객체 그대로 */
  function renderProfile() {
    var card = h('div', { class: 'card' });
    card.appendChild(h('h2', { text: '내 정보' }));
    card.appendChild(h('p', { class: 'hint', text: '세금과 감면 판정에만 쓰이며 AI 모델에는 전달되지 않습니다.' }));
    state.profileQs.forEach(function (q) {
      var key = q.field.replace(/^profile\./, '');
      var box = h('div', { class: 'q' });
      box.appendChild(h('label', { class: 't', text: q.text + (q.required ? ' (필수)' : '') }));
      var cur = state.profileVals[key];
      var ctl;
      if (q.inputType === 'select' || q.inputType === 'boolean') {
        var opts = q.inputType === 'boolean' ? [{ value: true, label: '예' }, { value: false, label: '아니오' }] : (q.options || []);
        ctl = h('select', { 'data-role': 'profile', 'data-key': key, 'aria-label': q.text, on: { change: function () {
          var found = opts.filter(function (o) { return String(o.value) === ctl.value; })[0];
          if (found) state.profileVals[key] = found.value; else delete state.profileVals[key];
        } } }, [h('option', { value: '', text: '—' })].concat(opts.map(function (o) { return h('option', { value: String(o.value), text: o.label }); })));
        ctl.value = cur === undefined ? '' : String(cur);
      } else if (q.inputType === 'number') {
        ctl = h('input', { type: 'number', inputmode: 'numeric', min: '0', 'data-role': 'profile', 'data-key': key, 'aria-label': q.text, value: cur === undefined ? '' : String(cur), on: { input: function () {
          if (ctl.value === '') delete state.profileVals[key]; else state.profileVals[key] = Number(ctl.value);
        } } });
      } else {
        ctl = h('input', { type: 'text', 'data-role': 'profile', 'data-key': key, 'aria-label': q.text, value: cur === undefined ? '' : String(cur), on: { input: function () {
          if (ctl.value === '') delete state.profileVals[key]; else state.profileVals[key] = ctl.value;
        } } });
      }
      box.appendChild(ctl);
      card.appendChild(box);
    });
    return card;
  }

  /* 가정 */
  function renderAssumptions() {
    var card = h('div', { class: 'card' });
    card.appendChild(h('h2', { text: '가정' }));
    var grid = h('div', { class: 'assume' });
    ['A', 'B'].forEach(function (pid) {
      var m = state.model[pid];
      var col = h('div');
      col.appendChild(h('h3', { text: '공고 ' + pid }));
      col.appendChild(h('label', { class: 'small', text: '비과세 월액(원)' }));
      var ni = h('input', { type: 'number', inputmode: 'numeric', min: '0', 'data-role': 'nontax', value: String(m.nonTax), 'aria-label': '공고 ' + pid + ' 비과세 월액', on: { input: function () {
        var v = ni.value === '' ? NaN : Number(ni.value);
        m.nonTax = isFinite(v) ? v : NaN;
      } } });
      ui.nonTaxInput[pid] = ni;
      col.appendChild(ni);
      col.appendChild(h('label', { class: 'small', text: '주거' }));
      var sel = h('select', { 'data-role': 'housing-mode', 'aria-label': '공고 ' + pid + ' 주거', on: { change: function () { m.housing.mode = sel.value; syncHousing(pid); } } }, [
        h('option', { value: 'market_rent', text: '월세 통계' }), h('option', { value: 'dormitory', text: '기숙사·본가(주거비 0원)' }), h('option', { value: 'custom', text: '직접 입력' })
      ]);
      var amt = h('input', { type: 'number', inputmode: 'numeric', min: '0', placeholder: '월 주거비(원)', 'data-role': 'housing-amt', 'aria-label': '공고 ' + pid + ' 월 주거비', on: { input: function () {
        m.housing.custom = amt.value === '' ? null : Number(amt.value);
      } } });
      ui.housing[pid] = { sel: sel, amt: amt };
      col.appendChild(sel);
      col.appendChild(amt);
      grid.appendChild(col);
      syncHousing(pid);
    });
    card.appendChild(grid);
    card.appendChild(h('div', { class: 'q' }, [
      h('label', { class: 't', text: '누적 기간' }),
      horizonSeg(state.horizon, function (v) { state.horizon = v; })
    ]));
    return card;
  }
  function syncHousing(pid) {
    var u = ui.housing[pid], m = state.model[pid];
    if (!u) return;
    u.sel.value = m.housing.mode;
    u.amt.hidden = m.housing.mode !== 'custom';
    u.amt.value = isNum(m.housing.custom) ? String(m.housing.custom) : '';
  }
  function horizonSeg(current, onPick) {
    var seg = h('div', { class: 'seg', role: 'group', 'aria-label': '누적 기간' });
    [1, 3, 5, 10].forEach(function (y) {
      var b = h('button', { type: 'button', class: y === current ? 'on' : '', 'data-year': y, text: y + '년', on: { click: function () {
        var bs = seg.children;
        for (var i = 0; i < bs.length; i++) bs[i].className = '';
        b.className = 'on';
        onPick(y);
      } } });
      seg.appendChild(b);
    });
    return seg;
  }

  /* ---------- 2 확인: 검증과 요청 ---------- */
  function collectRequest(lenient) {
    var errs = [], postings = [];
    ['A', 'B'].forEach(function (pid) {
      var m = state.model[pid];
      if (!lenient) pendingKeys(pid).forEach(function (d) { errs.push('공고 ' + pid + ': "' + d.label + '"을 확인하거나 값을 입력해 주세요.'); });
      var name = m.f.companyName.value;
      var sal = m.f.annualSalary.value;
      if (!isNum(sal) || sal <= 0) errs.push('공고 ' + pid + ': 연봉(원)을 입력해 주세요.');
      if (!/^\d{5}$/.test(m.sggCode || '')) errs.push('공고 ' + pid + ': 근무지 시군구가 정해지지 않았습니다.' + (m.candidates.length > 1 ? ' 위 후보 중 하나를 골라 주세요.' : ''));
      if (!isFinite(m.nonTax) || m.nonTax < 0) errs.push('공고 ' + pid + ': 비과세 월액을 0 이상의 숫자로 입력해 주세요.');
      if (m.housing.mode === 'custom' && (!isNum(m.housing.custom) || m.housing.custom < 0)) errs.push('공고 ' + pid + ': 직접 입력 주거비(원)를 입력해 주세요.');
      var sizeV = m.f.companySize.value, empV = m.f.employmentType.value;
      postings.push({ id: pid, confirmed: {
        companyName: (name && String(name).trim()) || ('공고 ' + pid),
        annualSalary: Math.round(isNum(sal) ? sal : 0),
        sggCode: m.sggCode,
        companySize: sizeV || 'unknown',
        industryText: m.f.industryText.value ? String(m.f.industryText.value) : '',
        employmentType: empV || 'unknown',
        nonTaxableMonthly: Math.round(isFinite(m.nonTax) ? m.nonTax : 0),
        housing: { mode: m.housing.mode, customMonthly: m.housing.mode === 'custom' ? Math.round(m.housing.custom || 0) : null }
      } });
    });
    var pv = state.profileVals;
    state.profileQs.forEach(function (q) {
      var key = q.field.replace(/^profile\./, '');
      if (q.required && pv[key] === undefined) errs.push('내 정보: "' + q.text + '"에 답해 주세요.');
    });
    var profile = {
      age: pv.age === undefined ? 0 : Math.round(pv.age),
      militaryServiceMonths: pv.militaryServiceMonths === undefined ? 0 : Math.round(pv.militaryServiceMonths),
      hireYear: pv.hireYear === undefined ? 2027 : Number(pv.hireYear),
      priorRelief: pv.priorRelief === undefined ? 'unknown' : String(pv.priorRelief)
    };
    return { errs: errs, req: { postings: postings, profile: profile, options: { horizonYears: state.horizon } } };
  }

  function onCalc() {
    hideMsg('msg2');
    state.skipped = false;
    var c = collectRequest();
    if (c.errs.length) {
      var ul = h('ul', null, c.errs.map(function (e) { return h('li', { text: e }); }));
      showMsg('msg2', [h('div', { text: '계산하기 전에 확인할 항목이 있습니다.' }), ul]);
      return;
    }
    setButtons(['btnCalc', 'btnBack1'], true);
    runCompare(c.req, 2, function () { setButtons(['btnCalc', 'btnBack1'], false); });
  }

  function runCompare(req, fromStep, done) {
    busy(fromStep, ['계산하는 중', '월세와 감면 조건을 확인하는 중', '설명문을 쓰는 중']);
    var msgId = 'msg' + fromStep;
    api('POST', '/api/compare', req).then(function (r) {
      unbusy(fromStep);
      if (done) done();
      var d = r.data;
      if (r.networkError || !d) { showMsg(msgId, netMessage(r)); return; }
      if (d.error) { showMsg(msgId, d.error.message || '계산하지 못했습니다.'); return; }
      if (d.needsInput) { onNeedsInput(d); return; }
      if (!Array.isArray(d.jobs) || !Array.isArray(d.comparison)) { showMsg(msgId, '서버 응답 형식이 올바르지 않습니다.'); return; }
      state.lastReq = req;
      state.horizon = req.options.horizonYears;
      state.result = d;
      state.names = {};
      req.postings.forEach(function (p) { state.names[p.id] = p.confirmed.companyName; });
      if (fromStep === 2) state.tab = 'current_law';
      renderResult();
      setStep(3);
    });
  }

  function onNeedsInput(d) {
    (d.trace || []).forEach(function (t) { state.earlyTrace.push(t); });
    state.extraQs = (d.questions || []).slice();
    renderConfirm();
    setStep(2);
    var unknown = state.extraQs.filter(function (q) { return !q.postingId || !state.model[q.postingId]; });
    var names = state.extraQs.map(function (q) { return q.postingId ? '공고 ' + q.postingId : '공통'; });
    showMsg('msg2', '계산에 필요한 값이 더 있습니다. (' + names.join(', ') + ') 아래 노란 칸에 답한 뒤 다시 계산해 주세요.' + (unknown.length ? ' 일부 질문은 표시만 됩니다.' : ''), 'info');
    if (unknown.length) {
      var box = h('div', { class: 'card soft' }, unknown.map(function (q) { return h('p', { text: q.text }); }));
      $('confirmBody').insertBefore(box, $('confirmBody').firstChild);
    }
  }

  /* ---------- 3 결과 ---------- */
  function byId(arr, id) { for (var i = 0; i < arr.length; i++) if (arr[i].id === id) return arr[i]; return null; }
  function compFor(sc) { var c = state.result.comparison; for (var i = 0; i < c.length; i++) if (c[i].scenarioId === sc) return c[i]; return null; }
  function scenOf(job, sc) { for (var i = 0; i < job.scenarios.length; i++) if (job.scenarios[i].id === sc) return job.scenarios[i]; return null; }

  function renderResult() {
    var R = state.result, body = $('resultBody');
    clear(body);
    hideMsg('msg3');
    if (typeof R.dataVersion === 'object' && R.dataVersion && String(R.dataVersion.rent).indexOf('sample') === 0) {
      body.appendChild(h('div', { class: 'band', text: '설명용 임의 월세 데이터입니다. 실제 실거래가가 아닙니다' }));
    }
    if (state.skipped) body.appendChild(renderSkipped());
    body.appendChild(renderConclusion());
    if (window.MoneyFlow) {   // 돈 흐름 시각화(flow.js). 실패해도 나머지 결과는 그대로 보인다
      var fl = h('div', { class: 'card flow' }, [h('h2', { text: '1년 동안 돈이 흘러가는 모습' }),
        h('p', { class: 'hint', text: '선 한 가닥 한 가닥이 돈입니다. 공제 지점에 가까워지면 붉게 물들어 폭포처럼 떨어지고, 끝까지 흘러간 초록 선이 남는 돈입니다.' })]);
      body.appendChild(fl);
      try { window.MoneyFlow.mount(fl, R, { A: state.names.A || '공고 A', B: state.names.B || '공고 B' }, state.tab); } catch (e) { if (fl.parentNode) fl.parentNode.removeChild(fl); }
    }
    var hz = h('div', { class: 'card' }, [
      h('div', { class: 'row' }, [h('strong', { text: '누적 기간' }), horizonSeg(state.horizon, onHorizon)])
    ]);
    body.appendChild(hz);
    body.appendChild(renderScenarioArea());
    body.appendChild(h('h2', { text: '공고별 정리' }));
    body.appendChild(h('div', { class: 'jobs' }, R.jobs.map(renderJob)));
    body.appendChild(renderExplanation());
    body.appendChild(renderNotices());
    body.appendChild(renderLists());
  }

  function onHorizon(y) {
    if (!state.lastReq) return;
    var req = JSON.parse(JSON.stringify(state.lastReq));
    req.options.horizonYears = y;
    hideMsg('msg3');
    runCompare(req, 3, function () {});
  }

  function renderConclusion() {
    var R = state.result, c = compFor('current_law') || R.comparison[0];
    var box = h('div', { class: 'conclusion' });
    var line = h('p', { class: 'big' });
    if (c) {
      if (c.difference === 0) {
        line.appendChild(document.createTextNode('현행법 시나리오 기준으로 ' + state.horizon + '년 동안 두 공고의 남는 돈 차이가 없습니다.'));
      } else {
        line.appendChild(document.createTextNode('현행법 시나리오 기준으로 ' + state.horizon + '년 동안 ' + jobName(c.betterJobId) + '가 약 '));
        line.appendChild(money(c.difference));
        line.appendChild(document.createTextNode(' 더 남습니다.'));
      }
    }
    box.appendChild(line);
    var sub = [];
    if (R.degraded) sub.push(badge('대체 응답', 'warn'));
    var notes = [];
    R.jobs.forEach(function (j) {
      if (j.eligibility.status === 'unlikely') notes.push(jobName(j.id) + '는 감면 대상이 아닐 가능성이 높아 감면 없음 기준으로 계산했습니다.');
      if (j.eligibility.status === 'uncertain') notes.push(jobName(j.id) + '의 감면 대상 여부가 불확실합니다. 대상이 아닐 때는 \'감면 없음\' 탭을 확인하세요.');
    });
    if (sub.length) box.appendChild(h('div', null, sub));
    notes.forEach(function (n) { box.appendChild(h('p', { class: 'small', text: n })); });
    box.appendChild(h('p', { class: 'small', text: '남는 돈 = 세후 소득 - 주거비. 식비 등 생활비는 들어 있지 않습니다.' }));
    return box;
  }

  function renderScenarioArea() {
    var area = h('div', { class: 'card' });
    var tabs = h('div', { class: 'tabs', role: 'tablist' });
    var panel = h('div');
    function draw() {
      clear(tabs); clear(panel);
      SCENARIOS.forEach(function (s) {
        tabs.appendChild(h('button', { type: 'button', role: 'tab', 'data-scenario': s.id, class: s.id === state.tab ? 'on' : '', text: s.label, on: { click: function () { state.tab = s.id; draw(); } } }));
      });
      var ids = (state.tab === 'proposal_base' || state.tab === 'proposal_pref') ? ['proposal_base', 'proposal_pref'] : [state.tab];
      var cols = h('div', { class: 'cols' + (ids.length === 2 ? ' two-col' : '') });
      ids.forEach(function (id) { cols.appendChild(renderScenarioCol(id, id === state.tab && ids.length === 2)); });
      panel.appendChild(cols);
    }
    area.appendChild(h('h2', { text: '시나리오별 남는 돈' }));
    area.appendChild(tabs);
    area.appendChild(panel);
    draw();
    return area;
  }
  function scLabel(id) { for (var i = 0; i < SCENARIOS.length; i++) if (SCENARIOS[i].id === id) return SCENARIOS[i].label; return id; }

  function renderScenarioCol(scId, active) {
    var R = state.result;
    var col = h('div', { class: 'col' + (active ? ' active' : ''), 'data-col': scId });
    col.appendChild(h('h3', { text: scLabel(scId) }));
    var c = compFor(scId);
    if (c) {
      var diff = h('div', { class: 'diff' });
      if (c.difference === 0) diff.appendChild(document.createTextNode('차이 없음'));
      else { diff.appendChild(document.createTextNode(jobName(c.betterJobId) + ' 약 ')); diff.appendChild(money(c.difference)); diff.appendChild(document.createTextNode(' 더')); }
      col.appendChild(diff);
      if (c.breakEven && isNum(c.breakEven.annualSalary)) {
        var be = h('p', { class: 'small' });
        be.appendChild(document.createTextNode('손익분기: ' + jobName(c.breakEven.jobId) + '의 연봉이 '));
        be.appendChild(money(c.breakEven.annualSalary));
        be.appendChild(document.createTextNode('이면 같아짐'));
        col.appendChild(be);
      }
    }
    // 요약 표
    var head = h('tr', null, [h('th', { text: '항목' })].concat(R.jobs.map(function (j) {
      var th = h('th', { class: 'r', text: '공고 ' + j.id });
      if (j.eligibility.status === 'unlikely') th.appendChild(h('div', { class: 'small', text: '감면 없음 기준' }));
      return th;
    })));
    function row(lbl, fn) { return h('tr', null, [h('td', { text: lbl })].concat(R.jobs.map(function (j) { var s = scOf(j, scId); return h('td', { class: 'r' }, s ? fn(s) : '-'); }))); }
    function scOf(j, id) { return scenOf(j, id); }
    var sum = h('table', null, [h('thead', null, head), h('tbody', null, [
      row('감면 연수', function (s) { return s.reliefYears + '년'; }),
      row('1년차 남는 돈', function (s) { return money(s.firstYearRemaining); }),
      row(state.horizon + '년 누적', function (s) { return money(s.cumulativeRemaining); }),
      row('감면액 합계', function (s) { return money(s.reliefTotal); })
    ])]);
    col.appendChild(h('div', { class: 'scroll' }, sum));
    // 연차별 표
    var years = {};
    R.jobs.forEach(function (j) { var s = scOf(j, scId); if (s) s.yearly.forEach(function (y) { years[y.year] = true; }); });
    var yl = Object.keys(years).map(Number).sort(function (a, b) { return a - b; });
    col.appendChild(h('h3', { text: '연차별' }));
    if (!yl.length) {
      col.appendChild(h('p', { class: 'small', text: '연차별 상세가 응답에 없습니다.' }));
    } else {
      var yh = h('tr', null, [h('th', { text: '연차' })].concat(R.jobs.reduce(function (a, j) { return a.concat([h('th', { class: 'r', text: j.id + ' 남는 돈' }), h('th', { class: 'r', text: j.id + ' 누적' })]); }, [])));
      var yb = yl.map(function (yr) {
        var anyRelief = false, cells = [];
        R.jobs.forEach(function (j) {
          var s = scOf(j, scId), y = null;
          if (s) s.yearly.forEach(function (x) { if (x.year === yr) y = x; });
          if (y && y.reliefApplied) anyRelief = true;
          cells.push(h('td', { class: 'r' }, y ? [money(y.remaining), y.reliefApplied ? badge('감면', 'accent') : null] : '-'));
          cells.push(h('td', { class: 'r' }, y ? money(y.cumulative) : '-'));
        });
        return h('tr', { class: anyRelief ? 'relief' : '' }, [h('td', { text: yr + '년차' })].concat(cells));
      });
      col.appendChild(h('div', { class: 'scroll' }, h('table', { class: 'yearly' }, [h('thead', null, yh), h('tbody', null, yb)])));
      col.appendChild(h('p', { class: 'small', text: '왼쪽에 노란 선이 있는 줄은 감면이 적용되는 해입니다.' }));
    }
    return col;
  }

  // 공고별 정리: 감열 계산서. 금액은 계산 모듈 출력 그대로(원 단위)이고, 화면에서는 더하거나 빼지 않는다
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function rcLine(label, value, cls) { return h('div', { class: 'rc-line' + (cls ? ' ' + cls : '') }, [h('span', { class: 'rc-l', text: label }), h('span', { class: 'rc-v', text: value })]); }
  function rcRule(dbl) { return h('div', { class: 'rc-rule' + (dbl ? ' dbl' : ''), 'aria-hidden': 'true' }); }
  function rcWon(n) { return nf.format(Math.round(n)); }

  function renderJob(j) {
    var card = h('div', { class: 'job receipt', 'data-job': j.id });
    var p = h('div', { class: 'rc-paper' });
    var reg = j.region || {}, none = j.pay.none, wr = j.pay.withRelief, el = j.eligibility;
    p.appendChild(h('div', { class: 'rc-title', text: '공고 ' + j.id + ' 계산서' }));
    if (state.names[j.id]) p.appendChild(h('div', { class: 'rc-center rc-name', text: state.names[j.id] }));
    p.appendChild(h('div', { class: 'rc-center', text: reg.name || '' }));
    if (reg.classUncertain) p.appendChild(h('div', { class: 'rc-note', text: '* 지역 분류 미확정' }));
    if (reg.prefCandidate) p.appendChild(h('div', { class: 'rc-note', text: '* 우대지역 후보(확정 아님)' }));
    p.appendChild(rcRule());
    p.appendChild(h('div', { class: 'rc-line rc-head' }, [h('span', { text: '항목' }), h('span', { text: '금액(원)' })]));
    p.appendChild(rcRule());
    p.appendChild(rcLine('세후 연봉(감면 없음)', rcWon(none.netAnnual), 'big'));
    p.appendChild(rcLine('월평균', rcWon(none.netMonthlyAvg), 'sub'));
    p.appendChild(rcLine('세후 연봉(감면 적용)', rcWon(wr.netAnnual)));
    p.appendChild(rcLine('월평균', rcWon(wr.netMonthlyAvg), 'sub'));
    p.appendChild(rcLine('월 주거비', rcWon(j.housingMonthly)));
    p.appendChild(rcRule(true));
    // 월세 근거
    p.appendChild(h('div', { class: 'rc-sec', text: '[월세 근거]' }));
    if (j.rent) {
      var r = j.rent;
      p.appendChild(rcLine('환산월세 중위값', rcWon(r.monthlyMedian)));
      p.appendChild(rcLine('p25 ~ p75', rcWon(r.p25) + ' ~ ' + rcWon(r.p75)));
      p.appendChild(rcLine('표본 수', nf.format(r.sampleCount) + '건'));
      p.appendChild(rcLine('기간', r.period));
      p.appendChild(rcLine('범위', SCOPE_LABEL[r.scope] || r.scope));
      p.appendChild(rcLine('데이터 기준일', r.dataAsOf));
      if (!r.sufficient) p.appendChild(h('div', { class: 'rc-note', text: '* 표본이 30건 미만이라 통계가 불안정할 수 있습니다' }));
    } else {
      var mode = state.lastReq ? (byId(state.lastReq.postings, j.id) || { confirmed: { housing: {} } }).confirmed.housing.mode : '';
      p.appendChild(rcLine(mode === 'dormitory' ? '기숙사·본가' : (mode === 'custom' ? '직접 입력' : '월세 통계 없음'), '월 ' + rcWon(j.housingMonthly)));
    }
    p.appendChild(rcRule());
    // 감면 대상 가능성
    p.appendChild(h('div', { class: 'rc-sec', text: '[감면 대상 가능성]' }));
    p.appendChild(h('div', { class: 'rc-status-row' }, [h('span', { class: 'rc-status ' + el.status, text: ELIG_LABEL[el.status] || el.status })]));
    if (el.status === 'uncertain') p.appendChild(h('div', { class: 'rc-note', text: "* 대상이 아닐 때는 '감면 없음' 탭을 보세요" }));
    if (el.status === 'unlikely') p.appendChild(h('div', { class: 'rc-note', text: '* 감면 없음 기준으로 계산했습니다' }));
    (el.checks || []).forEach(function (c) {
      p.appendChild(rcLine(RULE_LABEL[c.rule] || c.rule, RESULT_LABEL[c.result] || c.result, 'chk ' + c.result));
      if (c.evidence) p.appendChild(h('div', { class: 'rc-ev', text: c.evidence }));
    });
    if (el.hrQuestion) {
      var cp = h('button', { type: 'button', class: 'chip rc-copy', text: '복사' });
      cp.addEventListener('click', function () { copyText(el.hrQuestion, cp); });
      p.appendChild(rcRule());
      p.appendChild(h('div', { class: 'rc-sec' }, ['[인사팀에 확인할 질문] ', cp]));
      p.appendChild(h('div', { class: 'rc-ev rc-q', text: el.hrQuestion }));
    }
    p.appendChild(rcRule(true));
    p.appendChild(h('div', { class: 'rc-barcode rc-' + j.id, 'aria-hidden': 'true' }));
    p.appendChild(h('div', { class: 'rc-center rc-foot', text: '금액은 서버의 계산 코드가 산출' }));
    card.appendChild(p);
    // 화면에 들어오면 위에서부터 줄 단위로 인쇄되듯 나타난다
    if (!reduceMotion && 'IntersectionObserver' in window) {
      card.classList.add('pending');
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { card.classList.remove('pending'); card.classList.add('printing'); io.disconnect(); } });
      }, { threshold: 0.12 });
      io.observe(card);
    }
    return card;
  }

  function copyText(text, btn) {
    var done = function () { btn.textContent = '복사됨'; setTimeout(function () { btn.textContent = '복사'; }, 1500); };
    var fb = function () {
      try {
        var ta = h('textarea', { 'aria-hidden': 'true' });
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        done();
      } catch (e) { btn.textContent = '복사 실패'; }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fb); else fb();
  }

  function renderExplanation() {
    var ex = state.result.explanation, card = h('div', { class: 'card' });
    card.appendChild(h('h2', { text: '설명' }));
    if (!ex) return card;
    if (ex.aiGenerated) card.appendChild(h('div', null, badge('AI가 생성한 답변', 'accent')));
    if (ex.numbersVerified === false) card.appendChild(h('p', { class: 'small', text: '설명문의 숫자 검증을 통과하지 못해 표시하지 않습니다. 위 표의 값을 기준으로 봐 주세요.' }));
    else card.appendChild(h('p', { class: 'expl', text: ex.text }));
    return card;
  }

  function renderNotices() {
    var n = state.result.notices || [];
    var ul = h('ul', { class: 'notices', 'data-role': 'notices' }, n.map(function (t) { return h('li', { text: t }); }));
    return h('div', null, [h('h2', { text: '고지' }), ul]);
  }

  function renderLists() {
    var R = state.result, wrap = h('div');
    wrap.appendChild(h('h2', { text: '가정' }));
    wrap.appendChild(h('ul', { class: 'plain' }, (R.assumptions || []).map(function (a) { return h('li', { text: a }); })));
    wrap.appendChild(h('h2', { text: '출처' }));
    wrap.appendChild(h('ul', { class: 'plain' }, (R.sources || []).map(function (s) {
      var u = safeUrl(s.url);
      return h('li', null, [u ? h('a', { href: u, target: '_blank', rel: 'noopener noreferrer', text: s.name }) : s.name, h('span', { class: 'small', text: s.asOf ? ' (' + s.asOf + ')' : '' })]);
    })));
    var steps = state.earlyTrace.concat(R.trace || []);
    var ol = h('ol', { class: 'trace' }, steps.map(function (t) {
      return h('li', null, [badge(TRACE_LABEL[t.type] || t.type, ''), h('strong', { text: t.name + ' ' }), h('span', { text: t.summary })]);
    }));
    var meta = [];
    if (R.generatedAt) meta.push('생성 ' + R.generatedAt);
    if (R.dataVersion) meta.push('월세 데이터 ' + R.dataVersion.rent + ' · 규칙 ' + R.dataVersion.rules);
    wrap.appendChild(h('details', { open: true }, [h('summary', { text: '에이전트 진행 기록' }), ol]));
    if (meta.length) wrap.appendChild(h('p', { class: 'small', text: meta.join(' / ') }));
    return wrap;
  }

  /* ---------- 이동 ---------- */
  function reset() {
    var samples = state.samples;
    state = freshState();
    state.samples = samples;
    ['A', 'B'].forEach(function (id) { var t = $('text' + id); t.value = ''; t.dispatchEvent(new Event('input')); });
    hideMsg('msg1');
    setStep(1);
  }

  function init() {
    initStep1();
    $('btnCalc').addEventListener('click', onCalc);
    $('btnBack1').addEventListener('click', function () { setStep(1); });
    $('btnBack2').addEventListener('click', function () { setStep(2); });
    $('btnReset').addEventListener('click', reset);
  }

  if (MOCK && !window.MockApi) {
    var s = document.createElement('script');
    s.src = 'mock.js';
    s.onload = init;
    s.onerror = function () { document.body.insertBefore(h('div', { class: 'msg', text: 'mock.js를 불러오지 못했습니다.' }), document.body.firstChild); };
    document.head.appendChild(s);
  } else {
    init();
  }

  if (window.__NB_TEST__) {
    window.__NB_TEST__.get = function () { return { state: state, ui: ui, renderConfirm: renderConfirm, renderResult: renderResult, collectRequest: collectRequest, startManual: startManual, buildModel: buildModel }; };
  }
})();
