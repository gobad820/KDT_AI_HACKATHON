/* 첫 화면: 영수증 두 장이 프린터에서 출력되고, 더 남는 쪽에 도장이 찍힌다.
   숫자는 hero.json(계산 모듈 출력, scripts/build_hero.py)만 쓴다. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  if (!hero || !window.fetch) return;
  var rowsEl = document.getElementById('heroRows');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timers = [];
  var data = null;

  function won(n) { return Math.round(n).toLocaleString('ko-KR'); }
  function man(n) { return Math.round(n / 10000).toLocaleString('ko-KR'); }
  function later(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function line(label, value, cls) {
    return '<div class="r-line ' + (cls || '') + '"><span>' + label + '</span><span class="num">' + value + '</span></div>';
  }

  function render() {
    var a = data.jobs[0], b = data.jobs[1];
    var winner = a.remaining >= b.remaining ? a : b, loser = winner === a ? b : a;
    var richer = a.salary >= b.salary ? a : b, other = richer === a ? b : a;
    var gap = winner.remaining - loser.remaining;
    rowsEl.innerHTML = '';
    data.jobs.forEach(function (j) {
      var box = document.createElement('div');
      box.className = 'printer';
      box.innerHTML =
        '<div class="slot"></div>' +
        '<div class="feed"><div class="receipt">' +
        '<div class="r-head">' + esc(j.region) + '</div>' +
        '<div class="r-sub">' + esc(data.rentPeriod) + ' 월세 기준, 1년</div>' +
        '<div class="r-rule"></div>' +
        line('연봉', won(j.salary)) +
        line('세금과 4대보험', '-' + won(j.taxAndInsurance)) +
        line('월세 ' + man(j.rentMonthly) + '만 x 12', '-' + won(j.rentAnnual)) +
        '<div class="r-rule"></div>' +
        line('남는 돈', won(j.remaining), 'total') +
        '<div class="r-stampzone">' +
        (j === winner ? '<div class="stamp"><b>' + man(gap) + '만 원</b><span>더 남음</span></div>' : '') +
        '</div><div class="r-cut"></div>' +
        '</div></div>';
      rowsEl.appendChild(box);
      j._box = box;
    });
    var cap = document.getElementById('heroCaption');
    cap.textContent = winner === richer
      ? '연봉이 ' + man(richer.salary - other.salary) + '만 원 높은 ' + richer.label + ' 쪽이 1년에 ' + man(gap) + '만 원 더 남습니다.'
      : '연봉은 ' + richer.label + '이 ' + man(richer.salary - other.salary) + '만 원 높지만, 1년에 남는 돈은 ' + winner.label + '이 ' + man(gap) + '만 원 많습니다.';
    document.getElementById('heroNote').textContent = '예시: ' + data.assumption + '. 금액은 서버의 계산 코드가 산출했습니다.';
  }

  function play() {
    timers.forEach(clearTimeout); timers = [];
    hero.classList.remove('printed', 'stamped');
    data.jobs.forEach(function (j) { j._box.classList.remove('go'); });
    void hero.offsetWidth;   // 처음 상태로 되돌린 뒤 다시 재생
    if (reduce) { hero.classList.add('printed', 'stamped'); data.jobs.forEach(function (j) { j._box.classList.add('go'); }); return; }
    later(200, function () { data.jobs[0]._box.classList.add('go'); });
    later(650, function () { data.jobs[1]._box.classList.add('go'); });
    later(2700, function () { hero.classList.add('printed'); });
    later(3100, function () { hero.classList.add('stamped'); });
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
