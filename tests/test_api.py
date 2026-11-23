"""API 통합 테스트. 실제 데이터 모듈(샘플 스냅샷)과 에이전트 모듈을 쓰고, LLM 은 연결하지 않는다."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.agent.llm import FakeLLM
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


def _extract_with_fake(client, monkeypatch, text, raw):
    llm = FakeLLM(fn=lambda *_: raw)
    monkeypatch.setattr(main, "get_llm", lambda: llm)
    response = client.post("/api/extract", json={"postings": [{"id": pid, "text": text} for pid in ("A", "B")]})
    assert response.status_code == 200, response.json()
    body = response.json()
    questions = {q["field"]: q for q in body["questions"] if q["postingId"] == "A"}
    return body["postings"][0], questions


@pytest.mark.parametrize("body_pay, table_pay, amount, range_max, expected_salary", [
    ("3,800만원", "4,200만원", 3800, None, None),
    ("3,800만원", "3,800만원", 3800, None, 38_000_000),
    ("3,800~4,200만원", "4,200만원", 3800, 4200, 38_000_000),
])
def test_extract_salary_conflict_requires_manual_amount(client, monkeypatch, body_pay, table_pay,
                                                        amount, range_max, expected_salary):
    salary_line = f"급여: 연봉 {body_pay}"
    table_row = f"| 품질관리 | {table_pay} |"
    text = f"근무지: 서울 강남구\n{salary_line}\n\n| 직무 | 연봉 |\n{table_row}"
    raw = {"salary": {"amount": amount, "unit": "만원", "period": "year", "isRange": range_max is not None,
                      "rangeMax": range_max, "evidence": salary_line},
           "workLocationText": {"value": "서울 강남구", "evidence": "근무지: 서울 강남구"}}
    posting, questions = _extract_with_fake(client, monkeypatch, text, raw)
    fields = posting["fields"]
    assert fields["annualSalary"]["value"] == expected_salary
    if expected_salary is None:
        assert fields["annualSalary"]["status"] == "missing"
        assert fields["salaryConflictEvidence"] == [salary_line, table_row]
        question = questions["annualSalary"]
        assert question["required"] and question["inputType"] == "number"
        assert "본문과 표" in question["text"] and "범위" not in question["text"]
    else:
        assert fields["salaryConflictEvidence"] == []
        if range_max is None:
            assert "annualSalary" not in questions
        else:
            assert "범위" in questions["annualSalary"]["text"]


@pytest.mark.parametrize("quote_suffix, source_suffix, codes, field", [
    (" 본사 또는 부산 부산진구 공장", " 본사 또는 부산 부산진구 공장", ["11680", "26230"], "sggCode"),
    (" 본사 혹은 경기 공장", " 본사 혹은 경기 공장", ["11680"], "workLocationText"),
    (" 테헤란로 / 2층", " 테헤란로 / 2층", ["11680"], None),
    (" (정문 또는 후문)", " (정문 또는 후문)", ["11680"], None),
    (" 혹은 경기 공장", "", ["11680"], None),
])
def test_extract_location_alternatives_require_verified_quote(client, monkeypatch, quote_suffix, source_suffix,
                                                             codes, field):
    location = "서울 강남구"
    salary_line = "급여: 연봉 3,800만원"
    text = f"근무지: {location}{source_suffix}\n{salary_line}\n장비: 노트북 또는 데스크톱"
    raw = {"workLocationText": {"value": location, "evidence": f"근무지: {location}{quote_suffix}",
                                "multipleLocations": False},
           "salary": {"amount": 3800, "unit": "만원", "period": "year", "evidence": salary_line}}
    posting, questions = _extract_with_fake(client, monkeypatch, text, raw)
    assert posting["fields"]["multipleLocations"] is (field is not None)
    assert posting["region"]["ambiguous"] is (field is not None)
    assert [candidate["sggCode"] for candidate in posting["region"]["candidates"]] == codes
    assert set(questions) & {"sggCode", "workLocationText"} == ({field} if field else set())
    if field:
        question = questions[field]
        assert question["required"] and "여러 곳" in question["text"]
        if field == "sggCode":
            assert question["inputType"] == "select"
            assert [option["value"] for option in question["options"]] == codes
        else:
            assert question["inputType"] == "text" and "시군구 코드" in question["text"]


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
