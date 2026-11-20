"""감면 대상 가능성 판정."""
from app.relief.industries import EXCLUDED, UNKNOWN
from app.relief.rules import check_relief_rules
from app.schemas import CHECK_RULES, Profile

P = Profile(age=26, military_service_months=18, hire_year=2027, prior_relief="no")


def result(el, rule):
    return next(c.result for c in el.checks if c.rule == rule)


def test_likely_and_all_five_checks():
    el = check_relief_rules("sme", "제조업", "regular", P)
    assert el.status == "likely"
    assert tuple(c.rule for c in el.checks) == CHECK_RULES
    assert el.hr_question and "원" not in el.hr_question


def test_unlikely_cases():
    assert check_relief_rules("large", "제조업", "regular", P).status == "unlikely"
    assert check_relief_rules("public", "정보통신업", "regular", P).status == "unlikely"
    assert check_relief_rules("sme", EXCLUDED, "regular", P).status == "unlikely"
    assert check_relief_rules("sme", "제조업", "daily", P).status == "unlikely"
    old = Profile(age=40, military_service_months=24, hire_year=2027, prior_relief="no")
    assert check_relief_rules("sme", "제조업", "regular", old).status == "unlikely"


def test_uncertain_cases():
    assert check_relief_rules("unknown", "제조업", "regular", P).status == "uncertain"
    assert check_relief_rules("sme", UNKNOWN, "regular", P).status == "uncertain"
    assert check_relief_rules("sme", "제조업", "regular", P.model_copy(update={"prior_relief": "yes"})).status == "uncertain"
    assert check_relief_rules("sme", "목록에 없는 이름", "regular", P).status == "uncertain"


def test_age_with_military_service():
    # 만 36세, 병역 24개월: 34세 0개월 ~ 34세 11개월 -> 통과
    assert result(check_relief_rules("sme", "제조업", "regular", Profile(age=36, military_service_months=24)), "age") == "pass"
    # 만 36세, 병역 18개월: 34세 6개월 ~ 35세 5개월 -> 생일에 따라 달라짐
    assert result(check_relief_rules("sme", "제조업", "regular", Profile(age=36, military_service_months=18)), "age") == "unknown"
    # 만 35세, 병역 없음 -> 불가
    assert result(check_relief_rules("sme", "제조업", "regular", Profile(age=35)), "age") == "fail"
    # 병역 기간은 6년까지만 뺀다
    assert result(check_relief_rules("sme", "제조업", "regular", Profile(age=42, military_service_months=120)), "age") == "fail"


def test_evidence_does_not_leak_profile_values():
    el = check_relief_rules("sme", "제조업", "regular", Profile(age=29, military_service_months=21, prior_relief="no"))
    text = " ".join(c.evidence for c in el.checks)
    assert "29" not in text and "21" not in text
