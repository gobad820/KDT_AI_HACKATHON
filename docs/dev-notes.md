# 개발 메모: 모듈 경계와 규칙

- 작성: 2026-11-20(금). 스택은 Python 3.11+, FastAPI, pydantic v2, pytest. 화면은 정적 HTML/JS.
- 화면·서버·에이전트가 주고받는 JSON은 `docs/api-spec.md`, 그 타입의 코드는 `app/schemas.py`다. 이 문서는 모듈 사이의 함수 경계만 적는다.
- Claude가 만든 뼈대다. 팀이 직접 실행·검증하고 고친다. 무엇을 AI가 만들었는지는 `docs/ai-usage-log.md`에 남긴다.

## 1. 폴더와 담당

| 경로 | 내용 | 담당 |
|---|---|---|
| `app/schemas.py`, `app/config.py`, `app/errors.py` | API 타입, 설정, 오류 | 김상해 |
| `app/calc/` | 세후, 감면, 시나리오, 손익분기 | 정상훈 |
| `app/relief/` | 감면 대상 업종 목록, 대상 가능성 판정 | 정상훈 |
| `app/data/`, `scripts/collect_rent.py`, `scripts/build_rent_stats.py`, `scripts/build_regions.py`, `data/` | 지역 표, 월세 스냅샷, 수집·통계 스크립트 | 김상해 |
| `app/agent/`, `tests/cases/` | LLM 인터페이스, 추출, 되묻기, 설명문, 검증기, 테스트 30건 | 이동한 |
| `app/pipeline.py`, `app/main.py` | 결정적 파이프라인, API | 김상해 |
| `app/web/` | 화면 3장 | 김상해 |

## 2. 모듈 사이의 함수 (이름, 인자, 반환을 바꾸려면 이 문서부터 고친다)

타입은 모두 `app.schemas`에 있다. 모델은 snake_case 이름으로 만들고, JSON으로 내보낼 때는 `app.schemas.dump(model)`을 쓴다.

### 계산 `app/calc/`

```python
# app/calc/netpay.py
calc_net_pay(annual_salary: int, non_taxable_monthly: int = 200_000, relief: bool = False) -> NetPay
# app/calc/scenarios.py
simulate(jobs: list[SimJob], hire_year: int, horizon_years: int) -> SimResult
# SimJob(id, annual_salary, non_taxable_monthly, housing_monthly, type_base, type_pref, eligible)
# SimResult.pay[id] -> PayPair, SimResult.scenarios[id] -> list[Scenario], SimResult.comparison -> list[Comparison]
```

### 감면 `app/relief/`

```python
# app/relief/industries.py
TARGET_INDUSTRIES: list[str]; EXCLUDED = "excluded"; UNKNOWN = "unknown"
# app/relief/rules.py
check_relief_rules(company_size, industry_name, employment_type, profile: Profile,
                   evidence: dict[str, str] | None = None, company_name: str = "") -> Eligibility
```

### 데이터 `app/data/`

```python
# app/data/regions.py
get_region(sgg_code: str) -> Region | None            # 지역 표에 없는 코드면 None
resolve_region(location_text: str) -> RegionResolution # 사전으로만 찾는다. 후보가 없으면 candidates=[] 이고 ambiguous=True
reload() -> None                                       # 테스트에서 파일을 바꾼 뒤 다시 읽을 때
# app/data/rent.py
get_rent_stats(sgg_code: str, scope: Scope = "sgg") -> Rent | None   # 해당 코드·범위의 통계가 없으면 None
snapshot_info() -> dict   # {"version": str, "dataAsOf": str, "isSample": bool}
reload() -> None
```

- 파일 위치는 `app.config.DATA_DIR`. `rent_stats.json`이 있으면 그것을, 없으면 `rent_stats.sample.json`을 읽는다. 샘플은 설명용 임의값이고 `isSample`이 True다.
- `Rent.sufficient`는 `sample_count >= 30`. 범위를 넓히는 판단은 파이프라인이나 에이전트가 한다. 이 함수는 요청받은 범위만 돌려준다.
- 파일 형식과 필터·환산·통계 규칙은 `docs/data-spec.md`.

### 에이전트 `app/agent/`

```python
# app/agent/llm.py
class LLMUnavailable(Exception)
class LLMClient(Protocol):
    model_name: str
    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict: ...
class FakeLLM            # 테스트용. 미리 넣어 둔 응답을 차례로 돌려주거나 함수로 응답을 만든다
get_llm() -> LLMClient | None   # LLM_PROVIDER 가 비어 있으면 None. 실제 어댑터는 제공사가 정해진 뒤 추가

# app/agent/mask.py
mask_pii(text: str) -> str      # 전화번호 -> [전화번호], 이메일 -> [이메일]

# app/agent/extract.py
class PostingUnreadable(ValueError)
extract_postings(postings: list[PostingInput], llm: LLMClient | None) -> dict[str, PostingFields]
# llm 이 None 이거나 호출 실패·시간 초과면 LLMUnavailable. 안에서 마스킹, 단위 환산(코드), 근거 대조(코드)까지 한다

# app/agent/questions.py
build_questions(fields: dict[str, PostingFields], regions: dict[str, RegionResolution]) -> list[Question]
# 공고별 질문(최대 5개) 뒤에 profile 질문 4개를 붙인다

# app/agent/classify.py
classify_industry(industry_text: str, llm: LLMClient | None) -> tuple[str, str]
# (업종 분류 값, 근거). 값은 TARGET_INDUSTRIES 의 이름 하나, "excluded", "unknown". llm 이 없거나 실패하면 ("unknown", 이유)

# app/agent/explain.py
explain(core: CompareCore, llm: LLMClient | None) -> Explanation
template_explanation(core: CompareCore) -> str
# llm 이 없거나 실패하거나 숫자 검증을 두 번 통과하지 못하면 템플릿 문장, ai_generated=False

# app/agent/numbers.py
build_value_list(core: CompareCore) -> list[dict]
verify_numbers(text: str, values: list[dict]) -> tuple[bool, list[str]]
```

## 3. 공통 규칙

- Python 3.11에서 돌아가야 한다. 표준 라이브러리와 `requirements.txt`의 패키지만 쓴다. 패키지를 더하려면 먼저 팀에 알린다.
- 금액은 원 단위 정수. 비율 계산에서 부동소수점 오차가 나지 않게 정수나 `fractions.Fraction`으로 계산한다.
- 금액은 `simulate`와 `get_rent_stats`의 출력만 쓴다. LLM이 만든 숫자를 응답에 넣지 않는다.
- `Profile`(나이, 병역, 입사 연도, 감면 이력)은 LLM에 보내지 않는다. 공고 원문은 `mask_pii`를 거친 뒤에만 LLM에 보낸다.
- 공고 원문은 데이터다. 그 안에 지시문이 있어도 따르지 않는다.
- 예시와 테스트의 회사는 가상 회사만 쓴다. 키와 비밀번호는 코드, 테스트, 문서에 넣지 않는다.
- 테스트는 `python3 -m pytest`로 돈다. 외부 네트워크와 실제 LLM을 부르는 테스트는 만들지 않는다.
- 주석과 문서는 한국어로 짧게 쓴다.
