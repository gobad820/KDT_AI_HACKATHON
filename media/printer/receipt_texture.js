/* 첫 화면 영수증 텍스처 생성기 (Blender 렌더용).
   hero.json(계산 모듈 출력, scripts/build_hero.py)의 숫자로 감열 인쇄를 시뮬레이션해 PNG를 만든다.
   감열 프린터는 글꼴을 그리지 않고 한 줄 576개의 점(80mm, 203dpi)을 열로 태운다.
   - 한 줄 42칸: 영숫자 12점(반각), 한글 24점(전각). 공백으로 정렬한다
   - 강조는 프린터 기능(2배 확대, 굵게)과 형광펜만 쓴다
   사용: 앱 페이지(Pretendard와 hero.json이 있는 곳)에 이 파일을 넣고
         makeReceiptTexture(data, { stamp: '2026-11-21 14:00', seq: 1, scale: 2 }) → { url, rows, H, W }
   rows는 줄마다 [y, h](점 단위)이다. render_hero.py가 줄 단위 급지 타이밍에 쓴다. */
window.makeReceiptTexture = function (data, opt) {
  'use strict';
  opt = opt || {};
  var DOTS = 576, COLS = 42, CELL = 12, ROW = 30, MARGIN = (DOTS - COLS * CELL) / 2, SCALE = opt.scale || 2, seq = opt.seq || 1;
  var FONT = '"Pretendard Variable", Pretendard, "Apple SD Gothic Neo", sans-serif';
  var PAPER = opt.paper || '#f6f6f3', INK = [22, 22, 27], HL = [244, 234, 69];

  function won(n) { return Math.round(n).toLocaleString('ko-KR'); }
  function rng(seed) { return function () { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; }
  function wide(c) { return (c >= 0x1100 && c <= 0x115f) || (c >= 0x2e80 && c <= 0xa4cf) || (c >= 0xac00 && c <= 0xd7a3) || (c >= 0xff00 && c <= 0xff60); }
  function cols(s) { var n = 0; for (var i = 0; i < s.length; i++) n += wide(s.charCodeAt(i)) ? 2 : 1; return n; }
  function sp(n) { return n > 0 ? new Array(n + 1).join(' ') : ''; }
  function lr(l, r, w) { w = w || COLS; return l + sp(Math.max(1, w - cols(l) - cols(r))) + r; }
  function center(s, w) { w = w || COLS; return sp(Math.floor(Math.max(0, w - cols(s)) / 2)) + s; }
  function rpad(s, w) { return sp(w - cols(s)) + s; }
  function row3(a, b, c) { return a + sp(18 - cols(a)) + rpad(b, 12) + rpad(c, 12); }
  function rule(ch) { return new Array(COLS + 1).join(ch); }

  var A = data.jobs[0], B = data.jobs[1];
  var win = A.remaining >= B.remaining ? A : B, gap = Math.abs(A.remaining - B.remaining), wk = win === A ? 'A' : 'B';
  var L = [
    { t: center('남는 돈 계산서', COLS / 2), size: 2 },
    { t: center('nammeun-don.vercel.app') },
    { t: lr(opt.stamp || '', 'No.' + ('000' + (seq % 10000)).slice(-4)) },
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
    { barcode: true },
    { t: center('연봉 말고 남는 돈으로 고르세요') }
  ];

  // 1) 576점 캔버스에 글자를 칸 단위로 그린다
  var y = 34, rows = [];
  L.forEach(function (ln) { var h = ln.barcode ? 86 : ln.size === 2 ? ROW * 2 : ROW; rows.push({ y: y, h: h, ln: ln }); y += h; });
  var H = y + 40;
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
        var m = g.measureText(ch).width, x0 = MARGIN + col * CELL + (cw - m) / 2, by = rw.y + 21 * s;
        if (ch === '-' || ch === '=') {
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

  // 2) 점 단위 판정: 열 헤드가 점을 태운다. 헤드 온도 얼룩, 빠진 세로 줄, 드문드문 빠지는 점
  var img = g.getImageData(0, 0, DOTS, H), px = img.data, rr = rng(91 + seq * 7), band = [], streak = [];
  for (var yy = 0; yy < H; yy++) band.push(.86 + .14 * Math.sin(yy / 9.5 + rr() * .8) * .5 + rr() * .08);
  for (var xx = 0; xx < DOTS; xx++) streak.push(1);
  [137, 138, 311, 449].forEach(function (sx) { streak[sx] = .25; });
  var dens = new Float32Array(DOTS * H);
  for (var i2 = 0; i2 < DOTS * H; i2++) {
    var a = px[i2 * 4 + 3] / 255, x2 = i2 % DOTS, y2 = (i2 / DOTS) | 0;
    var on = a > .44 + (rr() - .5) * .22;
    if (on && rr() < .015) on = false;
    dens[i2] = on ? Math.min(1, band[y2] * streak[x2] * (.84 + rr() * .2)) * .97 : 0;
  }
  // 렌더에서 종이가 작게 보이므로 세로 획을 1점 굵힌다(헤드 열이 옆 점까지 번지는 모양)
  for (var yb = 0; yb < H; yb++) for (var xb = DOTS - 1; xb > 0; xb--) { var k1 = yb * DOTS + xb; dens[k1] = Math.max(dens[k1], dens[k1 - 1] * .92); }

  // 3) 종이 + 잉크 + 형광펜(잉크 위에 곱하기)을 SCALE배 캔버스에 합친다
  var W2 = DOTS * SCALE, H2 = H * SCALE, out = document.createElement('canvas'); out.width = W2; out.height = H2;
  var og = out.getContext('2d'), oimg = og.createImageData(W2, H2), o = oimg.data;
  var pc = [parseInt(PAPER.slice(1, 3), 16), parseInt(PAPER.slice(3, 5), 16), parseInt(PAPER.slice(5, 7), 16)];
  var hl = [];
  rows.forEach(function (rw) {
    if (rw.ln.key === 'remain') hl.push({ y0: rw.y - 3, y1: rw.y + rw.h - 1, x0: MARGIN + (rw.ln.hiCol === 'A' ? 18 : 30) * CELL - 2, x1: MARGIN + (rw.ln.hiCol === 'A' ? 30 : 42) * CELL + 2, tilt: -.012 });
    if (rw.ln.key === 'gap') hl.push({ y0: rw.y - 3, y1: rw.y + rw.h - 1, x0: MARGIN + 26 * CELL, x1: MARGIN + 42 * CELL + 2, tilt: .008 });
  });
  var hr = rng(3);
  hl.forEach(function (h) { h.row = []; for (var k = 0; k < (h.y1 - h.y0) * SCALE + 8; k++) h.row.push(.8 + hr() * .2); });   // 펜 결
  for (var Y = 0; Y < H2; Y++) {
    for (var X = 0; X < W2; X++) {
      var d = dens[((Y / SCALE) | 0) * DOTS + ((X / SCALE) | 0)], j = (Y * W2 + X) * 4;
      var R = pc[0] + (INK[0] - pc[0]) * d, G = pc[1] + (INK[1] - pc[1]) * d, Bc = pc[2] + (INK[2] - pc[2]) * d;
      for (var q = 0; q < hl.length; q++) {
        var h = hl[q], xd = X / SCALE, yd = Y / SCALE - (xd - h.x0) * h.tilt;
        if (xd < h.x0 || xd > h.x1 || yd < h.y0 || yd > h.y1) continue;
        var e = Math.min(1, (xd - h.x0) / 6, (h.x1 - xd) / 4, (yd - h.y0) / 2.5, (h.y1 - yd) / 2.5);   // 펜 끝이 옅어지는 가장자리
        var k2 = Math.max(0, e) * .88 * h.row[Math.min(h.row.length - 1, Math.max(0, ((yd - h.y0) * SCALE) | 0))];
        R *= 1 - k2 + k2 * HL[0] / 255; G *= 1 - k2 + k2 * HL[1] / 255; Bc *= 1 - k2 + k2 * HL[2] / 255;
      }
      o[j] = R; o[j + 1] = G; o[j + 2] = Bc; o[j + 3] = 255;
    }
  }
  og.putImageData(oimg, 0, 0);
  return { url: out.toDataURL('image/png'), rows: rows.map(function (rw) { return [rw.y, rw.h]; }), H: H, W: DOTS, scale: SCALE };
};
