# W1 서비스 이름 변경과 기본 누적 10년

- 담당: Claude Code(지시와 병합은 김상해) / 브랜치: `feat/sanghae-rename-10y` / 상태: 진행 중 / 마감: 19:00 PR(제안) / 먼저 끝나야 하는 것: 없음

## 왜

- 11/22 대표자 결정으로 서비스 이름을 「첫 직장, 10년 뒤 경제력」으로 바꾼다. 이유는 [docs/decisions.md](../decisions.md)에 있다.
- 같은 결정으로 결과 화면의 기본 누적 기간을 5년에서 10년으로 바꾼다.
- [docs/brief.md](../brief.md)에도 "감면기간 차이는 연차별 표와 10년 선택에서 드러난다"고 적혀 있다.
- 첫 화면 문장에도 10년 숫자를 더한다.
- 이 작업은 파일을 많이 고친다. 다른 작업은 이 PR이 합쳐진 뒤 `git pull origin main`을 하고 시작해야 충돌이 적다.
- [docs/decisions.md D-15](../decisions.md#d-15-서비스-이름과-기본-누적-기간)에 따르면 이름 변경, 기본값 10년, 첫 화면 문장은 브랜치에 이미 들어가 있다. 아래 목록은 그 브랜치와 맞춰 보는 기준이다.

## 할 일

1. 화면 이름을 바꾼다. `app/web/index.html`의 `<title>`과 첫 화면 `<h1>`이다.
2. API 문서 제목을 바꾼다. `app/main.py`의 `FastAPI(title=...)`이다.
3. 문서 이름을 바꾼다. `README.md` 제목과 한 줄 소개, `CLAUDE.md` 맨 위 소개 줄, `HANDOFF.md` 2장이다.
4. `docs/`의 명세 제목을 바꾼다. `brief.md`, `api-spec.md`, `calc-rules.md`, `data-spec.md`, `agent-spec.md`이다.
5. 머리 주석의 이름을 바꾼다. `app/web/app.js`, `app/web/style.css`이다.
6. 지난 기록(`docs/plan.md`의 11/20 계획, `docs/status-2026-11-21.md`)의 옛 이름은 기록이라 그대로 둔다(확인 필요).
7. 기본 누적 기간을 10년으로 바꾼다. `app/schemas.py`의 `horizon_years` 기본값과 `app/web/app.js`의 `freshState` 초기값이다.
8. 기본값 문구를 고친다. `docs/calc-rules.md` 7장과 `docs/brief.md`의 "기본값은 팀 결정(제안 5)"이다.
9. `scripts/build_hero.py`가 10년 누적 숫자를 계산 모듈로 만들어 `app/web/hero.json`에 새 키로 더하게 한다. 어느 시나리오로 셀지는 이 작업에서 정한다(확인 필요).
10. `app/web/hero.js`가 그 새 키로 첫 화면 문장(`heroFact`)에 10년 숫자를 넣게 한다. 화면 코드에서 곱하거나 더하지 않는다.
11. `hero.json`의 기존 값(1년차 숫자)은 바꾸지 않는다. 첫 화면 영상의 영수증이 그 값으로 구워져 있다(`media/printer/receipt_texture.js`).
12. 쇼릴 원본 `media/showreel/reel.html`의 이름을 바꾼다. 쇼릴 mp4는 다시 렌더하지 않는다(decisions.md U-8).
13. 기본값 5년을 가정한 테스트가 있으면 고친다.
14. 이 작업의 기록 한 줄을 `docs/ai-usage-log.md`에 둔다. 브랜치에 이미 있다(decisions.md U-8).
15. PR 본문에 "Claude Code가 한 일"과 "김상해가 직접 확인한 일"을 한 줄씩 적는다.

## 건드리는 파일

- `README.md`, `CLAUDE.md`, `HANDOFF.md`(2장)
- `docs/brief.md`, `docs/api-spec.md`, `docs/calc-rules.md`, `docs/data-spec.md`, `docs/agent-spec.md`(제목, 기본값 문구)
- `app/web/index.html`, `app/web/app.js`, `app/web/style.css`
- `app/main.py`, `app/schemas.py`
- `scripts/build_hero.py`, `app/web/hero.json`, `app/web/hero.js`
- `media/showreel/reel.html`(HTML만)
- `docs/ai-usage-log.md`(이 작업 기록 한 줄)
- 기본값을 가정한 `tests/test_*.py`(있을 때만)
- 이 파일의 상태 줄

## 건드리지 않는 파일

- 배포 주소 `nammeun-don.vercel.app`, Vercel 프로젝트 이름, 저장소 이름: 바꾸지 않는다(11/22 대표자 결정).
- `app/web/img/hero_print.mp4`, `media/printer/`: 첫 화면 영상은 다시 만들지 않는다. 렌더만 약 35분이 걸린다.
- `app/agent/`, `tests/cases/`: W2(이동한)가 고친다.
- `app/calc/`, `scripts/calc_ref.py`: W3(정상훈)이 고친다. `calc_ref.py` 머리말에도 옛 이름이 있다. 고칠지는 정상훈에게 묻는다(확인 필요).
- `app/web/flow.js`, `app/agent/classify.py`: W5가 고친다.
- `docs/ai-usage-log.md`의 다른 줄과 "(팀이 채울 것)" 칸: W4가 고친다.
- `docs/team-1122.md`, `docs/tasks/`의 다른 파일: 김상해가 고친다.

## 끝났다고 보는 기준

- 브라우저 탭 제목, 첫 화면 제목, API 문서 제목이 「첫 직장, 10년 뒤 경제력」이다.
- `grep`으로 찾은 옛 이름이 남겨도 되는 곳(지난 기록, `media/`)에만 있다.
- 결과 화면을 처음 열면 누적 기간이 10년으로 선택되어 있다.
- `/api/compare` 요청에 `horizonYears`가 없으면 10년으로 계산한다.
- 첫 화면 문장에 10년 숫자가 나온다. 그 숫자는 `hero.json`에 있다.
- `hero.json`의 기존 키 값이 바뀌지 않았다.
- `python3 -m pytest`가 전부 통과한다.
- 합친 뒤 배포 URL에서 샘플 2쌍이 입력부터 결과까지 통과한다(김상해 확인).

## 확인 방법

```bash
python3 -m pytest
grep -rn "남는 돈 비교" --exclude-dir=media --exclude-dir=.git .
python3 scripts/build_hero.py
git diff app/web/hero.json        # 기존 값은 그대로, 새 키만 더해졌는지
uvicorn app.main:app --reload     # http://localhost:8000
```

- 화면만 볼 때는 http://localhost:8000/?mock=1 을 연다.
- 첫 화면 문장, 탭 제목, 결과 화면의 누적 기간을 눈으로 본다.

## 위험과 되돌리는 법

- 고치는 파일이 많아 다른 PR과 충돌하기 쉽다. 그래서 이 PR을 가장 먼저 합친다.
- `hero.json`의 기존 값이 바뀌면 영상 속 영수증과 화면 문장이 어긋난다. `git diff`로 보고, 바뀌었으면 멈추고 김상해에게 알린다.
- 기본값이 10년이 되면 결과 화면의 누적 차이와 손익분기 숫자가 바뀐다. 소개서와 캡처는 10년 기준으로 다시 만든다(W4).
- 합친 뒤 문제가 생기면 병합 커밋을 `git revert`로 되돌린다. force push는 하지 않는다.

## Claude Code 시작 문장

```text
나는 김상해다.
docs/tasks/W1-rename-10y.md를 읽고 그대로 진행해.
이 작업은 브랜치 feat/sanghae-rename-10y에서 이미 진행 중이다.
먼저 그 브랜치에서 바뀐 파일을 할 일 목록과 맞춰 보고 남은 일을 보여 줘.
내가 확인하면 남은 일을 이어서 해.
hero.json의 기존 값이 바뀌면 멈추고 알려 줘.
끝나면 pytest 전부 통과를 확인하고 PR을 올려.
```
