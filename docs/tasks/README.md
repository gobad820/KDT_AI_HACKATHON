# 작업 목록 (11/22)

- 작업 하나에 파일 하나를 둔다.
- 자기 이름이 "담당"인 파일만 맡는다.
- 끝나면 그 파일의 "상태"를 고쳐 PR에 함께 올린다.

오늘 시간표와 처음 시작하는 법은 [docs/team-1122.md](../team-1122.md)에 있다. 결정과 그 이유는 [docs/decisions.md](../decisions.md)에 있다.

## 작업

번호 / 제목 / 담당 / 상태 / 먼저 끝나야 하는 것

- W1 [서비스 이름 변경과 기본 누적 10년](W1-rename-10y.md) / Claude Code / 진행 중 / 없음
- W2 [테스트 30건과 추출 프롬프트](W2-agent-tests.md) / 이동한 / 시작 전 / 없음(30건 실제 실행만 W8 뒤)
- W3 [공식 계산기 대조](W3-calc-check.md) / 정상훈 / 시작 전 / 없음
- W4 [소개서, AI 활용내역, Credits](W4-docs-and-intro.md) / 김상해 / 시작 전 / README·ai-usage-log를 고치기 전에 W1(소개서 초안은 먼저 시작, 검증 수치는 W2·W3 뒤)
- W5 [체감 속도 개선 세 가지](W5-perceived-latency.md) / Claude Code / 제안(대표자 승인 전) / W1, W8
- W6 [추출 일관성 측정 스크립트](W6-consistency-script.md) / Claude Code / 시작 전 / 없음(언제든)
- W7 [기능 동결과 제출](W7-freeze-and-submit.md) / 김상해 / 시작 전 / W1~W4, W8(W5·W6은 합친 경우만)
- W8 [연봉 인상 반영(기회비용 보강)](W8-salary-growth.md) / Claude Code(리뷰 이동한·정상훈) / 시작 전 / W1, U-12 결정

상태는 "시작 전, 진행 중, PR 올림, 합침, 제안(대표자 승인 전)" 중 하나로 쓴다. 기준은 각 W 파일의 상태 줄이다. 이 목록의 상태는 김상해가 PR을 합칠 때 맞춘다.

## 누가 어떤 파일을 고치나

같은 파일을 둘 이상이 고치면 화살표 순서를 따른다. 뒤 작업은 앞 작업이 합쳐진 뒤 `git pull origin main`을 하고 PR을 올린다.

문서

- `README.md` → W1(이름, 소개) → W4(Credits, "지금 상태"의 LLM 줄)
- `CLAUDE.md` → W1
- `HANDOFF.md` → W1(2장) → W2(5장 T12·T13 체크), W3(5장 T14 체크)
- `docs/brief.md`, `docs/data-spec.md` → W1(제목, 기본값 문구)
- `docs/agent-spec.md` → W1(제목) → W8(3·4·5장) → W2(12장, 필요할 때만)
- `docs/api-spec.md` → W1(제목) → W8 → W5
- `docs/dev-notes.md` → W8 → W5
- `docs/calc-rules.md` → W1(제목, 7장 기본값 문구) → W8(1장 가정, 7장 연차별 연봉), W3(8장 표, 2장 상수표). W8과 W3은 다른 장이라 동시에 해도 된다. 뒤에 합치는 쪽이 pull한다.
- `docs/ai-usage-log.md` → W1(이 작업 기록 한 줄, 브랜치에 이미 있음) → W4. W5·W6·W8(Claude Code)은 `git pull origin main` 뒤 파일 끝에 한 줄씩 직접 붙인다. W2·W3은 기록할 내용을 PR 본문에 적고, W4가 옮긴다.
- `docs/team-1122.md`, `docs/tasks/README.md` → 김상해
- `docs/tasks/W?-*.md` → 그 파일의 담당(상태 줄)

화면과 서버

- `app/main.py` → W1(API 문서 제목) → W5(`extract()`)
- `app/schemas.py` → W1(기본 누적 기간) → W8(인상률 필드) → W5(업종 분류 필드)
- `app/pipeline.py` → W8(인상률 검증, 가정 문구) → W5(`run_compare` 안의 분류)
- `app/web/app.js` → W1 → W8 → W5
- `app/web/mock.js` → W8
- `app/web/flow.js` → W5
- `app/web/index.html` → W1 → W8 → W5(`?v=` 캐시 값)
- `app/web/style.css` → W1
- `scripts/build_hero.py`, `app/web/hero.json`, `app/web/hero.js` → W1
- `media/showreel/reel.html` → W1(HTML만, 영상은 다시 만들지 않음)

에이전트

- `app/agent/classify.py` → W2(검토만). 고칠 곳은 PR 본문에 적는다. W5는 이 파일을 고치지 않는다.
- `app/agent/prompts/extract_v3.md`, `app/agent/extract.py`의 `PROMPT_VERSION`, `app/agent/evidence.py`, `app/agent/questions.py`, `app/agent/numbers.py` → W8(이동한 리뷰). W2는 이 파일에서 고칠 곳을 W8 PR 리뷰로 남긴다.
- `app/agent/`의 나머지 → W2
- `data/samples/*.json`의 본문과 `savedExtract` → W8(U-12에서 정할 때만, 이동한 확인)
- `tests/cases/` → W2
- `scripts/measure_consistency.py`, `scripts/consistency/`, `tests/test_measure_consistency.py` → W6
- `tests/test_pipeline.py`, `tests/test_api.py` → W1(기본값 테스트 한 개) → W8 → W5
- `tests/test_agent.py` → W8(W2는 1번에서 버그를 고칠 때만)

계산

- `app/calc/scenarios.py`, `scripts/calc_ref.py`의 `simulate`·`break_even_salary`, `tests/test_calc_scenarios.py` → W8(정상훈 리뷰)
- `app/calc/netpay.py`, `app/calc/constants.py`, `scripts/calc_ref.py`의 세후 계산 부분, `tests/test_calc_netpay.py` → W3
- `scripts/calc_ref.py`는 W3과 W8이 함께 고칠 수 있다. 뒤에 합치는 쪽이 pull하고 `python3 scripts/calc_ref.py` 출력을 다시 확인한다.

배포와 제출

- Vercel 배포, Vercel 환경변수, git 태그 → W7(김상해만)

W5, W6, W8이 고치는 파일은 각 작업 문서의 "건드리는 파일"과 맞춰 두었다. 서로 다르면 작업 문서를 따르고 김상해에게 알린다.

## 순서

- PR #1 → W1 → W8 → (W5)
- W8 PR은 15:00(제안)까지 올린다. W2의 30건 실제 실행은 W8이 합쳐진 뒤 최종 프롬프트(`extract_v3`)로 한다. 30건 파일 만들기는 지금 시작한다.
- W6은 W8이 합쳐지면 인상률 필드를 비교 대상에 넣는다.
- W2·W3·W4·W6·W8은 파일이 거의 겹치지 않아 동시에 진행한다. 시작 전에 `git pull origin main`을 한다.
- 겹치는 파일(`README.md`, `HANDOFF.md`, `docs/calc-rules.md`)을 고치는 작업은 PR 전에 한 번 더 pull한다.
- W7은 19:00(제안) PR 병합에서 시작해 22:00 동결, 제출로 이어진다.
