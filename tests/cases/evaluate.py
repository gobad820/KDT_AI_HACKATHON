"""테스트 30건 평가기 (docs/agent-spec.md 12장).

세 가지 방식으로 같은 케이스(tests/cases/cases.json)를 같은 기대(expect)로 판정한다.
- mock  : Claude Code가 미리 작성한 '가정한 LLM 응답'(mockLLM)을 FakeLLM 으로 넣고 실제 코드를 검사한다. 네트워크 없음. pytest 가 쓴다.
- live  : 저장소의 LLM 설정(.env, get_llm)으로 실제 모델을 부른다. 명시적으로 실행할 때만 쓴다.
- remote: 배포된 API(--base-url)에 HTTP 로 공고를 보낸다(실행 파일: tests/cases/run_cases.py). 모델명은 API 응답에 없어 확인할 수 없다.

판정: 통과 / 명세 차이(검사 실패) / 미구현 / 오류 / 미측정(그 방식으로 잴 수 없음) / 코드 결정(LLM 무관, 모의와 같은 코드).
키·공고 원문·LLM 요청 본문은 결과 파일에 남기지 않는다. 검사 이름, 기대값, 실제값만 남긴다.
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = Path(__file__).with_name("cases.json")

PASS, GAP, NOT_IMPL, ERROR, NOT_RUN, CODE_ONLY = "통과", "명세 차이", "미구현", "오류", "미측정", "코드 결정"

DEFAULT_RAW = {
    "companyName": {"value": None, "evidence": None},
    "salary": {"amount": None, "unit": None, "period": None, "isRange": False, "rangeMax": None,
               "negotiable": False, "evidence": None},
    "workLocationText": {"value": None, "evidence": None, "multipleLocations": False},
    "employmentType": {"value": "unknown", "evidence": None},
    "companySize": {"value": "unknown", "explicit": False, "evidence": None},
    "industryText": {"value": None, "evidence": None},
    "mealAllowanceMonthly": {"amount": None, "unit": None, "evidence": None},
    "dormitory": {"value": None, "evidence": None},
    "housingSupportMonthly": {"amount": None, "unit": None, "evidence": None},
    "others": [],
}


def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def make_raw(partial: Optional[dict]) -> dict:
    raw = copy.deepcopy(DEFAULT_RAW)
    for k, v in (partial or {}).items():
        if isinstance(v, dict) and isinstance(raw.get(k), dict):
            raw[k].update(v)
        else:
            raw[k] = v
    return raw


def _doc_blocks() -> List[dict]:
    doc = (ROOT / "docs" / "api-spec.md").read_text(encoding="utf-8")
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", doc, flags=re.S)]


def example_request(changes: Optional[dict] = None) -> dict:
    """docs/api-spec.md 5장 예시 요청에 'a.0.b' 꼴 경로로 값을 바꿔 넣는다."""
    data = copy.deepcopy(_doc_blocks()[2])
    for path, value in (changes or {}).items():
        node, keys = data, path.split(".")
        for k in keys[:-1]:
            node = node[int(k)] if k.isdigit() else node.setdefault(k, {})
        node[keys[-1]] = value
    return data


# ---- 검사 기록 ----

class Checks:
    def __init__(self):
        self.items: List[dict] = []

    def add(self, name: str, ok: bool, expected: Any = None, actual: Any = None, skipped: bool = False):
        self.items.append({"name": name, "ok": bool(ok), "expected": expected, "actual": actual, "skipped": skipped})

    def skip(self, name: str, reason: str):
        self.add(name, True, None, reason, skipped=True)

    @property
    def failed(self) -> List[str]:
        return [c["name"] for c in self.items if not c["ok"]]


# ---- LLM 래퍼: 보낸 요청을 메모리에만 기록한다(결과 파일에는 남기지 않는다) ----

class Recorder:
    def __init__(self, llm):
        self.llm, self.calls = llm, []
        self.model_name = getattr(llm, "model_name", "unknown")

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict:
        self.calls.append({"user": user, "schema_keys": sorted((schema or {}).get("properties", {}).keys())})
        return self.llm.complete_json(system=system, user=user, schema=schema, timeout_s=timeout_s)


# ---- 고정 도구(숫자 일치·도구 판단) ----

def fixed_deps(fixed: dict, classify_fn: Callable, explain_fn: Callable, llm_available: bool = True):
    from datetime import datetime

    from app.pipeline import KST, Deps
    from app.schemas import Region, Rent
    regions = {r["sggCode"]: Region.model_validate(r) for r in fixed["regions"]}
    rents = {}
    for r in fixed["rents"]:
        rents[(r["sggCode"], r["scope"])] = Rent(
            monthly_median=r["monthlyMedian"], p25=r["p25"], p75=r["p75"], sample_count=r["sampleCount"],
            period="2026-05~2026-10", housing_types=["officetel", "detached_multi"], scope=r["scope"],
            deposit_basis=10_000_000, conversion_rate=0.06, data_as_of="fixed", sufficient=r["sampleCount"] >= 30)
    return Deps(get_region=regions.get, get_rent_stats=lambda code, scope="sgg": rents.get((code, scope)),
                snapshot_info=lambda: {"version": "fixed", "dataAsOf": "fixed", "isSample": False},
                classify_industry=classify_fn, explain=explain_fn, llm_available=llm_available,
                now=lambda: datetime(2026, 11, 22, 12, 0, 0, tzinfo=KST))


def core_of(res, req_obj):
    from app.schemas import CompareCore
    return CompareCore(jobs=res.jobs, comparison=res.comparison, horizon_years=req_obj.options.horizon_years,
                       hire_year=req_obj.profile.hire_year,
                       company_names={p.id: p.confirmed.company_name for p in req_obj.postings},
                       annual_salaries={p.id: p.confirmed.annual_salary for p in req_obj.postings})


# ---- 실행 환경 ----

class Runner:
    """mode: mock | live | remote. live 는 llm, remote 는 client(httpx.Client 호환)와 base_url 이 필요하다."""

    def __init__(self, mode: str, llm=None, client=None, base_url: str = "", sleep_s: float = 0.0):
        self.mode, self.llm, self.client, self.base_url, self.sleep_s = mode, llm, client, base_url.rstrip("/"), sleep_s
        self.data = load_cases()

    # -- 추출 --
    def extract(self, text: str, mock_raw: Optional[dict]):
        """(fields, region, posting_questions, llm_payloads, degraded)"""
        from app.agent.extract import extract_postings
        from app.agent.llm import FakeLLM
        from app.agent.questions import build_questions
        from app.data.regions import resolve_region
        from app.schemas import PostingFields, PostingInput, Question, RegionResolution
        if self.mode == "remote":
            body = self._post("/api/extract", {"postings": [{"id": "A", "text": text},
                                                            {"id": "B", "text": self.data["partnerPosting"]}]})
            pa = next(p for p in body["postings"] if p["id"] == "A")
            qs = [Question.model_validate(q) for q in body["questions"] if q.get("postingId") == "A"]
            return (PostingFields.model_validate(pa["fields"]), RegionResolution.model_validate(pa["region"]), qs,
                    None, bool(body.get("degraded")))
        llm = Recorder(FakeLLM([make_raw(mock_raw)]) if self.mode == "mock" else self.llm)
        fields = extract_postings([PostingInput(id="A", text=text)], llm)["A"]
        loc = fields.work_location_text.value or ""
        region = resolve_region(loc) if loc.strip() else RegionResolution(candidates=[], ambiguous=True)
        qs = [q for q in build_questions({"A": fields}, {"A": region}) if q.posting_id]
        return fields, region, qs, [c["user"] for c in llm.calls], False

    # -- 계산 --
    def compare(self, req: dict, classify_mock: Optional[dict] = None):
        """(response, core, request_obj). remote 는 배포 서버의 실제 월세를 쓴다."""
        from app.agent import classify, explain
        from app.agent.llm import FakeLLM
        from app.pipeline import run_compare
        from app.schemas import CompareCore, CompareRequest, CompareResponse, NeedsInputResponse
        req_obj = CompareRequest.model_validate(req)
        if self.mode == "remote":
            body = self._post("/api/compare", req)
            if body.get("needsInput"):
                return NeedsInputResponse.model_validate(body), None, req_obj
            res = CompareResponse.model_validate(body)
            return res, core_of(res, req_obj), req_obj
        if self.mode == "mock":
            a_text = next(p.confirmed.industry_text for p in req_obj.postings if p.id == "A")
            # 가정한 분류 응답은 공고 A 의 사업 내용에만 쓴다. 나머지는 LLM 없는 키워드 규칙
            cfn = lambda t: classify.classify_industry(t, FakeLLM([classify_mock]) if classify_mock and t and t == a_text else None)
            efn = lambda core: explain.explain(core, None)
        else:
            rec = Recorder(self.llm)
            cfn = lambda t: classify.classify_industry(t, rec)
            efn = lambda core: explain.explain(core, rec)
        res = run_compare(req_obj, fixed_deps(self.data["fixedData"], cfn, efn))
        if isinstance(res, NeedsInputResponse):
            return res, None, req_obj
        return res, core_of(res, req_obj), req_obj

    def _post(self, path: str, payload: dict) -> dict:
        if self.sleep_s:
            time.sleep(self.sleep_s)
        r = self.client.post(self.base_url + path, json=payload, timeout=60)
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code != 200:
            err = (body or {}).get("error", {})
            raise RemoteError(f"HTTP {r.status_code} {err.get('code', '')} {err.get('fallback', '')}".strip())
        return body


class RemoteError(Exception):
    pass


# ---- 검사 ----

def check_extract(ck: Checks, exp: dict, text: str, fields, region, qs, payloads, mode: str):
    from app.agent.evidence import evidence_in_source
    from app.agent.mask import mask_pii
    masked = mask_pii(text)
    sal = fields.annual_salary
    # 공통 불변식: extracted 로 남은 필드의 근거는 (가린) 원문에 있어야 한다
    bad = []
    for name in ("company_name", "annual_salary", "work_location_text", "employment_type", "company_size", "industry_text"):
        f = getattr(fields, name)
        if f.status == "extracted" and not (f.evidence and evidence_in_source(f.evidence, masked)):
            bad.append(name)
    ck.add("invariant:extractedHasEvidence", not bad, [], bad)
    if "salary" in exp:
        for key, v in exp["salary"].items():
            ck.add(f"salary.{key}", getattr(sal, key) == v, v, getattr(sal, key))
    if "salaryNot" in exp:
        ck.add("salaryNot", sal.value != exp["salaryNot"], f"≠{exp['salaryNot']}", sal.value)
    if "salaryStatusIn" in exp:
        ck.add("salaryStatusIn", sal.status in exp["salaryStatusIn"], exp["salaryStatusIn"], sal.status)
    if exp.get("salaryEvidenceInSource"):
        ck.add("salaryEvidenceInSource", bool(sal.evidence and evidence_in_source(sal.evidence, masked)), True, sal.evidence)
    if "employmentType" in exp:
        ck.add("employmentType", fields.employment_type.value == exp["employmentType"], exp["employmentType"], fields.employment_type.value)
    if "companySize" in exp:
        for key, v in exp["companySize"].items():
            ck.add(f"companySize.{key}", getattr(fields.company_size, key) == v, v, getattr(fields.company_size, key))
    if "location" in exp:
        for key, v in exp["location"].items():
            ck.add(f"location.{key}", getattr(fields.work_location_text, key) == v, v, getattr(fields.work_location_text, key))
    for s in exp.get("othersContain", []):
        ck.add(f"othersContain:{s}", any(s in o for o in fields.benefits.others), s, fields.benefits.others)
    if exp.get("dormitory"):
        ck.add("dormitory", fields.benefits.dormitory.value is True, True, fields.benefits.dormitory.value)
    codes = [c.sgg_code for c in region.candidates]
    rexp = exp.get("region", {})
    if "sggCodes" in rexp:
        ck.add("region.sggCodes", codes == rexp["sggCodes"], rexp["sggCodes"], codes)
    if "ambiguous" in rexp:
        ck.add("region.ambiguous", region.ambiguous == rexp["ambiguous"], rexp["ambiguous"], region.ambiguous)
    if "minCandidates" in rexp:
        ck.add("region.minCandidates", len(codes) >= rexp["minCandidates"], f">={rexp['minCandidates']}", len(codes))
    if rexp.get("undecided"):     # 화면이 자동으로 고를 수 있는 '후보 1개 + 모호하지 않음'이 아니어야 한다
        ck.add("region.undecided", not (len(codes) == 1 and not region.ambiguous), "후보 확정 아님", {"codes": codes, "ambiguous": region.ambiguous})
    qexp = exp.get("questions", {})
    by_field = {}
    for q in qs:
        by_field.setdefault(q.field, q)
    for f in qexp.get("include", []):
        ck.add(f"questions.include:{f}", f in by_field, f, sorted(by_field))
    for f in qexp.get("exclude", []):
        ck.add(f"questions.exclude:{f}", f not in by_field, f"{f} 없음", sorted(by_field))
    for f in qexp.get("required", []):
        ck.add(f"questions.required:{f}", f in by_field and by_field[f].required, True, by_field[f].required if f in by_field else None)
    for f, t in qexp.get("inputType", {}).items():
        ck.add(f"questions.inputType:{f}", f in by_field and by_field[f].input_type == t, t, by_field[f].input_type if f in by_field else None)
    for f, words in qexp.get("textContains", {}).items():
        for w in words:
            txt = by_field[f].text if f in by_field else None
            ck.add(f"questions.textContains:{f}:{w}", bool(txt and w in txt), w, txt)
    for f, words in qexp.get("textExcludes", {}).items():
        for w in words:
            txt = by_field[f].text if f in by_field else None
            ck.add(f"questions.textExcludes:{f}:{w}", not (txt and w in txt), f"'{w}' 없음", txt)
    if "llmPayload" in exp:
        if payloads is None:
            ck.skip("llmPayload", "원격 실행에서는 LLM 요청 본문을 볼 수 없음")
        else:
            sent = "\n".join(payloads)
            for s in exp["llmPayload"].get("notContain", []):
                ck.add(f"llmPayload.notContain:{s}", s not in sent, "보내지 않음", "보냄" if s in sent else "보내지 않음")
            for s in exp["llmPayload"].get("contain", []):
                ck.add(f"llmPayload.contain:{s}", s in sent, s, "있음" if s in sent else "없음")


def check_compare(ck: Checks, exp: dict, res, core, req_obj):
    from app.agent import explain as E
    from app.schemas import NeedsInputResponse
    if isinstance(res, NeedsInputResponse):
        if "needsInput" in exp:
            fields = [q.field for q in res.questions]
            ck.add("needsInput", exp["needsInput"] in fields, exp["needsInput"], fields)
        else:
            ck.add("compare.result", False, "계산 결과", "needsInput")
        return
    if "needsInput" in exp:
        ck.add("needsInput", False, exp["needsInput"], "계산 결과가 나옴")
        return
    jobs = {j.id: j for j in res.jobs}
    if "eligibility" in exp:
        ck.add("eligibility", jobs["A"].eligibility.status == exp["eligibility"], exp["eligibility"], jobs["A"].eligibility.status)
    for rule, r in exp.get("checkResult", {}).items():
        got = next((c.result for c in jobs["A"].eligibility.checks if c.rule == rule), None)
        ck.add(f"checkResult.{rule}", got == r, r, got)
    if "baseScenario" in exp:
        got = E.base_scenario(core)
        ck.add("baseScenario", got == exp["baseScenario"], exp["baseScenario"], got)
    if exp.get("reliefYearsZero"):
        yrs = {s.id: s.relief_years for s in jobs["A"].scenarios}
        ck.add("reliefYearsZero", all(v == 0 for v in yrs.values()), 0, yrs)
    for w in exp.get("hrQuestionContains", []):
        ck.add(f"hrQuestionContains:{w}", w in (jobs["A"].eligibility.hr_question or ""), w, jobs["A"].eligibility.hr_question)
    notices = " / ".join(res.notices)
    for w in exp.get("noticeContains", []):
        ck.add(f"noticeContains:{w}", w in notices, w, notices[:300])
    for jid, v in exp.get("housingMonthly", {}).items():
        ck.add(f"housingMonthly.{jid}", jobs[jid].housing_monthly == v, v, jobs[jid].housing_monthly)
    for jid in exp.get("rentNull", []):
        ck.add(f"rentNull.{jid}", jobs[jid].rent is None, None, "rent 있음" if jobs[jid].rent else None)
    for jid, scope in exp.get("rentScope", {}).items():
        got = jobs[jid].rent.scope if jobs[jid].rent else None
        ck.add(f"rentScope.{jid}", got == scope, scope, got)
    for name, word in exp.get("traceContains", {}).items():
        summ = " / ".join(t.summary for t in res.trace if t.name == name)
        ck.add(f"traceContains:{name}", word in summ, word, summ[:200])
    if exp.get("rentDecisionTrace"):
        dec = [t for t in res.trace if t.type == "decision" and ("넓" in t.summary or "범위" in t.summary)]
        ck.add("rentDecisionTrace", bool(dec), "type=decision 인 범위 확장 기록", [f"{t.type}:{t.name}" for t in res.trace])
    for w in exp.get("explanationContains", []):
        ck.add(f"explanationContains:{w}", w in res.explanation.text, w,
               {"aiGenerated": res.explanation.ai_generated, "text": res.explanation.text[:200]})
    if "scenarios" in exp:
        got = [c.scenario_id for c in res.comparison]
        ck.add("scenarios", got == exp["scenarios"], exp["scenarios"], got)
    if "differenceIsHousingTimesYears" in exp:
        h = req_obj.options.horizon_years
        want = abs(jobs["A"].housing_monthly - jobs["B"].housing_monthly) * 12 * h
        for sid in exp["differenceIsHousingTimesYears"]:
            got = next(c.difference for c in res.comparison if c.scenario_id == sid)
            ck.add(f"differenceIsHousingTimesYears:{sid}", got == want, want, got)


def _confirmed_from(fields, region, partner: dict, housing: Optional[dict]) -> Optional[dict]:
    if len(region.candidates) != 1:
        return None
    return {"companyName": fields.company_name.value or "공고 A", "annualSalary": fields.annual_salary.value,
            "sggCode": region.candidates[0].sgg_code, "companySize": fields.company_size.value or "unknown",
            "industryText": fields.industry_text.value or "", "employmentType": fields.employment_type.value or "unknown",
            "nonTaxableMonthly": 200000, "housing": housing or {"mode": "market_rent", "customMonthly": None}}


# ---- 케이스 실행 ----

def _units(case: dict, mode: str) -> List[dict]:
    """실행 단위. 모의는 변형마다 돈다.
    실측(live/remote)은 실제로 보내는 입력(공고·요청)이 다른 변형마다 한 번씩 돈다. 공고를 물려받는 변형도 그 공고가
    다른 변형과 다르면 따로 돈다(T13). 모든 변형이 같은 입력이면(가정 응답만 다름: T10, T26) 케이스 기대로 한 번 돈다."""
    variants = case.get("variants") or []
    if not variants:
        return [dict(case, variantName=None)]
    merged = [_merge(case, v) for v in variants]
    if mode == "mock":
        return merged
    if not any("posting" in v or "request" in v or "remoteRequest" in v for v in variants):
        return [dict(case, variantName=None, mockLLM=None)]
    out, seen = [], set()
    for u in merged:
        key = json.dumps([u.get("posting"), u.get("request"), u.get("remoteRequest")], ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def _merge(case: dict, v: dict) -> dict:
    out = dict(case)
    out.update({k: v[k] for k in v if k not in ("name", "note", "expect", "request", "remoteRequest")})
    out.pop("variants", None)
    out["expect"] = dict(case.get("expect", {}), **v.get("expect", {}))
    for key in ("request", "remoteRequest"):
        if key in case or key in v:
            out[key] = dict(case.get(key, {}), **v.get(key, {}))
    out["variantName"], out["variantNote"] = v.get("name"), v.get("note")
    return out


def run_unit(runner: Runner, u: dict) -> dict:
    ck = Checks()
    started = time.perf_counter()
    result = {"id": u["id"], "variant": u.get("variantName"), "mode": runner.mode, "verdict": None,
              "checks": ck.items, "failed": [], "knownGaps": u.get("knownGaps", []), "error": None, "note": None}
    kind = u["kind"]
    try:
        if kind == "not_implemented":
            from app import main
            paths = {getattr(r, "path", "") for r in main.app.routes}
            ck.add(f"route:{u['route']}", u["route"] not in paths, "경로 없음(미구현)", "있음" if u["route"] in paths else "없음")
            if u.get("promptRule"):
                txt = (ROOT / u["promptRule"]["file"]).read_text(encoding="utf-8")
                for w in u["promptRule"]["contains"]:
                    ck.add(f"promptRule:{w}", w in txt, w, "있음" if w in txt else "없음")
            result["verdict"] = "재검토(경로가 생김)" if u["route"] in paths else NOT_IMPL
        elif kind == "fallback":
            if runner.mode != "mock":
                result["verdict"], result["note"] = NOT_RUN, "모의 장애로만 잰다(실제 장애를 일으키지 않음)"
            else:
                _run_fallback(ck, u)
        elif kind == "extract":
            fields, region, qs, payloads, degraded = runner.extract(u["posting"], u.get("mockLLM"))
            check_extract(ck, u.get("expect", {}), u["posting"], fields, region, qs, payloads, runner.mode)
            if runner.mode == "remote":
                ck.add("remote.degraded", degraded is False, False, degraded)
            if "compare" in u:
                partner = example_request()["postings"][1]
                conf = _confirmed_from(fields, region, partner, u["compare"].get("housing"))
                if conf is None or not conf["annualSalary"]:
                    ck.add("compare.input", False, "연봉·시군구 확정", {"codes": [c.sgg_code for c in region.candidates],
                                                                     "salary": fields.annual_salary.value})
                else:
                    req = example_request({"options.explanation": "template"})
                    req["postings"][0]["confirmed"] = conf
                    res, core, req_obj = runner.compare(req, u.get("classifyMock"))
                    check_compare(ck, u["compare"]["expect"], res, core, req_obj)
        elif kind == "compare":
            if runner.mode == "remote" and "remoteRequest" not in u:
                result["verdict"], result["note"] = NOT_RUN, "고정 월세가 필요해 원격에서 재지 않음"
            else:
                key = "remoteRequest" if runner.mode == "remote" else "request"
                req = example_request(dict({"options.explanation": "ai"}, **u.get(key, {})))
                res, core, req_obj = runner.compare(req)
                check_compare(ck, u.get("expect", {}), res, core, req_obj)
        elif kind == "numbers":
            _run_numbers(ck, runner, u)
        else:
            raise ValueError(f"알 수 없는 kind: {kind}")
    except Exception as exc:                                        # 케이스 하나가 실패해도 나머지는 돈다
        result["verdict"], result["error"] = ERROR, f"{type(exc).__name__}: {str(exc)[:200]}"
    result["failed"] = ck.failed
    if result["verdict"] is None:
        result["verdict"] = PASS if not ck.failed else GAP
    result["ms"] = round((time.perf_counter() - started) * 1000)
    if runner.mode == "remote" and u.get("remoteNote"):
        result["note"] = u["remoteNote"]
    if u.get("variantNote"):
        result["note"] = (result["note"] + " / " if result["note"] else "") + u["variantNote"]
    return result


def _run_numbers(ck: Checks, runner: Runner, u: dict):
    from app.agent import classify, explain as E, numbers as N
    from app.schemas import CompareRequest, NeedsInputResponse
    h, exp = u["horizon"], u["expect"]
    req = example_request({"options.horizonYears": h, "options.explanation": "template"})
    if runner.mode == "remote":
        # 배포 서버는 실제 월세를 쓴다. 문서의 고정 월세(85만/45만 원)를 직접 입력(custom)으로 넣어 같은 숫자를 대조한다
        for p, m in zip(req["postings"], (850_000, 450_000)):
            p["confirmed"]["housing"] = {"mode": "custom", "customMonthly": m}
        res, core, req_obj = runner.compare(req)
        if isinstance(res, NeedsInputResponse):
            raise RemoteError("needsInput 응답")
        body = runner._post("/api/explain", req)
        e = body.get("explanation") or {}
        ck.add("remote.aiExplanationVerified", bool(e.get("aiGenerated")) and bool(e.get("numbersVerified")),
               {"aiGenerated": True, "numbersVerified": True}, {k: e.get(k) for k in ("aiGenerated", "numbersVerified")})
    else:
        from app.pipeline import run_compare
        req_obj = CompareRequest.model_validate(req)
        res = run_compare(req_obj, fixed_deps(runner.data["fixedData"], lambda t: classify.classify_industry(t, None),
                                              lambda core: E.explain(core, None)))
    core = core_of(res, req_obj)
    cmp = {c.scenario_id: c for c in res.comparison}
    for key, want in exp.get("labels", {}).items():
        sid, what = key.split(".")
        c = cmp[sid]
        got = N.label(c.difference) if what == "difference" else (N.label(c.break_even.annual_salary, exact=True) if c.break_even else None)
        ck.add(f"label:{key}", got == want, want, got)
    values = N.build_value_list(core)
    tpl = E.template_explanation(core)
    ok, bad = N.verify_numbers(tpl, values)
    ck.add("templateNumbersVerified", ok, [], bad)
    for name in exp.get("docTexts", []):
        text = _doc_text(name)
        ok, bad = N.verify_numbers(text, values)
        ck.add(f"docText:{name}", ok, [], bad)
    if exp.get("calcRulesTable"):
        for row in _calc_rules_rows(h):
            for sid in row["scenarios"]:
                jobs = {j.id: {s.id: s for s in j.scenarios} for j in res.jobs}
                got = {"A": jobs["A"][sid].cumulative_remaining, "B": jobs["B"][sid].cumulative_remaining,
                       "diff": cmp[sid].difference, "be": cmp[sid].break_even.annual_salary if cmp[sid].break_even else None,
                       "better": cmp[sid].better_job_id}
                want = {k: row[k] for k in got}
                ck.add(f"calcRules:{h}:{sid}", got == want, want, got)
    jobs_by = {j.id: j for j in res.jobs}
    for key, want in exp.get("briefNumbers", {}).items():
        parts = key.split(".")
        if parts[-1] == "difference":
            got = cmp[parts[0]].difference
        else:
            got = next(s for s in jobs_by[parts[0]].scenarios if s.id == parts[1]).first_year_remaining
        in_doc = want in (ROOT / "docs" / "brief.md").read_text(encoding="utf-8")
        ck.add(f"brief:{key}", in_doc and f"{got:,}" == want, want, f"{got:,}" + ("" if in_doc else " (문서에 숫자 없음)"))
    if runner.mode == "live":
        e = E.explain(core, Recorder(runner.llm))
        ck.add("live.aiExplanationVerified", e.ai_generated and e.numbers_verified,
               {"aiGenerated": True, "numbersVerified": True}, {"aiGenerated": e.ai_generated, "numbersVerified": e.numbers_verified})


def _doc_text(name: str) -> str:
    if name == "api-spec-explanation":
        return _doc_blocks()[3]["explanation"]["text"]
    if name == "agent-spec-8":
        doc = (ROOT / "docs" / "agent-spec.md").read_text(encoding="utf-8")
        line = next(l for l in doc.splitlines() if l.startswith("예시(`docs/api-spec.md`의 예시 쌍, horizonYears 5"))
        return re.search(r'"(.+)"', line).group(1)
    raise ValueError(name)


def _calc_rules_rows(h: int) -> List[dict]:
    """docs/calc-rules.md 7장 회귀 표에서 horizonYears=h 행을 읽는다."""
    doc = (ROOT / "docs" / "calc-rules.md").read_text(encoding="utf-8")
    rows = []
    num = lambda s: int(s.replace(",", ""))
    for line in doc.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 9 and cells[0] == str(h) and cells[3].replace(",", "").isdigit():
            rows.append({"scenarios": [s.strip() for s in cells[1].split(",")], "A": num(cells[3]), "B": num(cells[5]),
                         "better": cells[6], "diff": num(cells[7]), "be": num(cells[8])})
    if not rows:
        raise ValueError(f"calc-rules 표에 horizonYears={h} 행이 없음")
    return rows


def _run_fallback(ck: Checks, u: dict):
    from fastapi.testclient import TestClient

    from app import config, main
    from app.agent.llm import FakeLLM, LLMUnavailable
    exp = u["expect"]
    sample = json.loads((config.DATA_DIR / "samples" / "pair1.json").read_text(encoding="utf-8"))
    timeout = lambda: FakeLLM(fn=lambda s, us, sc: (_ for _ in ()).throw(LLMUnavailable("LLM 호출 시간 초과(모의)")))

    def normal_fn(system, user, schema):
        props = (schema or {}).get("properties", {})
        if "industryName" in props:
            return {"industryName": "정보통신업" if "소프트웨어" in user else "제조업", "reason": "모의"}
        if "text" in props:
            return {"text": "두 공고의 계산 결과를 정리했습니다."}
        raise LLMUnavailable("추출은 이 검사에서 부르지 않음")

    orig_get, orig_limits = main.get_llm, (config.RATE_LIMIT_PER_IP_PER_DAY, config.RATE_LIMIT_TOTAL_PER_DAY)
    try:
        config.RATE_LIMIT_PER_IP_PER_DAY = config.RATE_LIMIT_TOTAL_PER_DAY = 0
        with TestClient(main.app) as c:
            main.get_llm = timeout
            r = c.post("/api/extract", json={"postings": sample["postings"]})
            body = r.json()
            a = next((p for p in body.get("postings", []) if p["id"] == "A"), {})
            got = {"status": r.status_code, "degraded": body.get("degraded"),
                   "salaryA": a.get("fields", {}).get("annualSalary", {}).get("value")}
            ck.add("extractSampleDegraded", got == {"status": 200, "degraded": True, "salaryA": 38_000_000},
                   {"status": 200, "degraded": True, "salaryA": 38_000_000}, got)
            r = c.post("/api/extract", json={"postings": [{"id": "A", "text": "[가상회사(가상)] 채용\n급여: 연봉 3,000만원"},
                                                          {"id": "B", "text": "[가상회사2(가상)] 채용\n급여: 연봉 3,100만원"}]})
            err = r.json().get("error", {})
            ck.add("extractOtherIs503", (r.status_code, err.get("code"), err.get("fallback")) == (503, "LLM_UNAVAILABLE", "manual_input"),
                   [503, "LLM_UNAVAILABLE", "manual_input"], [r.status_code, err.get("code"), err.get("fallback")])
            req = example_request({"options.explanation": "ai"})
            main.get_llm = lambda: FakeLLM(fn=normal_fn)
            ok_body = c.post("/api/compare", json=req).json()
            main.get_llm = timeout
            bad_body = c.post("/api/compare", json=req).json()
        strip = lambda b: [{k: j[k] for k in ("pay", "scenarios", "housingMonthly")} for j in b["jobs"]] + [b["comparison"]]
        ck.add("compareAmountsEqual", strip(ok_body) == strip(bad_body), "정상 흐름과 같은 금액",
               "같음" if strip(ok_body) == strip(bad_body) else "다름")
        ck.add("compareFallbackExplanation", bad_body["explanation"]["aiGenerated"] is False, False, bad_body["explanation"]["aiGenerated"])
        ck.add("compareDegraded", bad_body["degraded"] is True, True, bad_body["degraded"])
    finally:
        main.get_llm = orig_get
        config.RATE_LIMIT_PER_IP_PER_DAY, config.RATE_LIMIT_TOTAL_PER_DAY = orig_limits


def run_all(runner: Runner, only: Optional[List[str]] = None, on_result: Optional[Callable] = None) -> List[dict]:
    out = []
    for case in runner.data["cases"]:
        if only and case["id"] not in only:
            continue
        for u in _units(case, runner.mode):
            if runner.mode == "live" and u["kind"] == "compare" and u["id"] not in ("T19", "T22"):
                r = {"id": u["id"], "variant": u.get("variantName"), "mode": "live", "verdict": CODE_ONLY, "checks": [],
                     "failed": [], "knownGaps": u.get("knownGaps", []), "error": None, "ms": 0,
                     "note": "LLM 이 금액·판정에 관여하지 않음. 모의와 같은 코드"}
            else:
                r = run_unit(runner, u)
            out.append(r)
            if on_result:
                on_result(r)
    return out
