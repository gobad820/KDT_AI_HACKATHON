# W6 추출 일관성 측정 스크립트를 저장소에 남기기

- 담당: Claude Code(승인 김상해) / 브랜치: `feat/sanghae-consistency-script` / 상태: 제안(대표자 승인 전) / 마감: 11/22(일) 23:00 PR(배포되지 않는 스크립트라 문서 PR 마감을 따른다, 대표자 확인 필요) / 먼저 끝나야 하는 것: 없음. 기준 결과는 19:00 프롬프트 PR 마감 뒤 main의 최종 프롬프트로 잰다

## 왜

- 11/21 밤에 가상 공고 표기 7종을 실제 Gemini(`gemini-flash-lite-latest`, 프롬프트 `extract_v2`)로 3번씩 추출해 기대값과 비교했다. 샘플 2쌍은 저장본(`savedExtract`)과 2번씩 비교해 48/48이 맞았다.
- 그때 쓴 코드는 저장소에 없다. Claude Code 세션에서 터미널에 바로 넣고 돌린 일회성 코드였다.
- 임시 파일을 읽은 결과
  - `t8.py`: 모델 이름을 인자로 받아 가상 공고 2건을 한 번씩 추출하고 값을 찍는다. 기대값 비교와 반복이 없어 일관성 측정 코드가 아니다. `.env`를 읽는 방식(`from app import config`)과 `LLM_MODEL`을 바꿔 `get_llm()`을 부르는 방식만 참고한다.
  - `sim.py`: 가짜 LLM(지연 1초)으로 extract·compare 안의 LLM 호출 순서를 잰다. 실제 LLM을 부르지 않는다. W6와 관련이 없다.
  - 실제 측정 코드와 사례 문구는 세션 기록(11/21 22:24 KST 실행)에서 찾았다. 아래 "사례 7개"에 그대로 옮겼다.
- 11/21 코드의 약점. 새 스크립트에서 고친다.
  - 요청 3개를 동시에 보냈다(`ThreadPoolExecutor(3)`). 한 번 시간 초과가 나서 계약직 전환이 "세 번 같음 False"로 찍혔다. 호출 실패를 값 불일치로 센 것이다. 계약직 전환만 차례로 3번 다시 돌려 3/3을 확인했다.
  - 기대값을 첫 번째 실행 결과하고만 비교했다.
  - 비교한 필드 수를 찍지 않았다. 현황 노트 "배운 것" 5번(아무것도 비교하지 않고 "다른 필드 0개"를 보고함)과 같은 위험이다.
  - 실제로 답한 모델을 기록하지 않았다. 대체 모델로 넘어가도 알 수 없다.
- 언제 돌리나
  - 추출 프롬프트(`app/agent/prompts/extract_v*.md`, `extract.PROMPT_VERSION`)를 바꿀 때. 바꾸는 PR을 올리기 전에 돌린다.
  - `app/agent/extract.py`, `evidence.py`, `salary.py`를 바꿀 때.
  - `LLM_MODEL`이나 `LLM_MODEL_FALLBACKS`를 바꿀 때. 대체 모델도 `--model`로 하나씩 잰다.
  - 본선(12/7) 전. `gemini-flash-lite-latest`는 별칭이라 Google이 가리키는 버전을 바꾸면 결과가 달라질 수 있다. 1주 전과 전날 한 번씩 돌려 기준 결과와 비교한다(제안).
- 마감(11/23 17:00) 뒤에는 프롬프트를 고칠 수 없다. 본선 전 측정은 확인용이다. 결과가 나쁠 때 모델을 버전 고정 이름으로 바꾸는 것이 "실행 환경 복구"에 해당하는지는 대회 규정을 봐야 한다(확인 필요).

## 할 일

1. `git pull origin main` 후 `feat/sanghae-consistency-script` 브랜치를 만든다.
2. `scripts/consistency/cases/`에 사례 JSON 7개를 만든다. 문구와 기대값은 아래 "사례 7개"를 그대로 쓴다.
3. 사례 파일과 `--help` 초안을 김상해에게 보여 주고 확인받는다.
4. `scripts/measure_consistency.py`를 아래 "스크립트 사양"대로 만든다.
5. `tests/test_measure_consistency.py`를 만든다. FakeLLM만 쓰고 네트워크를 부르지 않는다.
6. `python3 -m pytest` 전부 통과를 확인한다.
7. 호출 1번으로 연결을 확인한다(`--only short_address --runs 1 --no-samples`).
8. 19:00 프롬프트 PR 마감 뒤 main을 다시 받는다. 이동한이 `extract_v3`를 만들었으면 그 버전으로 잰다.
9. 기준 결과를 한 번 잰다(`--runs 3 --out scripts/consistency/results/2026-11-22.json`).
10. 비교한 필드 수, 일치 수, 호출 실패 수, 응답 모델 값을 PR 본문에 적고 11/21 결과와 견준다.
11. 불일치가 있으면 사례, 필드, 기대 값, 실제 값을 PR에 적고 이동한에게 알린다. 프롬프트와 `app/agent`는 W6에서 고치지 않는다.
12. `docs/ai-usage-log.md`에 한 줄 남긴다(Claude Code가 한 일, 김상해가 확인한 일).
13. PR을 올린다.

### 스크립트 사양

위치와 폴더

- 스크립트: `scripts/measure_consistency.py`.
- 사례: `scripts/consistency/cases/*.json`. 파일 하나에 공고 하나다.
- 결과: `--out`을 줄 때만 JSON으로 쓴다. 기준 결과는 `scripts/consistency/results/`에 둔다.
- `tests/cases/`에 두지 않는다. 이동한의 T12(테스트 30건, `RESULTS.md`) 폴더다.
- `tests/` 아래에도 두지 않는다. pytest 대상 폴더라 "실제 LLM을 부르는 테스트는 만들지 않는다"(`docs/dev-notes.md` 3장)와 헷갈린다. 스크립트 이름도 `test_`로 시작하지 않는다.
- `scripts/`와 `tests/`는 `.vercelignore`로 배포 번들에서 빠진다. 서비스 동작은 바뀌지 않는다.

사례 파일 형식

```json
{
  "id": "monthly",
  "label": "월급",
  "text": "[가나물류(가상)] 물류 관리 신입\n근무지: 경기도 용인시 처인구\n급여: 월 280만원(세전)\n고용형태: 정규직\n기업규모: 중소기업",
  "expect": {"annualSalary": 33600000, "employmentType": "regular", "companySize": "sme"},
  "note": "11/21 기대값"
}
```

- 최상위 키는 `id`, `label`, `text`, `expect`, `note`(선택)다.
- `expect`의 키는 `schemas.dump(PostingFields)`의 camelCase 경로다. 각 필드의 `value`와 비교한다.
- 쓸 수 있는 키: `companyName`, `annualSalary`, `workLocationText`, `employmentType`, `companySize`, `industryText`, `benefits.mealAllowanceMonthly`, `benefits.dormitory`, `benefits.housingSupportMonthly`, `region.sggCode`.
- `region.sggCode`는 추출한 `workLocationText`를 `app.data.regions.resolve_region`에 넣어 후보가 하나일 때의 코드다. 후보가 없거나 여럿이면 null이다.
- 목록에 없는 키가 있으면 시작 전에 멈춘다. 오타 때문에 아무것도 비교하지 않는 일을 막는다.

샘플 공고

- `data/samples/pair1.json`, `pair2.json`의 `postings[]` 4건을 사례로 더한다.
- 기대값은 각 파일의 `savedExtract.fields`다. 11/21과 같은 6개 필드(`companyName`, `annualSalary`, `workLocationText`, `employmentType`, `companySize`, `industryText`)를 비교한다.
- 샘플 파일은 읽기만 한다. `--no-samples`로 뺀다.

실행 방식

- `from app import config`로 `.env`를 읽는다. 키 값은 어디에도 찍지 않는다.
- `--model`을 주면 `get_llm()`을 부르기 전에 `os.environ["LLM_MODEL"]`을 바꾼다.
- 기본으로 대체 모델을 끈다(`os.environ["LLM_MODEL_FALLBACKS"] = ""`). 결과가 한 모델의 것이 되게 한다. `--allow-fallback`이면 `.env` 그대로 쓴다.
- `get_llm()`이 None이면(`LLM_PROVIDER`가 빔) 알리고 종료 코드 2로 끝낸다.
- 공고 한 건을 `extract_postings([PostingInput(id="A", text=…)], llm)`로 부른다. 공고 하나에 LLM 호출 하나다.
- 11/21 코드가 쓴 비공개 함수 `_extract_one`은 쓰지 않는다. 샘플도 쌍이 아니라 한 건씩 부른다(11/21 코드는 두 건을 넣어 동시에 불렀다).
- 동시에 보내지 않는다. 호출이 끝나면 `--sleep`초(기본 4) 쉬고 다음을 보낸다. 분당 한도(429)를 피하려는 것이다. 무료 키의 분당 한도 값은 확인 필요.
- 호출마다 걸린 시간과 결과를 남긴다.
- 실패(`LLMUnavailable`, `PostingUnreadable`, 그 밖 예외)는 "호출 실패"로 따로 센다. 불일치로 세지 않고, 그 실행은 일치 수의 분모에서 뺀다. 실패 종류를 함께 찍는다.
- 실제로 답한 모델을 기록한다. 만든 `llm` 객체의 `_post`를 감싸 호출마다 요청한 모델, HTTP 상태 코드, 응답 JSON의 `model` 값을 남긴다. `llm.py`는 고치지 않는다.
- `_post`가 없는 어댑터(예: `AnthropicClient`)면 기록 없이 진행하고 "응답 모델 기록 안 됨"을 찍는다.
- 응답의 `model` 값이 별칭이 가리키는 실제 버전을 보여 주는지는 확인 필요다.
- 시작할 때 모든 사례 `text`에 "(가상)"이 있는지 검사하고, 없으면 멈춘다. 실제 회사명을 막는다(CLAUDE.md 규칙). 사례에 전화번호와 이메일도 넣지 않는다.

출력(표준 출력)

- 머리: 실행 시각(KST, ISO 8601), 요청한 모델, 대체 모델 사용 여부, 응답 모델 값 목록, 프롬프트 버전(`extract.PROMPT_VERSION`), 프롬프트 지문(`extract.SYSTEM_PROMPT`의 sha256 앞 12자리), 반복 횟수, 사례 수.
- 사례별: 필드마다 "일치 수/성공한 실행 수", 실행 사이에 나온 값 종류 수(1이면 안정), 평균 응답 시간.
- 필드별 합계: 예) `annualSalary 33/33`.
- 마지막 줄: `비교한 필드 N · 일치 M · 불일치 K · 호출 실패 F`.
- 불일치 상세: 사례 id, 실행 번호, 필드, 기대 값, 실제 값, `status`, `evidence` 앞 40자.
- `--out PATH`면 같은 내용을 JSON으로 쓴다(`meta`, `cases[].runs[]`, `summary`).

종료 코드

- 0: 불일치 0, 호출 실패 0.
- 1: 불일치가 하나라도 있다.
- 2: 설정 오류, 비교한 필드 0개, 또는 호출 실패만 있다.

`--help` 초안

```text
usage: measure_consistency.py [-h] [--cases DIR] [--runs N]
                              [--only ID[,ID]] [--no-samples]
                              [--sleep SEC] [--model NAME]
                              [--allow-fallback] [--out PATH]

가상 공고를 실제 LLM으로 여러 번 추출해 기대값과 같은지 센다.
요청은 한 건씩 차례로 보낸다. pytest에 넣지 않는다.

  --cases DIR       사례 폴더 (기본 scripts/consistency/cases)
  --runs N          사례마다 반복 횟수 (기본 3)
  --only ID[,ID]    이 id의 사례만
  --no-samples      data/samples 공고 4건을 빼기
  --sleep SEC       호출 사이 쉬는 초 (기본 4)
  --model NAME      LLM_MODEL 대신 쓸 모델
  --allow-fallback  .env의 대체 모델을 그대로 쓰기 (기본은 끔)
  --out PATH        결과 JSON을 쓸 경로
```

함수(테스트에서 부를 수 있게 나눈다)

- `load_cases(cases_dir) -> list[dict]`
- `load_sample_cases(samples_dir) -> list[dict]`
- `check_cases(cases) -> None`: 가상 회사 표시, 허용 키, id 중복을 검사한다.
- `extract_values(text, llm) -> dict`: camelCase 경로 → 값. `region.sggCode`를 포함한다.
- `compare(expect, values) -> list[dict]`
- `run(cases, llm, runs, sleep_s) -> dict`
- `print_report(result) -> None`
- `main(argv=None) -> int`
- 머리 docstring에 목적, 실행 예, 언제 돌리는지를 적는다. `ROOT`를 `sys.path`에 넣는 방식과 함께 `scripts/build_hero.py`를 따른다. 인자 처리는 `scripts/build_rent_stats.py`처럼 `argparse`와 `main(argv)`로 한다.

### 사례 7개

- 11/21 세션 기록에서 옮겼다. 회사는 모두 가상이다.
- id는 T01~T30과 헷갈리지 않게 영문으로 쓴다.
- 문구의 `\n`은 줄바꿈이다. JSON 파일에도 `\n`으로 쓴다.
- 기대값은 11/21에 맞은 값이다. `region.sggCode`만 새로 넣었다.

1. `monthly` 월급
   - 문구: `[가나물류(가상)] 물류 관리 신입\n근무지: 경기도 용인시 처인구\n급여: 월 280만원(세전)\n고용형태: 정규직\n기업규모: 중소기업`
   - 기대: `annualSalary` 33600000, `employmentType` regular, `companySize` sme
2. `range_negotiable` 범위·협의
   - 문구: `[다라소프트(가상)] 프론트엔드 개발자\n근무지: 서울 마포구 상암동\n연봉 3,200~3,600만원 (경력에 따라 협의)\n정규직, 수습 3개월`
   - 기대: `annualSalary` null, `employmentType` regular
   - "협의"가 있으면 `salary.normalize_salary`가 값을 비우고 되묻는다. agent-spec T03("연봉 3,000~3,400", 협의 없음 → 하한)과 다른 경우다.
3. `company_rule` 회사 내규
   - 문구: `[마바전자(가상)] 생산관리\n근무지 : 충남 아산시 탕정면\n급여 : 회사내규에 따름\n고용형태 : 정규직\n복리후생 : 기숙사 제공, 통근버스`
   - 기대: `annualSalary` null, `employmentType` regular, `benefits.dormitory` true
4. `contract_convert` 계약직 전환
   - 문구: `[사아바이오(가상)] 연구보조원 채용\n근무지: 대전광역시 유성구 대덕대로\n고용형태: 계약직(1년 후 정규직 전환 검토)\n연봉 2,900만원\n중견기업`
   - 기대: `annualSalary` 29000000, `employmentType` contract, `companySize` mid
5. `short_address` 약칭 주소
   - 문구: `[자차푸드(가상)] 품질관리 신입\n근무지: 전북 완주군 봉동읍\n급여: 연봉 3,100만원 (식대 별도)\n정규직 / 중소기업`
   - 기대: `annualSalary` 31000000, `employmentType` regular, `companySize` sme, `region.sggCode` "52710"
   - `resolve_region("전북 완주군 봉동읍")`이 52710(전북특별자치도 완주군) 하나를 돌려주는 것은 11/22 코드로 확인했다. LLM이 근무지를 이 문구로 읽는지는 첫 실행에서 본다(확인 필요).
6. `free_text` 자유 서술
   - 문구: `저희 카타랩(가상)은 부산 해운대구 센텀에 있는 스타트업입니다. 백엔드 개발자를 정규직으로 모십니다. 연봉은 4천만원이며 스톡옵션을 드립니다.`
   - 기대: `annualSalary` 40000000, `employmentType` regular, `companySize` sme
   - 11/21에 고치기 전에는 0/3이었다. 근거 검증이 한글 단위 표기를 버렸다.
7. `eok_unit` 억 단위
   - 문구: `[하파증권(가상)] IT 운영 경력직\n근무지: 서울 영등포구 여의도동\n연봉 1억 2천만원\n정규직, 대기업 계열사`
   - 기대: `annualSalary` 120000000, `companySize` large

- 비교 수: 실행 1회에 사례 20필드와 샘플 24필드(4건 × 6), 합 44다. `--runs 3`이면 132다.

## 건드리는 파일

- `scripts/measure_consistency.py`(새 파일): `load_cases`, `load_sample_cases`, `check_cases`, `extract_values`, `compare`, `run`, `print_report`, `main`.
- `scripts/consistency/cases/`(새 파일 7개): `monthly.json`, `range_negotiable.json`, `company_rule.json`, `contract_convert.json`, `short_address.json`, `free_text.json`, `eok_unit.json`.
- `scripts/consistency/results/2026-11-22.json`(새 파일): 기준 결과.
- `tests/test_measure_consistency.py`(새 파일): "확인 방법" 2의 테스트.
- `docs/ai-usage-log.md`: 한 줄 추가. W1·W5도 고치는 파일이라 `git pull origin main` 뒤 파일 끝에 붙인다.

## 건드리지 않는 파일

- `tests/cases/` 전부: 이동한의 T12(테스트 30건, `RESULTS.md`)다. 일관성 사례는 `scripts/consistency/cases/`에 따로 둔다.
- `docs/agent-spec.md` 12장: T12의 표와 결과표 양식이다.
- `app/agent/` 전부(`extract.py`, `llm.py`, `evidence.py`, `salary.py`, `classify.py`, `prompts/`): 이동한 담당이다. 스크립트는 import만 한다. 불일치가 나와도 W6에서 고치지 않는다.
- `data/samples/*.json`: 읽기만 한다. `savedExtract`는 LLM 장애 때 쓰는 저장본이다.
- `app/config.py`, `.env`: `.env`는 열지 않고 출력하지 않는다. 값은 `app.config`가 읽는다.
- `CLAUDE.md`, `HANDOFF.md`, `README.md`, `docs/team-1122.md`, `docs/status-2026-11-21.md`, `docs/decisions.md`, `docs/tasks/`의 다른 문서: W1과 다른 작업이 고친다. 사용법은 스크립트 머리말과 `--help`에 둔다. `CLAUDE.md` "명령"에 한 줄 넣을지는 김상해가 정한다.
- `requirements.txt`, `requirements-dev.txt`: 표준 라이브러리와 이미 있는 패키지만 쓴다. 새 오픈소스가 없으니 README Credits도 그대로다.
- `.vercelignore`: `scripts/`와 `tests/`가 이미 빠져 있다.
- W5가 고치는 `app/web/`, `app/main.py`, `app/pipeline.py`, `app/schemas.py`, `tests/test_api.py`, `tests/test_pipeline.py`.

## 끝났다고 보는 기준

- `python3 scripts/measure_consistency.py --help`가 사용법을 보여 준다.
- `python3 -m pytest`가 전부 통과한다. 새 테스트는 네트워크를 부르지 않는다.
- 실제 Gemini로 `--runs 3`을 한 번 돌렸다. 비교한 필드가 132개이고 호출 실패가 0이다.
- 결과 JSON이 `scripts/consistency/results/2026-11-22.json`으로 커밋돼 있다.
- 불일치가 있으면 PR에 사례·필드·값이 적혀 있고 이동한이 알고 있다.

## 확인 방법

1. 명령

```bash
source .venv/bin/activate
python3 scripts/measure_consistency.py --help
python3 -m pytest -k consistency
python3 scripts/measure_consistency.py --only short_address --runs 1 --no-samples
python3 scripts/measure_consistency.py --runs 3 --out scripts/consistency/results/2026-11-22.json
```

2. 테스트(`tests/test_measure_consistency.py`, FakeLLM만)

- 사례 파일 7개가 읽힌다. 모두 "(가상)"이 있고 `expect` 키가 허용 목록 안에 있다.
- 기대값대로 답하는 FakeLLM이면 불일치가 0이고 비교한 필드 수가 0보다 크다.
- 한 필드만 틀리게 답하면 불일치 1로 센다.
- `LLMUnavailable`를 던지면 호출 실패 1로 세고 불일치로 세지 않는다.
- 비교한 필드가 0개면 `main`이 2를 돌려준다.
- FakeLLM의 근거 문장은 사례 원문의 줄을 그대로 넣는다. 근거 대조를 통과해야 값이 남는다.

3. 측정 코드 점검

- 사례 하나의 기대값을 일부러 틀린 사본을 임시 폴더에 만든다.
- `--cases <임시 폴더> --no-samples --runs 1`로 돌린다.
- 불일치 1과 종료 코드 1이 나와야 한다.

4. 기대 숫자

- 비교한 필드 132 = (사례 20 + 샘플 24) × 3.
- 일치 132, 호출 실패 0. 11/21 결과(7종 모두 일치, 샘플 48/48)와 같아야 한다.
- 호출 33번(사례 7건 + 샘플 4건, × 3). 응답 중앙값 3.2초(11/21 실측)와 간격 4초를 더해 약 4~5분 걸린다.
- 대체 모델을 껐으므로 응답 모델 값이 한 종류만 나온다.

## 위험과 되돌리는 법

- 분당 한도(429): 기본 간격은 4초다. 429는 호출 실패로 세고 다음으로 넘어간다. 실패가 나오면 `--sleep`을 늘려 다시 돈다.
- 키: 각자 자기 키로 돈다. 다른 사람의 한도를 쓰지 않는다. 키는 출력하지 않는다.
- 측정 코드 오류: 실패를 불일치로 세거나 아무것도 비교하지 않는 버그는 테스트와 종료 코드 2로 막는다.
- `_post` 감싸기는 `llm.py`의 내부 이름에 기댄다. 이름이 바뀌면 응답 모델 기록만 빠지고 측정은 그대로 돈다.
- `extract_postings`의 인자, 반환, 예외가 바뀌면(`docs/dev-notes.md` 2장 경계) 스크립트도 고친다.
- 기대값이 틀릴 수도 있다. `region.sggCode`는 11/21에 재지 않은 새 값이다. 첫 실행에서 다르면 원인을 적고, 기대값을 고칠지 김상해·이동한과 정한다.
- 마감 뒤에는 결과 파일도 커밋하지 않고 `--out`으로 로컬에만 남긴다(대회 규정 해석, 확인 필요).
- 되돌리기: 새 파일만 더하므로 `git revert <커밋>` PR로 끝난다. force push와 rebase는 쓰지 않는다. 배포 번들에 들어가지 않아 서비스에는 영향이 없다.

## Claude Code 시작 문장

```text
나는 김상해다.
docs/tasks/W6-consistency-script.md를 읽고 그대로 진행해.
먼저 사례 파일 7개와 --help 초안을 보여 주고, 내가 확인하면 구현해.
실제 Gemini 기준 측정은 내 .env 키로 한 번만 돌리고, 요청은 한 건씩 차례로 보내.
.env 파일은 열거나 출력하지 마.
끝나면 python3 -m pytest 전부 통과를 확인하고 PR을 올려.
```
