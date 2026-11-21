/* 개발용 mock. ?mock=1 로 연다. 아래 DATA는 docs/api-spec.md의 JSON 블록(extract 응답, compare 응답)과 data/samples/*.json에서 생성했다. 손으로 고치지 않는다. */
window.MOCK_DATA = {
 "samples": [
  {
   "id": "pair1",
   "title": "서울 소프트웨어 회사와 부산 제조 회사 (가상)",
   "postings": [
    {
     "id": "A",
     "text": "[예시소프트(가상)] 백엔드 개발자 신입 채용\n사업내용: 기업용 소프트웨어 개발\n기업형태: 중소기업(벤처기업 인증)\n근무지: 서울 강남구 테헤란로\n고용형태: 정규직\n급여: 연봉 3,800만원 (식대 월 20만원 포함)\n복리후생: 자기계발비 지원, 건강검진"
    },
    {
     "id": "B",
     "text": "[보기정밀(가상)] 생산기술 엔지니어 신입 채용\n사업내용: 자동차 부품 제조\n근무지: 부산 부산진구 전포동\n고용형태: 정규직\n급여: 연봉 3,400만원\n복리후생: 통근버스, 경조사 지원"
    }
   ]
  },
  {
   "id": "pair2",
   "title": "서울 클라우드 회사와 대구 군위군 식품 회사 (가상, 기숙사 제공)",
   "postings": [
    {
     "id": "A",
     "text": "[예시테크(가상)] 데이터 엔지니어 신입 채용\n사업내용: 클라우드 서비스 개발\n기업형태: 중소기업\n근무지: 서울 강남구 역삼동\n고용형태: 정규직\n급여: 연봉 3,600만원\n복리후생: 재택근무 주 1회, 도서 구입비"
    },
    {
     "id": "B",
     "text": "[보기푸드(가상)] 품질관리 신입 채용\n사업내용: 식품 제조\n기업형태: 중소기업\n근무지: 대구 군위군 군위읍\n고용형태: 정규직\n급여: 연봉 3,300만원\n복리후생: 기숙사 제공, 통근버스"
    }
   ]
  }
 ],
 "extractResponse": {
  "requestId": "req_20261122_0001",
  "degraded": false,
  "postings": [
   {
    "id": "A",
    "fields": {
     "companyName": {
      "value": "예시소프트(가상)",
      "status": "extracted",
      "evidence": "[예시소프트(가상)] 백엔드 개발자 신입 채용",
      "note": null
     },
     "annualSalary": {
      "value": 38000000,
      "status": "extracted",
      "evidence": "급여: 연봉 3,800만원 (식대 월 20만원 포함)",
      "note": null
     },
     "workLocationText": {
      "value": "서울 강남구 테헤란로",
      "status": "extracted",
      "evidence": "근무지: 서울 강남구 테헤란로",
      "note": null
     },
     "employmentType": {
      "value": "regular",
      "status": "extracted",
      "evidence": "고용형태: 정규직",
      "note": null
     },
     "companySize": {
      "value": "sme",
      "status": "extracted",
      "evidence": "기업형태: 중소기업(벤처기업 인증)",
      "note": null
     },
     "industryText": {
      "value": "기업용 소프트웨어 개발",
      "status": "extracted",
      "evidence": "사업내용: 기업용 소프트웨어 개발",
      "note": null
     },
     "benefits": {
      "mealAllowanceMonthly": {
       "value": 200000,
       "status": "extracted",
       "evidence": "식대 월 20만원 포함",
       "note": null
      },
      "dormitory": {
       "value": null,
       "status": "missing",
       "evidence": null,
       "note": "공고에 언급 없음"
      },
      "housingSupportMonthly": {
       "value": null,
       "status": "missing",
       "evidence": null,
       "note": "공고에 언급 없음"
      },
      "others": [
       "자기계발비 지원",
       "건강검진"
      ]
     }
    },
    "region": {
     "candidates": [
      {
       "sggCode": "11680",
       "name": "서울특별시 강남구",
       "regionClass": "capital",
       "typeBase": 1,
       "typePref": 2,
       "prefCandidate": false,
       "classUncertain": false
      }
     ],
     "ambiguous": false
    }
   },
   {
    "id": "B",
    "fields": {
     "companyName": {
      "value": "보기정밀(가상)",
      "status": "extracted",
      "evidence": "[보기정밀(가상)] 생산기술 엔지니어 신입 채용",
      "note": null
     },
     "annualSalary": {
      "value": 34000000,
      "status": "extracted",
      "evidence": "급여: 연봉 3,400만원",
      "note": null
     },
     "workLocationText": {
      "value": "부산 부산진구 전포동",
      "status": "extracted",
      "evidence": "근무지: 부산 부산진구 전포동",
      "note": null
     },
     "employmentType": {
      "value": "regular",
      "status": "extracted",
      "evidence": "고용형태: 정규직",
      "note": null
     },
     "companySize": {
      "value": "unknown",
      "status": "missing",
      "evidence": null,
      "note": "공고에 회사 규모가 적혀 있지 않음"
     },
     "industryText": {
      "value": "자동차 부품 제조",
      "status": "extracted",
      "evidence": "사업내용: 자동차 부품 제조",
      "note": null
     },
     "benefits": {
      "mealAllowanceMonthly": {
       "value": null,
       "status": "missing",
       "evidence": null,
       "note": "공고에 언급 없음"
      },
      "dormitory": {
       "value": null,
       "status": "missing",
       "evidence": null,
       "note": "공고에 언급 없음"
      },
      "housingSupportMonthly": {
       "value": null,
       "status": "missing",
       "evidence": null,
       "note": "공고에 언급 없음"
      },
      "others": [
       "통근버스",
       "경조사 지원"
      ]
     }
    },
    "region": {
     "candidates": [
      {
       "sggCode": "26230",
       "name": "부산광역시 부산진구",
       "regionClass": "metro",
       "typeBase": 2,
       "typePref": 3,
       "prefCandidate": false,
       "classUncertain": false
      }
     ],
     "ambiguous": false
    }
   }
  ],
  "questions": [
   {
    "id": "q1",
    "postingId": "B",
    "field": "companySize",
    "text": "보기정밀(가상) 공고에는 회사 규모가 적혀 있지 않습니다. 어디에 해당하나요?",
    "inputType": "select",
    "options": [
     {
      "value": "sme",
      "label": "중소기업"
     },
     {
      "value": "mid",
      "label": "중견기업"
     },
     {
      "value": "large",
      "label": "대기업"
     },
     {
      "value": "public",
      "label": "공공기관"
     },
     {
      "value": "unknown",
      "label": "모름"
     }
    ],
    "required": true
   },
   {
    "id": "q2",
    "postingId": null,
    "field": "profile.age",
    "text": "근로계약을 맺는 시점의 만 나이를 알려주세요.",
    "inputType": "number",
    "options": null,
    "required": true
   },
   {
    "id": "q3",
    "postingId": null,
    "field": "profile.militaryServiceMonths",
    "text": "병역을 마쳤다면 복무 기간을 개월 수로 적어 주세요. 해당이 없으면 0입니다.",
    "inputType": "number",
    "options": null,
    "required": false
   },
   {
    "id": "q4",
    "postingId": null,
    "field": "profile.hireYear",
    "text": "입사 예정 시기를 골라 주세요.",
    "inputType": "select",
    "options": [
     {
      "value": 2026,
      "label": "2026년 안"
     },
     {
      "value": 2027,
      "label": "2027년 이후"
     }
    ],
    "required": true
   },
   {
    "id": "q5",
    "postingId": null,
    "field": "profile.priorRelief",
    "text": "중소기업 취업자 소득세 감면을 받은 적이 있나요?",
    "inputType": "select",
    "options": [
     {
      "value": "no",
      "label": "없음"
     },
     {
      "value": "yes",
      "label": "있음"
     },
     {
      "value": "unknown",
      "label": "모름"
     }
    ],
    "required": false
   }
  ],
  "trace": [
   {
    "step": 1,
    "type": "extract",
    "name": "extract_postings",
    "summary": "공고 2건에서 필드 7종을 읽음. B의 회사 규모는 원문에 없음"
   },
   {
    "step": 2,
    "type": "tool_call",
    "name": "resolve_region",
    "summary": "'서울 강남구 테헤란로'는 11680, '부산 부산진구 전포동'은 26230 하나씩만 대응"
   },
   {
    "step": 3,
    "type": "question",
    "name": "ask_user",
    "summary": "감면 판정에 필요한 B의 회사 규모 1건을 되묻기로 함"
   }
  ]
 },
 "compareResponse": {
  "requestId": "req_20261122_0002",
  "generatedAt": "2026-11-22T15:20:31+09:00",
  "dataVersion": {
   "rent": "2026-11-22",
   "rules": "2026-v1"
  },
  "degraded": false,
  "jobs": [
   {
    "id": "A",
    "region": {
     "sggCode": "11680",
     "name": "서울특별시 강남구",
     "regionClass": "capital",
     "typeBase": 1,
     "typePref": 2,
     "prefCandidate": false,
     "classUncertain": false
    },
    "rent": {
     "monthlyMedian": 850000,
     "p25": 720000,
     "p75": 1010000,
     "sampleCount": 412,
     "period": "2026-05~2026-10",
     "housingTypes": [
      "officetel",
      "detached_multi"
     ],
     "scope": "sgg",
     "depositBasis": 10000000,
     "conversionRate": 0.06,
     "dataAsOf": "2026-11-22",
     "sufficient": true
    },
    "housingMonthly": 850000,
    "eligibility": {
     "status": "likely",
     "checks": [
      {
       "rule": "age",
       "result": "pass",
       "evidence": "입력한 나이에서 병역 기간을 뺀 나이가 34세 이하"
      },
      {
       "rule": "company_size",
       "result": "pass",
       "evidence": "공고의 '기업형태: 중소기업(벤처기업 인증)'"
      },
      {
       "rule": "industry",
       "result": "pass",
       "evidence": "공고의 '사업내용: 기업용 소프트웨어 개발'을 정보통신업으로 분류"
      },
      {
       "rule": "employment_type",
       "result": "pass",
       "evidence": "공고의 '고용형태: 정규직'"
      },
      {
       "rule": "prior_relief",
       "result": "pass",
       "evidence": "감면 이력 없음(사용자 입력)"
      }
     ],
     "hrQuestion": "귀사는 중소기업 취업자 소득세 감면 신청이 가능한 회사인가요?"
    },
    "pay": {
     "none": {
      "insurance": 3458880,
      "finalTax": 1028468,
      "localTax": 102846,
      "netAnnual": 33409806,
      "netMonthlyAvg": 2784150
     },
     "withRelief": {
      "insurance": 3458880,
      "finalTax": 0,
      "localTax": 0,
      "netAnnual": 34541120,
      "netMonthlyAvg": 2878426
     }
    },
    "scenarios": [
     {
      "id": "none",
      "reliefYears": 0,
      "firstYearRemaining": 23209806,
      "cumulativeRemaining": 232098060,
      "reliefTotal": 0,
      "yearly": []
     },
     {
      "id": "current_law",
      "reliefYears": 0,
      "firstYearRemaining": 23209806,
      "cumulativeRemaining": 232098060,
      "reliefTotal": 0,
      "yearly": []
     },
     {
      "id": "proposal_base",
      "reliefYears": 5,
      "firstYearRemaining": 24341120,
      "cumulativeRemaining": 237754630,
      "reliefTotal": 5656570,
      "yearly": [
       {
        "year": 5,
        "reliefApplied": true,
        "netAnnual": 34541120,
        "housingAnnual": 10200000,
        "remaining": 24341120,
        "cumulative": 121705600
       },
       {
        "year": 6,
        "reliefApplied": false,
        "netAnnual": 33409806,
        "housingAnnual": 10200000,
        "remaining": 23209806,
        "cumulative": 144915406
       }
      ]
     },
     {
      "id": "proposal_pref",
      "reliefYears": 6,
      "firstYearRemaining": 24341120,
      "cumulativeRemaining": 238885944,
      "reliefTotal": 6787884,
      "yearly": []
     }
    ]
   },
   {
    "id": "B",
    "region": {
     "sggCode": "26230",
     "name": "부산광역시 부산진구",
     "regionClass": "metro",
     "typeBase": 2,
     "typePref": 3,
     "prefCandidate": false,
     "classUncertain": false
    },
    "rent": {
     "monthlyMedian": 450000,
     "p25": 380000,
     "p75": 540000,
     "sampleCount": 188,
     "period": "2026-05~2026-10",
     "housingTypes": [
      "officetel",
      "detached_multi"
     ],
     "scope": "sgg",
     "depositBasis": 10000000,
     "conversionRate": 0.06,
     "dataAsOf": "2026-11-22",
     "sufficient": true
    },
    "housingMonthly": 450000,
    "eligibility": {
     "status": "likely",
     "checks": [
      {
       "rule": "age",
       "result": "pass",
       "evidence": "입력한 나이에서 병역 기간을 뺀 나이가 34세 이하"
      },
      {
       "rule": "company_size",
       "result": "pass",
       "evidence": "공고에는 없고 사용자가 중소기업이라고 답함"
      },
      {
       "rule": "industry",
       "result": "pass",
       "evidence": "공고의 '사업내용: 자동차 부품 제조'를 제조업으로 분류"
      },
      {
       "rule": "employment_type",
       "result": "pass",
       "evidence": "공고의 '고용형태: 정규직'"
      },
      {
       "rule": "prior_relief",
       "result": "pass",
       "evidence": "감면 이력 없음(사용자 입력)"
      }
     ],
     "hrQuestion": "귀사는 중소기업기본법상 중소기업이고, 중소기업 취업자 소득세 감면 신청이 가능한 회사인가요?"
    },
    "pay": {
     "none": {
      "insurance": 3070200,
      "finalTax": 583186,
      "localTax": 58318,
      "netAnnual": 30288296,
      "netMonthlyAvg": 2524024
     },
     "withRelief": {
      "insurance": 3070200,
      "finalTax": 0,
      "localTax": 0,
      "netAnnual": 30929800,
      "netMonthlyAvg": 2577483
     }
    },
    "scenarios": [
     {
      "id": "none",
      "reliefYears": 0,
      "firstYearRemaining": 24888296,
      "cumulativeRemaining": 248882960,
      "reliefTotal": 0,
      "yearly": []
     },
     {
      "id": "current_law",
      "reliefYears": 0,
      "firstYearRemaining": 24888296,
      "cumulativeRemaining": 248882960,
      "reliefTotal": 0,
      "yearly": []
     },
     {
      "id": "proposal_base",
      "reliefYears": 6,
      "firstYearRemaining": 25529800,
      "cumulativeRemaining": 252731984,
      "reliefTotal": 3849024,
      "yearly": []
     },
     {
      "id": "proposal_pref",
      "reliefYears": 7,
      "firstYearRemaining": 25529800,
      "cumulativeRemaining": 253373488,
      "reliefTotal": 4490528,
      "yearly": []
     }
    ]
   }
  ],
  "comparison": [
   {
    "scenarioId": "none",
    "betterJobId": "B",
    "difference": 16784900,
    "breakEven": {
     "jobId": "A",
     "annualSalary": 40190000
    }
   },
   {
    "scenarioId": "current_law",
    "betterJobId": "B",
    "difference": 16784900,
    "breakEven": {
     "jobId": "A",
     "annualSalary": 40190000
    }
   },
   {
    "scenarioId": "proposal_base",
    "betterJobId": "B",
    "difference": 14977354,
    "breakEven": {
     "jobId": "A",
     "annualSalary": 39810000
    }
   },
   {
    "scenarioId": "proposal_pref",
    "betterJobId": "B",
    "difference": 14487544,
    "breakEven": {
     "jobId": "A",
     "annualSalary": 39730000
    }
   }
  ],
  "explanation": {
   "text": "연봉은 A가 3,800만 원으로 B의 3,400만 원보다 높지만, 세금과 월세를 빼고 10년을 더하면 B가 약 1,678만 원 더 남습니다(감면 없음 기준). 근무지 주변 환산월세 중위값이 A는 월 85만 원, B는 월 45만 원으로 차이가 크기 때문입니다. 정부안이 통과되면 차이는 약 1,498만 원으로 줄어드는데, 감면 기간은 B(6년)가 A(5년)보다 길어도 감면액 합계는 A가 약 566만 원으로 B의 약 385만 원보다 크기 때문입니다. 정부안 기준으로 두 공고가 같아지려면 A의 연봉이 3,981만 원이어야 합니다.",
   "aiGenerated": true,
   "numbersVerified": true
  },
  "trace": [
   {
    "step": 1,
    "type": "tool_call",
    "name": "get_rent_stats",
    "summary": "두 지역 모두 최근 6개월 표본이 30건 이상(412건, 188건)이라 범위를 넓히지 않음"
   },
   {
    "step": 2,
    "type": "tool_call",
    "name": "check_relief_rules",
    "summary": "두 회사 모두 중소기업이고 대상 업종(정보통신업, 제조업)이라 likely. B의 회사 규모는 사용자 답 기준"
   },
   {
    "step": 3,
    "type": "decision",
    "name": "scenario_selection",
    "summary": "입사가 2027년이라 current_law의 감면 연수는 0. 지역 구분이 미확정이라 proposal_base와 proposal_pref를 모두 계산"
   },
   {
    "step": 4,
    "type": "tool_call",
    "name": "simulate",
    "summary": "10년 기준으로 시나리오 4개의 누적 남는 돈과 손익분기 연봉을 계산"
   },
   {
    "step": 5,
    "type": "explain",
    "name": "explanation",
    "summary": "도구 결과에 있는 숫자만 써서 설명문을 쓰고 숫자 대조를 통과"
   }
  ],
  "assumptions": [
   "1인 가구이고 근로소득만 있다고 가정",
   "식대 비과세 월 200,000원 적용",
   "같은 회사, 같은 연봉, 같은 월세, 2026년 요율이 10년 동안 유지된다고 가정",
   "환산월세는 보증금 10,000,000원 기준, 전환율 연 6% 가정",
   "1월 입사로 보고 감면기간을 연 단위로 계산",
   "지역 유형은 공고의 근무지 기준으로 판정"
  ],
  "notices": [
   "AI가 생성한 답변입니다. 금액은 서버의 계산 코드가 산출했습니다.",
   "2026년 8월 정부 세제개편안 기준입니다. 국회에서 확정되지 않았고 지역 구분은 시행령으로 정해질 예정입니다.",
   "감면은 회사를 통해 신청해야 하며 대상 여부는 회사와 국세청에서 확인해야 합니다.",
   "남는 돈에는 식비·교통비 등 생활비가 들어 있지 않습니다."
  ],
  "sources": [
   {
    "name": "국토교통부 오피스텔 전월세 실거래가 자료",
    "url": "https://www.data.go.kr/data/15126475/openapi.do",
    "asOf": "2026-11-22"
   },
   {
    "name": "국토교통부 단독/다가구 전월세 실거래가 자료",
    "url": "https://www.data.go.kr/data/15126472/openapi.do",
    "asOf": "2026-11-22"
   },
   {
    "name": "조세특례제한법 시행령 제27조",
    "url": "https://law.go.kr/LSW/lsLinkCommonInfo.do?lspttninfSeq=128365",
    "asOf": "2026-11-20"
   },
   {
    "name": "2026년 세제개편안(재정경제부, 2026.8.3 발표)",
    "url": "https://nsp.nanet.go.kr/plan/subject/detail.do?nationalPlanControlNo=PLAN0000065941",
    "asOf": "2026-11-20"
   }
  ]
 }
};

/* mock API. ?mock=1 기본. 선택 인자: degraded=1(extract degraded), sample=1(월세 sample 경고), case=needs(첫 compare에 needsInput) | case=err503(extract 503) | case=err400 */
(function () {
  'use strict';
  var qs = new URLSearchParams(location.search);
  var needsDone = false;
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function res(status, data) { return Promise.resolve({ status: status, data: data }); }
  function delay(v) { return new Promise(function (r) { setTimeout(function () { r(v); }, 350); }); }

  window.MockApi = {
    request: function (method, path, body) {
      var D = window.MOCK_DATA;
      if (method === 'GET' && path === '/api/samples') {
        return delay({ status: 200, data: { samples: clone(D.samples) } });
      }
      if (method === 'POST' && path === '/api/extract') {
        var c = qs.get('case');
        if (c === 'err503') return delay({ status: 503, data: { error: { code: 'LLM_UNAVAILABLE', message: '공고를 읽는 서비스에 연결하지 못했습니다. 직접 입력으로 이어갑니다.', fallback: 'manual_input' } } });
        if (c === 'err400') return delay({ status: 400, data: { error: { code: 'INVALID_INPUT', message: '공고 본문이 비어 있습니다.', fallback: 'fix_input' } } });
        if (c === 'err429') return delay({ status: 429, data: { error: { code: 'RATE_LIMITED', message: '오늘 사용 한도를 넘었습니다.', fallback: 'sample_mode' } } });
        var e = clone(D.extractResponse);
        if (qs.get('degraded') === '1') e.degraded = true;
        return delay({ status: 200, data: e });
      }
      if (method === 'POST' && path === '/api/compare') {
        var custom = body && body.postings && body.postings.some(function (p) { return p.confirmed.housing.mode === 'custom'; });
        if (qs.get('case') === 'needs' && !needsDone && !custom) {
          needsDone = true;
          return delay({ status: 200, data: { needsInput: true, questions: [
            { id: 'q9', postingId: 'A', field: 'housing.customMonthly', text: '공고 A 근무지의 월세 통계를 확인하지 못했습니다. 월 주거비를 원 단위로 직접 입력해 주세요.', inputType: 'number', options: null, required: true }
          ], trace: [{ step: 1, type: 'tool_call', name: 'get_rent_stats', summary: '(mock) 월세 표본 부족' }] } });
        }
        var r = clone(D.compareResponse);
        var h = (body && body.options && body.options.horizonYears) || 10;
        r.jobs.forEach(function (j) { j.scenarios.forEach(function (s) { s.yearly = s.yearly.filter(function (y) { return y.year <= h; }); }); });
        if (qs.get('sample') === '1') r.dataVersion.rent = 'sample-' + r.dataVersion.rent;
        if (qs.get('degraded') === '1') r.degraded = true;
        return delay({ status: 200, data: r });
      }
      return delay({ status: 404, data: { error: { code: 'INVALID_INPUT', message: 'mock에 없는 경로: ' + path, fallback: 'fix_input' } } });
    }
  };
})();
