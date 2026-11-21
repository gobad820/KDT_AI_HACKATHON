"""지역 표와 월세 스냅샷 조회 (서버가 쓰는 부분)."""
import json

import pytest

from app import config
from app.data import regions, rent


def test_get_region():
    r = regions.get_region("11680")
    assert (r.name, r.region_class, r.type_base, r.type_pref) == ("서울특별시 강남구", "capital", 1, 2)
    g = regions.get_region("27720")
    assert g.pref_candidate is True and g.class_uncertain is False
    s = regions.get_region("36110")
    assert s.name == "세종특별자치시" and s.class_uncertain is True
    assert regions.get_region("99999") is None


@pytest.mark.parametrize("text,code", [
    ("서울 강남구 테헤란로 000", "11680"),
    ("서울 강남구 역삼동", "11680"),
    ("서울특별시 강남구 (OO빌딩 5층)", "11680"),
    ("부산 부산진구 전포동", "26230"),
    ("부산광역시 부산진구", "26230"),
    ("대구 군위군 군위읍", "27720"),
    ("세종시 한누리대로", "36110"),
])
def test_resolve_single(text, code):
    res = regions.resolve_region(text)
    assert [c.sgg_code for c in res.candidates] == [code] and res.ambiguous is False


@pytest.mark.parametrize("text", ["중구", "", "재택근무", "서울", "서울 본사 또는 부산 공장", "경기 성남시 분당구"])
def test_resolve_ambiguous_or_missing(text):
    assert regions.resolve_region(text).ambiguous is True


def test_rent_stats_sample():
    a = rent.get_rent_stats("11680")
    assert (a.monthly_median, a.p25, a.p75, a.sample_count, a.scope, a.sufficient) == (850_000, 720_000, 1_010_000, 412, "sgg", True)
    assert rent.get_rent_stats("26230").sample_count == 188
    assert rent.get_rent_stats("27720").sufficient is False
    assert rent.get_rent_stats("27720", "sgg_12m").sufficient is False
    s = rent.get_rent_stats("27720", "sido")
    assert s.sufficient is True and s.scope == "sido" and s.monthly_median == 420_000
    assert rent.get_rent_stats("99999") is None
    assert rent.get_rent_stats("36110", "sido") is None
    assert rent.snapshot_info()["isSample"] is True
    with pytest.raises(ValueError):
        rent.get_rent_stats("11680", "nearby")


def test_real_snapshot_is_preferred(tmp_path, monkeypatch):
    (tmp_path / "regions.csv").write_text((config.DATA_DIR / "regions.csv").read_text(encoding="utf-8"), encoding="utf-8")
    real = {"version": "2026-11-22", "dataAsOf": "2026-11-22", "depositBasis": 10_000_000, "conversionRate": 0.06,
            "housingTypes": ["officetel"], "stats": {"11680": {"sgg": {"period": "2026-05~2026-10", "sampleCount": 40,
            "p25": 1, "monthlyMedian": 2, "p75": 3}}}, "sidoStats": {}}
    (tmp_path / "rent_stats.json").write_text(json.dumps(real), encoding="utf-8")
    (tmp_path / "rent_stats.sample.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    rent.reload(); regions.reload()
    try:
        assert rent.snapshot_info() == {"version": "2026-11-22", "dataAsOf": "2026-11-22", "isSample": False}
        r = rent.get_rent_stats("11680")
        assert r.monthly_median == 2 and r.housing_types == ["officetel"] and r.data_as_of == "2026-11-22"
    finally:
        monkeypatch.undo()
        rent.reload(); regions.reload()
