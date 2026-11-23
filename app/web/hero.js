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

  // 샘플 영수증 요약. 금액은 모두 hero.json(계산 모듈 출력)에서 온다: 공고별 1년차 남는 돈(remaining), 1년차 차이(두 remaining의 차),
  // 누적 차이는 화면에서 곱하지 않고 comparison.difference(simulate 출력)를 쓴다. 날짜는 실제 데이터인 월세 수집 기간(rentPeriod)만 쓴다
  function esc(s) { return String(s).replace(/[&<>"]/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]; }); }
  function won(n) { return man(n) + '만 원'; }
  function wire(data) {
    var A = data.jobs[0], B = data.jobs[1], win = A.remaining >= B.remaining ? A : B, lose = win === A ? B : A;
    var c = data.comparison, n = data.horizonYears, gap = win.remaining - lose.remaining;
    var many = c && n > 1 && c.betterJob === win.label;   // 누적에서도 같은 쪽이 더 남을 때만 누적 줄을 쓴다
    function place(j) { var r = String(j.region || '').split(' '); return j.label + (r.length > 1 ? ' ' + r[r.length - 1] : ''); }
    function row(cls, k, v, sub) {
      return '<div class="rx-row' + (cls ? ' ' + cls : '') + '"><dt>' + esc(k) + (sub ? '<small>' + esc(sub) + '</small>' : '') + '</dt><dd>' + esc(won(v)) + '</dd></div>';
    }
    var rows = row('', place(A), A.remaining, '연봉 ' + won(A.salary)) + row('', place(B), B.remaining, '연봉 ' + won(B.salary))
      + (many ? row('rx-gap', '1년차 차이', gap) + row('rx-total', n + '년 누적 차이', c.difference) : row('rx-total', '1년차 차이', gap));
    // 우위 문장은 사실일 때만: 차이가 있을 때, 연봉이 낮은 쪽이 이기면 그 사실을 붙인다
    var msg = gap > 0 ? (win.salary < lose.salary ? '연봉은 ' + won(lose.salary - win.salary) + ' 낮아도 ' : '') + win.label + ' 공고가 ' + (many ? '더 남아요.' : '1년차에 더 남아요.') : '';
    document.getElementById('heroFact').innerHTML =
      '<div class="rx-head"><span class="rx-tag">샘플 데이터로 계산한 예시</span>' + (data.rentPeriod ? '<span class="rx-meta">월세 ' + esc(data.rentPeriod) + '</span>' : '') + '</div>'
      + '<div class="rx-cols" aria-hidden="true"><span>샘플 공고</span><span>1년 남는 돈</span></div>'
      + '<dl class="rx-rows">' + rows + '</dl>'
      + (msg ? '<p class="rx-msg">' + esc(msg) + '</p>' : '');
    // 가정은 hero.json에 있는 것만 쓴다: 감면은 comparison.scenarioId, 식대·월세 기준은 assumption 문장(build_hero.py)에서 읽는다
    var as = data.assumption || '', meal = /비과세 식대 월 ([\d,]+만 원)/.exec(as);
    document.getElementById('heroNote').textContent = [
      c && c.scenarioId === 'none' ? '감면 미적용' : '',
      meal ? '비과세 식대 월 ' + meal[1] + ' 반영' : '',
      /원룸 월세 중위값/.test(as) ? '근무지 원룸 월세 중위값' : '',
      many ? n + '년간 연봉·월세 동일 가정' : ''
    ].filter(Boolean).join(' · ');
    document.getElementById('heroReceipt').hidden = false;
  }

  // CTA. 둘 다 아래 입력 영역의 기존 흐름(app.js)을 그대로 쓴다
  var form = document.querySelector('#step1 .card'), start = document.getElementById('btnStart');
  var own = document.getElementById('heroOwn'), tryBtn = document.getElementById('heroTry');
  function go(el, block) { if (el) el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: block || 'start' }); }
  // 공고 비교하기: 입력 영역으로 내려가 공고 A에 키보드 포커스. 이미 붙여 넣어 정리된 보기면 고치기 상태로 바꾼다(app.js의 보기 클릭과 같은 동작)
  if (own && form) own.addEventListener('click', function () {
    var ta = document.getElementById('textA'), view = document.getElementById('viewA');
    if (ta && ta.hidden && view) { view.hidden = true; ta.hidden = false; }
    if (ta) { try { ta.focus({ preventScroll: true }); } catch (e) { ta.focus(); } }
    go(form);
  });
  // 샘플 결과 보기: 첫 샘플을 채우고 기존 비교 시작을 누른다. 확인이 필요 없으면 app.js가 결과까지 바로 간다.
  // 비교 시작이 진행 중(disabled)이면 이 버튼도 잠근다. 샘플이 아직 없으면 샘플 줄로 안내한다. 실패 메시지는 app.js가 msg1에 띄운다
  if (tryBtn && start && form) {
    var sync = function () { tryBtn.disabled = start.disabled; tryBtn.setAttribute('aria-busy', start.disabled ? 'true' : 'false'); };
    if (window.MutationObserver) new MutationObserver(sync).observe(start, { attributes: true, attributeFilter: ['disabled'] });
    tryBtn.addEventListener('click', function () {
      if (start.disabled) return;
      var sample = document.querySelector('#sampleButtons button'), samples = document.getElementById('samples');
      if (!sample) { if (samples) samples.classList.add('flash'); go(samples, 'center'); return; }
      sample.click();
      start.click();
      var busy1 = document.getElementById('busy1'), msg1 = document.getElementById('msg1');
      go(busy1 && !busy1.hidden ? busy1 : (msg1 && !msg1.hidden ? msg1 : form), 'center');
    });
  }

  startVideo();
  fetch('hero.json', { cache: 'no-cache' }).then(function (r) {
    if (!r.ok) throw new Error('hero.json ' + r.status);
    return r.json();
  }).then(function (d) {
    if (!d || !d.jobs || d.jobs.length !== 2) throw new Error('bad');
    wire(d);
  }).catch(function () { /* 문장 없이 둔다 */ });
})();
