"""회사 규모 단서(국민연금 가입 사업장 정보). 외부 API는 부르지 않고 가짜 조회 함수를 넣는다."""
import json
from pathlib import Path

from app.data import company
from app.data.company import CompanyHit, apply_company_lookup, normalize_name
from app.schemas import PostingFields

ROOT = Path(__file__).resolve().parents[1]


def _fields(size_value, size_status, name="한빛정밀"):
    saved = json.loads((ROOT / "data/samples/pair1.json").read_text(encoding="utf-8"))["savedExtract"]["fields"]["A"]
    f = PostingFields.model_validate(saved)
    f = f.model_copy(update={
        "company_name": f.company_name.model_copy(update={"value": name}),
        "company_size": f.company_size.model_copy(update={"value": size_value, "status": size_status}),
    })
    return {"A": f}


def test_normalize_name():
    assert normalize_name("(주)한빛 정밀") == "한빛정밀"
    assert normalize_name("주식회사 한빛정밀") == "한빛정밀"


def test_small_headcount_becomes_inferred_sme():
    fields = _fields("unknown", "missing")
    notes = apply_company_lookup(fields, {}, lambda n, h: CompanyHit("한빛정밀", 45, "202610", "48123"))
    f = fields["A"].company_size
    assert f.value == "sme" and f.status == "inferred"
    assert "가입자 45명" in f.note and "2026-10" in f.note
    assert notes == ["A 가입자 45명"]


def test_large_headcount_keeps_value_and_adds_note():
    fields = _fields("unknown", "missing")
    apply_company_lookup(fields, {}, lambda n, h: CompanyHit("한빛정밀", 1200, "202610", "48123"))
    f = fields["A"].company_size
    assert f.value == "unknown" and "300명 이상" in f.note


def test_extracted_or_user_size_is_not_touched():
    called = []
    for value, status in (("sme", "extracted"), ("large", "user")):
        fields = _fields(value, status)
        apply_company_lookup(fields, {}, lambda n, h: called.append(n))
        assert fields["A"].company_size.value == value
    assert called == []


def test_no_hit_changes_nothing():
    fields = _fields("unknown", "missing")
    assert apply_company_lookup(fields, {}, lambda n, h: None) == []
    assert fields["A"].company_size.value == "unknown"


def test_lookup_is_off_without_key_and_skips_virtual_names(monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_KEY_NPS", raising=False)
    assert company.enabled() is False
    assert company.lookup("한빛정밀") is None
    monkeypatch.setenv("DATA_GO_KR_KEY_NPS", "dummy")
    assert company.lookup("예시소프트(가상)") is None


def test_company_endpoint_without_key_returns_not_found(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_KEY_NPS", raising=False)
    r = TestClient(app).get("/api/company", params={"name": "한빛정밀", "sgg": "11680"})
    assert r.status_code == 200 and r.json() == {"found": False}


def test_company_endpoint_returns_hit(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("DATA_GO_KR_KEY_NPS", "dummy")
    monkeypatch.setattr(company, "lookup", lambda n, h=None: CompanyHit("（주）한빛정밀", 45, "202609", "11680"))
    d = TestClient(app).get("/api/company", params={"name": "한빛정밀"}).json()
    assert d["found"] and d["headcount"] == 45 and d["asOf"] == "2026-09" and d["smeLikely"] is True
