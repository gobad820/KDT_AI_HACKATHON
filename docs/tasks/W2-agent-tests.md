# W2 테스트 30건과 추출 프롬프트

- 담당: 이동한 / 브랜치: `feat/donghan-agent-tests` / 상태: 시작 전 / 마감: 프롬프트·코드를 고치면 19:00 PR(제안), 30건 결과표는 23:00 PR(제안) / 먼저 끝나야 하는 것: 없음(W1이 합쳐졌으면 pull하고 시작)

## 왜

- 테스트 30건 결과표는 AI 활용내역 ④ "검증 및 한계 대응"의 근거가 된다([docs/agent-spec.md 13장](../agent-spec.md#13-ai-활용내역에-쓸-기록)).
- 30건 목록은 [docs/agent-spec.md 12장](../agent-spec.md#12-테스트-30건)에만 있다. `tests/cases/`는 아직 없다(HANDOFF T12).
- 11/21 밤에 Claude Code가 이동한 담당 영역(`app/agent`)을 고쳤다. 담당자가 확인해야 한다.

## 할 일

1. 11/21 밤에 바뀐 `app/agent`를 훑어본다. 이상하면 PR 본문에 적는다.
   - `evidence.py`: "4천만 원" 같은 한글 단위 연봉을 근거로 인정한다. 지시문처럼 생긴 근거는 거부한다.
   - `questions.py`: 회사 규모 질문 문구를 고쳤다.
   - `extract.py`: 회사명의 "(가상)"을 되살린다.
   - `llm.py`, `classify.py`: 시도당 8초, 실패하면 바로 대체 모델로 넘긴다. 업종 분류는 동시에 부르고 캐시한다.
2. [`app/agent/prompts/extract_v2.md`](../../app/agent/prompts/extract_v2.md)를 읽고 고칠 곳이 있는지 본다. 없으면 v2로 간다.
3. 고칠 곳이 있으면 `extract_v3.md`를 새로 만들고 `app/agent/extract.py`의 `PROMPT_VERSION`을 바꾼다. v2 파일은 지우지 않는다.
4. 프롬프트를 바꿨으면 샘플 2쌍의 새 출력과 `data/samples/*.json`의 `savedExtract`(LLM 장애 때 쓰는 저장본)를 비교한다. 다르면 `savedExtract`를 새 출력으로 바꾼다(HANDOFF T13).
5. 12장의 30건을 `tests/cases/`에 만든다. 공고 문구는 가상 회사로 쓰고, 샘플처럼 회사명에 "(가상)"을 붙인다.
6. 30건을 돌리는 실행 파일은 `tests/cases/` 안에 두고, 이름을 `test_`로 시작하지 않는다. pytest가 실제 Gemini를 부르지 않게 하려는 것이다.
7. 최종 프롬프트 버전으로 30건을 실제 Gemini에 한 번 돌린다. 한 건씩 차례로 보낸다. 한꺼번에 보내면 분당 한도(429)에 걸린다.
8. 결과를 `tests/cases/RESULTS.md`에 12장 양식대로 적는다. 칸은 ID, 입력 요약, 기대, 결과, 조치, 실행일, 모델·프롬프트 버전이다.
   - 어댑터(`app/agent/llm.py`)는 어느 모델이 답했는지 밖으로 돌려주지 않는다. 모델 칸에는 주 모델 `gemini-flash-lite-latest`와 대체 모델 2개를 함께 적는다.
9. 실패 건마다 원인과 조치를 적는다. 고치지 못한 것은 남은 한계로 적는다.
10. 결과표 맨 위에 12장 "통과 기준(제안)"과 비교한 요약을 적는다. 숫자 불일치 수, 금액 추정 수, 안전·장애 통과 여부, 필드 정확도다.
11. [docs/decisions.md](../decisions.md)에서 이동한 의견이 필요한 항목에 의견을 김상해에게 준다. U-2 3번(업종 분류를 추출 단계로), U-6(모델 별칭), U-7(LLM 역할 서술), U-11(감면 이력 기본값)이다. 기한은 각 항목에 있다.
12. `HANDOFF.md` 5장의 T12 체크박스를 고친다. 4번을 했으면 T13도 고친다.
13. PR 본문에 "Claude Code가 한 일"과 "내가 직접 확인한 일"을 한 줄씩 적는다.

## 건드리는 파일

- `tests/cases/`: 30건, 실행 파일, `RESULTS.md`
- `app/agent/prompts/extract_v3.md`: 프롬프트를 고칠 때만
- `app/agent/extract.py`의 `PROMPT_VERSION`: 프롬프트를 고칠 때만
- `data/samples/pair1.json`, `pair2.json`의 `savedExtract`: 프롬프트를 고칠 때만
- `app/agent/`의 다른 파일과 `tests/test_agent.py`: 1번에서 버그를 찾아 고칠 때만
- `HANDOFF.md` 5장의 T12·T13 체크박스
- 이 파일의 상태 줄

## 건드리지 않는 파일

- `scripts/measure_consistency.py`, `scripts/consistency/`: W6이 쓴다. `tests/cases/`는 W2만 쓴다.
- `app/agent/classify.py`: W5(제안)가 업종 분류를 추출 단계로 옮길 수 있다. 고칠 곳은 PR 본문에 적는다.
- `app/main.py`, `app/schemas.py`, `app/web/`: W1과 W5가 고친다.
- `docs/ai-usage-log.md`: W4가 고친다. 기록할 내용은 PR 본문에 적는다.
- `docs/agent-spec.md`: W1이 제목을 고친다. 12장을 고쳐야 하면 W1이 합쳐진 뒤 pull하고 고친다.

## 끝났다고 보는 기준

- `tests/cases/RESULTS.md`에 T01~T30 30행이 있다.
- 행마다 결과, 실행일, 모델·프롬프트 버전이 있다.
- 실패 건마다 원인과 조치, 또는 남은 한계가 있다.
- 결과표의 프롬프트 버전이 `extract.py`의 `PROMPT_VERSION`과 같다.
- 프롬프트를 바꿨다면 `savedExtract`가 새 출력과 같다.
- LLM 키 없이도 `python3 -m pytest`가 전부 통과한다.

## 확인 방법

```bash
python3 -m pytest
LLM_PROVIDER= python3 -m pytest                       # LLM 없이도 통과하는지
grep -c "^| T[0-3][0-9] " tests/cases/RESULTS.md      # 30
grep -n "PROMPT_VERSION" app/agent/extract.py
```

- 프롬프트를 바꿨으면 `uvicorn app.main:app --reload`로 서버를 띄운다.
- http://localhost:8000 에서 샘플 2쌍을 입력부터 결과까지 눌러 본다.

## 위험과 되돌리는 법

- 프롬프트를 바꾸면 샘플 추출 결과와 배포 화면이 바뀐다. 김상해가 합친 뒤 배포 URL에서 샘플 2쌍을 다시 확인한다.
- 19:00(제안) 뒤에 찾은 프롬프트 문제는 고치기 전에 김상해에게 묻는다. 고치지 못하면 결과표에 한계로 적는다.
- 마감(11/23 17:00) 뒤에는 프롬프트를 바꿀 수 없다.
- 실제 Gemini를 반복해서 부르면 자기 키의 한도를 쓴다. 같은 건을 여러 번 돌리지 않는다.
- 프롬프트를 되돌릴 때는 `PROMPT_VERSION`을 `extract_v2`로 바꾼다. v2 파일을 지우지 않는 이유다.
- 합친 뒤 문제가 생기면 병합 커밋을 `git revert`로 되돌린다. force push는 하지 않는다.

## Claude Code 시작 문장

```text
나는 이동한이다.
docs/tasks/W2-agent-tests.md를 읽고 그대로 진행해.
먼저 할 일 순서와 건드릴 파일을 보여 주고, 내가 확인하면 시작해.
브랜치는 feat/donghan-agent-tests로 만들어.
실제 Gemini 호출은 한 건씩 차례로 보내.
끝나면 pytest 전부 통과를 확인하고 PR을 올려.
```
