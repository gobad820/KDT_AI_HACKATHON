# 첫 직장, 10년 뒤 경제력

채용공고 두 개를 넣으면 세금과 월세를 빼고 10년 동안 남는 돈을 비교합니다.

채용공고 두 건을 넣으면 AI 에이전트가 조건을 읽고 빠진 것은 되물은 뒤, 세후 급여, 근무지 월세, 지역에 따라 달라지는 청년 세제(중소기업 취업 청년 소득세 감면)를 계산해 어느 쪽이 얼마 더 남는지와 손익분기 연봉을 근거와 함께 보여준다.

2026 대한민국 청년 CAREER FAIR AI 해커톤(대한상공회의소) 출품 프로젝트. 전체 그림은 `docs/brief.md`.

## 지금 상태 (11/21 토 밤)

| 부분 | 상태 |
|---|---|
| 계산 (세후, 감면, 시나리오, 손익분기) | 동작. 따로 짠 참고 구현과 대조함. **공식 계산기와는 대조 전** |
| 감면 대상 가능성 판정 | 동작. 조문 원문 대조 전 |
| 결정적 파이프라인, API | 동작. `docs/api-spec.md`의 예시 요청을 넣으면 예시 응답의 금액이 나옴 |
| 화면 3장 | 동작. 샘플 2쌍으로 입력부터 결과까지 확인(데스크톱, 휴대폰 폭) |
| 월세 데이터 | 국토부 전월세 실거래가로 만든 확정 스냅샷(`data/rent_stats.json`, 버전 2026-11-21). 오피스텔·연립다세대·단독다가구, 면적 33㎡ 이하 |
| 지역 표 | 전국 269행(시군구 256곳 + 일반구 합산 13곳, `data/regions.csv`), 인구감소지역 92곳(`data/depop_2026.csv`) |
| 배포 | Vercel, https://nammeun-don.vercel.app |
| LLM | Gemini `gemini-3.1-flash-lite`(OpenAI 호환 주소)로 연결. 11/21 가상 공고로 추출·업종 분류·설명문까지 확인. 장애 때는 샘플 공고만 저장된 추출 결과로 응답하고, 업종은 키워드 규칙, 설명문은 템플릿 |
| 도구 호출 루프, 후속 질문(`/api/followup`) | 아직 없음 |

## 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # 키는 .env 에만. 커밋 금지
uvicorn app.main:app --reload   # http://localhost:8000
python3 -m pytest               # 전체 테스트
```

- 화면: `http://localhost:8000/` (서버 없이 보려면 `?mock=1`)
- API 문서: `http://localhost:8000/api/docs`
- Python 3.11 이상

## 폴더

| 경로 | 내용 | 담당 |
|---|---|---|
| `app/schemas.py` | API 타입. `docs/api-spec.md`와 1:1 | 김상해 |
| `app/calc/` | 세후, 감면, 시나리오, 손익분기 | 정상훈 |
| `app/relief/` | 감면 대상 업종 목록과 판정 | 정상훈 |
| `app/data/`, `data/`, `scripts/` | 지역 표, 월세 스냅샷, 수집·통계 스크립트 | 김상해 |
| `app/agent/`, `tests/cases/` | LLM 인터페이스, 추출, 되묻기, 설명문, 검증기, 테스트 30건 | 이동한 |
| `app/pipeline.py`, `app/main.py` | 결정적 파이프라인, API 서버 | 김상해 |
| `app/web/` | 화면 3장 | 김상해 |
| `docs/` | 브리프, 명세, 계산 규칙, 개발 메모, AI 사용 기록 | 전원 |

모듈 사이의 함수 경계는 `docs/dev-notes.md`, JSON 계약은 `docs/api-spec.md`. 바꿀 때는 문서부터 고친다.

## 실제 데이터 넣기

1. 공공데이터포털에서 전월세 실거래가 3종(오피스텔, 단독/다가구, 연립다세대) 활용신청 후 `.env`의 `DATA_GO_KR_KEY`에 인증키를 넣는다.
2. 행정표준코드관리시스템의 법정동 코드 파일과 행정안전부 인구감소지역 목록을 받아 `scripts/build_regions.py`로 `data/regions.csv`를 만든다.
3. `scripts/collect_rent.py`로 수집하고 `scripts/build_rent_stats.py`로 `data/rent_stats.json`을 만든다. 이 파일이 있으면 서버는 샘플 대신 이 파일을 읽는다.
4. 사용법은 각 스크립트의 `--help`, 규칙은 `docs/data-spec.md`.

`APP_ENV=prod`에서는 샘플 스냅샷이나 `-partial` 스냅샷으로 서버가 시작되지 않는다.

## LLM

Gemini `gemini-flash-lite-latest`를 OpenAI 호환 주소로 부른다(`app/agent/llm.py`의 `OpenAIClient`). 응답 온도는 0이고, 한 번 시도는 8초까지 기다린다. 429·5xx·시간 초과면 `LLM_MODEL_FALLBACKS`의 모델(`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`)로 바로 넘어간다. 결과 화면은 금액을 먼저 보여 주고 AI 설명문은 `POST /api/explain`으로 나중에 받는다. 키는 로컬에서는 `.env`, 배포에서는 Vercel 환경변수로만 읽는다.

## 지킬 것 (대회 규정)

- 키·비밀번호를 코드, 문서, 채팅에 넣지 않는다.
- 외부 LLM에 실제 개인정보를 보내지 않는다. 시연과 테스트는 가상 회사의 샘플 공고만 쓴다.
- 금액은 코드가 계산한다. LLM은 금액을 만들지 않는다.
- 마감(11/23 17:00) 뒤에는 기능·알고리즘·프롬프트·데이터를 바꾸지 않는다.
- 이 저장소의 코드는 대부분 AI(Claude)가 생성했다. 팀이 직접 실행·검증·수정하고 그 내용을 `docs/ai-usage-log.md`에 남긴다.

## Credits / Licenses

| 이름 | 라이선스 | 링크 | 용도 |
|---|---|---|---|
| FastAPI | MIT | https://github.com/fastapi/fastapi | API 서버 |
| Starlette | BSD-3-Clause | https://github.com/encode/starlette | FastAPI의 기반, 정적 파일 제공 |
| Pydantic | MIT | https://github.com/pydantic/pydantic | 타입 검증 |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn | 서버 실행 |
| HTTPX | BSD-3-Clause | https://github.com/encode/httpx | 실거래가 수집, 테스트 |
| pytest (개발용) | MIT | https://github.com/pytest-dev/pytest | 테스트 |
| Pretendard | SIL Open Font License 1.1 | https://github.com/orioncactus/pretendard | 화면 글꼴 (jsDelivr CDN, v1.3.9) |
| Nanum Gothic Coding | SIL Open Font License 1.1 | https://fonts.google.com/specimen/Nanum+Gothic+Coding | 결과 화면 공고별 계산서의 고정폭 글꼴 (Google Fonts) |
| 국토교통부 전월세 실거래가 자료 | 공공데이터포털 이용허락범위 제한 없음(포털 표기, 확인 필요) | https://www.data.go.kr | 원룸 월세 통계 (수집 2026-11-21, 오피스텔·연립다세대·단독다가구) |
| 행정표준코드관리시스템 법정동 코드 | 확인 필요 | https://www.code.go.kr | 시군구 코드 |
| 행정안전부 인구감소지역 지정 고시 | 정부 고시(확인 필요) | https://www.mois.go.kr | 인구감소지역 92곳 (`data/depop_2026.csv`) |
| Playwright (개발용) | Apache-2.0 | https://github.com/microsoft/playwright | 쇼릴 프레임 캡처, 화면 확인. 배포물에 포함하지 않음 |
| FFmpeg (개발용) | LGPL-2.1 / GPL | https://ffmpeg.org | 쇼릴·첫 화면 영상 인코딩 도구로만 사용. 배포물에 포함하지 않음 |
| 첫 화면 출력 영상 (app/web/img/hero_print.mp4) | 자체 제작 | media/printer/render_hero.py | POS 프린터·감열지 영수증 3D 렌더. Blender 5.3(GPL)은 렌더 도구로만 사용했고 배포물에 포함하지 않음 |
| PublicDataReader (참고만 함) | MIT | https://github.com/WooilJeong/PublicDataReader | 실거래가 API 주소와 필드명 확인. 코드는 가져오지 않음 |

라이선스 표기는 제출 전에 각 저장소의 LICENSE 파일로 한 번 더 확인한다.
