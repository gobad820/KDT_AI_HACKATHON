# 첫 직장, 10년 뒤 경제력: API 명세

- 작성: 2026-11-20(금)
- 주 독자: 김상해(서버·화면), 이동한(에이전트)
- Claude가 조사해 정리한 초안이다. 결정과 검증은 팀이 직접 하고, 기획에 Claude를 쓴 사실은 AI 활용내역에 적는다.

화면, 서버, 에이전트가 주고받는 JSON을 고정한다. 계산 규칙은 `docs/calc-rules.md`, 월세·지역 데이터는 `docs/data-spec.md`, 에이전트 동작은 `docs/agent-spec.md`에 있다. 예시의 금액은 `scripts/calc_ref.py` 초안 로직의 출력이고 공식 계산기와 대조하기 전이다. 예시의 월세 통계는 설명용 임의값이고 실데이터가 아니다.

## 1. 원칙

- 금액은 원 단위 정수다(문자열, 소수, 만 원 단위 금지). 비율은 소수(`0.06`), 연수는 정수. 키는 camelCase, 시각은 ISO 8601, 날짜는 `YYYY-MM-DD`.
- 시나리오 ID는 `none`, `current_law`, `proposal_base`, `proposal_pref` 네 개로 고정한다. 응답에는 항상 네 개가 모두 들어간다.
- 응답의 금액은 도구 `simulate`와 `get_rent_stats`의 출력만 쓴다. LLM이 만든 숫자는 넣지 않는다. `explanation.text`에 나온 숫자는 서버가 요청·응답 JSON의 값과 대조하고 결과를 `numbersVerified`에 넣는다.
- 월세는 수집 스냅샷에서만 읽는다. 요청을 처리하면서 외부 API를 부르지 않는다. `dataVersion.rent`에 수집 기준일을 넣는다.
- `profile`은 서버 코드에서만 쓰고 LLM에 보내지 않는다.
- 서버는 요청 사이에 상태를 저장하지 않는다. 화면이 확인된 값을 다음 요청에 모두 실어 보낸다(제안).
- 경계를 바꿀 때는 이 문서를 먼저 고친다(10장).

## 2. 엔드포인트

| 메서드 | 경로 | 용도 | 화면 | LLM 호출 | 시간 제한(제안) |
|---|---|---|---|---|---|
| GET | `/api/samples` | 샘플 공고 쌍(가상 회사) | 1 입력 | 없음 | |
| POST | `/api/extract` | 공고 두 건에서 조건 추출, 되물을 질문 생성 | 1 입력 → 2 확인 | 있음 | 20초 |
| POST | `/api/compare` | 확인된 조건으로 계산·비교·설명 | 2 확인 → 3 결과 | 있음(업종 분류, `explanation: "ai"`면 설명문) | 40초 |
| POST | `/api/explain` | 같은 요청으로 AI 설명문과 고지만 받기(화면이 결과를 먼저 띄운 뒤 부름) | 3 결과 | 있음 | 40초 |
| POST | `/api/followup` | 후속 질문 재계산 (선택, 가장 먼저 뺌) | 3 결과 | 있음 | 40초 |
| GET | `/api/health` | 상태 확인 | | 없음 | |

## 3. 공통 타입

| 타입 | 필드 | 비고 |
|---|---|---|
| Field | `value`, `status`, `evidence`, `note` | `status`는 `extracted`(원문에 있음), `inferred`(단서로 추정, 화면에서 확인 필수), `missing`(원문에 없음), `user`(사용자가 입력·수정). `evidence`는 원문을 그대로 인용하고 없으면 null |
| 추출 필드 | `companyName`, `annualSalary`, `workLocationText`, `employmentType`, `companySize`, `industryText`, `benefits` | 각각 Field. `annualSalary`는 원. `companySize`는 `sme`, `mid`, `large`, `public`, `unknown`. `employmentType`은 `regular`, `contract`, `intern`, `daily`, `unknown`. `benefits`는 Field인 `mealAllowanceMonthly`, `dormitory`, `housingSupportMonthly`와 계산에 넣지 않는 복지 목록 `others[]` |
| 추출 확인 정보 | `salaryConflictEvidence`, `multipleLocations` | `salaryConflictEvidence`에는 급여가 다른 본문과 표의 인용문을 담는다. 이때 `annualSalary.value`는 null이고 연봉을 직접 입력한다. `multipleLocations`는 여러 근무지가 명시되었음을 나타낸다. 원문에서 확인된 근무지 인용문에 `또는`이나 `혹은`으로 이어진 선택지가 있으면 모델이 여러 근무지를 표시하지 않아도 true로 설정한다. |
| Question | `id`, `postingId`, `field`, `text`, `inputType`, `options`, `required` | `inputType`은 `number`, `select`, `text`, `boolean`. `options`는 `[{ value, label }]` 또는 null. `postingId`가 null이면 profile 질문 |
| Profile | `age`, `militaryServiceMonths`, `hireYear`, `priorRelief` | `age`는 만 나이, `hireYear`는 2026 또는 2027, `priorRelief`는 `no`, `yes`, `unknown` |
| Region | `sggCode`, `name`, `regionClass`, `typeBase`, `typePref`, `prefCandidate`, `classUncertain` | `regionClass`는 `capital`, `metro`, `other`. `typeBase`는 우대지역이 아닐 때, `typePref`는 우대지역으로 지정될 때의 유형. 분류 규칙과 미확정 지역 처리는 `docs/data-spec.md` |
| Rent | `monthlyMedian`, `p25`, `p75`, `sampleCount`, `period`, `housingTypes`, `scope`, `depositBasis`, `conversionRate`, `dataAsOf`, `sufficient` | 환산월세(보증금 1,000만 원 기준) 통계. `scope`는 `sgg`(6개월), `sgg_12m`, `sido`. `sufficient`는 `sampleCount`가 30 이상일 때 true. `housingTypes` 값은 `officetel`, `detached_multi`, `row_multi`. `conversionRate` 0.06은 `[가정]` |
| Eligibility | `status`, `checks[]`, `hrQuestion` | `status`는 `likely`, `uncertain`, `unlikely`. `checks[]`는 `{ rule, result, evidence }`. `rule`은 `age`, `company_size`, `industry`, `employment_type`, `prior_relief` 다섯 개를 항상 모두 돌려주고 `result`는 `pass`, `fail`, `unknown`. `hrQuestion`은 인사팀에 보낼 확인 질문 |
| Pay | `insurance`, `finalTax`, `localTax`, `netAnnual`, `netMonthlyAvg` | 연액. `pay.none`(감면 없음)과 `pay.withRelief`(감면 적용) 두 벌 |
| Scenario | `id`, `reliefYears`, `firstYearRemaining`, `cumulativeRemaining`, `reliefTotal`, `yearly[]` | `yearly[]`는 `{ year, reliefApplied, netAnnual, housingAnnual, remaining, cumulative }`를 1년차부터 `horizonYears`년차까지 담는다 |
| Comparison | `scenarioId`, `betterJobId`, `difference`, `breakEven` | `difference`는 누적 남는 돈의 차이(0 이상). `breakEven`은 `{ jobId, annualSalary }`로, 덜 남는 쪽 공고가 받아야 같아지는 연봉(만 원 단위 올림). 찾지 못하면 null |
| Trace | `step`, `type`, `name`, `summary` | `type`은 `extract`, `question`, `tool_call`, `decision`, `explain`. `extract`와 `compare` 응답에 각각 들어가고 화면이 이어 붙여 진행 기록으로 보여준다 |

- `extract` 응답 최상위에도 `degraded`가 있다. LLM 대신 샘플 저장본으로 응답했으면 true다.
- `jobs[].housingMonthly`는 계산에 쓴 월 주거비(원)다. `jobs[].rent`는 `housing.mode`가 `dormitory`나 `custom`이면 null이다.
- `notices[]`의 첫 문장은 설명문이 서버 템플릿이면(`aiGenerated` false) "금액은 서버의 계산 코드가 산출했습니다. 설명 문장은 정해진 틀로 작성했습니다."로 바뀐다.

`dataVersion.rent`는 월세 수집 기준일, `dataVersion.rules`는 계산 상수·규칙의 버전이다. `sources[]`는 `{ name, url, asOf }`. `employmentType`, `housingTypes`, `checks[].rule`, `error.code`의 값 목록은 이 문서에서 처음 정한 초안이다. 다른 문서와 다르면 이 문서를 기준으로 맞춘다.

## 4. POST /api/extract

요청. 공고는 정확히 2건이고 `id`는 `A`와 `B`다. 본문 길이 상한은 건당 8,000자를 제안한다.

```json
{
  "postings": [
    {"id": "A", "text": "[예시소프트(가상)] 백엔드 개발자 신입 채용\n사업내용: 기업용 소프트웨어 개발\n기업형태: 중소기업(벤처기업 인증)\n근무지: 서울 강남구 테헤란로\n고용형태: 정규직\n급여: 연봉 3,800만원 (식대 월 20만원 포함)\n복리후생: 자기계발비 지원, 건강검진"},
    {"id": "B", "text": "[보기정밀(가상)] 생산기술 엔지니어 신입 채용\n사업내용: 자동차 부품 제조\n근무지: 부산 부산진구 전포동\n고용형태: 정규직\n급여: 연봉 3,400만원\n복리후생: 통근버스, 경조사 지원"}
  ]
}
```

응답. `evidence`는 모두 요청 본문에 그대로 있는 문장이다. 보기정밀(가상) 공고에는 회사 규모가 없어 질문 `q1`이 생겼다.

```json
{
  "requestId": "req_20261122_0001", "degraded": false,
  "postings": [
    {
      "id": "A",
      "fields": {
        "companyName": {"value": "예시소프트(가상)", "status": "extracted", "evidence": "[예시소프트(가상)] 백엔드 개발자 신입 채용", "note": null},
        "annualSalary": {"value": 38000000, "status": "extracted", "evidence": "급여: 연봉 3,800만원 (식대 월 20만원 포함)", "note": null},
        "workLocationText": {"value": "서울 강남구 테헤란로", "status": "extracted", "evidence": "근무지: 서울 강남구 테헤란로", "note": null},
        "employmentType": {"value": "regular", "status": "extracted", "evidence": "고용형태: 정규직", "note": null},
        "companySize": {"value": "sme", "status": "extracted", "evidence": "기업형태: 중소기업(벤처기업 인증)", "note": null},
        "industryText": {"value": "기업용 소프트웨어 개발", "status": "extracted", "evidence": "사업내용: 기업용 소프트웨어 개발", "note": null},
        "benefits": {
          "mealAllowanceMonthly": {"value": 200000, "status": "extracted", "evidence": "식대 월 20만원 포함", "note": null},
          "dormitory": {"value": null, "status": "missing", "evidence": null, "note": "공고에 언급 없음"},
          "housingSupportMonthly": {"value": null, "status": "missing", "evidence": null, "note": "공고에 언급 없음"},
          "others": ["자기계발비 지원", "건강검진"]
        }
      },
      "region": {"candidates": [{"sggCode": "11680", "name": "서울특별시 강남구", "regionClass": "capital", "typeBase": 1, "typePref": 2, "prefCandidate": false, "classUncertain": false}], "ambiguous": false}
    },
    {
      "id": "B",
      "fields": {
        "companyName": {"value": "보기정밀(가상)", "status": "extracted", "evidence": "[보기정밀(가상)] 생산기술 엔지니어 신입 채용", "note": null},
        "annualSalary": {"value": 34000000, "status": "extracted", "evidence": "급여: 연봉 3,400만원", "note": null},
        "workLocationText": {"value": "부산 부산진구 전포동", "status": "extracted", "evidence": "근무지: 부산 부산진구 전포동", "note": null},
        "employmentType": {"value": "regular", "status": "extracted", "evidence": "고용형태: 정규직", "note": null},
        "companySize": {"value": "unknown", "status": "missing", "evidence": null, "note": "공고에 회사 규모가 적혀 있지 않음"},
        "industryText": {"value": "자동차 부품 제조", "status": "extracted", "evidence": "사업내용: 자동차 부품 제조", "note": null},
        "benefits": {
          "mealAllowanceMonthly": {"value": null, "status": "missing", "evidence": null, "note": "공고에 언급 없음"},
          "dormitory": {"value": null, "status": "missing", "evidence": null, "note": "공고에 언급 없음"},
          "housingSupportMonthly": {"value": null, "status": "missing", "evidence": null, "note": "공고에 언급 없음"},
          "others": ["통근버스", "경조사 지원"]
        }
      },
      "region": {"candidates": [{"sggCode": "26230", "name": "부산광역시 부산진구", "regionClass": "metro", "typeBase": 2, "typePref": 3, "prefCandidate": false, "classUncertain": false}], "ambiguous": false}
    }
  ],
  "questions": [
    {"id": "q1", "postingId": "B", "field": "companySize", "text": "보기정밀(가상) 공고에는 회사 규모가 적혀 있지 않습니다. 어디에 해당하나요?", "inputType": "select", "options": [{"value": "sme", "label": "중소기업"}, {"value": "mid", "label": "중견기업"}, {"value": "large", "label": "대기업"}, {"value": "public", "label": "공공기관"}, {"value": "unknown", "label": "모름"}], "required": true},
    {"id": "q2", "postingId": null, "field": "profile.age", "text": "근로계약을 맺는 시점의 만 나이를 알려주세요.", "inputType": "number", "options": null, "required": true},
    {"id": "q3", "postingId": null, "field": "profile.militaryServiceMonths", "text": "병역을 마쳤다면 복무 기간을 개월 수로 적어 주세요. 해당이 없으면 0입니다.", "inputType": "number", "options": null, "required": false},
    {"id": "q4", "postingId": null, "field": "profile.hireYear", "text": "입사 예정 시기를 골라 주세요.", "inputType": "select", "options": [{"value": 2026, "label": "2026년 안"}, {"value": 2027, "label": "2027년 이후"}], "required": true},
    {"id": "q5", "postingId": null, "field": "profile.priorRelief", "text": "중소기업 취업자 소득세 감면을 받은 적이 있나요?", "inputType": "select", "options": [{"value": "no", "label": "없음"}, {"value": "yes", "label": "있음"}, {"value": "unknown", "label": "모름"}], "required": false}
  ],
  "trace": [
    {"step": 1, "type": "extract", "name": "extract_postings", "summary": "공고 2건에서 필드 7종을 읽음. B의 회사 규모는 원문에 없음"},
    {"step": 2, "type": "tool_call", "name": "resolve_region", "summary": "'서울 강남구 테헤란로'는 11680, '부산 부산진구 전포동'은 26230 하나씩만 대응"},
    {"step": 3, "type": "question", "name": "ask_user", "summary": "감면 판정에 필요한 B의 회사 규모 1건을 되묻기로 함"}
  ]
}
```

- `annualSalary.value`는 원 단위로 맞춘 값이다. "3,800만원" 같은 표기를 원 단위 연봉으로 바꾸는 계산은 서버 코드가 한다. 서버는 `evidence`가 원문에 그대로 있는지도 대조한다(`docs/agent-spec.md`).
- `region.ambiguous`가 true이면 후보를 자동으로 채우지 않는다. 여러 근무지에서 시군구 후보를 하나만 확인하면 참고용으로 표시하고 `workLocationText` 질문으로 실제 시군구 코드 입력을 요구한다. 후보가 여럿이면 `sggCode` 질문으로 선택을 요구하며, 후보에 없는 근무지는 코드를 직접 입력할 수 있다.
- `questions`에는 공고별 질문과 profile 질문이 함께 들어간다. 공고별 질문은 에이전트가 만들고(`ask_user`), profile 질문 4개는 서버가 고정 문구로 붙인다.
- 화면 2는 `fields`를 표로 보여주고, 사용자가 확인하거나 고친 값만 `compare`의 `confirmed`에 담는다. `inferred`와 `missing`은 사용자가 확인해야 다음으로 넘어간다.

## 5. POST /api/compare

요청. `confirmed`는 화면 2에서 사용자가 확인한 값이고 `sggCode`는 `region.candidates`에서 고른 것이다. `housing.mode`는 `market_rent`(월세 통계 사용), `dormitory`(주거비 0), `custom`(`customMonthly` 사용). `nonTaxableMonthly`의 기본값은 200000. `employmentType`은 `check_relief_rules`에 필요해 `confirmed`에 넣는다.

```json
{
  "postings": [
    {"id": "A", "confirmed": {"companyName": "예시소프트(가상)", "annualSalary": 38000000, "sggCode": "11680", "companySize": "sme", "industryText": "기업용 소프트웨어 개발", "employmentType": "regular", "nonTaxableMonthly": 200000, "housing": {"mode": "market_rent", "customMonthly": null}}},
    {"id": "B", "confirmed": {"companyName": "보기정밀(가상)", "annualSalary": 34000000, "sggCode": "26230", "companySize": "sme", "industryText": "자동차 부품 제조", "employmentType": "regular", "nonTaxableMonthly": 200000, "housing": {"mode": "market_rent", "customMonthly": null}}}
  ],
  "profile": {"age": 26, "militaryServiceMonths": 18, "hireYear": 2027, "priorRelief": "no"},
  "options": {"horizonYears": 10}
}
```

`options.horizonYears`(선택)는 누적 기간으로 1, 3, 5, 10 중 하나다. 빼면 10이다(11/22 변경, 그전 기본값 5).

`options.explanation`(선택, 11/21 추가): `"ai"`(기본)면 LLM 설명문을 숫자 검증 후 넣고, `"template"`이면 LLM 없이 정해진 틀의 문장을 넣는다. 화면은 `"template"`으로 금액을 먼저 받아 띄우고, 같은 요청을 `POST /api/explain`에 보내 검증된 AI 설명문으로 바꿔 끼운다. 금액은 두 경우 모두 같다.

응답. `horizonYears` 10, `hireYear` 2027인 경우다.

```json
{
  "requestId": "req_20261122_0002", "generatedAt": "2026-11-22T15:20:31+09:00",
  "dataVersion": {"rent": "2026-11-22", "rules": "2026-v1"}, "degraded": false,
  "jobs": [
    {
      "id": "A",
      "region": {"sggCode": "11680", "name": "서울특별시 강남구", "regionClass": "capital", "typeBase": 1, "typePref": 2, "prefCandidate": false, "classUncertain": false},
      "rent": {"monthlyMedian": 850000, "p25": 720000, "p75": 1010000, "sampleCount": 412, "period": "2026-05~2026-10", "housingTypes": ["officetel", "detached_multi"], "scope": "sgg", "depositBasis": 10000000, "conversionRate": 0.06, "dataAsOf": "2026-11-22", "sufficient": true},
      "housingMonthly": 850000,
      "eligibility": {
        "status": "likely",
        "checks": [
          {"rule": "age", "result": "pass", "evidence": "입력한 나이에서 병역 기간을 뺀 나이가 34세 이하"},
          {"rule": "company_size", "result": "pass", "evidence": "공고의 '기업형태: 중소기업(벤처기업 인증)'"},
          {"rule": "industry", "result": "pass", "evidence": "공고의 '사업내용: 기업용 소프트웨어 개발'을 정보통신업으로 분류"},
          {"rule": "employment_type", "result": "pass", "evidence": "공고의 '고용형태: 정규직'"},
          {"rule": "prior_relief", "result": "pass", "evidence": "감면 이력 없음(사용자 입력)"}
        ],
        "hrQuestion": "귀사는 중소기업 취업자 소득세 감면 신청이 가능한 회사인가요?"
      },
      "pay": {"none": {"insurance": 3458880, "finalTax": 1028468, "localTax": 102846, "netAnnual": 33409806, "netMonthlyAvg": 2784150}, "withRelief": {"insurance": 3458880, "finalTax": 0, "localTax": 0, "netAnnual": 34541120, "netMonthlyAvg": 2878426}},
      "scenarios": [
        {"id": "none", "reliefYears": 0, "firstYearRemaining": 23209806, "cumulativeRemaining": 232098060, "reliefTotal": 0, "yearly": []},
        {"id": "current_law", "reliefYears": 0, "firstYearRemaining": 23209806, "cumulativeRemaining": 232098060, "reliefTotal": 0, "yearly": []},
        {"id": "proposal_base", "reliefYears": 5, "firstYearRemaining": 24341120, "cumulativeRemaining": 237754630, "reliefTotal": 5656570, "yearly": [
          {"year": 5, "reliefApplied": true, "netAnnual": 34541120, "housingAnnual": 10200000, "remaining": 24341120, "cumulative": 121705600},
          {"year": 6, "reliefApplied": false, "netAnnual": 33409806, "housingAnnual": 10200000, "remaining": 23209806, "cumulative": 144915406}
        ]},
        {"id": "proposal_pref", "reliefYears": 6, "firstYearRemaining": 24341120, "cumulativeRemaining": 238885944, "reliefTotal": 6787884, "yearly": []}
      ]
    },
    {
      "id": "B",
      "region": {"sggCode": "26230", "name": "부산광역시 부산진구", "regionClass": "metro", "typeBase": 2, "typePref": 3, "prefCandidate": false, "classUncertain": false},
      "rent": {"monthlyMedian": 450000, "p25": 380000, "p75": 540000, "sampleCount": 188, "period": "2026-05~2026-10", "housingTypes": ["officetel", "detached_multi"], "scope": "sgg", "depositBasis": 10000000, "conversionRate": 0.06, "dataAsOf": "2026-11-22", "sufficient": true},
      "housingMonthly": 450000,
      "eligibility": {
        "status": "likely",
        "checks": [
          {"rule": "age", "result": "pass", "evidence": "입력한 나이에서 병역 기간을 뺀 나이가 34세 이하"},
          {"rule": "company_size", "result": "pass", "evidence": "공고에는 없고 사용자가 중소기업이라고 답함"},
          {"rule": "industry", "result": "pass", "evidence": "공고의 '사업내용: 자동차 부품 제조'를 제조업으로 분류"},
          {"rule": "employment_type", "result": "pass", "evidence": "공고의 '고용형태: 정규직'"},
          {"rule": "prior_relief", "result": "pass", "evidence": "감면 이력 없음(사용자 입력)"}
        ],
        "hrQuestion": "귀사는 중소기업기본법상 중소기업이고, 중소기업 취업자 소득세 감면 신청이 가능한 회사인가요?"
      },
      "pay": {"none": {"insurance": 3070200, "finalTax": 583186, "localTax": 58318, "netAnnual": 30288296, "netMonthlyAvg": 2524024}, "withRelief": {"insurance": 3070200, "finalTax": 0, "localTax": 0, "netAnnual": 30929800, "netMonthlyAvg": 2577483}},
      "scenarios": [
        {"id": "none", "reliefYears": 0, "firstYearRemaining": 24888296, "cumulativeRemaining": 248882960, "reliefTotal": 0, "yearly": []},
        {"id": "current_law", "reliefYears": 0, "firstYearRemaining": 24888296, "cumulativeRemaining": 248882960, "reliefTotal": 0, "yearly": []},
        {"id": "proposal_base", "reliefYears": 6, "firstYearRemaining": 25529800, "cumulativeRemaining": 252731984, "reliefTotal": 3849024, "yearly": []},
        {"id": "proposal_pref", "reliefYears": 7, "firstYearRemaining": 25529800, "cumulativeRemaining": 253373488, "reliefTotal": 4490528, "yearly": []}
      ]
    }
  ],
  "comparison": [
    {"scenarioId": "none", "betterJobId": "B", "difference": 16784900, "breakEven": {"jobId": "A", "annualSalary": 40190000}},
    {"scenarioId": "current_law", "betterJobId": "B", "difference": 16784900, "breakEven": {"jobId": "A", "annualSalary": 40190000}},
    {"scenarioId": "proposal_base", "betterJobId": "B", "difference": 14977354, "breakEven": {"jobId": "A", "annualSalary": 39810000}},
    {"scenarioId": "proposal_pref", "betterJobId": "B", "difference": 14487544, "breakEven": {"jobId": "A", "annualSalary": 39730000}}
  ],
  "explanation": {
    "text": "연봉은 A가 3,800만 원으로 B의 3,400만 원보다 높지만, 세금과 월세를 빼고 10년을 더하면 B가 약 1,678만 원 더 남습니다(감면 없음 기준). 근무지 주변 환산월세 중위값이 A는 월 85만 원, B는 월 45만 원으로 차이가 크기 때문입니다. 정부안이 통과되면 차이는 약 1,498만 원으로 줄어드는데, 감면 기간은 B(6년)가 A(5년)보다 길어도 감면액 합계는 A가 약 566만 원으로 B의 약 385만 원보다 크기 때문입니다. 정부안 기준으로 두 공고가 같아지려면 A의 연봉이 3,981만 원이어야 합니다.",
    "aiGenerated": true, "numbersVerified": true
  },
  "trace": [
    {"step": 1, "type": "tool_call", "name": "get_rent_stats", "summary": "두 지역 모두 최근 6개월 표본이 30건 이상(412건, 188건)이라 범위를 넓히지 않음"},
    {"step": 2, "type": "tool_call", "name": "check_relief_rules", "summary": "두 회사 모두 중소기업이고 대상 업종(정보통신업, 제조업)이라 likely. B의 회사 규모는 사용자 답 기준"},
    {"step": 3, "type": "decision", "name": "scenario_selection", "summary": "입사가 2027년이라 current_law의 감면 연수는 0. 지역 구분이 미확정이라 proposal_base와 proposal_pref를 모두 계산"},
    {"step": 4, "type": "tool_call", "name": "simulate", "summary": "10년 기준으로 시나리오 4개의 누적 남는 돈과 손익분기 연봉을 계산"},
    {"step": 5, "type": "explain", "name": "explanation", "summary": "도구 결과에 있는 숫자만 써서 설명문을 쓰고 숫자 대조를 통과"}
  ],
  "assumptions": [
    "1인 가구이고 근로소득만 있다고 가정", "식대 비과세 월 200,000원 적용",
    "같은 회사, 같은 연봉, 같은 월세, 2026년 요율이 10년 동안 유지된다고 가정", "환산월세는 보증금 10,000,000원 기준, 전환율 연 6% 가정",
    "1월 입사로 보고 감면기간을 연 단위로 계산", "지역 유형은 공고의 근무지 기준으로 판정"
  ],
  "notices": [
    "AI가 생성한 답변입니다. 금액은 서버의 계산 코드가 산출했습니다.",
    "2026년 8월 정부 세제개편안 기준입니다. 국회에서 확정되지 않았고 지역 구분은 시행령으로 정해질 예정입니다.",
    "감면은 회사를 통해 신청해야 하며 대상 여부는 회사와 국세청에서 확인해야 합니다.",
    "남는 돈에는 식비·교통비 등 생활비가 들어 있지 않습니다."
  ],
  "sources": [
    {"name": "국토교통부 오피스텔 전월세 실거래가 자료", "url": "https://www.data.go.kr/data/15126475/openapi.do", "asOf": "2026-11-22"},
    {"name": "국토교통부 단독/다가구 전월세 실거래가 자료", "url": "https://www.data.go.kr/data/15126472/openapi.do", "asOf": "2026-11-22"},
    {"name": "조세특례제한법 시행령 제27조", "url": "https://law.go.kr/LSW/lsLinkCommonInfo.do?lspttninfSeq=128365", "asOf": "2026-11-20"},
    {"name": "2026년 세제개편안(재정경제부, 2026.8.3 발표)", "url": "https://nsp.nanet.go.kr/plan/subject/detail.do?nationalPlanControlNo=PLAN0000065941", "asOf": "2026-11-20"}
  ]
}
```

- `yearly`는 실제 응답에서는 모든 시나리오에 1년차부터 10년차까지 들어간다. 예시는 A의 `proposal_base`에서 감면이 끝나는 5년차와 6년차만 남기고 지면상 생략했다.
- `hireYear`가 2027이라 `current_law`는 `none`과 값이 같다. 2026이면 `current_law`의 `reliefYears`가 두 공고 모두 5다. 유형별 감면기간(1유형 5년, 2유형 6년, 3유형 7년, 4유형 10년)은 정부안 보도 기준 `[2차]`, 한도 200만 원 유지는 `[가정]`이다.
- `eligibility.status`가 `unlikely`인 공고는 모든 시나리오에서 `reliefYears`가 0이다. `uncertain`인 공고는 대상이라고 보고 계산하되, 화면이 그 공고의 `none` 값(대상이 아닐 때)을 함께 보여준다. 두 공고 중 한쪽만 대상인 조합은 확인 화면에서 회사 규모를 바꿔 다시 계산한다.
- 화면은 정부안을 보여줄 때 `proposal_base`와 `proposal_pref`를 항상 같이 보여주고 `notices`와 `assumptions`를 그대로 표시한다. `region.classUncertain`이 true면 "분류 미확정"을, `prefCandidate`가 true면 우대지역 후보(확정 아님)임을 표시한다.
- `explanation.text`에 나오는 숫자는 모두 요청이나 응답 JSON에 있는 값을 만 원 단위로 반올림해 쓴 것이다(표기와 대조 규칙은 `docs/agent-spec.md`). `numbersVerified`가 false인 설명문은 화면에 내보내지 않는다(제안).
- 계산 도중 값이 더 필요하면(예: 월세가 `sido`까지 넓혀도 확인 불가) 200으로 `{ "needsInput": true, "questions": Question[], "trace": Trace[] }`만 돌려주고 계산 결과는 넣지 않는다. 화면은 확인 화면에 질문을 띄우고, 답을 `confirmed`에 반영해(월세는 `housing.mode`를 `custom`으로) `compare`를 다시 부른다.

## 6. 그 밖의 엔드포인트

- `GET /api/samples`: 응답은 `{ "samples": [{ "id", "title", "postings": [{ "id", "text" }] }] }`. 공고는 가상 회사로 직접 쓰고 `data/samples/`에 둔다. 샘플도 `extract`와 `compare`를 그대로 거친다.
- `POST /api/followup`(선택): 요청은 `{ "previous": 직전 compare 요청 본문, "message": "기숙사에 들어가면?" }`, 응답은 `compare` 응답과 같은 형식이다. 에이전트가 바뀐 조건만 반영해 `simulate`를 다시 부르고, 무엇을 바꿨는지 `trace`에 `decision`으로 남긴다. 일정이 밀리면 가장 먼저 뺀다.
- `POST /api/explain`(11/21 추가): 요청은 `compare`와 같다(`options.explanation`은 무시하고 `"ai"`로 처리). 응답은 `{ "explanation": Explanation, "notices": [string] }`. 숫자 검증을 두 번 통과하지 못하면 `explanation.aiGenerated`가 false인 템플릿 문장이다. 조건이 모자라면 `{ "explanation": null, "notices": [] }`.
- `GET /api/health`: `{ "status": "ok", "dataVersion": { "rent": "2026-11-22", "rules": "2026-v1" } }`. LLM을 부르지 않는다. 심사 기간의 접속 점검에 쓴다.

## 7. 오류와 대체 응답

오류 응답은 `{ "error": { "code", "message", "fallback" } }` 형식이다. `fallback`은 화면이 다음에 할 일이고, `code`와 `fallback`은 아래 표의 값만 쓴다.

| HTTP | `error.code` | 상황 | `fallback` |
|---|---|---|---|
| 400 | `INVALID_INPUT` | 공고가 2건이 아니거나 비어 있음, 길이 상한 초과, 필수 값 누락 | `fix_input` |
| 422 | `POSTING_UNREADABLE` | 채용공고로 볼 수 없거나 연봉과 근무지를 모두 읽지 못함 | `manual_input` (확인 화면에서 직접 입력) |
| 429 | `RATE_LIMITED` | IP당 일일 한도 또는 전체 일일 한도 초과 | `sample_mode` (샘플 저장본 안내) |
| 503 | `LLM_UNAVAILABLE` | `extract`에서 LLM 호출 실패 또는 시간 초과 | `manual_input` |

- `compare`에서 LLM 호출이 실패하거나 시간 제한을 넘으면 오류를 내지 않는다. 같은 도구를 정해진 순서(`get_rent_stats` → `check_relief_rules` → `simulate`)로 부르는 결정적 파이프라인으로 계산해 200으로 응답하고 `degraded`를 true로 둔다. 이때 `explanation.text`는 서버 템플릿 문장이고 `aiGenerated`는 false다. 업종은 보수적인 키워드 규칙으로 분류하고(대상 업종 하나에 분명히 해당할 때만), 그렇지 않으면 `industry` 판정은 `unknown`이 된다.
- 시간 제한은 2장의 값을 제안한다. LLM 호출 한 번의 제한과 재시도 횟수는 `docs/agent-spec.md`에서 정한다.

## 8. 에이전트 도구

서버 내부 함수다. 에이전트(LLM)가 호출을 결정하고 서버가 실행한다. 금액은 `simulate`와 `get_rent_stats`의 출력만 쓴다.

| 도구 | 입력 | 출력 | 비고 |
|---|---|---|---|
| `resolve_region` | `locationText` | `{ candidates: Region[], ambiguous }` | 지역 표 조회. 후보가 없거나 여럿이면 `ask_user` |
| `get_rent_stats` | `sggCode`, `scope` | Rent | 스냅샷 조회. `scope`는 `sgg` → `sgg_12m` → `sido` 순서로만 넓힌다 |
| `check_relief_rules` | `postingId`, `companySize`, `industryName`, `employmentType`, `hireYear` | Eligibility | `profile`은 서버가 넣는다. `industryName`은 시행령 제27조 제3항 목록의 업종명, 대상이 아닌 업종이면 `excluded`, 판단할 수 없으면 `unknown`. 목록 대조와 판정은 코드가 한다 |
| `simulate` | `jobs[]`, `hireYear`, `horizonYears` | 공고별 `pay`와 `scenarios`, 그리고 `comparison` | 계산 규칙은 `docs/calc-rules.md`. 입력 예시는 아래 |
| `ask_user` | Question[] | 사용자 답 | HTTP에서는 `extract` 응답의 `questions`와 `compare` 요청의 `confirmed`, `profile`에 대응. `compare` 도중의 질문은 `needsInput` 응답으로 보낸다(5장) |

```json
{"jobs": [
  {"id": "A", "annualSalary": 38000000, "nonTaxableMonthly": 200000, "housingMonthly": 850000, "typeBase": 1, "typePref": 2, "eligible": true},
  {"id": "B", "annualSalary": 34000000, "nonTaxableMonthly": 200000, "housingMonthly": 450000, "typeBase": 2, "typePref": 3, "eligible": true}
], "hireYear": 2027, "horizonYears": 10}
```

- `eligible`은 `eligibility.status`가 `likely`나 `uncertain`이면 true, `unlikely`면 false다.
- `housingMonthly`는 `housing.mode`가 `market_rent`면 `rent.monthlyMedian`, `dormitory`면 0, `custom`이면 `customMonthly`다.
- `sufficient`가 false면 에이전트가 `scope`를 넓혀 다시 부를지 판단한다. `sido`까지 넓혀도 부족하면 "확인 불가"로 두고 `ask_user`로 월세를 직접 받는다(`housing.mode`는 `custom`).
- 도구 호출 횟수 상한과 순서 검증은 `docs/agent-spec.md`에서 정한다.

## 9. 운영 메모

- 요청마다 로그에 `requestId`, 엔드포인트, 단계별 소요 시간, LLM 호출 수, 입력·출력 토큰 수, 호출한 도구 목록, `degraded`, 오류 코드를 남긴다. 요청 1건당 비용은 이 로그로 실측해 소개서 08에 적는다. `profile` 값은 남기지 않고, 공고 원문을 남길 때는 담당자 이름과 연락처를 가린다(제안).
- IP당 일일 한도와 전체 일일 한도를 둔다. 값은 팀이 정하고 마감 전에 확정한다. 넘으면 429와 함께 샘플 저장본을 안내한다.
- 샘플 쌍마다 `extract`와 `compare` 응답 저장본을 마감 전에 만들어 둔다. LLM 장애나 한도 초과 때 저장본으로 응답하고 `degraded`를 true로 두며 화면에 "저장된 예시 결과"라고 표시한다.
- 마감 뒤에는 기능·알고리즘·프롬프트·데이터를 바꿀 수 없다. 접속 복구와 인증정보 교체만 한다.

## 10. 변경 절차

- 경로, 필드, 값 목록을 바꾸려면 이 문서를 먼저 고치고 팀 채널에 알린 뒤 코드를 바꾼다. 시나리오 ID, 금액 단위, `Field.status` 값은 바꾸지 않는다.
- 11/21(토) 24시 기능 동결 뒤에는 필드를 추가하지 않는다. 버그 수정만 한다.
- 예시 JSON의 숫자를 바꿀 일이 생기면 `scripts/calc_ref.py` 출력과 다시 대조한다.
