/* 첫 화면: 한국 POS 감열지 영수증 두 장이 출력된다.
   - 한 줄 42칸, 한글 2칸(전각)·영숫자 1칸(반각)으로 공백을 채워 정렬한다 (ESC/POS 프린터 방식)
   - 강조는 프린터 기능만 쓴다: 2배 확대, 반전 인쇄
   - "다시 출력"을 누르면 이전 영수증은 구겨져 버려지고 새로 출력된다
   숫자는 hero.json(계산 모듈 출력, scripts/build_hero.py)만 쓴다. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  if (!hero || !window.fetch) return;
  var rowsEl = document.getElementById('heroRows');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W = 42;                 // 80mm 감열지 한 줄 칸 수
  var timers = [];
  var data = null;
  var printedOnce = false;

  function won(n) { return Math.round(n).toLocaleString('ko-KR'); }
  function man(n) { return Math.round(n / 10000).toLocaleString('ko-KR'); }
  function later(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // 칸 수: 한글·전각 2칸, 나머지 1칸
  function cols(s) {
    var n = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      n += ((c >= 0x1100 && c <= 0x115f) || (c >= 0x2e80 && c <= 0xa4cf) || (c >= 0xac00 && c <= 0xd7a3) ||
            (c >= 0xf900 && c <= 0xfaff) || (c >= 0xff00 && c <= 0xff60) || (c >= 0xffe0 && c <= 0xffe6)) ? 2 : 1;
    }
    return n;
  }
  function sp(n) { return n > 0 ? new Array(n + 1).join(' ') : ''; }
  function lr(l, r, w) { return l + sp(Math.max(1, (w || W) - cols(l) - cols(r))) + r; }
  function center(s, w) { return sp(Math.floor(Math.max(0, (w || W) - cols(s)) / 2)) + s; }
  function rule(ch) { return new Array(W + 1).join(ch); }
  function ln(text, cls) { return '<span class="pl' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</span>'; }

  // 바코드: 요청 문자열로 막대 폭을 정한다 (장식)
  function barcode(seed) {
    var h = 0, bars = '';
    for (var i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
    for (var k = 0; k < 46; k++) {
      h = (h * 1103515245 + 12345) >>> 0;
      bars += '<i style="width:' + (1 + (h >>> 29) % 3) + 'px;margin-right:' + (1 + (h >>> 26) % 3) + 'px"></i>';
    }
    return '<div class="bc">' + bars + '</div>';
  }

  function receiptHtml(j, isWinner, gap, today) {
    var x = [];
    x.push(ln(center('[남는 돈 계산서]', W / 2), 'dbl'));
    x.push(ln(''));
    x.push(ln('근무지  ' + j.region));
    x.push(ln('기준    ' + data.rentPeriod + ' 원룸 월세'));
    x.push(ln('출력    ' + today));
    x.push(ln(rule('-')));
    x.push(ln(lr('항목', '금액')));
    x.push(ln(rule('-')));
    x.push(ln(lr('연봉', won(j.salary))));
    x.push(ln(lr('세금과 4대보험', '-' + won(j.taxAndInsurance))));
    x.push(ln(lr('월세 ' + won(j.rentMonthly) + ' x 12', '-' + won(j.rentAnnual))));
    x.push(ln(rule('=')));
    x.push(ln(lr('남는 돈', won(j.remaining), W / 2), 'dbl'));
    x.push(ln(rule('=')));
    if (isWinner) {
      x.push(ln(center(j.label + ' 쪽이 1년에 ' + won(gap) + '원 더 남음'), 'rev tall'));
    } else {
      x.push(ln(center('* 연봉이 높아도 남는 돈은 적습니다 *')));
    }
    x.push(ln(''));
    x.push(ln(center('1년차, 감면 없음, 식대 월 20만 원 비과세')));
    return '<pre class="tp">' + x.join('\n') + '</pre>' + barcode(j.sggCode + j.salary) + '<div class="feedtail"></div>';
  }

  function render() {
    var a = data.jobs[0], b = data.jobs[1];
    var winner = a.remaining >= b.remaining ? a : b, loser = winner === a ? b : a;
    var richer = a.salary >= b.salary ? a : b, other = richer === a ? b : a;
    var gap = winner.remaining - loser.remaining;
    var d = new Date(), today = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
    rowsEl.innerHTML = '';
    data.jobs.forEach(function (j) {
      var box = document.createElement('div');
      box.className = 'printer';
      box.innerHTML = '<div class="slot"></div><div class="feed"><div class="receipt thermal">' +
        receiptHtml(j, j === winner, gap, today) + '</div></div>';
      rowsEl.appendChild(box);
      j._box = box;
    });
    var cap = document.getElementById('heroCaption');
    cap.textContent = winner === richer
      ? '연봉이 ' + man(richer.salary - other.salary) + '만 원 높은 ' + richer.label + ' 쪽이 1년에 ' + man(gap) + '만 원 더 남습니다.'
      : '연봉은 ' + richer.label + '이 ' + man(richer.salary - other.salary) + '만 원 높지만, 1년에 남는 돈은 ' + winner.label + '이 ' + man(gap) + '만 원 많습니다.';
    document.getElementById('heroNote').textContent = '예시: ' + data.assumption + '. 금액은 서버의 계산 코드가 산출했습니다.';
  }

  // 이전 영수증을 구겨서 버린다: 당김 → 구김(윤곽이 뭉개지고 작아짐) → 중력으로 낙하
  function crumplePoly(w, h, seed, amount) {
    var pts = [], n = 22, cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.34, s = seed;
    for (var i = 0; i < n; i++) {
      var t = i / n, px, py, per = 2 * (w + h), dpos = t * per;
      if (dpos < w) { px = dpos; py = 0; }
      else if (dpos < w + h) { px = w; py = dpos - w; }
      else if (dpos < 2 * w + h) { px = w - (dpos - w - h); py = h; }
      else { px = 0; py = h - (dpos - 2 * w - h); }
      s = (s * 9301 + 49297) % 233280;
      var ang = Math.atan2(py - cy, px - cx), r = R * (0.72 + 0.5 * (s / 233280));
      var bx = cx + Math.cos(ang) * r, by = cy + Math.sin(ang) * r;
      pts.push((px + (bx - px) * amount).toFixed(1) + 'px ' + (py + (by - py) * amount).toFixed(1) + 'px');
    }
    return 'polygon(' + pts.join(',') + ')';
  }

  function discard(box, idx) {
    var paper = box.querySelector('.receipt');
    if (!paper || !paper.animate) return;
    var r = paper.getBoundingClientRect();
    if (r.height < 10 || r.bottom < 0) return;
    var layer = document.getElementById('trashLayer');
    if (!layer) { layer = document.createElement('div'); layer.id = 'trashLayer'; document.body.appendChild(layer); }
    var c = paper.cloneNode(true);
    c.classList.add('discarding');
    c.style.left = r.left + 'px'; c.style.top = r.top + 'px'; c.style.width = r.width + 'px'; c.style.height = r.height + 'px';
    var wr = document.createElement('div'); wr.className = 'wrinkle'; c.appendChild(wr);
    layer.appendChild(c);
    var w = r.width, h = r.height, seed = 17 + idx * 101;
    var dir = idx === 0 ? -1 : 1;
    var fall = window.innerHeight - r.top + 200;
    var anim = c.animate([
      { offset: 0, transform: 'translate(0,0) rotate(0deg) scale(1)', clipPath: crumplePoly(w, h, seed, 0), easing: 'cubic-bezier(.3,0,.2,1)' },
      { offset: 0.14, transform: 'translate(0,16px) rotate(' + (dir * 1.5) + 'deg) scale(1)', clipPath: crumplePoly(w, h, seed, 0.04), easing: 'cubic-bezier(.5,0,.3,1)' },
      { offset: 0.5, transform: 'translate(' + (dir * 30) + 'px,-10px) rotate(' + (dir * 35) + 'deg) scale(.36)', clipPath: crumplePoly(w, h, seed, 1), easing: 'cubic-bezier(.55,0,1,.45)' },
      { offset: 1, transform: 'translate(' + (dir * 160) + 'px,' + fall + 'px) rotate(' + (dir * 320) + 'deg) scale(.3)', clipPath: crumplePoly(w, h, seed, 1) }
    ], { duration: 1150, fill: 'forwards' });
    wr.animate([{ opacity: 0 }, { opacity: 0 , offset: 0.15 }, { opacity: 1, offset: 0.5 }, { opacity: 1 }], { duration: 1150, fill: 'forwards' });
    anim.onfinish = function () { c.remove(); };
  }

  function play() {
    timers.forEach(clearTimeout); timers = [];
    var delay = 0;
    if (printedOnce && !reduce) {
      data.jobs.forEach(function (j, i) { discard(j._box, i); });
      delay = 450;
    }
    printedOnce = true;
    hero.classList.remove('printed');
    data.jobs.forEach(function (j) { j._box.classList.remove('go'); });
    void hero.offsetWidth;
    if (reduce) { hero.classList.add('printed'); data.jobs.forEach(function (j) { j._box.classList.add('go'); }); return; }
    later(delay + 200, function () { data.jobs[0]._box.classList.add('go'); });
    later(delay + 650, function () { data.jobs[1]._box.classList.add('go'); });
    later(delay + 2900, function () { hero.classList.add('printed'); });
  }

  fetch('hero.json', { cache: 'no-cache' }).then(function (r) {
    if (!r.ok) throw new Error('hero.json ' + r.status);
    return r.json();
  }).then(function (d) {
    if (!d || !d.jobs || d.jobs.length !== 2) return;
    data = d;
    render();
    hero.hidden = false;
    document.getElementById('heroReplay').addEventListener('click', play);
    play();
  }).catch(function () { hero.hidden = true; });
})();
