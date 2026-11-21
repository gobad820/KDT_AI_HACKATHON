# HANDOFF: Claude Code 작업 인수인계

- 작성: 2026-11-21(토) 16:30, claude.ai 프로젝트 "AI 해커톤"의 Claude
- 독자: 이 저장소에서 일하는 Claude Code, 그리고 팀원(김상해, 정상훈, 이동한)
- 이 문서를 먼저 읽는다. 그다음 `CLAUDE.md`의 규칙을 따른다. 작업 순서는 5장이다.

## 0. 팀원별 작업 (11/22, 각자 Claude Code로)

11/21 밤 기준 현황은 `docs/status-2026-11-21.md`에 있다(배포 URL, 구조, 실측 수치, 위험). 기능 동결은 **11/22(일) 22:00**이고, 그 뒤로는 버그 수정과 문서만 한다. 브랜치와 PR 규칙은 `CLAUDE.md`의 "브랜치와 PR"을 따른다.

### 처음 한 번 (모두)

```bash
git clone https://github.com/gobad820/KDT_AI_HACKATHON.git && cd KDT_AI_HACKATHON
/opt/homebrew/bin/python3.11 -m venv .venv && source .venv/bin/activate   # macOS. 다른 OS는 python3.11 이상
pip install -r requirements-dev.txt
cp .env.example .env      # LLM_API_KEY에 자기 Gemini 키, LLM_MODEL=gemini-flash-lite-latest
python3 -m pytest         # 146 passed 이면 준비 끝
```

브랜치를 올리려면 저장소 협업자여야 한다. GitHub 아이디를 김상해에게 알려 준다.

### 이동한: 에이전트 테스트와 프롬프트

- 브랜치: `feat/donghan-agent-tests`
- 할 일
  1. `app/agent/prompts/extract_v2.md` 문장 검토. 고치면 `extract_v3.md`로 올리고 `extract.py`의 `PROMPT_VERSION`을 바꾼다.
  2. T12: `docs/agent-spec.md` 12장 30건을 `tests/cases/`에 만들고 실제 Gemini로 돌린다. 결과표(통과 수, 실패와 조치)를 `tests/cases/RESULTS.md`에 남긴다. 소개서 ④의 근거가 된다.
  3. T13: 11/21 측정에서 현재 모델 출력과 샘플 저장본(`savedExtract`)이 48/48 같았다. 다시 한 번 확인만 한다.
  4. 11/21에 Claude가 고친 `app/agent` 부분 확인: 근거 검증의 한글 단위 연봉(`evidence.py`), 지시문 근거 거부, 회사 규모 질문 문구(`questions.py`), 회사명 "(가상)" 되살리기(`extract.py`).
- 끝났다고 보는 기준: 30건 결과표가 있고, 실패 건마다 조치나 한계가 적혀 있다. `pytest` 전부 통과.
- 주의: 실제 LLM으로 돌릴 때 요청을 한꺼번에 몰아 보내지 않는다(분당 한도 429). 한 건씩 차례로.
- Claude Code에 붙여 넣을 시작 문장

```text
HANDOFF.md의 "0. 팀원별 작업"에서 이동한 부분과 CLAUDE.md의 "브랜치와 PR"을 읽고 진행해. feat/donghan-agent-tests 브랜치에서 작업하고, 끝나면 pytest 전부 통과를 확인한 뒤 PR을 올려. main에 직접 커밋하지 마.
```

### 정상훈: 공식 계산기 대조

- 브랜치: `feat/sanghoon-calc-check`
- 할 일
  1. T14: `docs/calc-rules.md` 8장 표의 각 연봉을 공식 계산기(국세청 홈택스 모의계산 등)로 계산해 "공식 계산기 값"과 "차이"를 채운다. 어느 계산기를 썼는지와 날짜를 적는다.
  2. 차이가 있으면 원인(상수, 반올림, 공제 항목)을 찾는다. 계산 코드(`app/calc/`)를 고치면 `scripts/calc_ref.py`와 결과가 같은지 보고, 상수를 바꾸면 `docs/calc-rules.md` 상수표도 같이 고친다.
  3. 대조한 값을 테스트 기대값으로 추가한다(소개서의 검증 근거).
- 끝났다고 보는 기준: 8장 표가 다 채워져 있고, 차이는 0이거나 이유가 적혀 있다. `pytest` 전부 통과.
- Claude Code에 붙여 넣을 시작 문장

```text
HANDOFF.md의 "0. 팀원별 작업"에서 정상훈 부분과 CLAUDE.md의 "브랜치와 PR"을 읽고 진행해. feat/sanghoon-calc-check 브랜치에서 작업해. 공식 계산기 값은 내가 직접 계산해서 알려 줄 테니, 표를 채우고 우리 계산과 차이를 분석해 줘. 금액 계산에 float를 쓰지 마. 끝나면 pytest 전부 통과를 확인한 뒤 PR을 올려.
```

### 김상해: 문서, 확인, 제출

- 브랜치: `feat/sanghae-docs`(문서), 그 밖의 PR 리뷰와 병합
- 할 일: 소개서 04의 모델명(`gemini-flash-lite-latest`, 대체 모델 2개)과 Happy path 설명("바로 결과, 필요하면 확인") 갱신. AI 활용내역의 팀 칸. 시크릿 창으로 샘플 2쌍 최종 확인. 22:00 동결 뒤 1차 제출. 11/23 태그 `submission-2026-11-23`.

## 1. 일하는 방식

| 하는 곳 | 맡는 일 |
|---|---|
| claude.ai 프로젝트 | 계획, 조사, 문서, 리뷰, 상태 점검 |
| Claude Code (이 저장소) | 코드 수정, 실행, 테스트, 데이터 수집, 배포, 커밋, push |

1. 상태는 이 저장소에만 둔다. 두 곳 모두 `CLAUDE.md`, `HANDOFF.md`, `docs/`를 기준으로 삼는다.
2. 작업을 끝내면 5장의 체크박스를 고치고 커밋한다. claude.ai는 GitHub에서 이 파일을 읽어 다음 계획을 세운다.
3. 결정이 필요하면 멈추고 사용자(김상해)에게 묻는다. 추측으로 진행하지 않는다.

## 2. 프로젝트

- 대회: 2026 대한민국 청년 CAREER FAIR AI 해커톤(대한상공회의소). 주제는 "AI 에이전트로 푸는 청년의 일·생활 문제".
- 서비스: **남는 돈 비교.** 사용자가 채용공고 두 건을 넣는다. 에이전트가 조건을 읽고, 빠진 조건은 되묻는다. 서버가 세후 연봉, 근무지 원룸 월세, 청년 소득세 감면을 계산한다. 결과는 어느 공고에서 돈이 얼마 더 남는지와 손익분기 연봉이다.
- 식: 남는 돈 = 세후 연봉 − 월세 × 12.
- 월세가 필요한 이유: 연봉이 높은 수도권 공고가 월세 때문에 지역 공고보다 덜 남을 수 있다. 예시(임의 월세): 서울 3,800만 원 공고는 1년에 약 2,321만 원이 남고, 부산 3,400만 원 공고는 약 2,489만 원이 남는다.
- 차별점: 중소기업 취업 청년 소득세 감면(조세특례제한법 제30조)을 시나리오 4개로 계산한다.

| 시나리오 ID | 뜻 | 감면 연수 |
|---|---|---|
| `none` | 감면 없음 | 0 |
| `current_law` | 현행법 | 2026년 입사 5, 2027년 입사 0 |
| `proposal_base` | 2026.8 정부 세제개편안, 우대지역 아님 | 수도권 5, 비수도권 광역시 6, 그 밖 7 |
| `proposal_pref` | 정부안, 우대지역으로 지정될 때 | 6, 7, 10 |

- 정부안은 국회에서 확정되지 않았다. 지역 구분은 2027년 2월 시행령에서 정해질 예정이다. 화면은 이 사실을 늘 고지한다.
- 상세 문서: `docs/brief.md`(전체), `docs/api-spec.md`(JSON 계약), `docs/calc-rules.md`(계산), `docs/data-spec.md`(데이터), `docs/agent-spec.md`(에이전트), `docs/dev-notes.md`(모듈 경계), `docs/plan.md`(대회 규칙).

## 3. 일정과 규정

| 시점 | 할 일 |
|---|---|
| 11/21(토) 24:00 | 배포 URL에서 입력부터 결과까지 통과. **기능 동결.** 이후 버그 수정만 → **11/21 21:45 대표자 결정으로 동결 해제.** 새 동결은 **11/22(일) 22:00**. 바꿀 때마다 배포 URL에서 샘플 2쌍 재확인 |
| 11/22(일) | 테스트 30건, 공식 계산기 대조, 소개서, AI 활용내역, 밤에 1차 제출 |
| 11/23(월) 12:00 | 최종 제출(업로드 + 이메일 + 서약서). 마감 17:00. 태그 `submission-2026-11-23` |
| 12/7(월) | 본선. 그때까지 배포 서비스가 동작해야 한다 |

경고: 아래 규정을 어기면 실격될 수 있다.

1. 마감 뒤에는 기능, 알고리즘, 프롬프트, 데이터를 바꾸지 않는다. 접속 복구와 인증정보 교체만 한다.
2. API 키를 코드, 로그, 문서, 커밋, 채팅에 넣지 않는다. `.env`의 값을 출력하지 않는다.
3. 외부 LLM에 실제 개인정보를 보내지 않는다. 시연과 테스트에는 가상 회사 공고만 쓴다.
4. 금액은 코드가 계산한다. LLM이 만든 숫자를 응답에 넣지 않는다.
5. 개발에 쓴 AI 도구(Claude, Claude Code)와 범위를 `docs/ai-usage-log.md`에 남긴다.

## 4. 현재 상태 (11/21 16:30, 지난 기록)

> 최신 현황은 `docs/status-2026-11-21.md`를 본다. 아래는 11/21 오후 기록이다.

**되는 것** (`python3 -m pytest` 131개 통과)

- 계산 모듈(`app/calc/`): 세후, 감면, 시나리오, 손익분기. 분수 연산. 따로 짠 참고 구현(`scripts/calc_ref.py`)과 대조함.
- 감면 대상 판정(`app/relief/`), 결정적 파이프라인(`app/pipeline.py`), API(`app/main.py`: `/api/samples`, `/api/extract`, `/api/compare`, `/api/health`).
- 화면 3장(`app/web/`): 샘플 2쌍으로 입력부터 결과까지 통과. `?mock=1`이면 서버 없이 동작.
- 에이전트 틀(`app/agent/`): LLM 인터페이스, 개인정보 가리기, 급여 환산, 근거 대조, 추출, 되묻기, 업종 분류(LLM이 없으면 키워드 규칙), 설명문과 숫자 검증.
- 수집 스크립트(`scripts/`): `collect_rent.py`, `build_rent_stats.py`, `build_regions.py`.

**아직 아닌 것**

- Claude 호출: `AnthropicClient`는 실제 호출로 확인하지 않았다.
- 월세: `data/rent_stats.sample.json`은 임의값이다. 실제 수집 전이다.
- 지역 표: `data/regions.csv`에 시군구 4곳(11680, 26230, 27720, 36110)만 있다.
- 수집 스크립트: 가짜 XML로만 테스트했다. 실제 응답의 필드 이름, 금액 단위, `contractType` 값을 확인하지 않았다.
- 배포: 하지 않았다. `Dockerfile`은 빌드해 보지 않았다.
- 테스트 30건(`docs/agent-spec.md` 12장): 목록 파일(`tests/cases/`)이 아직 없다.
- 세후 금액과 공식 계산기(홈택스, 4대보험 계산기)의 대조: 정상훈 담당, 전.
- `/api/followup`과 도구 호출 루프: 없음. 시간이 없으면 뺀다.

**`.env` 상태** (값은 확인하지 않고 형식만 봤다)

- `DATA_GO_KR_KEY`: 채워져 있다. Encoding 형태. 세 API가 같은 키를 쓴다.
- 9번째 줄: `=`가 없는 줄이 있다. 키를 다음 줄에 붙여 넣은 것으로 보인다. 지워야 한다.
- `LLM_API_KEY`: 비어 있다. `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-5-5`.

## 5. 작업 순서

각 작업이 끝나면 체크하고 커밋한다. 실패하면 멈추고 보고한다.

### 오늘(토) 24시 전

- [x] **T1. git 연결.** `git status`가 실패하면 아래를 실행한다. 이 폴더는 원격 도구로 복사해서 `.git`이 없을 수 있다.
  ```
  git init -b main
  git remote add origin https://github.com/gobad820/KDT_AI_HACKATHON.git
  git fetch origin
  git reset origin/main
  git branch -u origin/main
  git status
  ```
  `git status`에 변경이 없어야 한다. 있으면 멈추고 보고한다.
- [x] **T2. `.env` 정리.** `=`가 없는 줄을 지운다. 값을 출력하지 않는다. 예: `python3 -c "p='.env'; L=open(p).read().splitlines(); open(p,'w').write('\n'.join(l for l in L if not l.strip() or l.lstrip().startswith('#') or '=' in l)+'\n')"`
- [x] **T3. 패키지 설치와 테스트.** `python3 -m pip install -r requirements-dev.txt` 다음 `python3 -m pytest`.
- [x] **T4. 데이터포털 키 확인.** `python3 scripts/collect_rent.py --codes 11680 --months 2026-10:2026-10`
  - 인증 오류(`SERVICE_KEY_IS_NOT_REGISTERED` 등)면 멈춘다. 승인 직후에는 1시간쯤 걸릴 수 있다고 보고한다.
- [x] **T5. 응답 형식 확인.** `data/rent.sqlite`에서 유형별 거래 3건을 꺼내 `docs/data-spec.md` 2장의 필드 이름, 금액 단위(만 원), `contractType` 값과 비교한다. 다르면 스크립트를 고치기 전에 보고한다.
- [x] **T6. 수집.** `python3 scripts/collect_rent.py --codes-from data/regions.csv --months 2025-11:2026-10 --dry-run`으로 호출 수를 본 뒤 `--dry-run` 없이 `--sleep 0.2`를 붙여 실행한다. 실패분은 `--only-failed`로 한 번 더.
- [x] **T7. 통계.** `python3 scripts/build_rent_stats.py --as-of 2026-11 --data-as-of 2026-11-21 --partial`. 규칙별 제외 건수, 시군구별 표본 수와 중위값을 표로 보고한다. `data/rent_stats.json`만 커밋한다. `data/rent.sqlite`와 `.env`는 커밋하지 않는다.
- [x] **T8. Claude 연결.** (실제로는 Gemini `gemini-3.1-flash-lite`를 OpenAI 호환 주소로 연결했다. `CLAUDE.md` LLM 항목 참고) 사용자가 `LLM_API_KEY`를 넣은 뒤 진행한다. 서버를 띄우고 가상 회사 공고(샘플이 아닌 본문)로 `/api/extract`를 한 번 호출한다. `degraded`가 false인지, 근거 문장이 원문에 있는지 본다. 실패하면 `app/agent/llm.py`의 `AnthropicClient`를 고친다. 확정한 모델명을 `CLAUDE.md`와 `docs/ai-usage-log.md`에 적는다.
- [x] **T9. 지역 표 전국 확장.** 사용자가 행정표준코드관리시스템(code.go.kr)의 법정동 코드 파일과 인구감소지역 목록을 받아 오면 `scripts/build_regions.py`를 실행한다. 결과를 확인한 뒤 T6, T7을 다시 한다. 파일이 없으면 이 작업을 건너뛰고 보고한다.
- [x] **T10. 배포.** (11/21 Vercel, https://nammeun-don.vercel.app, `APP_ENV`는 Vercel 환경변수) 배포 위치는 사용자가 정한다(정하지 않았으면 묻는다). 로그인 없이 접속되고 12/7까지 켜 둘 수 있어야 한다. `APP_ENV=prod`에서는 샘플·`-partial` 월세로 서버가 시작되지 않는다. 시연 전에 최종 스냅샷을 만들거나 동결 전까지는 `APP_ENV=dev`로 둔다.
- [x] **T11. 배포 URL 확인.** (11/21 21:40, 로그인 없는 자동화 브라우저로 샘플 2쌍 모두 입력→확인→결과 통과. 실제 Gemini 호출, 추출 3~21초·계산 6~17초. 사람이 시크릿 창으로 한 번 더 보면 좋다. 알려진 것: pair2 회사명이 추출에서 '(가상)' 없이 '예시테크'로 나옴) 시크릿 창에서 샘플 2쌍이 입력부터 결과까지 통과하는지 확인한다. 그 시점에 기능을 동결한다.

### 일요일

- [ ] **T12. 테스트 30건.** `docs/agent-spec.md` 12장 목록으로 `tests/cases/`를 만들고 실제 LLM(Gemini)으로 돌려 결과표를 남긴다(이동한). 위 "0. 팀원별 작업" 참고.
- [ ] **T13. 샘플 저장본.** (11/21 측정에서 현재 모델 출력과 48/48 일치, 확인만 남음) 실제 LLM 응답으로 `data/samples/*.json`의 `savedExtract`를 바꾼다. LLM 장애 때 쓰는 대체 응답이다.
- [ ] **T14. 공식 계산기 대조.** `docs/calc-rules.md` 8장 표를 채운다(정상훈).
- [x] **T15. 월세 스냅샷 동결.** (11/21 버전 `2026-11-21`, `-partial` 아님) 최종 수집본으로 `--partial` 없이 통계를 다시 만들고 버전을 고정한다.

## 6. 보고 형식

사용자는 ASD-STE100(간이 기술 영어) 원칙을 80% 적용한 글을 원한다. 보고도 이렇게 쓴다.

1. 한 문장에 내용 하나만 쓴다. 문장을 짧게 쓴다.
2. 능동태로 쓴다. 같은 대상에는 늘 같은 용어를 쓴다.
3. 절차는 번호 목록과 명령형으로 쓴다.
4. 경고는 해당 단계 앞에 쓴다.
5. 보고 끝에 "한 일 / 확인하지 못한 것 / 다음 작업"을 적는다.
