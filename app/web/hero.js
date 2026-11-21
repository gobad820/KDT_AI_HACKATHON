/* 첫 화면: POS 감열 프린터 시뮬레이션.
   감열 프린터는 글꼴을 그리지 않고 한 줄 576개의 점(80mm, 203dpi)을 열로 태운다.
   그래서 576점 폭 캔버스에 글자를 그린 뒤, 점마다 찍힐지 판정하고 진하기를 흩뜨린다.
   - 한 줄 42칸: 영숫자 12점(반각), 한글 24점(전각). 공백으로 정렬한다
   - 강조는 프린터 기능(2배 확대, 굵게)과 형광펜만 쓴다
   숫자는 hero.json(계산 모듈 출력, scripts/build_hero.py)만 쓴다. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  var wrap = document.getElementById('paperWrap');
  if (!hero || !wrap || !window.fetch) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DOTS = 576, COLS = 42, CELL = 12, ROW = 30, MARGIN = (DOTS - COLS * CELL) / 2, FONT = '"Pretendard Variable", Pretendard, "Apple SD Gothic Neo", sans-serif';
  var data = null, paper = null, timers = [], printedOnce = false, seq = 0;

  function won(n) { return Math.round(n).toLocaleString('ko-KR'); }
  function man(n) { return Math.round(n / 10000).toLocaleString('ko-KR'); }
  function later(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function rng(seed) { return function () { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; }
  function wide(c) { return (c >= 0x1100 && c <= 0x115f) || (c >= 0x2e80 && c <= 0xa4cf) || (c >= 0xac00 && c <= 0xd7a3) || (c >= 0xff00 && c <= 0xff60); }
  function cols(s) { var n = 0; for (var i = 0; i < s.length; i++) n += wide(s.charCodeAt(i)) ? 2 : 1; return n; }
  function sp(n) { return n > 0 ? new Array(n + 1).join(' ') : ''; }
  function lr(l, r, w) { w = w || COLS; return l + sp(Math.max(1, w - cols(l) - cols(r))) + r; }
  function center(s, w) { w = w || COLS; return sp(Math.floor(Math.max(0, w - cols(s)) / 2)) + s; }
  function rpad(s, w) { return sp(w - cols(s)) + s; }
  function row3(a, b, c) { return a + sp(18 - cols(a)) + rpad(b, 12) + rpad(c, 12); }
  function rule(ch) { return new Array(COLS + 1).join(ch); }

  // 영수증 줄 목록. size 2 = 가로·세로 2배, bold = 두 번 찍기
  function lines(now) {
    var A = data.jobs[0], B = data.jobs[1];
    var win = A.remaining >= B.remaining ? A : B, gap = Math.abs(A.remaining - B.remaining), wk = win === A ? 'A' : 'B';
    var d = now, ts = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2) + ' ' +
      ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    return [
      { t: center('남는 돈 계산서', COLS / 2), size: 2 },
      { t: center('nammeun-don.vercel.app') },
      { t: lr(ts, 'No.' + ('000' + (seq % 10000)).slice(-4)) },
      { t: rule('-') },
      { t: 'A ' + A.region },
      { t: 'B ' + B.region },
      { t: rule('-') },
      { t: row3('항목', 'A ' + A.label, 'B ' + B.label), bold: true },
      { t: rule('-') },
      { t: row3('연봉', won(A.salary), won(B.salary)) },
      { t: row3('세금과 4대보험', '-' + won(A.taxAndInsurance), '-' + won(B.taxAndInsurance)) },
      { t: row3('월세 x 12', '-' + won(A.rentAnnual), '-' + won(B.rentAnnual)) },
      { t: rule('=') },
      { t: row3('남는 돈', won(A.remaining), won(B.remaining)), bold: true, key: 'remain', hiCol: wk },
      { t: rule('=') },
      { t: lr('1년 차이', wk + ' +' + won(gap)), bold: true, key: 'gap' },
      { t: '' },
      { t: '* 1년차, 감면 없음, 식대 월 20만 원 비과세' },
      { t: '* 월세: ' + data.rentPeriod + ' 원룸 중위값' },
      { t: '* 금액은 서버의 계산 코드가 산출' },
      { t: '' },
      { barcode: true },
      { t: center('연봉 말고 남는 돈으로 고르세요') },
      { t: '' }
    ];
  }

  // 1) 576점 캔버스에 글자를 칸 단위로 그린다
  function typeset(L) {
    var y = 34, rows = [];
    L.forEach(function (ln) { var h = ln.barcode ? 86 : ln.size === 2 ? ROW * 2 : ROW; rows.push({ y: y, h: h, ln: ln }); y += h; });
    var H = y + 30;
    var c = document.createElement('canvas'); c.width = DOTS; c.height = H;
    var g = c.getContext('2d'); g.fillStyle = '#000'; g.textBaseline = 'alphabetic';
    var r = rng(7 + seq * 13);
    rows.forEach(function (rw) {
      var ln = rw.ln;
      if (ln.barcode) {
        var x = MARGIN + 60;
        while (x < DOTS - MARGIN - 60) { var w = 2 + Math.floor(r() * 3) * 2; if (r() > .42) g.fillRect(x, rw.y + 6, w, 66); x += w + 2 + Math.floor(r() * 2) * 2; }
        return;
      }
      var s = ln.size || 1, col = 0, text = ln.t || '';
      for (var i = 0; i < text.length; i++) {
        var ch = text[i], cw = (wide(text.charCodeAt(i)) ? 2 : 1) * CELL * s;
        if (ch !== ' ') {
          g.font = (wide(text.charCodeAt(i)) ? '600 ' + (22 * s) : '700 ' + (21 * s)) + 'px ' + FONT;
          var m = g.measureText(ch).width, x0 = MARGIN + col * CELL + (cw - m) / 2;
          var by = rw.y + 21 * s;
          if (ch === '-' || ch === '=') {   // 구분선은 칸을 꽉 채운 점선으로
            if (ch === '-') g.fillRect(MARGIN + col * CELL + 1, rw.y + 12 * s, CELL - 2, 2);
            else { g.fillRect(MARGIN + col * CELL + 1, rw.y + 9, CELL - 2, 2); g.fillRect(MARGIN + col * CELL + 1, rw.y + 15, CELL - 2, 2); }
          } else {
            g.fillText(ch, x0, by);
            if (ln.bold || s === 2) g.fillText(ch, x0 + 1, by);
          }
        }
        col += cw / CELL;
      }
    });
    return { canvas: c, rows: rows, H: H };
  }

  // 2) 점 단위 판정: 열 헤드가 점을 태우는 방식
  function burn(ts) {
    var c = ts.canvas, g = c.getContext('2d'), img = g.getImageData(0, 0, c.width, c.height), px = img.data;
    var r = rng(91 + seq * 7), W = c.width, H = c.height;
    var band = [], streak = [];
    for (var y = 0; y < H; y++) band.push(.86 + .14 * Math.sin(y / 9.5 + r() * .8) * .5 + r() * .08);  // 헤드 온도에 따른 가로 얼룩
    for (var x = 0; x < W; x++) streak.push(1);
    [137, 138, 311, 449].forEach(function (sx) { streak[sx] = .25; });                               // 점이 빠진 세로 줄
    for (var i = 0; i < W * H; i++) {
      var a = px[i * 4 + 3] / 255, x2 = i % W, y2 = (i / W) | 0;
      var on = a > .44 + (r() - .5) * .22;
      if (on && r() < .015) on = false;                                                                 // 드문드문 빠지는 점
      var dens = on ? Math.min(1, band[y2] * streak[x2] * (.84 + r() * .2)) : 0;
      px[i * 4] = 38; px[i * 4 + 1] = 38; px[i * 4 + 2] = 42; px[i * 4 + 3] = Math.round(dens * 238);
    }
    g.putImageData(img, 0, 0);
    return c.toDataURL('image/png');
  }

  function build() {
    seq += 1;
    var L = lines(new Date()), ts = typeset(L), url = burn(ts);
    var el = document.createElement('div'); el.className = 'thermal-paper';
    var img = document.createElement('img'); img.alt = ''; img.src = url; img.draggable = false; el.appendChild(img);
    var hl = [];
    ts.rows.forEach(function (rw) {
      if (rw.ln.key === 'remain') hl.push({ y: rw.y, h: rw.h, x0: MARGIN + (rw.ln.hiCol === 'A' ? 18 : 30) * CELL - 2, x1: MARGIN + (rw.ln.hiCol === 'A' ? 30 : 42) * CELL + 2 });
      if (rw.ln.key === 'gap') hl.push({ y: rw.y, h: rw.h, x0: MARGIN + 26 * CELL, x1: MARGIN + 42 * CELL + 2 });
    });
    hl.forEach(function (h, i) {
      var m = document.createElement('i'); m.className = 'marker m' + i;
      m.style.left = (h.x0 / DOTS * 100) + '%'; m.style.width = ((h.x1 - h.x0) / DOTS * 100) + '%';
      m.style.top = ((h.y - 3) / ts.H * 100) + '%'; m.style.height = ((h.h + 2) / ts.H * 100) + '%';
      el.appendChild(m);
    });
    var shade = document.createElement('div'); shade.className = 'paper-shade'; el.appendChild(shade);
    return { el: el, rows: ts.rows, H: ts.H };
  }

  // 3) 출력: 줄마다 덜컥 밀려 올라온다 (아래가 프린터 출구)
  function print(p) {
    wrap.appendChild(p.el);
    var fullW = p.el.getBoundingClientRect().width, k = fullW / DOTS;
    var stops = p.rows.map(function (rw) { return (rw.y + rw.h) * k; }).concat([p.H * k]);
    p.el.style.height = '0px';
    if (reduce) { p.el.style.height = p.H * k + 'px'; p.el.classList.add('done'); hero.classList.add('printed'); return; }
    var t = 250;
    stops.forEach(function (h, i) {
      later(t, function () { p.el.style.height = h + 'px'; wrap.classList.add('feeding'); });
      t += i === 0 ? 180 : (p.rows[i] && p.rows[i].ln.barcode ? 160 : 95);
    });
    later(t + 60, function () { wrap.classList.remove('feeding'); p.el.classList.add('done'); hero.classList.add('printed'); });
  }

  // 다시 출력: 이전 영수증을 뜯어서 구겨 버린다
  function crumplePoly(w, h, seed, amount) {
    var pts = [], n = 22, cx = w / 2, cy = h / 2, R = Math.min(w, h) * .36, r = rng(seed);
    for (var i = 0; i < n; i++) {
      var d = i / n * 2 * (w + h), px, py;
      if (d < w) { px = d; py = 0; } else if (d < w + h) { px = w; py = d - w; } else if (d < 2 * w + h) { px = w - (d - w - h); py = h; } else { px = 0; py = h - (d - 2 * w - h); }
      var a = Math.atan2(py - cy, px - cx), rr = R * (.7 + .55 * r());
      pts.push((px + (cx + Math.cos(a) * rr - px) * amount).toFixed(1) + 'px ' + (py + (cy + Math.sin(a) * rr - py) * amount).toFixed(1) + 'px');
    }
    return 'polygon(' + pts.join(',') + ')';
  }
  function discard(old) {
    if (!old || !old.el.animate) { if (old) old.el.remove(); return; }
    var r = old.el.getBoundingClientRect();
    var layer = document.getElementById('trashLayer');
    if (!layer) { layer = document.createElement('div'); layer.id = 'trashLayer'; document.body.appendChild(layer); }
    var c = old.el; c.classList.add('discarding');
    c.style.left = r.left + 'px'; c.style.top = r.top + 'px'; c.style.width = r.width + 'px'; c.style.height = r.height + 'px';
    var wr = document.createElement('div'); wr.className = 'wrinkle'; c.appendChild(wr);
    layer.appendChild(c);
    var w = r.width, h = r.height, fall = window.innerHeight - r.top + 240;
    var an = c.animate([
      { offset: 0, transform: 'translate(0,0) rotate(0deg) scale(1)', clipPath: crumplePoly(w, h, 5, 0), easing: 'cubic-bezier(.3,0,.2,1)' },
      { offset: .16, transform: 'translate(0,-22px) rotate(-1.5deg) scale(1)', clipPath: crumplePoly(w, h, 5, .03), easing: 'cubic-bezier(.5,0,.3,1)' },
      { offset: .52, transform: 'translate(-60px,-40px) rotate(-38deg) scale(.34)', clipPath: crumplePoly(w, h, 5, 1), easing: 'cubic-bezier(.55,0,1,.45)' },
      { offset: 1, transform: 'translate(-260px,' + fall + 'px) rotate(-340deg) scale(.3)', clipPath: crumplePoly(w, h, 5, 1) }
    ], { duration: 1250, fill: 'forwards' });
    wr.animate([{ opacity: 0 }, { opacity: 0, offset: .16 }, { opacity: 1, offset: .52 }, { opacity: 1 }], { duration: 1250, fill: 'forwards' });
    an.onfinish = function () { c.remove(); };
  }

  function play() {
    timers.forEach(clearTimeout); timers = [];
    hero.classList.remove('printed');
    var old = paper;
    paper = build();
    if (old) { if (reduce) old.el.remove(); else discard(old); }
    later(old && !reduce ? 380 : 0, function () { print(paper); });
    printedOnce = true;
  }

  function wire() {
    var A = data.jobs[0], B = data.jobs[1], win = A.remaining >= B.remaining ? A : B, lose = win === A ? B : A;
    var rich = A.salary >= B.salary ? A : B, poor = rich === A ? B : A;
    document.getElementById('heroFact').innerHTML = win !== rich
      ? '연봉이 <b>' + man(rich.salary - poor.salary) + '만 원</b> 낮은 ' + win.label + ' 공고가 1년에 <mark>' + man(win.remaining - lose.remaining) + '만 원</mark> 더 남습니다.'
      : win.label + ' 공고가 1년에 <mark>' + man(win.remaining - lose.remaining) + '만 원</mark> 더 남습니다.';
    document.getElementById('heroNote').textContent = '예시: ' + A.region + ' 연봉 ' + man(A.salary) + '만 원과 ' + B.region + ' 연봉 ' + man(B.salary) + '만 원, 1년차, 감면 없음.';
    document.getElementById('heroReplay').addEventListener('click', play);
    var card = document.querySelector('#step1 .card');
    document.getElementById('heroOwn').addEventListener('click', function () { card.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }); setTimeout(function () { var t = document.getElementById('textA'); if (t) t.focus({ preventScroll: true }); }, 450); });
    document.getElementById('heroTry').addEventListener('click', function () {
      var b = document.querySelector('#sampleButtons button');
      if (b) b.click();
      card.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    });
  }

  fetch('hero.json', { cache: 'no-cache' }).then(function (r) {
    if (!r.ok) throw new Error('hero.json ' + r.status);
    return r.json();
  }).then(function (d) {
    if (!d || !d.jobs || d.jobs.length !== 2) throw new Error('bad');
    data = d;
    wire();
    var probe = data.jobs.map(function (j) { return j.region; }).join('') + '남는 돈 계산서 항목 연봉 세금과 4대보험 월세 차이 감면 없음 식대 비과세 원룸 중위값 금액은 서버의 계산 코드가 산출 고르세요';
    var fonts = document.fonts ? Promise.all([document.fonts.load('600 22px "Pretendard Variable"', probe), document.fonts.load('700 21px "Pretendard Variable"', '0123456789,-+.:No')]) : Promise.resolve();
    return fonts.catch(function () {}).then(function () { play(); });
  }).catch(function () { var s = hero.querySelector('.hero-stage'); if (s) s.hidden = true; });
})();
