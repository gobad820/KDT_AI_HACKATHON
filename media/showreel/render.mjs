// 쇼릴 렌더링: reel.html 을 프레임 단위로 그려 캡처한 뒤 ffmpeg 로 묶는다.
// 실행: PW_CORE=<playwright-core 경로> node media/showreel/render.mjs [fps] [frames-dir]
// 미리보기: media/showreel 폴더를 정적 서버로 띄워 reel.html 을 연다 (data.json 은 build_data.py 로 만든다)
import { createRequire } from 'module';
import { spawnSync } from 'child_process';
import { mkdirSync, rmSync } from 'fs';
import http from 'http';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const pwPath = process.env.PW_CORE;
const { chromium } = require(pwPath);
const here = path.dirname(fileURLToPath(import.meta.url));
const FPS = Number(process.argv[2] || 60), DUR = 15;
const outDir = process.argv[3] || path.join(here, 'frames');
rmSync(outDir, { recursive: true, force: true }); mkdirSync(outDir, { recursive: true });
// data.json 을 fetch 하려고 작은 정적 서버를 띄운다
const srv = http.createServer((q, s) => {
  const f = path.join(here, decodeURIComponent(q.url.split('?')[0]).replace(/^\/+/, '') || 'reel.html');
  try { const b = readFileSync(f); s.writeHead(200, { 'content-type': f.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/json' }); s.end(b); }
  catch { s.writeHead(404); s.end(); }
}).listen(0);
const port = srv.address().port;
const browser = await chromium.launch({ channel: 'chrome', args: ['--force-device-scale-factor=1'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', e => console.error('pageerror', e.message));
await page.goto(`http://127.0.0.1:${port}/reel.html?render=1`);
await page.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
if (process.env.STILLS) {
  for (const t of process.env.STILLS.split(',').map(Number)) {
    await page.evaluate(t => window.renderAt(t), t);
    await page.screenshot({ path: path.join(outDir, `still_${t.toFixed(2)}.png`) });
  }
  await browser.close(); srv.close(); process.exit(0);
}
const n = Math.round(FPS * DUR);
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  await page.evaluate(t => window.renderAt(t), i / FPS);
  await page.screenshot({ path: path.join(outDir, `f_${String(i).padStart(4, '0')}.png`), clip: { x: 0, y: 0, width: 1920, height: 1080 } });
  if (i % 60 === 0) console.log(`frame ${i}/${n} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
await browser.close(); srv.close();
const mp4 = path.join(here, 'showreel.mp4');
const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(outDir, 'f_%04d.png'),
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4], { stdio: 'inherit' });
console.log('ffmpeg exit', r.status, mp4);
