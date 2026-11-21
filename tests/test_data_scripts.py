"""데이터 스크립트(scripts/collect_rent.py, build_rent_stats.py, build_regions.py) 테스트.

네트워크를 쓰지 않는다. API 응답은 tests/fixtures 의 가짜 XML 과 httpx.MockTransport 로 흉내 낸다.
"""
import csv
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

import _common  # noqa: E402
import build_regions as br  # noqa: E402
import build_rent_stats as brs  # noqa: E402
import collect_rent as cr  # noqa: E402

KEY = "abcDEF123+/=zzzzKEYvalue"


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# ---------- _common ----------

def test_service_key_encoding_and_redact():
    assert _common.normalize_service_key("abc%2Bdef%3D") == "abc%2Bdef%3D"  # 이미 인코딩: 그대로
    assert _common.normalize_service_key("abc+de/f=") == "abc%2Bde%2Ff%3D"  # 디코딩 키: 인코딩
    url = cr.build_url("http://x.test/1613000/", "officetel", KEY, "11680", "202610")
    assert "%2B" in url and KEY not in url and url.startswith("http://x.test/1613000/RTMSDataSvcOffiRent/")
    assert "LAWD_CD=11680&DEAL_YMD=202610&numOfRows=1000&pageNo=1" in url
    red = _common.redact(f"GET {url} failed; raw {KEY}", KEY)
    assert "serviceKey=***" in red and KEY not in red and "%2B" not in red.split("serviceKey=")[1].split("&")[0]


def test_env_file_parsing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# c\nOTHER=1\nexport DATA_GO_KR_KEY=\"k+1/2=\"  \n", encoding="utf-8")
    assert _common.get_service_key(env={}, env_path=env) == "k+1/2="
    assert _common.get_service_key(env={"DATA_GO_KR_KEY": "fromenv"}, env_path=env) == "fromenv"
    env.write_text("DATA_GO_KR_KEY=\n", encoding="utf-8")
    assert _common.get_service_key(env={}, env_path=env) is None


def test_month_helpers():
    assert _common.month_range("2025-11:2026-02") == ["202511", "202512", "202601", "202602"]
    assert _common.month_range("2026-10,202609") == ["202609", "202610"]
    assert _common.months_before("2026-11", 6) == ["202605", "202606", "202607", "202608", "202609", "202610"]
    assert _common.months_before("2026-11", 12)[0] == "202511"
    with pytest.raises(ValueError):
        _common.month_range("2026-13")


# ---------- collect_rent: 파싱 ----------

def test_parse_ok_many_single_empty():
    page = cr.parse_response(fx("rent_officetel_ok.xml"))
    assert page.total_count == 3 and len(page.items) == 3
    assert page.items[0]["deposit"] == "1,000" and page.items[0]["contractType"] == "신규"
    assert page.items[1]["contractType"] == ""
    one = cr.parse_response(fx("rent_sh_single.xml"))
    assert one.total_count == 1 and len(one.items) == 1 and one.items[0]["totalFloorAr"] == "28.3"
    empty = cr.parse_response(fx("rent_rh_empty.xml"))
    assert empty.items == [] and empty.total_count == 0


def test_parse_error_structures():
    with pytest.raises(cr.ApiError) as e:
        cr.parse_response(fx("rent_error_auth.xml"))
    assert e.value.fatal and e.value.code == "30" and "NOT_REGISTERED" in str(e.value)
    bad = ('<response><header><resultCode>99</resultCode><resultMsg>ERR</resultMsg></header></response>')
    with pytest.raises(cr.ApiError) as e2:
        cr.parse_response(bad)
    assert e2.value.retryable and not e2.value.fatal
    with pytest.raises(cr.ApiError):
        cr.parse_response("<html>gateway error</html>")
    nodata = '<response><header><resultCode>03</resultCode><resultMsg>NODATA_ERROR</resultMsg></header></response>'
    assert cr.parse_response(nodata).items == []


def test_money_and_row_conversion():
    assert cr.parse_man_won("1,000") == 10_000_000
    assert cr.parse_man_won("  60 ") == 600_000
    assert cr.parse_man_won("") is None and cr.parse_man_won("abc") is None
    item = cr.parse_response(fx("rent_officetel_ok.xml")).items[0]
    row = cr.item_to_row(item, "officetel", "11680", "202610", "t")
    assert row["deposit_won"] == 10_000_000 and row["monthly_rent_won"] == 600_000
    assert row["area_m2"] == 24.5 and row["area_basis"] == "excluUseAr" and row["deal_day"] == 5
    assert json.loads(row["raw_json"])["offiNm"] == "가상오피스텔"
    sh = cr.item_to_row(cr.parse_response(fx("rent_sh_single.xml")).items[0], "detached_multi", "11680", "202610", "t")
    assert sh["area_basis"] == "totalFloorAr" and sh["area_m2"] == 28.3


# ---------- collect_rent: 호출(가짜 서버) ----------

def make_fetcher(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    kw.setdefault("sleep", 0)
    return cr.Fetcher(client, KEY, "https://fake.test/1613000/", sleep_fn=lambda s: None, **kw)


def _page_xml(items_xml: str, total: int) -> str:
    return (f"<response><header><resultCode>000</resultCode></header><body><items>{items_xml}</items>"
            f"<totalCount>{total}</totalCount></body></response>")


def test_paging_and_totalcount():
    one = "<item><dealDay>1</dealDay><deposit>1</deposit><monthlyRent>1</monthlyRent></item>"
    seen = []

    def handler(req):
        page = int(req.url.params["pageNo"])
        seen.append(page)
        return httpx.Response(200, text=_page_xml(one * (2 if page == 1 else 1), 3))

    f = make_fetcher(handler, rows=2)
    items, total = f.fetch_key("officetel", "11680", "202610")
    assert len(items) == 3 and total == 3 and seen == [1, 2] and f.calls == 2


def test_retry_then_success_and_failure_has_no_key():
    state = {"n": 0}

    def flaky(req):
        state["n"] += 1
        return httpx.Response(200, text=fx("rent_officetel_ok.xml")) if state["n"] == 3 else httpx.Response(500, text="boom")

    f = make_fetcher(flaky)
    items, _ = f.fetch_key("officetel", "11680", "202610")
    assert len(items) == 3 and f.calls == 3

    def always_500(req):
        return httpx.Response(500, text="boom")

    with pytest.raises(cr.ApiError) as e:
        make_fetcher(always_500).fetch_key("officetel", "11680", "202610")
    assert KEY not in str(e.value) and "3회" in str(e.value)

    def boom(req):
        raise httpx.ConnectError(f"cannot connect {req.url}")

    with pytest.raises(cr.ApiError) as e2:
        make_fetcher(boom).fetch_key("officetel", "11680", "202610")
    assert KEY not in str(e2.value) and "serviceKey=***" in str(e2.value)


def test_fatal_error_stops_without_retry_and_count_mismatch():
    f = make_fetcher(lambda req: httpx.Response(200, text=fx("rent_error_auth.xml")))
    with pytest.raises(cr.ApiError) as e:
        f.fetch_key("officetel", "11680", "202610")
    assert e.value.fatal and f.calls == 1
    one = "<item><dealDay>1</dealDay></item>"
    f2 = make_fetcher(lambda req: httpx.Response(200, text=_page_xml(one, 5) if req.url.params["pageNo"] == "1" else _page_xml("", 5)))
    with pytest.raises(cr.ApiError, match="건수 불일치"):
        f2.fetch_key("officetel", "11680", "202610")


def test_save_key_replaces_and_logs(tmp_path):
    conn = cr.init_db(tmp_path / "r.sqlite")
    items = cr.parse_response(fx("rent_officetel_ok.xml")).items
    assert cr.save_key(conn, "officetel", "11680", "202610", items, 3) == 3
    assert cr.save_key(conn, "officetel", "11680", "202610", items, 3) == 3  # 다시 받아도 중복 없음
    assert conn.execute("SELECT COUNT(*) FROM rent_deals").fetchone()[0] == 3
    assert cr.is_done(conn, "officetel", "11680", "202610") and not cr.is_done(conn, "officetel", "11680", "202609")
    cr.save_key(conn, "row_multi", "11680", "202610", [], 0)  # 0건도 받은 것으로 기록
    assert cr.is_done(conn, "row_multi", "11680", "202610")


def test_main_end_to_end_with_fake_server(tmp_path, monkeypatch, capsys):
    """성공·0건·실패가 섞인 실행 -> 실패 목록 -> --only-failed 재실행. 키가 어디에도 남지 않는다."""
    monkeypatch.setenv("DATA_GO_KR_KEY", KEY)
    mode = {"officetel_ok": False}

    def handler(req):
        path, ym = req.url.path, req.url.params["DEAL_YMD"]
        if "OffiRent" in path and ym == "202610":
            return httpx.Response(200, text=fx("rent_officetel_ok.xml"))
        if "OffiRent" in path and ym == "202609" and not mode["officetel_ok"]:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, text=fx("rent_rh_empty.xml"))

    real_client = httpx.Client
    monkeypatch.setattr(cr.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    db, failed = tmp_path / "r.sqlite", tmp_path / "raw" / "failed.jsonl"
    args = ["--types", "officetel", "--codes", "11680", "--months", "2026-09:2026-10", "--sleep", "0",
            "--retry-wait", "0", "--db", str(db), "--failed-file", str(failed)]
    assert cr.main(args) == 1
    out = capsys.readouterr().out
    assert KEY not in out and "실패" in out
    entries = [json.loads(x) for x in failed.read_text(encoding="utf-8").splitlines()]
    assert [(e["type"], e["code"], e["ym"]) for e in entries] == [("officetel", "11680", "202609")]
    assert KEY not in failed.read_text(encoding="utf-8")
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM rent_deals").fetchone()[0] == 3

    mode["officetel_ok"] = True
    assert cr.main(["--only-failed", "--sleep", "0", "--db", str(db), "--failed-file", str(failed)]) == 0
    assert failed.read_text(encoding="utf-8") == ""
    assert cr.main(args) == 0  # 모두 받음: 건너뜀
    assert "건너뜀 2" in capsys.readouterr().out


def test_plan_and_codes_from_csv(tmp_path):
    keys = cr.plan_keys(["officetel"], ["11680"], ["202609", "202610"])
    assert keys == [("officetel", "11680", "202610"), ("officetel", "11680", "202609")]
    regions = tmp_path / "regions.csv"
    regions.write_text("sggCode,memberCodes\n11680,\n41110,41111|41113\n41111,\n", encoding="utf-8")
    assert cr.read_codes_from_csv(regions) == ["11680", "41111", "41113"]
    with pytest.raises(ValueError):
        cr.validate_codes(["1168"])


# ---------- build_rent_stats ----------

def test_converted_rent_spec_examples():
    assert brs.converted_rent(500_000, 5_000_000, 0.06) == 475_000
    assert brs.converted_rent(400_000, 30_000_000, 0.06) == 500_000
    assert brs.converted_rent(500_000, 10_000_000, "0.06") == 500_000
    assert brs.converted_rent(100_001, 10_000_000 + 1, "0.06") == 100_001  # 0.005 는 올림 아님: 100,001.005 -> 100,001
    assert brs.converted_rent(0, 10_000_000 + 100, "0.06") == 1  # 0.5 -> 올림


def test_percentile_linear_interpolation():
    assert brs.percentile([10, 20, 30, 40], 0.25) == 18  # 10 + 10 x 0.75 = 17.5 -> 18
    assert brs.percentile([10, 20, 30, 40], 0.5) == 25
    assert brs.percentile([7], 0.75) == 7
    assert brs.percentile([475000, 500000, 600000], 0.25) == 487_500
    with pytest.raises(ValueError):
        brs.percentile([], 0.5)


def deal(**kw):
    d = dict(housing_type="officetel", sgg_code="11680", deal_ym="202610", deal_day=5, deposit_won=5_000_000,
             monthly_rent_won=500_000, area_m2=24.0, contract_type="신규")
    d.update(kw)
    return d


def test_keep_deal_rules():
    assert brs.keep_deal(deal()) is None
    assert brs.keep_deal(deal(contract_type="")) is None  # 빈 값은 포함
    assert brs.keep_deal(deal(monthly_rent_won=0)) == brs.R_RENT
    assert brs.keep_deal(deal(monthly_rent_won=None)) == brs.R_RENT
    assert brs.keep_deal(deal(area_m2=33.0)) is None and brs.keep_deal(deal(area_m2=33.01)) == brs.R_AREA
    assert brs.keep_deal(deal(contract_type="갱신")) == brs.R_RENEW
    assert brs.keep_deal(deal(area_m2=0)) == brs.R_ERROR and brs.keep_deal(deal(area_m2=None)) == brs.R_ERROR
    assert brs.keep_deal(deal(deposit_won=-1)) == brs.R_ERROR and brs.keep_deal(deal(deposit_won=None)) == brs.R_ERROR
    assert brs.keep_deal(deal(deal_day=None)) == brs.R_ERROR


def sample_deals():
    return [
        deal(),  # 475,000
        deal(deposit_won=30_000_000, monthly_rent_won=400_000, deal_day=7),  # 500,000
        deal(deposit_won=10_000_000, monthly_rent_won=600_000, deal_day=9),  # 600,000
        deal(monthly_rent_won=0),  # 전세
        deal(area_m2=40.0),
        deal(contract_type="갱신"),
        deal(deal_day=None),
        deal(deposit_won=0, monthly_rent_won=10_000),  # 환산 -40,000
        deal(housing_type="detached_multi", deal_ym="202604", deposit_won=10_000_000, monthly_rent_won=700_000),
        deal(deal_ym="202510"),  # 12개월 밖
        deal(sgg_code="26230", deposit_won=10_000_000, monthly_rent_won=300_000),
    ]


def test_build_stats_structure_and_values():
    excl = Counter()
    doc = brs.build_stats(sample_deals(), as_of="2026-11", conversion_rate=0.06, version="2026-11-22",
                          data_as_of="2026-11-22", exclusions=excl)
    assert list(doc) == ["version", "dataAsOf", "depositBasis", "conversionRate", "housingTypes", "note", "stats", "sidoStats"]
    assert doc["version"] == "2026-11-22" and doc["dataAsOf"] == "2026-11-22"
    assert doc["depositBasis"] == 10_000_000 and doc["conversionRate"] == 0.06
    assert doc["housingTypes"] == ["officetel", "detached_multi"]
    sgg = doc["stats"]["11680"]["sgg"]
    assert sgg == {"period": "2026-05~2026-10", "sampleCount": 3, "p25": 487_500, "monthlyMedian": 500_000,
                   "p75": 550_000, "countsByType": {"officetel": 3}}
    s12 = doc["stats"]["11680"]["sgg_12m"]
    assert s12["period"] == "2025-11~2026-10" and s12["sampleCount"] == 4
    assert (s12["p25"], s12["monthlyMedian"], s12["p75"]) == (493_750, 550_000, 625_000)
    assert s12["countsByType"] == {"officetel": 3, "detached_multi": 1}
    assert doc["sidoStats"]["11"]["sampleCount"] == 3 and doc["sidoStats"]["26"]["monthlyMedian"] == 300_000
    assert doc["stats"]["26230"]["sgg"]["sampleCount"] == 1
    for e in list(doc["stats"].values()):
        for v in e.values():
            assert all(isinstance(v[k], int) for k in ("sampleCount", "p25", "monthlyMedian", "p75"))
    assert excl[brs.R_RENT] == 1 and excl[brs.R_AREA] == 1 and excl[brs.R_RENEW] == 1
    assert excl[brs.R_ERROR] == 1 and excl[brs.R_CONV] == 1 and excl[brs.R_PERIOD] == 1 and excl[brs.KEPT] == 5
    json.dumps(doc, ensure_ascii=False)


def test_build_stats_omits_empty_and_merges_city():
    # 12개월에만 표본이 있으면 sgg 항목은 없고 sgg_12m 만 있다. 표본이 없으면 코드 자체가 없다.
    doc = brs.build_stats([deal(deal_ym="202601", sgg_code="41111"), deal(sgg_code="41113", deal_day=8)],
                          as_of="2026-11", version="v", data_as_of="2026-11-22", city_members={"41110": ["41111", "41113"]})
    assert "sgg" not in doc["stats"]["41111"] and "sgg_12m" in doc["stats"]["41111"]
    assert doc["stats"]["41110"]["sgg"]["sampleCount"] == 1 and doc["stats"]["41110"]["sgg_12m"]["sampleCount"] == 2
    assert doc["sidoStats"]["41"]["sampleCount"] == 1  # 시 행은 시도 집계에 이중으로 들어가지 않는다
    assert brs.build_stats([], as_of="2026-11", version="v", data_as_of="d")["stats"] == {}


def test_stats_main_from_sqlite(tmp_path, capsys):
    db = tmp_path / "r.sqlite"
    conn = cr.init_db(db)
    for ym, items in (("202610", cr.parse_response(fx("rent_officetel_ok.xml")).items),):
        cr.save_key(conn, "officetel", "11680", ym, items, len(items))
    cr.save_key(conn, "detached_multi", "11680", "202610", cr.parse_response(fx("rent_sh_single.xml")).items, 1)
    conn.close()
    out = tmp_path / "rent_stats.json"
    rc = brs.main(["--as-of", "2026-11", "--db", str(db), "--out", str(out), "--regions", str(tmp_path / "none.csv"),
                   "--data-as-of", "2026-11-22"])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    # officetel: 1,000만/60만 -> 600,000 / 500만/50만 -> 475,000 / 갱신 제외, 단독: 2,000만/45만 -> 450,000+50,000=500,000
    s = doc["stats"]["11680"]["sgg"]
    assert s["sampleCount"] == 3 and s["monthlyMedian"] == 500_000
    assert s["countsByType"] == {"officetel": 2, "detached_multi": 1}
    assert doc["version"] == "2026-11-22" and doc["housingTypes"] == ["officetel", "detached_multi"]
    assert "갱신 계약: 1" in capsys.readouterr().out


# ---------- build_regions ----------

def law(code, name, abolished=False):
    return {"code": code, "name": name, "abolished": abolished}


FAKE_LAW = [
    law("1100000000", "서울특별시"), law("1168000000", "서울특별시 강남구"), law("1168010100", "서울특별시 강남구 역삼동"),
    law("2600000000", "부산광역시"), law("2623000000", "부산광역시 부산진구"),
    law("2700000000", "대구광역시"), law("2772000000", "대구광역시 군위군"),
    law("3600000000", "세종특별자치시"), law("3611000000", "세종특별자치시"),
    law("4100000000", "경기도"), law("4111000000", "경기도 수원시"), law("4111100000", "경기도 수원시 장안구"),
    law("4111300000", "경기도 수원시 권선구"), law("4182000000", "경기도 가평군"),
    law("4300000000", "충청북도"), law("4375000000", "충청북도 단양군"),
    law("2900000000", "광주광역시", True), law("2914000000", "광주광역시 서구", True),
    law("5500000000", "전남광주통합특별시"), law("5511000000", "전남광주통합특별시 서구"),
    law("5512000000", "전남광주통합특별시 북구"), law("5521000000", "전남광주통합특별시 순천시"),
    law("5599000000", "전남광주통합특별시 구폐지", True),
]


def test_classify():
    assert br.classify("11", "11680")["regionClass"] == "capital"
    c = br.classify("41", "41111")
    assert (c["typeBase"], c["typePref"]) == (1, 2)
    m = br.classify("26", "26230")
    assert (m["regionClass"], m["typeBase"], m["typePref"], m["classUncertain"]) == ("metro", 2, 3, False)
    s = br.classify("36", "36110")
    assert s["regionClass"] == "metro" and s["classUncertain"] is True
    o = br.classify("43", "43750")
    assert (o["regionClass"], o["typeBase"], o["typePref"]) == ("other", 3, 4)
    gj = br.classify("55", "55110", "55", ["55110", "55120"])
    assert gj["regionClass"] == "metro" and gj["classUncertain"] is True
    jn = br.classify("55", "55210", "55", ["55110", "55120"])
    assert jn["regionClass"] == "other" and jn["classUncertain"] is False


def test_build_region_rows_and_csv(tmp_path):
    depop = [{"code": "", "sido": "충북", "name": "단양군"}, {"code": "", "sido": "대구", "name": "군위군"},
             {"code": "", "sido": "전남", "name": "순천시"}, {"code": "", "sido": "전남", "name": "없는군"}]
    msgs = []
    rows = br.build_region_rows(FAKE_LAW, depop, "55", ["55110", "55120"], msgs.append)
    by = {r["sggCode"]: r for r in rows}
    assert [r["sggCode"] for r in rows] == sorted(by)
    assert "11680" in by and "11000" not in by and "29140" not in by and "55990" not in by  # 동·시도·폐지 행 제외
    assert by["11680"]["aliases"] == ["강남"] and by["11680"]["prefCandidate"] is False
    assert by["36110"]["sggName"] == "" and by["36110"]["classUncertain"] and "세종시" in by["36110"]["aliases"]
    assert by["41110"]["memberCodes"] == ["41111", "41113"] and by["41110"]["sggName"] == "수원시"
    assert by["41111"]["memberCodes"] == [] and by["41111"]["regionClass"] == "capital"
    assert by["27720"]["prefCandidate"] and by["43750"]["prefCandidate"] and by["55210"]["prefCandidate"]
    assert by["55110"]["classUncertain"] and "광주광역시 서구" in by["55110"]["aliases"]
    assert by["55210"]["regionClass"] == "other" and "전라남도 순천시" in by["55210"]["aliases"]
    assert any("미매칭 1곳" in m for m in msgs)

    out = tmp_path / "regions.csv"
    br.write_regions_csv(rows, out)
    with out.open(encoding="utf-8", newline="") as f:
        read = list(csv.DictReader(f))
    assert list(read[0]) == br.COLUMNS and not out.read_bytes().startswith(b"\xef\xbb\xbf")
    r41110 = next(r for r in read if r["sggCode"] == "41110")
    assert r41110["memberCodes"] == "41111|41113" and r41110["prefCandidate"] == "false" and r41110["typeBase"] == "1"


def test_build_region_rows_errors():
    with pytest.raises(br.FormatError, match="--merged-sido-code"):
        br.build_region_rows(FAKE_LAW)  # 전남광주 행이 있는데 옵션이 없다
    with pytest.raises(br.FormatError, match="--old-gwangju-codes"):
        br.build_region_rows(FAKE_LAW, None, "55", [])
    with pytest.raises(br.FormatError, match="파일에 없거나"):
        br.build_region_rows(FAKE_LAW, None, "55", ["55999"])
    with pytest.raises(br.FormatError):
        br.parse_law_rows("code\tname\n1\t2\n")


def test_parse_law_file_and_depop_formats(tmp_path):
    text = "법정동코드\t법정동명\t폐지여부\n1168000000\t서울특별시 강남구\t존재\n1100000000\t서울특별시\t존재\n4100000000\t경기도\t폐지\n"
    rows = br.parse_law_rows(text)
    assert [r["abolished"] for r in rows] == [False, False, True]
    f = tmp_path / "law.txt"
    f.write_bytes(text.encode("cp949"))
    assert br.read_text_any(f) == text
    assert br.parse_depop("sggCode\n27720\n")[0]["code"] == "27720"
    assert br.parse_depop("시도,시군구\n부산,동구\n")[0] == {"code": "", "sido": "부산", "name": "동구"}
    with pytest.raises(br.FormatError, match="sggCode"):
        br.parse_depop("a,b\n1,2\n")


def test_build_regions_main_stops_on_bad_file(tmp_path, capsys):
    bad = tmp_path / "law.txt"
    bad.write_text("코드\t이름\n1\t2\n", encoding="utf-8")
    assert br.main(["--law-code-file", str(bad), "--out", str(tmp_path / "o.csv")]) == 2
    assert "형식 오류" in capsys.readouterr().err and not (tmp_path / "o.csv").exists()


# ---------- CLI ----------

@pytest.mark.parametrize("script", ["collect_rent.py", "build_rent_stats.py", "build_regions.py"])
def test_help(script):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "usage" in r.stdout


def test_dry_run_cli_without_network():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_rent.py"), "--dry-run", "--codes", "11680",
                        "--months", "2026-05:2026-10", "--db", str(ROOT / "nonexistent_dir_for_test" / "x.sqlite")],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode == 0 and "예상 호출 수 18" in r.stdout and "serviceKey=***" in r.stdout
    assert not (ROOT / "nonexistent_dir_for_test").exists()
