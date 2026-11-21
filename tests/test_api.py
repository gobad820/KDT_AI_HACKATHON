"""API 통합 테스트. 실제 데이터 모듈(샘플 스냅샷)과 에이전트 모듈을 쓰고, LLM 은 연결하지 않는다."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.data import rent as rent_data

DOC = (Path(__file__).resolve().parent.parent / "docs" / "api-spec.md").read_text(encoding="utf-8")
BLOCKS = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", DOC, flags=re.S)]
EXTRACT_REQ, EXTRACT_RES, COMPARE_REQ, COMPARE_RES = BLOCKS[0], BLOCKS[1], BLOCKS[2], BLOCKS[3]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(main, "get_llm", lambda: None)          # LLM 미연결 상태
    monkeypatch.setattr(config, "RATE_LIMIT_PER_IP_PER_DAY", 0)
    monkeypatch.setattr(config, "RATE_LIMIT_TOTAL_PER_DAY", 0)
    main._counts.clear()
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["dataVersion"]["rules"] == "2026-v1"
    assert body["dataVersion"]["rent"] == rent_data.snapshot_info()["version"]


def test_samples_are_fictional_pairs(client):
    samples = client.get("/api/samples").json()["samples"]
    assert len(samples) >= 2
    for s in samples:
        assert [p["id"] for p in s["postings"]] == ["A", "B"]
        assert all("(가상)" in p["text"] for p in s["postings"])
        assert "savedExtract" not in s


def test_extract_sample_without_llm_uses_saved_result(client):
    res = client.post("/api/extract", json=EXTRACT_REQ)
    assert res.status_code == 200
    body = res.json()
    assert body["degraded"] is True
    a, b = body["postings"]
    assert a["fields"]["annualSalary"]["value"] == 38_000_000 and b["fields"]["annualSalary"]["value"] == 34_000_000
    assert a["region"]["candidates"][0]["sggCode"] == "11680" and a["region"]["ambiguous"] is False
    assert b["region"]["candidates"][0]["sggCode"] == "26230"
    assert b["fields"]["companySize"]["status"] == "missing"
    posting_qs = [q for q in body["questions"] if q["postingId"]]
    assert any(q["postingId"] == "B" and q["field"] == "companySize" for q in posting_qs)
    profile_fields = [q["field"] for q in body["questions"] if q["postingId"] is None]
    assert profile_fields == ["profile.age", "profile.militaryServiceMonths", "profile.hireYear", "profile.priorRelief"]
    assert [t["step"] for t in body["trace"]] == list(range(1, len(body["trace"]) + 1))


def test_extract_unknown_text_without_llm_falls_back_to_manual_input(client):
    req = {"postings": [{"id": "A", "text": "아무 공고 A"}, {"id": "B", "text": "아무 공고 B"}]}
    res = client.post("/api/extract", json=req)
    assert res.status_code == 503
    assert res.json()["error"] == {"code": "LLM_UNAVAILABLE", "message": res.json()["error"]["message"], "fallback": "manual_input"}


@pytest.mark.parametrize("payload", [
    {"postings": [{"id": "A", "text": "하나뿐"}]},
    {"postings": [{"id": "A", "text": ""}, {"id": "B", "text": "내용"}]},
    {"postings": [{"id": "A", "text": "가" * 9000}, {"id": "B", "text": "내용"}]},
    {"wrong": 1},
])
def test_extract_invalid_input(client, payload):
    res = client.post("/api/extract", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT" and res.json()["error"]["fallback"] == "fix_input"


def test_compare_example_numbers_without_llm(client):
    """LLM 이 없어도 금액은 문서 예시와 같다. 달라지는 것은 설명 문장과 업종 판정뿐이다."""
    res = client.post("/api/compare", json=COMPARE_REQ)
    assert res.status_code == 200
    body = res.json()
    assert body["degraded"] is True
    for job, expected in zip(body["jobs"], COMPARE_RES["jobs"]):
        assert job["pay"] == expected["pay"]
        assert job["housingMonthly"] == expected["housingMonthly"]
        assert job["rent"]["monthlyMedian"] == expected["rent"]["monthlyMedian"]
        assert job["rent"]["sampleCount"] == expected["rent"]["sampleCount"]
        assert job["eligibility"]["status"] == expected["eligibility"]["status"]   # 키워드 규칙으로 업종 분류
        for s, e in zip(job["scenarios"], expected["scenarios"]):
            assert (s["id"], s["reliefYears"], s["cumulativeRemaining"]) == (e["id"], e["reliefYears"], e["cumulativeRemaining"])
    assert body["comparison"] == COMPARE_RES["comparison"]
    assert body["explanation"]["aiGenerated"] is False and body["explanation"]["text"]
    assert len(body["notices"]) >= 4 and len(body["assumptions"]) >= 5


def test_compare_region_with_few_samples_widens_scope(client):
    req = json.loads(json.dumps(COMPARE_REQ))
    req["postings"][1]["confirmed"]["sggCode"] = "27720"
    body = client.post("/api/compare", json=req).json()
    job = body["jobs"][1]
    assert job["rent"]["scope"] == "sido" and job["rent"]["sufficient"] is True
    assert job["region"]["prefCandidate"] is True


def test_compare_dormitory(client):
    req = json.loads(json.dumps(COMPARE_REQ))
    req["postings"][1]["confirmed"]["housing"] = {"mode": "dormitory", "customMonthly": None}
    job = client.post("/api/compare", json=req).json()["jobs"][1]
    assert job["rent"] is None and job["housingMonthly"] == 0


def test_compare_invalid_input(client):
    req = json.loads(json.dumps(COMPARE_REQ))
    req["postings"][0]["confirmed"]["sggCode"] = "99999"
    res = client.post("/api/compare", json=req)
    assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_INPUT"
    res = client.post("/api/compare", json={"postings": []})
    assert res.status_code == 400 and res.json()["error"]["fallback"] == "fix_input"


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_IP_PER_DAY", 1)
    assert client.post("/api/compare", json=COMPARE_REQ).status_code == 200
    res = client.post("/api/compare", json=COMPARE_REQ)
    assert res.status_code == 429
    assert res.json()["error"] == {"code": "RATE_LIMITED", "message": res.json()["error"]["message"], "fallback": "sample_mode"}


def test_profile_is_not_logged(client, caplog):
    req = json.loads(json.dumps(COMPARE_REQ))
    req["profile"]["age"] = 33
    req["profile"]["militaryServiceMonths"] = 21
    with caplog.at_level("INFO", logger="app"):
        client.post("/api/compare", json=req)
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "militaryServiceMonths" not in text and '"age"' not in text and "예시소프트" not in text



def test_explain_endpoint_returns_explanation_and_notices(client):
    res = client.post("/api/explain", json=COMPARE_REQ)
    assert res.status_code == 200
    body = res.json()
    assert body["explanation"]["text"] and body["explanation"]["aiGenerated"] is False      # LLM 미연결이면 템플릿
    assert len(body["notices"]) >= 4


def test_compare_template_option(client):
    req = dict(COMPARE_REQ, options=dict(COMPARE_REQ.get("options", {}), explanation="template"))
    res = client.post("/api/compare", json=req)
    assert res.status_code == 200 and res.json()["explanation"]["aiGenerated"] is False
