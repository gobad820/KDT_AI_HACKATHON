/* 첫 화면: Blender로 렌더한 POS 감열 프린터 출력 영상(img/hero_print.mp4)을 제어한다.
   - 처음: 0초부터 재생해 영수증이 다 나오고 잘린 뒤(pauseAt) 멈춘다
   - 다시 출력: 멈춘 자리에서 이어서 재생한다. 정지 구간(pauseAt~tossAt)은 빨리 지나가고, 구겨서 던지는 장면은 제 속도로 본다.
     영상이 끝나면 0초부터 다시 출력해 pauseAt에서 멈춘다
   - 움직임 줄이기 설정, 자동 재생 거부, 불러오기 실패·지연이면 출력이 끝난 장면(still 이미지)을 보여 준다
   영수증 숫자는 hero.json(계산 모듈 출력, scripts/build_hero.py)을 media/printer/receipt_texture.js로 감열 인쇄해 렌더에 구운 것이다.
   영수증에 쓰는 1년차 값(jobs[]의 label·region·salary·taxAndInsurance·rentAnnual·remaining, rentPeriod)이 바뀌면 media/printer 의 텍스처와 영상을 다시 만든다(render_hero.py 머리말 참고).
   아래 문장(heroFact, heroNote)도 같은 hero.json에서 만든다. 문장에는 1년 숫자와 누적(horizonYears년) 숫자를 함께 밝힌다. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  var video = document.getElementById('heroVideo');
  var replay = document.getElementById('heroReplay');
  if (!hero || !window.fetch) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var STILL = 'img/hero_print_still.webp?v=2', SKIP = 2.5;
  var tl = null, stopAt = null, busy = true, started = false, guard = null;

  function man(n) { return Math.round(n / 10000).toLocaleString('ko-KR'); }
  function lock(on) { busy = on; if (replay) replay.setAttribute('aria-disabled', on ? 'true' : 'false'); }

  function done() {
    stopAt = null; clearTimeout(guard);
    video.playbackRate = 1;
    hero.classList.add('printed');
    lock(false);
  }

  // 출력이 끝난 장면에 멈춘다. 영상 데이터가 없어도 포스터가 같은 장면을 보여 준다
  function still() {
    if (!video) return;
    started = true;
    video.onended = null;
    video.poster = STILL;
    try { video.pause(); } catch (e) { /* 무시 */ }
    if (tl) { try { video.currentTime = tl.pauseAt; } catch (e) { /* 아직 불러오는 중 */ } }
    done();
    if (reduce && replay) replay.hidden = true;
  }

  function overdue(ms) { clearTimeout(guard); guard = setTimeout(function () { if (busy) still(); }, ms); }

  // 멈출 시점 감시. 백그라운드 탭에서 지나쳤으면 멈출 시점으로 되돌린다
  function check() {
    if (stopAt === null) return;
    if (tl && video.playbackRate !== 1 && video.currentTime >= tl.tossAt) video.playbackRate = 1;
    if (video.currentTime >= stopAt) {
      video.pause();
      if (video.currentTime > stopAt + 0.1) { try { video.currentTime = stopAt; } catch (e) { /* 무시 */ } }
      done();
    }
  }
  function watch() { check(); if (stopAt !== null) requestAnimationFrame(watch); }

  function play(onFail) {
    var p = video.play();
    if (p && p.catch) p.catch(onFail || still);
  }

  function runTo(from, to) {
    lock(true); stopAt = to;
    hero.classList.remove('printed');
    video.onended = still;
    try { video.currentTime = from; } catch (e) { /* 무시 */ }
    play();
    overdue((to - from) * 1000 + 4000);
    requestAnimationFrame(watch);
  }

  function reprint() {
    if (!tl || busy || reduce) return;
    lock(true); stopAt = null;
    hero.classList.remove('printed');
    video.onended = function () { video.onended = null; runTo(0, tl.pauseAt); };
    if (video.currentTime < tl.tossAt) video.playbackRate = SKIP;
    play();
    overdue((tl.duration - video.currentTime) * 1000 + 4000);
    (function speed() { if (busy && stopAt === null) { if (video.currentTime >= tl.tossAt) video.playbackRate = 1; requestAnimationFrame(speed); } })();
  }

  function startVideo() {
    if (!video) return;
    lock(true);
    if (replay) replay.addEventListener('click', reprint);
    video.addEventListener('error', still);
    video.addEventListener('timeupdate', check);
    document.addEventListener('visibilitychange', function () { if (document.hidden && busy && started) still(); });
    fetch('img/hero_print.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (t) {
      tl = t;
      if (reduce) { still(); return; }
      var go = function () { if (started) return; started = true; runTo(0, tl.pauseAt); };
      if (video.readyState >= 2) go();
      else {
        video.addEventListener('loadeddata', go, { once: true });
        setTimeout(function () { if (!started) still(); }, 3500);   // 저전력 모드 등으로 불러오지 않으면
      }
    }).catch(still);
  }

  // 1년 숫자(영수증과 같은 값)와 누적 숫자를 함께 쓴다. 누적 차이는 화면에서 곱하지 않고 hero.json comparison.difference(simulate 출력)를 쓴다
  function wire(data) {
    var A = data.jobs[0], B = data.jobs[1], win = A.remaining >= B.remaining ? A : B, lose = win === A ? B : A;
    var rich = A.salary >= B.salary ? A : B, poor = rich === A ? B : A;
    var c = data.comparison, n = data.horizonYears;
    var many = c && n > 1 && c.betterJob === win.label;   // 누적에서도 같은 쪽이 더 남을 때만 이어 쓴다
    var gap = many
      ? '1년에 <b>' + man(win.remaining - lose.remaining) + '만 원</b>, ' + n + '년이면 <mark>' + man(c.difference) + '만 원</mark> 더 남습니다.'
      : '1년에 <mark>' + man(win.remaining - lose.remaining) + '만 원</mark> 더 남습니다.';
    document.getElementById('heroFact').innerHTML = (win !== rich
      ? '연봉이 <b>' + man(rich.salary - poor.salary) + '만 원</b> 낮은 ' + win.label + ' 공고가 '
      : win.label + ' 공고가 ') + gap;
    document.getElementById('heroNote').textContent = '예시: ' + A.region + ' 연봉 ' + man(A.salary) + '만 원과 ' + B.region + ' 연봉 ' + man(B.salary) + '만 원, '
      + (many ? '감면 없음. 영수증은 1년차 금액이고, ' + n + '년 금액은 같은 연봉과 월세가 이어진다고 보고 ' + n + '년을 더한 값입니다.' : '1년차, 감면 없음.');
  }

  var card = document.querySelector('#step1 .card');
  document.getElementById('heroOwn').addEventListener('click', function () {
    card.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    setTimeout(function () { var t = document.getElementById('textA'); if (t) t.focus({ preventScroll: true }); }, 450);
  });
  document.getElementById('heroTry').addEventListener('click', function () {
    var b = document.querySelector('#sampleButtons button');
    if (b) b.click();
    card.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  });

  startVideo();
  fetch('hero.json', { cache: 'no-cache' }).then(function (r) {
    if (!r.ok) throw new Error('hero.json ' + r.status);
    return r.json();
  }).then(function (d) {
    if (!d || !d.jobs || d.jobs.length !== 2) throw new Error('bad');
    wire(d);
  }).catch(function () { /* 문장 없이 둔다 */ });
})();
