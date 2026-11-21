/* 첫 화면 예시 애니메이션. 숫자는 hero.json(계산 모듈 출력, scripts/build_hero.py)만 쓴다.
   연봉 막대에서 세금과 월세가 차례로 깎여 나가고, 남는 돈이 줄어드는 장면 하나만 보여준다. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  if (!hero || !window.fetch) return;
  var rowsEl = document.getElementById('heroRows');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timers = [];
  var data = null;

  function man(won) { return Math.round(won / 10000).toLocaleString('ko-KR'); }
  function later(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }

  function count(el, from, to, ms) {
    if (reduce || ms <= 0) { el.textContent = man(to); return; }
    var start = null;
    function step(t) {
      if (start === null) start = t;
      var p = Math.min(1, (t - start) / ms);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = man(from + (to - from) * e);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function pct(part, whole) { return (part / whole * 100).toFixed(3) + '%'; }

  function render() {
    var jobs = data.jobs;
    var max = Math.max.apply(null, jobs.map(function (j) { return j.salary; }));
    rowsEl.innerHTML = '';
    jobs.forEach(function (j) {
      var row = document.createElement('div');
      row.className = 'hero-row';
      row.innerHTML =
        '<div class="hero-who"><b>' + j.region + '</b><span>연봉 ' + man(j.salary) + '만 원</span></div>' +
        '<div class="hero-track"><div class="hero-bar" style="--w:' + pct(j.salary, max) + '">' +
        '<i class="seg remain"></i><i class="seg tax"></i><i class="seg rent"></i></div></div>' +
        '<div class="hero-num"><span class="n">' + man(j.salary) + '</span><small>만 원</small></div>';
      rowsEl.appendChild(row);
      j._row = row;
    });
    var a = jobs[0], b = jobs[1];
    var richer = a.salary >= b.salary ? a : b, other = richer === a ? b : a;
    var winner = a.remaining >= b.remaining ? a : b, loser = winner === a ? b : a;
    var cap = document.getElementById('heroCaption');
    if (winner === richer) {
      cap.textContent = '연봉이 ' + man(richer.salary - other.salary) + '만 원 높은 ' + richer.label + ' 쪽이 1년에 ' +
        man(winner.remaining - loser.remaining) + '만 원 더 남습니다.';
    } else {
      cap.textContent = '연봉은 ' + richer.label + '이 ' + man(richer.salary - other.salary) + '만 원 높지만, 1년에 남는 돈은 ' +
        winner.label + '이 ' + man(winner.remaining - loser.remaining) + '만 원 많습니다.';
    }
    data._winner = winner;
    document.getElementById('heroNote').textContent = '예시: ' + data.assumption + '(' + data.rentPeriod +
      ' 실거래 기준). 금액은 서버의 계산 코드가 산출했습니다.';
  }

  function setSegs(j, tax, rent) {
    var s = j._row.querySelectorAll('.seg');
    s[1].style.width = pct(tax, j.salary);
    s[2].style.width = pct(rent, j.salary);
  }

  function play() {
    clearTimers();
    hero.classList.remove('done');
    data.jobs.forEach(function (j) {
      j._row.classList.remove('win');
      j._row.querySelector('.hero-bar').classList.remove('grown');
      setSegs(j, 0, 0);
      j._row.querySelector('.n').textContent = man(j.salary);
    });
    if (reduce) {
      data.jobs.forEach(function (j) {
        j._row.querySelector('.hero-bar').classList.add('grown');
        setSegs(j, j.taxAndInsurance, j.rentAnnual);
        j._row.querySelector('.n').textContent = man(j.remaining);
      });
      data._winner._row.classList.add('win');
      hero.classList.add('done');
      return;
    }
    // 1) 연봉 막대가 자란다  2) 세금이 깎인다  3) 월세가 깎인다  4) 결론
    later(150, function () { data.jobs.forEach(function (j) { j._row.querySelector('.hero-bar').classList.add('grown'); }); });
    later(1000, function () {
      data.jobs.forEach(function (j) {
        setSegs(j, j.taxAndInsurance, 0);
        count(j._row.querySelector('.n'), j.salary, j.salary - j.taxAndInsurance, 600);
      });
    });
    later(1900, function () {
      data.jobs.forEach(function (j) {
        setSegs(j, j.taxAndInsurance, j.rentAnnual);
        count(j._row.querySelector('.n'), j.salary - j.taxAndInsurance, j.remaining, 800);
      });
    });
    later(2900, function () { data._winner._row.classList.add('win'); hero.classList.add('done'); });
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
