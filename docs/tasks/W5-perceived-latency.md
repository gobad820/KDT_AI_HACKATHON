# W5 체감 속도 개선 세 가지

- 담당: Claude Code(승인 김상해) / 브랜치: `feat/sanghae-perceived-latency` (개선 3은 `feat/sanghae-classify-at-extract`로 따로) / 상태: 제안(대표자 승인 전) / 마감: 11/22(일) 19:00 PR, 22:00 동결 전 배포 확인 / 먼저 끝나야 하는 것: W1(이름 변경, 기본 10년)과 W8(연봉 인상) main 병합. W8이 `app/schemas.py`, `app/pipeline.py`, `app/web/app.js`, `index.html`, `docs/api-spec.md`, `docs/dev-notes.md`를 먼저 고친다

## 왜

- 「첫 직장, 10년 뒤 경제력」의 결과 화면은 11/21 밤 배포에서 6.7~7.7초에 떴다. AI 설명은 10.7~13.4초에 바뀌어 들어왔다(브라우저 실측, `docs/status-2026-11-21.md`).
- 시간 구성: 추출 1.5~4.7초, 계산 1.5~3.9초(업종 분류 LLM, 캐시 전), 화면 그리기 약 1.2초, 설명문 3.1~6.6초.
- 화면은 `/api/extract` → `/api/compare`(`options.explanation: "template"`) → `/api/explain` 순서로 부른다.
- 아래 세 가지는 코드를 읽고 찾은 대기 원인이다. 금액, 프롬프트, 모델은 바꾸지 않는다.

### 개선 1: AI 설명 요청을 화면을 그리기 전에 보낸다

- 지금: `app/web/app.js`의 `runCompare`는 compare 응답을 받은 뒤 `renderResult()` → `setStep(3)` → `loadAiExplanation(req)` 순서로 부른다. 그리기가 끝나야 explain 요청이 나간다.
- explain 요청 본문은 compare 요청을 복사해 `options.explanation`만 `"ai"`로 바꾼 것이다. compare 응답이 없어도 만들 수 있다.
- 바꿀 것: `loadAiExplanation(req)` 호출을 `renderResult()` 앞으로 옮긴다. 응답 처리 함수는 그리기가 끝난 뒤에만 돈다(자바스크립트는 한 줄기로 돈다).
- `explainSeq`(늦게 온 이전 요청의 응답을 버리는 번호)와 `!state.result` 검사는 그대로 둔다.
- 기대 효과: AI 설명이 그리기 시간만큼 빨리 들어온다. 11/21 실측으로 최대 약 1.2초다. 결과 화면이 뜨는 시각은 그대로다.
- compare와 explain을 동시에 보내는 안은 하지 않는다.
  - explain도 `run_compare`를 돌며 업종을 분류한다. 새 인스턴스에서는 분류 LLM이 두 번 돈다(분당 한도 위험).
  - 누적 기간을 바꿀 때 새 설명이 옛 결과 화면에 먼저 끼워질 수 있다. 그러면 `state.explainPending`이 꼬여 대기 표시가 남는다.

### 개선 2: 돈 흐름 그림의 예열을 없앤다

- 판단: 첫 표시를 막는다.
  - `renderResult()`는 `setStep(3)` 전에 `window.MoneyFlow.mount`를 동기로 부른다.
  - `app/web/flow.js`의 `Stream()`은 만들 때 입자를 300단계 미리 움직인다(`for (var w = 0; w < 300; w++) self.step(1 / 30)`).
  - `mountYear`가 입자 6,500개짜리 줄기 둘을, `mountCumulative`가 10,000개짜리 하나를 만든다. 300단계 × 23,000개, 약 690만 번 갱신이다.
- 측정(11/22): node에서 가짜 DOM으로 `MoneyFlow.mount`만 5번 돌렸다(Apple M2 Pro). 444~487ms가 걸렸다. 예열 줄만 빼면 3~18ms다.
- 이 예열은 대부분 버려진다. `Scene`의 IntersectionObserver가 캔버스를 처음 볼 때 `st.reset(true)`로 입자를 왼쪽 빈 상태로 되돌린다(움직임 줄이기 설정이 아닐 때). 예열 결과는 첫 프레임 한 장에만 보인다.
- 애니메이션 루프는 이미 화면 밖에서 멈춘다(`Scene`의 `visible`). 첫 표시를 막는 것은 만들 때의 예열이다.
- 바꿀 것: 예열은 움직임 줄이기(`reduce`)이거나 IntersectionObserver가 없을 때만 돌린다. 이 두 경우에는 정지 화면이 필요하다. 그 밖에는 처음부터 빈 상태(`self.reset(true)`)로 시작한다.
- 카드 전체를 IntersectionObserver로 늦게 만드는 안은 기본으로 하지 않는다.
  - 흐름 카드는 결론 바로 아래라 첫 화면에 걸리는 경우가 많다(확인 필요: 화면 크기별).
  - 예열을 빼면 만드는 비용이 3~18ms라 늦춰서 얻는 것이 작다.
  - 바꾼 뒤에도 `mount`가 50ms를 넘으면 그때 한다.
- 기대 효과: 결과 화면이 약 0.45초 빨리 뜬다(M2 Pro 기준. 느린 노트북에서는 더 클 수 있다, 확인 필요). 누적 기간을 바꿀 때(`onHorizon` → `renderResult`)도 같은 만큼 줄어든다. 지금은 약 1.6초다.
- 11/21에 잰 그리기 1.2초 가운데 `mount`가 아닌 나머지 약 0.75초가 어디서 드는지는 모른다(확인 필요: DevTools Performance).
- 개선 1과 함께 해도 AI 설명 단축은 더해지지 않는다. 개선 1 뒤에는 그리기와 explain 응답 대기가 겹치기 때문이다. AI 설명은 최대 약 1.2초, 결과 화면은 약 0.45초 줄어든다.

### 개선 3: 업종 분류를 추출 단계에서 미리 한다

- 지금: compare와 explain이 모두 `app/pipeline.py`의 `run_compare`를 돈다. 그 안에서 두 공고의 업종을 동시에 분류한다(`ThreadPoolExecutor`, `deps.classify_industry`).
- `app/agent/classify.py`의 `_CACHE`는 (모델, 사업 내용)을 키로 한 메모리 캐시다. Vercel 함수 인스턴스 안에서만 유효하다. 새 인스턴스는 다시 분류한다.
- 근거 숫자(11/21)
  - compare는 캐시 전 1.5~3.9초, 같은 인스턴스에서 캐시가 걸린 뒤 0.25~1.0초였다. 분류 LLM 2건이 약 1.2~2.9초로 추정된다(콜드 스타트가 섞였을 수 있다, 확인 필요).
  - 브라우저에서 explain은 3.1~6.6초, curl로 같은 인스턴스에서 잰 explain은 1.3~2.2초였다. 차이의 일부가 분류 재실행일 수 있다(확인 필요).

방식 A: 추출 응답에 분류 결과를 싣고, 화면이 compare·explain 요청에 다시 실어 보낸다 (권장)

- extract 응답에 `postings[].industryClass = {text, name, reason}`을 넣는다. 분류하지 않았으면 null이다.
- compare 요청에 `postings[].confirmed.industryClass`(선택)를 받는다.
- 서버는 두 조건이 맞을 때만 실린 값을 쓴다. `text`가 `confirmed.industryText`와 같아야 하고, `name`이 허용 목록(`TARGET_INDUSTRIES`, `excluded`, `unknown`)에 있어야 한다. 아니면 지금처럼 분류한다.
- 장점
  - 인스턴스와 상관없이 compare, explain, 누적 기간 변경에서 분류 LLM을 부르지 않는다.
  - `docs/api-spec.md` 1장 원칙(서버는 상태를 저장하지 않고 화면이 확인된 값을 실어 보낸다)과 맞는다.
  - 확인 화면에서 사업 내용을 고치면 글자가 달라지므로 서버가 다시 분류한다.
- 단점
  - API 경계가 바뀐다. 문서 2개, `schemas.py`, `main.py`, `pipeline.py`, `app.js`, 테스트를 고친다.
  - 화면이 보낸 분류 값을 서버가 받아 쓴다. 값 목록과 글자 일치로 검사한다. 값을 꾸며 보내도 보낸 사람의 결과만 바뀐다.

방식 B: 추출 단계에서 분류해 `_CACHE`만 채운다

- `main.py`의 `extract()`에서 `classify_industry`를 불러 결과는 버린다. 같은 인스턴스로 간 compare·explain이 캐시를 맞힌다.
- 장점: `main.py`만 고친다. API, 화면, 문서가 그대로다.
- 단점
  - compare·explain이 다른 인스턴스로 가면 효과가 없다. 그때는 추출이 늦어진 만큼 손해다.
  - 같은 인스턴스로 가는 비율을 모른다(확인 필요).

두 방식 공통

- 분류 시간이 compare에서 extract로 옮겨 간다. 확인 화면을 건너뛰는 경로(샘플 2쌍)에서는 결과 화면까지의 시간이 거의 그대로다.
- 이득은 세 곳이다.
  - explain이 분류를 다시 하지 않는다. 새 인스턴스로 갔을 때 AI 설명이 약 1.2~2.9초 빨라질 수 있다(확인 필요).
  - 누적 기간 변경과 확인 화면 경로의 compare가 분류 없이 돈다.
  - 결과 한 번에 부르는 LLM 수가 줄어 분당 한도에 여유가 생긴다.
- 추출을 LLM 대신 저장본으로 응답했을 때(`degraded=true`)는 분류하지 않는다. LLM 실패를 두 번 기다리지 않기 위해서다.
- 셋 가운데 결과 화면 단축 효과가 가장 작다. 19:00까지 시간이 모자라면 개선 3을 통째로 뺀다.

## 할 일

1. W1이 main에 합쳐졌는지 확인한다. 안 됐으면 멈추고 김상해에게 묻는다.
2. `git pull origin main` 후 `feat/sanghae-perceived-latency` 브랜치를 만든다.
3. 고치기 전 숫자를 로컬에서 잰다("확인 방법" 2). W1을 합친 main에서 재야 기본 10년 기준으로 전·후가 맞는다.
4. [개선 1] `runCompare`의 `if (state.explainPending) loadAiExplanation(req);`를 `renderResult();` 바로 앞으로 옮긴다. `state.explainPending`을 정하는 줄은 그보다 앞에 둔다.
5. [개선 2] `flow.js`의 `Stream`에서 300단계 예열을 `reduce || !('IntersectionObserver' in window)`일 때만 돌린다.
6. [개선 2] 같은 조건이 아니면 `self.reset(false)` 대신 `self.reset(true)`로 시작한다. 첫 프레임에 폭포 없는 줄기가 한 장 보였다 사라지는 깜박임을 막는다.
7. `app/web/index.html` 맨 아래 `flow.js?v=`와 `app.js?v=` 값을 새로 올린다. 브라우저와 CDN이 옛 파일을 쓰지 않게 한다.
8. 고친 뒤 같은 숫자를 다시 잰다. 전·후를 PR 본문에 적는다.
9. `docs/ai-usage-log.md`에 한 줄 남긴다(Claude Code가 한 일, 김상해가 확인한 일).
10. `python3 -m pytest` 전부 통과를 확인하고 PR 1을 올린다.
11. [개선 3] 김상해가 방식 A, 방식 B, 빼기 가운데 하나를 고른다. 12번부터는 방식 A 기준이다.
12. main을 다시 받고 `feat/sanghae-classify-at-extract` 브랜치를 만든다.
13. 코드보다 먼저 `docs/api-spec.md`를 고친다(CLAUDE.md: 경계를 바꿀 때는 이 문서부터). 3장 표에 `IndustryClass`, 4장 응답 예시에 `industryClass`, 5장에 `confirmed.industryClass`와 서버 검사 규칙, 6장 `/api/explain` 설명에 "실린 분류를 쓰면 다시 분류하지 않는다"를 적는다.
14. 코드보다 먼저 `docs/dev-notes.md` 2장 `classify_industry` 아래에 "추출 단계에서 한 번 부르고, compare·explain은 요청에 실린 결과를 먼저 쓴다"를 적는다.
15. `app/schemas.py`에 `IndustryClass(text: str, name: str, reason: str = "")`를 만든다. `ExtractedPosting.industry_class`와 `Confirmed.industry_class`를 `Optional[IndustryClass] = None`으로 더한다.
16. `app/main.py`의 `extract()`에서 `llm = get_llm()`을 `try` 안에서 한 번만 부르고, 추출과 분류에 같이 넘긴다.
17. 같은 `extract()`에서 추출이 성공하고 `degraded`가 아니면 두 공고의 `industry_text`를 `classify.classify_industry(text, llm)`로 동시에 분류해 `industry_class`에 넣는다. 사업 내용이 비면 null로 둔다.
18. 같은 `extract()`의 trace에 `("tool_call", "classify_industry", "A: 정보통신업 / B: 제조업")` 꼴의 단계를 더한다.
19. `app/pipeline.py`의 `run_compare` 안 `_classify`가 `confirmed.industry_class`를 먼저 보게 한다. 검사를 통과하면 `(name, reason[:120])`을 쓰고, 아니면 `deps.classify_industry`를 부른다. 두 공고를 동시에 처리하는 구조는 유지한다.
20. `app/web/app.js`의 `buildModel`에서 `p.industryClass || null`을 `state.model[pid].industryClass`에 담는다.
21. `app/web/app.js`의 `collectRequest`에서 `confirmed.industryClass`로 보낸다. 사업 내용을 고쳤는지는 화면이 따지지 않는다. 서버의 글자 비교가 맡는다.
22. 테스트를 더한다("확인 방법" 4).
23. `index.html`의 `app.js?v=`를 다시 올린다.
24. `docs/ai-usage-log.md`에 한 줄 남긴다.
25. `python3 -m pytest` 전부 통과를 확인하고 PR 2를 올린다.
26. 김상해가 PR을 합치고 배포한다. 배포 URL에서 샘플 2쌍을 입력부터 결과까지 다시 통과시키고 숫자를 잰다("확인 방법" 5).

## 건드리는 파일

PR 1 (개선 1·2)

- `app/web/app.js`: `runCompare`(호출 순서 한 줄). `loadAiExplanation`은 고치지 않는다.
- `app/web/flow.js`: `Stream`(예열 조건과 시작 상태).
- `app/web/index.html`: `<script src="flow.js?v=…">`, `<script src="app.js?v=…">`의 `v` 값.
- `docs/ai-usage-log.md`: 한 줄 추가.

PR 2 (개선 3, 방식 A)

- `docs/api-spec.md`: 3장 공통 타입 표, 4장 응답 예시, 5장 요청 설명, 6장 `/api/explain`.
- `docs/dev-notes.md`: 2장 `classify_industry`.
- `app/schemas.py`: 새 `IndustryClass`, `ExtractedPosting`, `Confirmed`.
- `app/main.py`: `extract()`.
- `app/pipeline.py`: `run_compare` 안 `_classify`.
- `app/web/app.js`: `buildModel`, `collectRequest`.
- `app/web/index.html`: `app.js?v=`.
- `tests/test_pipeline.py`, `tests/test_api.py`: 새 테스트.
- `docs/ai-usage-log.md`: 한 줄 추가.
- 방식 B를 고르면 `app/main.py`의 `extract()`와 테스트만 고친다.

W1과 겹치는 곳 (11/22 W1 작업 폴더를 읽은 기준, 확인 필요)

- `app/web/app.js`: W1은 맨 위 주석과 `freshState()`의 `horizon: 5 → 10`을 고친다. W5는 `runCompare`, `buildModel`, `collectRequest`를 고친다.
- `app/web/index.html`: W1도 `<title>`, 머리글, `style.css`·`app.js`·`hero.js`의 `?v=`를 바꾼다. `app.js?v=` 줄이 겹친다.
- `app/schemas.py`: W1은 `CompareOptions.horizon_years` 기본값을 고친다. W5는 새 모델과 필드를 더한다.
- `app/main.py`: W1은 `FastAPI(title=…)`을 고친다. W5는 `extract()`를 고친다.
- `docs/api-spec.md`, `docs/ai-usage-log.md`: 둘 다 고친다.
- `tests/test_pipeline.py`: W1이 `test_default_horizon_is_10_years`를 더한다. W5도 파일 끝에 테스트를 더한다.
- 순서: W1을 main에 합친다. 그다음 W5가 `git pull origin main`을 하고 시작한다. 겹치는 줄의 충돌을 미리 없앤다. rebase로 맞추지 않는다.

## 건드리지 않는 파일

- `app/web/mock.js`: api-spec의 JSON 블록에서 만든 파일이고 "손으로 고치지 않는다"고 적혀 있다. `industryClass`가 없어도 화면이 돌아야 한다(`?mock=1`로 확인).
- `app/web/style.css`, `app/web/hero.js`, `app/web/hero.json`: W1이 고친다. W5는 화면 모양을 바꾸지 않는다.
- `app/agent/classify.py`, `extract.py`, `explain.py`, `llm.py`, `app/agent/prompts/`: 이동한 담당이고 T12와 겹친다. 공개 함수 `classify_industry`만 부른다. `_CACHE`도 그대로 둔다.
- `app/relief/`: 정상훈 담당. `TARGET_INDUSTRIES`, `EXCLUDED`, `UNKNOWN`을 읽기만 한다.
- `app/calc/`, `scripts/calc_ref.py`, `docs/calc-rules.md`: 정상훈 T14. 금액 계산은 바꾸지 않는다.
- `tests/cases/`: 이동한 T12.
- `scripts/`: W6가 `scripts/measure_consistency.py`를 만든다.
- `CLAUDE.md`, `HANDOFF.md`, `README.md`, `docs/team-1122.md`, `docs/status-2026-11-21.md`, `docs/decisions.md`, `docs/tasks/`의 다른 문서: W1과 다른 작업이 고친다.
- Vercel 설정과 환경변수: 김상해만 바꾼다.

## 끝났다고 보는 기준

- 개선 1: compare 응답이 끝나고 explain 요청이 시작되기까지 50ms 이하다.
- 개선 2: `MoneyFlow.mount` 한 번이 50ms 이하다.
- 개선 2: 움직임 줄이기 설정에서 그림이 지금처럼 폭포까지 그려진 정지 화면으로 보인다. 보통 설정에서 첫 프레임 깜박임이 없다.
- 개선 3(했다면): 맞는 `industryClass`가 실린 compare와 explain은 분류를 부르지 않는다. 사업 내용을 고친 요청은 다시 분류한다.
- 개선 3(했다면): api-spec·dev-notes를 고친 커밋이 코드 커밋보다 앞에 있다.
- `python3 -m pytest`가 전부 통과한다.
- 배포 URL에서 샘플 2쌍이 입력부터 결과까지 통과한다. AI 설명이 바뀌어 들어오고 "AI가 생성한 답변" 표시가 붙는다.
- 전·후 숫자가 PR 본문에 있다. 22:00 동결 전에 합쳐진다.

## 확인 방법

1. 로컬 실행

```bash
source .venv/bin/activate
python3 -m pytest
uvicorn app.main:app --port 8765
```

- 그리기만 볼 때는 `http://localhost:8765/?mock=1`을 연다.
- 실제 흐름은 자기 Gemini 키가 든 `.env`로 `http://localhost:8765/`에서 샘플 공고를 고르고 "비교 시작"을 누른다.

2. 시간 재기. 페이지를 연 뒤 DevTools 콘솔에 붙여 넣고 "비교 시작"을 누른다.

```js
performance.clearResourceTimings();
var t0 = 0, s3 = document.getElementById('step3');
document.getElementById('btnStart').addEventListener('click',
  function () { t0 = performance.now(); }, true);
new MutationObserver(function () {
  if (!s3.hidden) console.log('결과 화면 ms', Math.round(performance.now() - t0));
}).observe(s3, { attributes: true });
var m0 = MoneyFlow.mount;
MoneyFlow.mount = function () {
  var t = performance.now(), r = m0.apply(this, arguments);
  console.log('mount ms', Math.round(performance.now() - t));
  return r;
};
```

AI 설명이 바뀌어 들어온 뒤 이어서 붙여 넣는다.

```js
var r = performance.getEntriesByType('resource');
function g(p) { return r.filter(function (e) { return e.name.indexOf(p) >= 0; }).pop(); }
var e = g('/api/extract'), c = g('/api/compare'), x = g('/api/explain');
console.log('compare 끝 → explain 시작 ms', Math.round(x.startTime - c.responseEnd));
console.log('추출 시작 → AI 설명 응답 ms', Math.round(x.responseEnd - e.startTime));
```

3. 움직임 줄이기 확인. DevTools → Rendering → "Emulate CSS media feature prefers-reduced-motion"을 `reduce`로 두고 새로고침한다. `flow.js`가 이 값을 불러올 때 한 번 읽기 때문이다. 흐름 그림이 폭포까지 그려진 정지 화면이어야 한다.

4. 개선 3 테스트(pytest, 실제 LLM 없음)

- `tests/test_pipeline.py`: 맞는 `industryClass`가 실린 요청이면 `deps.classify_industry` 호출이 0회다. 판정은 실린 값을 따른다.
- `tests/test_pipeline.py`: `text`가 `industryText`와 다르거나 `name`이 목록에 없으면 분류를 부른다.
- `tests/test_pipeline.py`: 기존 `test_industry_classification_runs_for_both_postings_in_parallel`이 계속 통과한다.
- `tests/test_api.py`: `monkeypatch`로 `main.get_llm`을 `FakeLLM(fn=…)`으로 바꾼다. fn은 스키마로 호출을 나눈다(`salary`가 있으면 추출, `industryName`이 있으면 분류). 근거 문장은 요청 원문의 줄을 그대로 넣는다(근거 대조를 통과해야 값이 남는다).
- `tests/test_api.py`: extract 응답에 `industryClass`가 2개 있다. 그 값을 실은 compare와 explain에서 분류 호출이 0회다.
- `tests/test_api.py`: LLM 없이 저장본으로 응답한 extract(`degraded=true`)는 `industryClass`가 null이다.
- 스키마로 호출을 나눠 세는 방식은 11/21 임시 측정(`sim.py`, 저장소에 없음)에서 쓴 방법이다.

5. 배포 URL(김상해가 배포한 뒤)

- 시크릿 창으로 https://nammeun-don.vercel.app 를 연다.
- 샘플 2쌍을 3번씩 돌리고 2번 스니펫으로 잰다. 첫 회는 콜드 스타트라 따로 적는다.
- "1년 / 3년 / 5년 / 10년" 누적 기간을 바꿔 다시 그리는 시간도 본다.

기대 숫자

- `mount`: 444~487ms → 3~18ms(node, M2 Pro). 브라우저 값은 이번에 처음 잰다(확인 필요).
- compare 끝 → explain 시작: 지금은 그리기 시간만큼(수백 ms~약 1.2초) → 50ms 이하.
- 배포 결과 화면: 6.7~7.7초에서 약 0.45초 줄어든다(확인 필요).
- 배포 AI 설명: 10.7~13.4초에서 약 1.2초 줄어든다(확인 필요).
- 누적 기간 변경: 약 1.6초 → 약 1.15초(확인 필요).
- 개선 3 뒤: compare는 인스턴스와 상관없이 0.25~1.0초 수준이다. extract는 분류만큼 늘어난다(확인 필요).
- 11/21 숫자는 기본 5년일 때 쟀다. W1 뒤에는 기본 10년이라 전·후를 같은 main에서 잰다.

## 위험과 되돌리는 법

- 개선 1: 메인 스레드가 그리기로 바쁜 동안에도 브라우저가 요청을 바로 내보내는지는 확인 필요다. Network 탭에서 explain 시작이 그리기 뒤로 밀리면, 요청을 보낸 뒤 `renderResult()`와 `setStep(3)`을 `setTimeout(…, 0)`으로 한 번 미룬다.
- 개선 1: `renderResult()`가 예외로 멈추면 explain 요청만 헛돈다. 호출 수는 지금과 같다.
- 개선 2: 예열을 빼면 선이 왼쪽에서 채워지며 들어온다. 지금도 IntersectionObserver가 예열을 버린 뒤 같은 모습이다. 달라지는 것은 첫 프레임 한 장뿐이다(눈으로 확인).
- 개선 3: 추출 단계에서 분류 LLM이 실패하면 키워드 규칙 결과가 실려 간다. compare는 그 값을 그대로 쓴다. 지금은 compare에서 LLM을 한 번 더 시도한다.
- 개선 3: 추출 응답이 분류 시간만큼 늦어진다. 확인 화면을 건너뛰는 경로의 결과 시간은 거의 같다.
- 개선 3: 테스트가 `docs/api-spec.md`의 json 코드 블록을 순서(0~3번)로 읽는다(`tests/test_api.py`, `tests/test_pipeline.py`, `tests/test_agent.py`).
  - 4장 응답 예시(1번 블록)에 필드를 넣는 것은 괜찮다.
  - 5장 요청 예시(2번 블록)에는 넣지 않는다. 넣으면 `test_compare_example_numbers_without_llm`이 키워드 분류 대신 실린 값을 시험하게 된다.
  - 새 예시 블록이 필요하면 5장 응답 예시(3번 블록) 뒤에 둔다.
- 개선 3: 새 필드는 선택이고, pydantic은 모르는 필드를 무시한다(`ApiModel`에 `extra` 설정이 없다). 옛 화면과 새 서버, 새 화면과 옛 서버 모두 지금처럼 돈다.
- 되돌리기: 개선마다 커밋을 나눈다. 문제가 생기면 `git revert <커밋>`으로 되돌리는 PR을 올린다. force push와 rebase는 쓰지 않는다.
- 급하면 김상해가 Vercel에서 이전 배포로 되돌린다.
- 22:00 동결 뒤에는 되돌리기와 버그 수정만 한다.

## Claude Code 시작 문장

```text
나는 김상해다.
docs/tasks/W5-perceived-latency.md를 읽고 그대로 진행해.
W1이 main에 합쳐졌는지 먼저 확인하고, 안 됐으면 멈추고 알려 줘.
개선 1·2를 먼저 하고, 개선 3은 내가 방식을 고른 뒤에 따로 시작해.
고치기 전과 후의 숫자를 "확인 방법"대로 재서 보여 줘.
끝나면 python3 -m pytest 전부 통과를 확인하고 PR을 올려.
```
