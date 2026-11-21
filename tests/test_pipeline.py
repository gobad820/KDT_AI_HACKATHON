"""결정적 파이프라인. 도구는 가짜를 넣어 다른 모듈과 무관하게 검사한다."""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from app.errors import ApiError
from app.pipeline import KST, Deps, basic_explanation, run_compare
from app.schemas import CompareRequest, CompareResponse, NeedsInputResponse, Region, Rent, dump

DOC = (Path(__file__).resolve().parent.parent / "docs" / "api-spec.md").read_text(encoding="utf-8")
BLOCKS = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", DOC, flags=re.S)]
EXAMPLE_REQ, EXAMPLE_RES = BLOCKS[2], BLOCKS[3]

REGIONS = {
    "11680": Region(sgg_code="11680", name="서울특별시 강남구", region_class="capital", type_base=1, type_pref=2),
    "26230": Region(sgg_code="26230", name="부산광역시 부산진구", region_class="metro", type_base=2, type_pref=3),
    "27720": Region(sgg_code="27720", name="대구광역시 군위군", region_class="metro", type_base=2, type_pref=3, pref_candidate=True),
    "36110": Region(sgg_code="36110", name="세종특별자치시", region_class="metro", type_base=2, type_pref=3, class_uncertain=True),
}


def rent(median, p25, p75, n, scope="sgg"):
    return Rent(monthly_median=median, p25=p25, p75=p75, sample_count=n, period="2026-05~2026-10",
                housing_types=["officetel", "detached_multi"], scope=scope, deposit_basis=10_000_000,
                conversion_rate=0.06, data_as_of="2026-11-22", sufficient=n >= 30)


RENTS = {
    ("11680", "sgg"): rent(850_000, 720_000, 1_010_000, 412),
    ("26230", "sgg"): rent(450_000, 380_000, 540_000, 188),
    ("27720", "sgg"): rent(300_000, 250_000, 350_000, 12),
    ("27720", "sgg_12m"): rent(310_000, 260_000, 360_000, 21, "sgg_12m"),
    ("27720", "sido"): rent(420_000, 350_000, 500_000, 300, "sido"),
    ("36110", "sgg"): rent(500_000, 420_000, 600_000, 9),
}
INDUSTRY = {"기업용 소프트웨어 개발": ("정보통신업", "공고의 '사업내용: 기업용 소프트웨어 개발'을 정보통신업으로 분류"),
            "자동차 부품 제조": ("제조업", "공고의 '사업내용: 자동차 부품 제조'를 제조업으로 분류"),
            "은행": ("excluded", "금융·보험업은 대상 업종이 아님")}


def deps(**over):
    base = dict(
        get_region=REGIONS.get,
        get_rent_stats=lambda code, scope="sgg": RENTS.get((code, scope)),
        snapshot_info=lambda: {"version": "2026-11-22", "dataAsOf": "2026-11-22", "isSample": False},
        classify_industry=lambda text: INDUSTRY.get(text, ("unknown", "업종을 분류하지 못함")),
        explain=basic_explanation, llm_available=True,
        now=lambda: datetime(2026, 11, 22, 15, 20, 31, tzinfo=KST),
    )
    base.update(over)
    return Deps(**base)


def request(**changes):
    data = json.loads(json.dumps(EXAMPLE_REQ))
    for path, value in changes.items():
        node, keys = data, path.split(".")
        for k in keys[:-1]:
            node = node[int(k)] if k.isdigit() else node[k]
        node[keys[-1]] = value
    return CompareRequest.model_validate(data)


def test_api_spec_example_numbers():
    """docs/api-spec.md 의 예시 요청을 넣으면 예시 응답의 금액이 그대로 나온다."""
    res = run_compare(request(), deps())
    assert isinstance(res, CompareResponse)
    got = dump(res)
    for job, expected in zip(got["jobs"], EXAMPLE_RES["jobs"]):
        assert job["region"] == expected["region"]
        assert job["rent"] == expected["rent"]
        assert job["housingMonthly"] == expected["housingMonthly"]
        assert job["pay"] == expected["pay"]
        assert job["eligibility"]["status"] == expected["eligibility"]["status"]
        assert [c["rule"] for c in job["eligibility"]["checks"]] == [c["rule"] for c in expected["eligibility"]["checks"]]
        for s, e in zip(job["scenarios"], expected["scenarios"]):
            assert {k: v for k, v in s.items() if k != "yearly"} == {k: v for k, v in e.items() if k != "yearly"}
            assert len(s["yearly"]) == 10
            for row in e["yearly"]:                          # 문서에는 일부 연차만 실려 있다
                assert s["yearly"][row["year"] - 1] == row
    assert got["comparison"] == EXAMPLE_RES["comparison"]
    assert got["dataVersion"] == EXAMPLE_RES["dataVersion"]
    assert got["generatedAt"] == EXAMPLE_RES["generatedAt"]
    assert got["degraded"] is False
    assert [t["name"] for t in got["trace"]] == ["get_rent_stats", "check_relief_rules", "scenario_selection", "simulate", "explanation"]
    assert got["notices"][1:4] == EXAMPLE_RES["notices"][1:4]
    assert {s["url"] for s in EXAMPLE_RES["sources"]} == {s["url"] for s in got["sources"]}


def test_scope_widening_and_pref_candidate_notice():
    res = run_compare(request(**{"postings.1.confirmed.sggCode": "27720"}), deps())
    job = next(j for j in res.jobs if j.id == "B")
    assert job.rent.scope == "sido" and job.housing_monthly == 420_000
    assert "넓힘" in res.trace[0].summary
    assert any("우대지역" in n and "확정이 아닙니다" in n for n in res.notices)


def test_needs_input_when_no_sufficient_rent():
    res = run_compare(request(**{"postings.1.confirmed.sggCode": "36110"}), deps())
    assert isinstance(res, NeedsInputResponse) and res.needs_input is True
    assert res.questions[0].posting_id == "B" and res.questions[0].field == "housing.customMonthly"
    # 사용자가 월세를 직접 넣으면 계산된다
    res2 = run_compare(request(**{"postings.1.confirmed.sggCode": "36110",
                                  "postings.1.confirmed.housing": {"mode": "custom", "customMonthly": 500_000}}), deps())
    job = next(j for j in res2.jobs if j.id == "B")
    assert job.rent is None and job.housing_monthly == 500_000
    assert any("분류가 정해지지 않아" in n for n in res2.notices)


def test_dormitory_means_zero_housing():
    res = run_compare(request(**{"postings.1.confirmed.housing": {"mode": "dormitory", "customMonthly": None}}), deps())
    job = next(j for j in res.jobs if j.id == "B")
    assert job.rent is None and job.housing_monthly == 0
    assert job.scenarios[0].yearly[0].housing_annual == 0


def test_unlikely_job_gets_no_relief_in_any_scenario():
    res = run_compare(request(**{"postings.0.confirmed.companySize": "large"}), deps())
    job = next(j for j in res.jobs if j.id == "A")
    assert job.eligibility.status == "unlikely"
    assert all(s.relief_years == 0 for s in job.scenarios)
    assert any("공고 A" in n and "감면 없음" in n for n in res.notices)


def test_degraded_without_llm_and_template_notice():
    res = run_compare(request(), deps(llm_available=False, classify_industry=lambda t: ("unknown", "업종을 분류하지 못함")))
    assert res.degraded is True
    assert all(j.eligibility.status == "uncertain" for j in res.jobs)
    assert res.explanation.ai_generated is False and res.notices[0].startswith("금액은 서버의 계산 코드가")


def test_sample_snapshot_notice_and_min_wage_warning():
    res = run_compare(request(**{"postings.1.confirmed.annualSalary": 25_000_000}),
                      deps(snapshot_info=lambda: {"version": "sample", "dataAsOf": "sample", "isSample": True}))
    assert any("설명용 임의 데이터" in n for n in res.notices)
    assert any("최저임금" in n and "공고 B" in n for n in res.notices)


@pytest.mark.parametrize("path,value", [
    ("postings.0.confirmed.annualSalary", 0),
    ("postings.0.confirmed.sggCode", "99999"),
    ("postings.0.confirmed.nonTaxableMonthly", 5_000_000),
    ("postings.0.confirmed.housing", {"mode": "custom", "customMonthly": None}),
])
def test_invalid_input(path, value):
    with pytest.raises(ApiError) as exc:
        run_compare(request(**{path: value}), deps())
    assert exc.value.code == "INVALID_INPUT" and exc.value.status == 400


def test_profile_never_reaches_explainer_or_classifier():
    seen = []
    def spy_explain(core):
        seen.append(json.dumps(dump(core), ensure_ascii=False))
        return basic_explanation(core)
    def spy_classify(text):
        seen.append(text)
        return ("제조업", "제조업으로 분류")
    req = request(**{"profile.age": 31, "profile.militaryServiceMonths": 23})
    run_compare(req, deps(explain=spy_explain, classify_industry=spy_classify))
    blob = " ".join(seen)
    # 판정 결과("rule": "age")는 넘어가도 되지만 입력값 자체는 넘어가면 안 된다
    assert '"age":' not in blob and "militaryServiceMonths" not in blob and "priorRelief" not in blob



def test_template_explanation_skips_llm_but_keeps_amounts():
    """options.explanation=template 이면 설명문 LLM을 부르지 않고, 금액은 ai 와 같다."""
    called = []
    def explain(core):
        called.append(1)
        return basic_explanation(core)
    ai = run_compare(request(), deps(explain=explain))
    tpl = run_compare(request(**{"options.explanation": "template"}), deps(explain=explain))
    assert len(called) == 1
    assert tpl.explanation.ai_generated is False
    assert [j.pay for j in tpl.jobs] == [j.pay for j in ai.jobs] and tpl.comparison == ai.comparison


def test_industry_classification_runs_for_both_postings_in_parallel():
    import threading, time as _t
    seen, lock = [], threading.Lock()
    def classify(text):
        with lock:
            seen.append(threading.get_ident())
        _t.sleep(0.2)
        return INDUSTRY.get(text, ("unknown", "업종을 분류하지 못함"))
    started = _t.perf_counter()
    run_compare(request(), deps(classify_industry=classify))
    assert len(seen) == 2 and _t.perf_counter() - started < 0.35     # 0.2초 두 번을 순차로 부르면 0.4초 이상
