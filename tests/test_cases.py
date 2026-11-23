"""테스트 30건(tests/cases/cases.json)을 모의 방식으로 돌린다. 네트워크와 실제 LLM 은 쓰지 않는다.

케이스마다 '실패한 검사 = 기록한 명세 차이(knownGaps)'인지 본다. 코드를 고쳐 차이가 없어지거나 새로 생기면
이 테스트가 실패하므로 cases.json 의 knownGaps 와 tests/cases/RESULTS.md 를 같이 고친다.
실측은 tests/cases/run_cases.py --mode live|remote 로 따로 돌린다(pytest 가 모으지 않는 이름).
"""
import shutil

import pytest

from app.data import regions as region_data
from tests.cases import evaluate as ev

DATA = ev.load_cases()
UNITS = [u for c in DATA["cases"] for u in ev._units(c, "mock")]


@pytest.fixture()
def real_regions(sample_data_dir):
    # 근무지 케이스(중구, 창원 등)는 전국 지역 표가 필요하다. 월세는 cases.json 의 고정값을 쓴다
    shutil.copy(ev.ROOT / "data" / "regions.csv", sample_data_dir / "regions.csv")
    region_data.reload()
    yield


@pytest.mark.parametrize("unit", UNITS, ids=[f"{u['id']}-{u.get('variantName') or ''}" for u in UNITS])
def test_case_mock(unit, real_regions):
    r = ev.run_unit(ev.Runner("mock"), unit)
    assert r["error"] is None, r["error"]
    assert sorted(r["failed"]) == sorted(unit.get("knownGaps", [])), [c for c in r["checks"] if not c["ok"]]
    if unit["kind"] == "not_implemented":
        assert r["verdict"] == ev.NOT_IMPL
    else:
        assert r["verdict"] == (ev.PASS if not unit.get("knownGaps") else ev.GAP)


def test_all_30_ids_present():
    assert [c["id"] for c in DATA["cases"]] == [f"T{i:02d}" for i in range(1, 31)]


def test_case_postings_are_fictional():
    texts = [DATA["partnerPosting"]] + [c.get("posting", "") for c in DATA["cases"]] + \
            [v.get("posting", "") for c in DATA["cases"] for v in c.get("variants", [])]
    for t in filter(None, texts):
        assert "(가상)" in t.splitlines()[0]


def test_mock_evidence_quotes_are_in_postings():
    """가정한 LLM 응답의 근거 문장이 공고에 실제로 있는지(케이스 자체의 오류 방지). T26 주입 변형은 주입문을 근거로 쓴다."""
    from app.agent.evidence import evidence_in_source
    for u in UNITS:
        raw = u.get("mockLLM") or {}
        for k, v in raw.items():
            if isinstance(v, dict) and v.get("evidence"):
                assert evidence_in_source(v["evidence"], u["posting"]), (u["id"], u.get("variantName"), k)


# ---- 원격 경로: 배포 API 대신 TestClient + FakeLLM 으로 같은 평가 코드를 돌린다 ----

def _remote_fake_llm():
    from app.agent.llm import FakeLLM
    by_posting = {}
    for u in UNITS:
        if u.get("mockLLM"):
            by_posting.setdefault(u["posting"], (u["mockLLM"], u.get("classifyMock")))
    partner = {"companyName": {"value": "보기정밀(가상)", "evidence": "[보기정밀(가상)] 생산기술 엔지니어 신입 채용"},
               "salary": {"amount": 3400, "unit": "만원", "period": "year", "evidence": "급여: 연봉 3,400만원"},
               "workLocationText": {"value": "부산 부산진구 전포동", "evidence": "근무지: 부산 부산진구 전포동"},
               "employmentType": {"value": "regular", "evidence": "고용형태: 정규직"},
               "industryText": {"value": "자동차 부품 제조", "evidence": "사업내용: 자동차 부품 제조"}}
    industry = {raw["industryText"]["value"]: cm for raw, cm in by_posting.values()
                if cm and raw.get("industryText", {}).get("value")}

    def fn(system, user, schema):
        props = schema.get("properties", {})
        if "salary" in props:
            # 공고 전체로 먼저 찾는다(T13 두 변형은 첫 줄이 같다). 개인정보를 가린 공고(T27)는 첫 줄로 찾는다
            for match in (lambda t: t in user, lambda t: t.splitlines()[0] in user):
                for text, (raw, _) in by_posting.items():
                    if match(text):
                        return ev.make_raw(raw)
            return ev.make_raw(partner)
        if "industryName" in props:
            for text, cm in industry.items():
                if text in user:
                    return cm
            return {"industryName": "제조업" if "제조" in user else "unknown", "reason": "모의"}
        return {"text": "두 공고의 계산 결과를 정리했습니다."}
    return FakeLLM(fn=fn)


@pytest.mark.parametrize("cid", ["T01", "T10", "T13", "T15", "T16", "T18", "T21", "T23", "T25", "T27"])
def test_remote_path_offline(cid, monkeypatch, real_regions):
    from fastapi.testclient import TestClient

    from app import config, main
    monkeypatch.setattr(main, "get_llm", _remote_fake_llm)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_IP_PER_DAY", 0)
    monkeypatch.setattr(config, "RATE_LIMIT_TOTAL_PER_DAY", 0)
    with TestClient(main.app) as client:
        runner = ev.Runner("remote", client=client, base_url="")
        case = next(c for c in DATA["cases"] if c["id"] == cid)
        for u in ev._units(case, "remote"):
            r = ev.run_unit(runner, u)
            assert r["error"] is None, r["error"]
            assert sorted(r["failed"]) == sorted(u.get("knownGaps", [])), [c for c in r["checks"] if not c["ok"]]
            if cid in ("T21", "T25") and "remoteRequest" in u:
                assert r["verdict"] == ev.PASS
            if cid == "T27":
                assert any(c["skipped"] and c["name"] == "llmPayload" for c in r["checks"])


def test_remote_units_run_each_distinct_posting():
    """실측 단위: 공고를 물려받는 변형도 실제 공고가 다르면 따로 돈다(T13 두 변형). 가정 응답만 다른 변형은 한 번(T10)."""
    units = lambda cid: ev._units(next(c for c in DATA["cases"] if c["id"] == cid), "remote")
    assert [u["variantName"] for u in units("T13")] == ["명세 문구", "후보 1개만 걸림"]
    assert len({u["posting"] for u in units("T13")}) == 2
    assert [u["variantName"] for u in units("T10")] == [None] and units("T10")[0]["mockLLM"] is None
    assert [u["variantName"] for u in units("T25")] == ["10년", "5년(정부안도 감면 연수 같음)"]
    assert all(u["remoteRequest"]["postings.0.confirmed.housing"]["customMonthly"] == 850000 for u in units("T25"))


def test_run_cases_live_loads_config_before_get_llm():
    """tests/cases/run_cases.py --mode live 는 get_llm 전에 app.config(.env 로더)를 불러야 한다.
    새 인터프리터에서 get_llm 을 '설정이 이미 로드됐는지만 적고 None 을 돌려주는' 가짜로 바꿔 돌린다. 실제 LLM 은 부르지 않는다."""
    import subprocess
    import sys
    code = (
        "import sys\n"
        "from tests.cases import run_cases\n"
        "import app.agent.llm as L\n"
        "L.get_llm = lambda: (print('CONFIG_LOADED' if 'app.config' in sys.modules else 'CONFIG_MISSING'), None)[1]\n"
        "run_cases.run('live', '', ['T01'], 1, 0)\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ev.ROOT, capture_output=True, timeout=60)
    text = out.stdout.decode("utf-8", "replace") + out.stderr.decode("utf-8", "replace")
    assert out.returncode == 0, text[-500:]
    assert "CONFIG_LOADED" in text and "CONFIG_MISSING" not in text
