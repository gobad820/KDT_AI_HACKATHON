/* 결과 화면의 돈 흐름 시각화 (별빛 Sankey).
   점 하나하나가 돈이다. 연봉이 왼쪽에서 들어와 오른쪽으로 흐르고, 4대보험·세금·월세만큼 폭포처럼 떨어져 사라진다.
   떨어질 점은 공제 지점까지 거리의 4/5를 지나면서 붉게 물든다. 마지막 폭포를 지난 점이 남는 돈이다.
   금액은 서버 응답(/api/compare)만 쓴다. 연봉 = 실수령 + 4대보험 + 소득세 + 지방소득세. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var NS = 'http://www.w3.org/2000/svg', DPR = Math.min(2, window.devicePixelRatio || 1), SIZES = [1.7, 3.6, 7], GAP = 2.5;
  var COLORS = { money: '219,230,255', keep: '69,240,166', loss: '255,93,82', save: '255,212,92' };
  var SPR = null;

  function man(n) { return Math.round(n / 1e4).toLocaleString('ko-KR') + '만'; }
  function eok(n) { var e = Math.floor(n / 1e8), m = Math.round((n % 1e8) / 1e4); return (e ? e + '억 ' : '') + (m ? m.toLocaleString('ko-KR') + '만' : (e ? '' : '0')); }
  function s(tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function txt(parent, x, y, t, cls, anchor) { var e = s('text', { x: x, y: y, 'text-anchor': anchor || 'start' }, parent); if (cls) e.setAttribute('class', cls); e.textContent = t; return e; }
  function el(tag, cls, parent, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }

  function sprite(c, r) {
    var cv = document.createElement('canvas'), d = Math.ceil(r * 2 * DPR); cv.width = cv.height = d;
    var g = cv.getContext('2d'), gr = g.createRadialGradient(d / 2, d / 2, 0, d / 2, d / 2, d / 2);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.18, 'rgba(' + c + ',.95)'); gr.addColorStop(.45, 'rgba(' + c + ',.35)'); gr.addColorStop(1, 'rgba(' + c + ',0)');
    g.fillStyle = gr; g.fillRect(0, 0, d, d); return cv;
  }
  function sprites() {
    if (SPR) return SPR;
    var m = COLORS.money.split(',').map(Number), l = COLORS.loss.split(',').map(Number), cols = [];
    for (var b = 0; b < 6; b++) cols.push(m.map(function (v, j) { return Math.round(v + (l[j] - v) * b / 5); }).join(','));   // 0~5: 별빛 흰색 → 빨강
    cols.push(COLORS.keep, COLORS.save);                                                                                     // 6: 남는 돈, 7: 감면
    SPR = cols.map(function (c) { return SIZES.map(function (r) { return sprite(c, r); }); });
    return SPR;
  }

  /* 줄기 하나 = 공고 하나. 위에서부터 [남는 돈][마지막 공제]...[첫 공제] 순서로 구간이 쌓인다 */
  function Stream(cfg) {
    var N = cfg.n, X = new Float32Array(N), Y = new Float32Array(N), V = new Float32Array(N), VX = new Float32Array(N), VY = new Float32Array(N),
      ST = new Uint8Array(N), T = new Float32Array(N), SV = new Uint8Array(N), EV = new Int8Array(N), PH = new Float32Array(N), FR = new Float32Array(N),
      AM = new Float32Array(N), SZ = new Uint8Array(N), TW = new Float32Array(N);
    var self = { cfg: cfg, time: 0 }, C;
    function cuts() { var c = 0, out = []; cfg.events.forEach(function (e) { out.push([c, c + e.amt]); c += e.amt; }); return { list: out, total: c }; }
    function gapsAbove(v) { if (v >= C.total) return 0; var n = 0; for (var e = C.list.length - 1; e >= 0; e--) { n++; if (v >= C.list[e][0]) return n; } return n; }
    function baseY(v) { return cfg.top + (cfg.salary - v) * cfg.k + gapsAbove(v) * GAP; }
    function wave(x) { return Math.sin(x * .011 - self.time * 1.3) * cfg.wave * Math.min(1, (x - cfg.x0 + 40) / 120); }
    self.baseY = baseY; self.cuts = function () { return C; };
    function spawn(i, x) {
      X[i] = x; V[i] = Math.random() * cfg.salary; VX[i] = cfg.speed * (.85 + Math.random() * .3); VY[i] = 0; ST[i] = 0; T[i] = 0; EV[i] = -1;
      for (var e = 0; e < C.list.length; e++) if (V[i] >= C.list[e][0] && V[i] < C.list[e][1]) EV[i] = e;
      var lo = EV[i] >= 0 ? C.list[EV[i]][0] : C.total, hi = EV[i] >= 0 ? C.list[EV[i]][1] : cfg.salary;
      AM[i] = Math.min(5, Math.max(0, Math.min(V[i] - lo, hi - V[i]) * cfg.k - .8));
      PH[i] = Math.random() * 6.283; FR[i] = 1.2 + Math.random() * 1.8;
      var rr = Math.random(); SZ[i] = rr < .8 ? 0 : rr < .98 ? 1 : 2; TW[i] = 1.5 + Math.random() * 4;
      SV[i] = (cfg.rescue && EV[i] === cfg.rescue.ev && Math.random() < cfg.rescue.frac) ? 1 : 0;
      Y[i] = baseY(V[i]);
    }
    self.reset = function (empty) { C = cuts(); for (var i = 0; i < N; i++) spawn(i, empty ? cfg.x0 - Math.random() * (cfg.xEnd - cfg.x0 + 260) : cfg.x0 + Math.random() * (cfg.xEnd - cfg.x0)); };
    self.setCfg = function (patch) { for (var k in patch) cfg[k] = patch[k]; C = cuts(); for (var i = 0; i < N; i++) spawn(i, X[i]); };
    self.step = function (dt) {
      self.time += dt;
      var g = 620, tm = self.time;
      for (var i = 0; i < N; i++) {
        var st = ST[i];
        if (st === 0 || st === 3) {
          X[i] += VX[i] * dt;
          Y[i] = (st === 3 ? VY[i] : baseY(V[i])) + wave(X[i]) + Math.sin(PH[i] + tm * FR[i]) * AM[i];
          if (st === 0 && EV[i] >= 0 && X[i] >= cfg.events[EV[i]].x + (Math.random() - .5) * 8) {
            if (SV[i]) { ST[i] = 2; T[i] = 0; VY[i] = Y[i]; VX[i] = X[i]; }
            else { ST[i] = 1; T[i] = 0; VY[i] = 6 + Math.random() * 30; VX[i] *= .7 + Math.random() * .35; }
          }
          if (X[i] > cfg.xEnd + 30) spawn(i, cfg.x0 - Math.random() * 30);
        } else if (st === 1) {
          T[i] += dt; VY[i] += g * dt; VX[i] *= (1 - .9 * dt); X[i] += VX[i] * dt; Y[i] += VY[i] * dt;
          if (Y[i] > cfg.floor) spawn(i, cfg.x0 - Math.random() * 30);
        } else if (st === 2) {
          T[i] += dt; var u = Math.min(1, T[i] / 1.1), sx = VX[i], sy = VY[i];
          var tv = C.total + (V[i] / cfg.salary) * (cfg.salary - C.total), ty = baseY(tv), tx = sx + 170, m = 1 - u;
          X[i] = m * m * sx + 2 * m * u * (sx + 40) + u * u * tx; Y[i] = m * m * sy + 2 * m * u * (sy + 90) + u * u * (ty + wave(tx));
          if (u >= 1) { ST[i] = 3; VY[i] = ty; VX[i] = cfg.speed; }
        }
      }
    };
    self.draw = function (ctx) {
      var spr = sprites(), lastX = cfg.events.length ? cfg.events[cfg.events.length - 1].x : cfg.x0, tm = self.time, BASE = [.62, .85, 1], i, b, a, r;
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (i = 0; i < N; i++) {
        var st = ST[i], x = X[i], y = Y[i];
        if (x < cfg.x0 - 2 || x > cfg.xEnd + 2) continue;
        a = BASE[SZ[i]] * (.6 + .4 * Math.sin(tm * TW[i] + PH[i]));
        if (st === 0) {
          if (EV[i] < 0) b = x <= lastX ? 0 : 6;
          else { var pr = (x - cfg.x0) / (cfg.events[EV[i]].x - cfg.x0); b = pr < .8 ? 0 : Math.min(5, 1 + (((pr - .8) / .2 * 4.999) | 0)); }
        } else if (st === 1) { b = 5; var dp = (y - cfg.top) / (cfg.floor - cfg.top); a = Math.max(a, .75) * (dp < .6 ? 1 : Math.max(0, 1 - (dp - .6) / .4)); if (a <= .02) continue; }
        else b = 7;
        var zc = st === 1 ? Math.max(1, SZ[i]) : SZ[i]; r = SIZES[zc];
        ctx.globalAlpha = Math.min(1, a);
        ctx.drawImage(spr[b][zc], x - r, y - r, r * 2, r * 2);
      }
      ctx.restore();
    };
    self.reset(false);
    for (var w = 0; w < 300; w++) self.step(1 / 30);
    return self;
  }

  /* 캔버스 한 장 + 라벨 SVG. 화면에서 빠지면 루프를 멈춘다 */
  function Scene(host, H, streams) {
    var inner = el('div', 'flow-inner', host), cv = el('canvas', null, inner), svg = s('svg', { viewBox: '0 0 960 ' + H, preserveAspectRatio: 'none' }, inner);
    cv.setAttribute('role', 'img');
    var ctx = cv.getContext('2d'), W = 960, visible = true, started = false, dead = false;
    function frame(dt) { ctx.clearRect(0, 0, W, H); streams.forEach(function (st) { if (dt) st.step(dt); st.draw(ctx); }); }
    function size() { var w = inner.clientWidth || 720, sc = w / W; cv.width = Math.round(w * DPR); cv.height = Math.round(H * sc * DPR); cv.style.height = (H * sc) + 'px'; ctx.setTransform(sc * DPR, 0, 0, sc * DPR, 0, 0); frame(0); }
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting;
      if (visible && !started) { started = true; if (!reduce) streams.forEach(function (st) { st.reset(true); }); }
    }, { threshold: .25 }) : null;
    if (io) io.observe(cv);
    window.addEventListener('resize', size);
    var last = performance.now();
    function loop(now) {
      if (!cv.isConnected) { dead = true; window.removeEventListener('resize', size); if (io) io.disconnect(); return; }
      var dt = Math.min(.05, (now - last) / 1000); last = now;
      if (visible && !reduce) frame(dt);
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(function () { size(); requestAnimationFrame(loop); });
    return { svg: svg, canvas: cv, replay: function () { streams.forEach(function (st) { st.reset(true); }); } };
  }

  function labels(svg, st, opt) {
    var c = st.cfg, g = s('g', {}, svg), C = st.cuts(), mid = (st.baseY(c.salary) + st.baseY(0)) / 2;
    txt(g, c.x0 - 16, mid - 6, opt.startName, 'nm', 'end');
    txt(g, c.x0 - 16, mid + 18, opt.fmt(c.salary), 'v', 'end');
    s('line', { x1: c.x0, x2: c.xEnd, y1: c.floor + 1, y2: c.floor + 1, class: 'rule' }, g);
    c.events.forEach(function (e) {
      s('line', { x1: e.x, x2: e.x, y1: c.floor - 6, y2: c.floor + 6, class: 'tick' }, g);
      txt(g, e.x, c.floor + 22, e.label, 'nm', 'start');
      txt(g, e.x, c.floor + 46, '−' + opt.fmt(e.shown != null ? e.shown : e.amt), 'v loss', 'start');
      if (e.note) txt(g, e.x, c.floor + 66, e.note, 'nm', 'start');
    });
    var ky = (st.baseY(c.salary) + st.baseY(C.total)) / 2, shown = opt.keepShown != null ? opt.keepShown : c.salary - C.total;
    txt(g, c.xEnd + 16, ky - 12, opt.endName || '남는 돈', 'nm', 'start');
    txt(g, c.xEnd + 16, ky + 16, opt.fmt(shown), 'v keep', 'start');
    if (opt.sub) txt(g, c.xEnd + 16, ky + 38, opt.sub, 'nm', 'start');
    return g;
  }

  var XE = [330, 480, 630];
  function events(j, mult, savedTax) {
    var ev = [], xs = XE.slice();
    if (j.insurance > 0) ev.push({ amt: j.insurance * mult, label: '4대보험' });
    if (j.tax > 0) ev.push({ amt: j.tax * mult, shown: j.tax * mult - (savedTax || 0), label: mult > 1 ? '낸 세금' : '소득세·지방세', note: savedTax > 0 ? '감면으로 ' + man(savedTax) + ' 돌아옴' : '', tax: true });
    if (j.rent > 0) ev.push({ amt: j.rent * mult, label: mult > 1 ? '월세' : '월세 ' + man(j.rentMonthly) + ' x 12' });
    ev.forEach(function (e, i) { e.x = xs[i]; });
    return ev;
  }

  /* 서버 응답의 공고 하나 → 흐름에 쓰는 값 */
  function fromJob(job, name) {
    var n = job.pay.none, w = job.pay.withRelief;
    var tax = n.finalTax + n.localTax, salary = n.netAnnual + n.insurance + tax;
    return { id: job.id, name: name, salary: salary, insurance: n.insurance, tax: tax, rentMonthly: job.housingMonthly, rent: job.housingMonthly * 12,
      remain: n.netAnnual - job.housingMonthly * 12, taxRelief: tax - (w.finalTax + w.localTax), scenarios: job.scenarios };
  }

  /* 1년 흐름: 두 공고를 같은 축척으로 나란히 */
  function mountYear(host, jobs) {
    var max = Math.max(jobs[0].salary, jobs[1].salary), k = 150 / max, tops = [30, 360], sts = [];
    jobs.forEach(function (j, i) {
      sts.push(Stream({ salary: j.salary, top: tops[i], k: k, x0: 170, xEnd: 780, floor: tops[i] + 220, speed: 105, n: 8500, wave: 5, events: events(j, 1) }));
    });
    var scn = Scene(host, 660, sts);
    scn.canvas.setAttribute('aria-label', '두 공고의 1년 연봉 흐름');
    var a = jobs[0], b = jobs[1], win = a.remain >= b.remain ? a : b, lose = win === a ? b : a;
    sts.forEach(function (st, i) {
      var j = jobs[i];
      labels(scn.svg, st, { fmt: man, startName: j.id + ' ' + j.name, sub: j === win && win.remain !== lose.remain ? lose.id + '보다 ' + man(win.remain - lose.remain) + ' 더' : '연봉의 ' + Math.round(j.remain / j.salary * 100) + '%' });
    });
    s('line', { x1: 0, x2: 960, y1: 335, y2: 335, class: 'rule' }, scn.svg);
    return scn;
  }

  /* 누적 흐름과 감면: 선택한 공고·시나리오, 서버가 계산한 누적 기간 */
  var SC = { none: '감면 없음', current_law: '현행법', proposal_base: '정부안(우대지역 아님)', proposal_pref: '정부안(우대지역)' };
  function mountCumulative(host, jobs, opt) {
    var job = opt.job || jobs[0].id, sc = opt.scenario || 'current_law', g = null;
    var head = el('div', 'flow-head', host), stats = el('div', 'flow-stats', head), ctr = el('div', 'flow-ctr', head);
    var s1 = el('div', 'flow-stat', stats), s2 = el('div', 'flow-stat', stats);
    el('span', 'k', s1, ''), el('span', 'v', s1, ''); el('span', 'k', s2, '감면으로 돌아온 세금'), el('span', 'v', s2, '');
    var jobChips = el('div', 'flow-chips', ctr), scChips = el('div', 'flow-chips', ctr);
    var box = el('div', 'flow-box', host), note = el('p', 'flow-note', host);
    function jobOf(id) { return jobs[0].id === id ? jobs[0] : jobs[1]; }
    function scen(j) { for (var i = 0; i < j.scenarios.length; i++) if (j.scenarios[i].id === sc) return j.scenarios[i]; return j.scenarios[0]; }
    function cfgFor() {
      var j = jobOf(job), sv = scen(j), Y = sv.yearly.length, yrs = Math.min(sv.reliefYears, Y), saved = j.taxRelief * yrs, tax = j.tax * Y;
      var ev = events(j, Y, saved), ti = -1; ev.forEach(function (e, i) { if (e.tax) ti = i; });
      return { Y: Y, saved: saved, total: sv.cumulativeRemaining,
        cfg: { salary: j.salary * Y, top: 50, k: 230 / (Math.max(jobs[0].salary, jobs[1].salary) * Y), x0: 160, xEnd: 780, floor: 470, speed: 105, n: 14000, wave: 7, events: ev,
          rescue: saved > 0 && ti >= 0 ? { ev: ti, frac: saved / tax } : null } };
    }
    var c = cfgFor(), st = Stream(c.cfg), scn = Scene(box, 560, [st]);
    scn.canvas.setAttribute('aria-label', '누적 연봉 흐름과 감면');
    function draw() {
      if (g) g.remove();
      g = labels(scn.svg, st, { fmt: eok, startName: c.Y + '년 연봉', endName: c.Y + '년 남는 돈', keepShown: c.total });
      s1.children[0].textContent = c.Y + '년 남는 돈'; s1.children[1].textContent = eok(c.total);
      s2.children[1].textContent = c.saved > 0 ? man(c.saved) : '0';
      var sv = scen(jobOf(job));
      note.textContent = SC[sc] + ' 기준, ' + jobOf(job).name + '의 감면 기간 ' + sv.reliefYears + '년.' + (sc.indexOf('proposal') === 0 ? ' 2026년 8월 정부 세제개편안 기준이며 국회 확정 전입니다.' : '') + ' 남는 돈은 서버가 계산한 누적값입니다.';
    }
    draw();
    function go() { c = cfgFor(); st.setCfg(c.cfg); draw(); }
    function chips(box, items, cur, pick) {
      items.forEach(function (it) {
        var b = el('button', null, box, it[1]); b.type = 'button'; b.setAttribute('aria-pressed', it[0] === cur);
        b.addEventListener('click', function () { [].forEach.call(box.children, function (x) { x.setAttribute('aria-pressed', x === b); }); pick(it[0]); go(); });
      });
    }
    chips(jobChips, jobs.map(function (j) { return [j.id, j.id + ' ' + j.name]; }), job, function (k) { job = k; });
    chips(scChips, Object.keys(SC).map(function (k) { return [k, SC[k]]; }), sc, function (k) { sc = k; });
    return scn;
  }

  window.MoneyFlow = {
    /* result: /api/compare 응답, names: {A: 이름, B: 이름}, scenario: 기본 시나리오 */
    mount: function (host, result, names, scenario) {
      if (!result || !result.jobs || result.jobs.length !== 2) return null;
      var jobs = result.jobs.map(function (j) { return fromJob(j, names[j.id] || ('공고 ' + j.id)); });
      var winner = jobs[0].remain >= jobs[1].remain ? jobs[0] : jobs[1];
      var yearBox = el('div', 'flow-box', host);
      mountYear(yearBox, jobs);
      el('h3', 'flow-sub', host, '누적 기간 동안의 흐름과 감면');
      mountCumulative(el('div', 'flow-cum', host), jobs, { job: winner.id, scenario: scenario });
      return true;
    }
  };
})();
