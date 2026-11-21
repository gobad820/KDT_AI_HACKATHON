# W8 연봉 인상 반영 (기회비용 보강)

- 담당: Claude Code(승인 김상해) / 리뷰: 이동한(추출·되묻기), 정상훈(계산) / 브랜치: `feat/sanghae-salary-growth` / 상태: 시작 전 / 마감: PR 15:00(제안). W2의 30건 실제 실행이 이 PR 뒤에 이어진다 / 먼저 끝나야 하는 것: W1(PR #2) main 병합

## 왜

- 지금 10년 누적은 1년 값에 10을 곱한 것과 같다. `app/calc/scenarios.py`의 `cumulative_remaining`과 `_scenario`가 연봉을 고정한다([docs/calc-rules.md 1장](../calc-rules.md#1-범위와-가정) "연봉과 월세도 고정한다").
  - 서울 예시(연봉 3,800만 원)는 1년에 23,119,806원, 10년에 231,198,060원이 남는다. 정확히 10배다.
- 서비스 이름이 「첫 직장, 10년 뒤 경제력」인데 10년 동안 연봉이 오르지 않는다. 심사에서 가장 먼저 물을 곳이다.
- 빠진 기회비용 가운데 금액이 가장 크다. 시작 연봉 3,400만 원에서 인상률이 연 1%p만 달라도 10년이면 세전으로 1,500만 원 넘게 달라진다. 지금 화면의 10년 차이(세후 1,768만 원)와 비슷한 크기다.
- 공고 본문에 단서가 있는 항목이라 AI가 할 일이 생긴다. AI는 단서를 근거 문장과 함께 찾고, 없으면 묻는다. 금액은 코드가 계산한다([decisions.md D-17](../decisions.md#d-17-기회비용-보강-연봉-인상만-넣는다)).

## 범위

- 넣는 것: 공고별 연 인상률 하나. 1년차 연봉에서 매년 같은 비율로 오른다.
- 넣지 않는 것: 월세 인상, 통근, 생활비, 지역 청년 지원금, 저축 수익, 이직. 소개서의 "한계와 다음 단계"에만 적는다(W4).
- 기본 인상률은 U-12 결정을 따른다. 이 문서는 제안안(기본 0%, 공고 근거나 사용자 입력이 있을 때만 반영)을 기준으로 쓴다.

## 할 일

경계 문서를 먼저 고치고 코드로 간다(`CLAUDE.md` "문서").

1. `docs/calc-rules.md`
   - 1장 가정을 고친다. "연봉은 공고별 연 인상률로 매년 오른다. 월세, 요율, 비과세는 고정한다."
   - 7장에 연차별 연봉을 넣는다. t년차 연봉 = 1년차 연봉 × (1 + 인상률)^(t−1)을 원 단위로 내린 값이다.
   - 인상률은 만분율 정수로 받는다(300 = 연 3%). `fractions.Fraction`으로 계산하고 float를 쓰지 않는다.
   - 감면은 연차별 연봉으로 해마다 다시 계산한다. 연 한도도 해마다 적용한다.
   - 손익분기 연봉은 "1년차 연봉" 기준으로 바꾼다. 그 공고의 인상률은 그대로 둔다. 이분 탐색 범위와 만 원 올림은 지금과 같다.
   - 7장 회귀 표는 인상률 0% 표로 남기고, 3% 예시 표를 하나 더 붙인다. 값은 `scripts/calc_ref.py` 출력에서 가져온다.
2. `docs/api-spec.md`
   - 추출 응답의 공고 필드에 `annualRaise`를 넣는다(Field 객체, 값은 만분율 정수).
   - `/api/compare` 요청의 `confirmed`에 `annualRaiseBp`를 넣는다(정수, 0~2000, 기본 0).
   - 응답의 연차별 행에 `annualSalary`를 넣는다.
3. `docs/agent-spec.md`
   - 3장 추출 스키마에 인상률 필드를 넣는다.
     - 공고에 "연 ○% 인상"처럼 숫자가 있을 때만 값을 넣는다.
     - 호봉제, "매년 인상"처럼 숫자가 없으면 값은 비우고 근거 문장과 메모만 남긴다.
     - "업계 평균" 같은 값을 LLM이 만들지 않는다.
   - 4장 근거 검증에 비율 규칙을 넣는다. 근거 문장에 그 숫자가 있어야 한다.
   - 5장 되묻기에 인상률 질문을 넣는다. 선택 질문이고, 이 질문 때문에 확인 화면을 띄우지 않는다(D-06).
4. `docs/dev-notes.md`의 함수 경계(`SimJob`, `simulate`)를 고친다.
5. 추출
   - `app/agent/prompts/extract_v3.md`를 새로 만들고 `app/agent/extract.py`의 `PROMPT_VERSION`을 `extract_v3`로 바꾼다. v2 파일은 지우지 않는다.
   - `app/schemas.py`의 `PostingFields`에 인상률 필드를 넣는다.
   - `app/agent/evidence.py`에 비율 근거 검증을 넣는다. 근거에 숫자가 없거나 지시문처럼 생긴 근거는 거부한다.
6. 되묻기(`app/agent/questions.py`)
   - 인상률 값이 없으면 질문 하나를 붙인다. 예: "○○ 공고에는 연봉 인상률이 없습니다. 알고 있다면 적어 주세요. 비우면 0%(연봉 고정)로 계산합니다."
   - 호봉제 같은 단서가 있으면 그 근거 문장을 질문에 인용한다.
   - `MAX_POSTING_QUESTIONS` 안에서 가장 낮은 순위로 둔다. 필수 질문을 밀어내지 않는다.
7. 계산(`app/calc/scenarios.py`, `scripts/calc_ref.py`)
   - `SimJob`에 인상률을 넣고, `_scenario`와 `cumulative_remaining`을 연차별 합으로 바꾼다.
   - `_net` 캐시는 그대로 쓴다(연봉별 캐시).
   - `calc_ref.py`의 `simulate`, `break_even_salary`도 같은 정의로 따로 고친다.
   - 인상률 0%이면 지금 결과와 1원도 다르지 않아야 한다.
8. 파이프라인과 스키마
   - `Confirmed`에 `annual_raise_bp`(기본 0, 0~2000)를 넣는다. 범위 밖이면 `invalid_input`으로 막는다.
   - `YearRow`에 `annual_salary`를 넣는다.
   - 가정 문구에 공고별 인상률과 출처를 적는다. 예: "공고 A: 연 3%(공고 근거) / 공고 B: 0%(공고에 없음, 연봉 고정)".
9. 설명문 숫자 검증(`app/agent/numbers.py`)
   - 인상률과 연차별 연봉을 허용 목록에 넣는다. 넣지 않으면 AI 설명문이 인상률을 말할 때 검증에 떨어지고 템플릿 문장으로 바뀐다.
10. 화면(`app/web/app.js`, `app/web/mock.js`, `app/web/index.html`)
    - 확인 화면에 "연봉 인상률(%)" 칸을 넣고 근거 문장을 보여 준다.
    - 결과 연차별 표에 연봉 열을 넣는다. 결과 맨 위 가정 문구에 공고별 인상률을 보여 준다.
    - `index.html`의 `?v=` 캐시 값을 바꾼다.
11. 샘플과 첫 화면
    - U-12에서 샘플 공고에 인상 문구를 넣기로 하면 `data/samples/*.json`의 공고 본문과 `savedExtract`를 함께 고친다. 이동한에게 확인받는다(W2 영역).
    - `scripts/build_hero.py`는 `simulate`를 부르므로 기본 인상률이 0%이면 `hero.json`은 바뀌지 않는다. 바뀌면 다시 만든다.
    - 첫 화면 영상의 영수증은 1년차 숫자라 인상률과 관계없다. 다시 렌더하지 않는다.
12. 테스트
    - 계산: 인상률 0%이면 기존 기대값과 같다. 3%이면 `calc_ref.py`와 연차별 값이 같다. 손익분기가 1년차 연봉에 대해 단조 증가한다.
    - 에이전트(가짜 LLM): 숫자가 있는 인상 문구, 호봉제만 있는 문구, 근거 없는 값, 지시문 근거.
    - API: `annualRaiseBp` 왕복, 범위 밖 오류, 빼고 보내면 0%.
13. 실제 Gemini로 샘플 2쌍을 한 번씩 추출한다. 한 건씩 차례로 보낸다.
14. 로컬 서버에서 샘플 2쌍을 입력부터 결과까지 눌러 본다.
15. `git pull origin main` 뒤 `docs/ai-usage-log.md` 끝에 한 줄을 붙인다.
16. PR 본문에 이동한(추출·되묻기)과 정상훈(계산) 리뷰를 요청하고, "Claude Code가 한 일"과 "김상해가 직접 확인한 일"을 한 줄씩 적는다.

## 건드리는 파일

- 문서: `docs/calc-rules.md` 1장·7장, `docs/api-spec.md`, `docs/agent-spec.md` 3·4·5장, `docs/dev-notes.md`
- 에이전트: `app/agent/prompts/extract_v3.md`(새 파일), `app/agent/extract.py`(`PROMPT_VERSION`), `app/agent/evidence.py`, `app/agent/questions.py`, `app/agent/numbers.py`
- 서버: `app/schemas.py`, `app/pipeline.py`
- 계산: `app/calc/scenarios.py`, `scripts/calc_ref.py`의 `simulate`·`break_even_salary`
- 화면: `app/web/app.js`, `app/web/mock.js`, `app/web/index.html`
- 샘플: `data/samples/*.json`(U-12에서 정할 때만)
- 테스트: `tests/test_calc_scenarios.py`, `tests/test_agent.py`, `tests/test_api.py`, `tests/test_pipeline.py`
- `docs/ai-usage-log.md` 끝 한 줄, 이 파일의 상태 줄

## 건드리지 않는 파일

- `app/calc/netpay.py`, `app/calc/constants.py`, `scripts/calc_ref.py`의 세후 계산 부분: W3이 공식 계산기 대조로 고칠 수 있다.
- `tests/cases/`: W2가 쓴다.
- `app/agent/classify.py`, `app/web/flow.js`: W5(제안) 영역이다.
- `scripts/measure_consistency.py`, `scripts/consistency/`: W6이 W8 뒤에 새 필드를 비교 대상에 넣는다.
- `app/web/hero.json`을 손으로 고치지 않는다. 바뀌면 `build_hero.py`로만 만든다.

## 끝났다고 보는 기준

- 인상률 0%로 계산하면 기존 테스트 기대값이 1원도 바뀌지 않는다.
- 인상률 3%의 연차별 값이 `app/calc`와 `scripts/calc_ref.py`에서 같다.
- 공고에 인상률 숫자가 없으면 추출값이 비어 있다. LLM이 추정한 값이 나오지 않는다.
- 결과 화면에 공고별 인상률과 그 출처(공고 근거, 사용자 입력, 기본 0%)가 보인다.
- `python3 -m pytest`가 전부 통과하고, `LLM_PROVIDER= python3 -m pytest`도 통과한다.
- 이동한과 정상훈이 PR에 리뷰를 남겼다.

## 확인 방법

```bash
python3 -m pytest
LLM_PROVIDER= python3 -m pytest
python3 scripts/calc_ref.py                     # 0% 표가 calc-rules 7장 회귀 표와 같은지
python3 -m pytest tests/test_calc_scenarios.py -k raise
grep -n "PROMPT_VERSION" app/agent/extract.py   # extract_v3
```

- `uvicorn app.main:app --reload`로 서버를 띄우고 http://localhost:8000 에서 샘플 2쌍을 눌러 본다.
- `?mock=1` 화면에서도 연차별 표와 가정 문구가 깨지지 않는지 본다.

## 위험과 되돌리는 법

- 계산 경로가 바뀌면 모든 누적 금액이 바뀔 수 있다. 인상률 0% 회귀 테스트로 막는다.
- 프롬프트가 바뀌면 샘플 추출과 W2의 30건 결과가 바뀐다. 그래서 마감을 15:00(제안)으로 앞당겼다. W2는 이 PR이 합쳐진 뒤 30건을 실행한다.
- 손익분기 정의가 "1년차 연봉"으로 바뀐다. 소개서 설명도 바꾼다(W4).
- 15:00까지 추출 부분을 끝내지 못하면 범위를 줄인다. 추출은 v2로 두고, 확인 화면의 사용자 입력 인상률과 계산만 넣는다. 이 경우 AI가 맡는 일은 늘지 않는다. 줄일지는 김상해가 정한다.
- 프롬프트를 되돌릴 때는 `PROMPT_VERSION`을 `extract_v2`로 바꾼다.
- 합친 뒤 문제가 생기면 병합 커밋을 `git revert`로 되돌린다. force push는 하지 않는다.

## Claude Code 시작 문장

```text
나는 김상해다.
docs/tasks/W8-salary-growth.md를 읽고 그대로 진행해.
먼저 할 일 순서와 건드릴 파일을 보여 주고, 내가 확인하면 시작해.
경계 문서(calc-rules, api-spec, agent-spec, dev-notes)부터 고치고 코드로 가.
브랜치는 feat/sanghae-salary-growth로 만들어.
실제 Gemini 호출은 한 건씩 차례로 보내.
끝나면 pytest 전부 통과를 확인하고 PR을 올려. 리뷰는 이동한(추출·되묻기), 정상훈(계산)에게 요청해.
```
