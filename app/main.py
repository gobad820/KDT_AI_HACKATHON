"""API 서버. 경로와 형식은 docs/api-spec.md.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import json
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.calc import constants as C
from app.errors import ApiError, invalid_input, llm_unavailable, posting_unreadable, rate_limited
from app.pipeline import KST, Deps, basic_explanation, new_request_id, run_compare
from app.schemas import (CompareRequest, DataVersion, ExtractedPosting, ExtractRequest, ExtractResponse,
                         HealthResponse, PostingFields, PostingInput, RegionResolution, Sample, SamplesResponse,
                         TraceStep, dump)

log = logging.getLogger("app")


# ---- 도구 연결 (테스트에서 바꿔 끼울 수 있게 함수로 둔다) ----

def get_llm():
    from app.agent.llm import get_llm as _get
    return _get()


def build_deps(llm) -> Deps:
    from app.agent import classify, explain
    from app.data import regions, rent
    return Deps(
        get_region=regions.get_region,
        get_rent_stats=rent.get_rent_stats,
        snapshot_info=rent.snapshot_info,
        classify_industry=lambda text: classify.classify_industry(text, llm),
        explain=lambda core: explain.explain(core, llm),
        hr_question=getattr(explain, "hr_question", None),
        llm_available=llm is not None,
    )


def snapshot_info() -> dict:
    from app.data import rent
    return rent.snapshot_info()


# ---- 샘플 공고 ----

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_samples() -> list:
    out = []
    for path in sorted((config.DATA_DIR / "samples").glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def find_saved_extract(postings) -> Optional[Dict[str, PostingFields]]:
    """요청이 샘플 공고와 같으면 저장본을 돌려준다. LLM 을 쓸 수 없을 때만 쓴다."""
    texts = {p.id: _norm(p.text) for p in postings}
    for sample in load_samples():
        saved = sample.get("savedExtract")
        if not saved:
            continue
        if {p["id"]: _norm(p["text"]) for p in sample["postings"]} == texts:
            return {pid: PostingFields.model_validate(f) for pid, f in saved["fields"].items()}
    return None


# ---- 사용량 한도 (메모리, 하루 단위) ----

_counts: Dict[Tuple[str, str], int] = {}


def check_rate_limit(request: Request) -> None:
    per_ip, total = config.RATE_LIMIT_PER_IP_PER_DAY, config.RATE_LIMIT_TOTAL_PER_DAY
    if not per_ip and not total:
        return
    day = datetime.now(KST).strftime("%Y%m%d")
    ip = request.client.host if request.client else "unknown"
    for key in [k for k in _counts if k[0] != day]:
        del _counts[key]
    if (per_ip and _counts.get((day, ip), 0) >= per_ip) or (total and _counts.get((day, "*"), 0) >= total):
        raise rate_limited("오늘 사용량 한도를 넘었습니다. 샘플 결과를 이용해 주세요.")
    _counts[(day, ip)] = _counts.get((day, ip), 0) + 1
    _counts[(day, "*")] = _counts.get((day, "*"), 0) + 1


def _log(request_id: str, endpoint: str, started: float, **extra) -> None:
    # 공고 원문과 profile 은 남기지 않는다.
    log.info(json.dumps({"requestId": request_id, "endpoint": endpoint,
                         "ms": round((time.perf_counter() - started) * 1000), **extra}, ensure_ascii=False))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    info = snapshot_info()
    if config.APP_ENV == "prod" and (info.get("isSample") or str(info.get("version", "")).endswith("-partial")):
        raise RuntimeError("운영 모드에서는 샘플·부분 월세 스냅샷으로 시작할 수 없습니다. data/rent_stats.json 을 확인하세요.")
    yield


app = FastAPI(title="남는 돈 비교", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)


@app.exception_handler(ApiError)
async def _api_error(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status,
                        content={"error": {"code": exc.code, "message": exc.message, "fallback": exc.fallback}})


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(status_code=400, content={"error": {
        "code": "INVALID_INPUT", "message": f"입력 형식이 맞지 않습니다: {where}".rstrip(": "), "fallback": "fix_input"}})


@app.get("/api/health")
def health():
    info = snapshot_info()
    return JSONResponse(dump(HealthResponse(
        status="ok", data_version=DataVersion(rent=str(info.get("version", "unknown")), rules=C.RULES_VERSION))))


@app.get("/api/samples")
def samples():
    items = [Sample(id=s["id"], title=s["title"], postings=[PostingInput(**p) for p in s["postings"]])
             for s in load_samples()]
    return JSONResponse(dump(SamplesResponse(samples=items)))


@app.post("/api/extract")
def extract(req: ExtractRequest, request: Request):
    started = time.perf_counter()
    request_id = new_request_id()
    if sorted(p.id for p in req.postings) != ["A", "B"]:
        raise invalid_input("공고는 A와 B 두 건이어야 합니다.")
    for p in req.postings:
        if not p.text.strip():
            raise invalid_input(f"공고 {p.id}의 내용이 비어 있습니다.")
        if len(p.text) > config.MAX_POSTING_CHARS:
            raise invalid_input(f"공고 {p.id}가 {config.MAX_POSTING_CHARS:,}자를 넘습니다.")
    check_rate_limit(request)

    from app.agent.extract import PostingUnreadable, extract_postings
    from app.agent.llm import LLMUnavailable
    from app.agent.questions import build_questions
    from app.data.regions import resolve_region

    degraded = False
    trace = []
    try:
        fields = extract_postings(req.postings, get_llm())
        trace.append(("extract", "extract_postings", "공고 2건에서 조건과 근거 문장을 읽음"))
    except LLMUnavailable:
        fields = find_saved_extract(req.postings)
        if fields is None:
            _log(request_id, "extract", started, error="LLM_UNAVAILABLE")
            raise llm_unavailable("지금은 공고를 자동으로 읽을 수 없습니다. 조건을 직접 입력해 주세요.")
        degraded = True
        trace.append(("extract", "saved_extract", "LLM을 쓸 수 없어 샘플 공고의 저장된 추출 결과를 사용"))
    except PostingUnreadable as exc:
        _log(request_id, "extract", started, error="POSTING_UNREADABLE")
        raise posting_unreadable(str(exc) or "채용공고에서 연봉과 근무지를 읽지 못했습니다.")

    regions = {}
    notes = []
    for pid in sorted(fields):
        text = fields[pid].work_location_text.value or ""
        res = resolve_region(text) if text.strip() else RegionResolution(candidates=[], ambiguous=True)
        regions[pid] = res
        if len(res.candidates) == 1 and not res.ambiguous:
            notes.append(f"{pid} '{text}'는 {res.candidates[0].sgg_code}")
        else:
            notes.append(f"{pid} '{text}'는 후보 {len(res.candidates)}개")
    trace.append(("tool_call", "resolve_region", " / ".join(notes)))

    questions = build_questions(fields, regions)
    asked = [q for q in questions if q.posting_id]
    if asked:
        trace.append(("question", "ask_user", f"공고에서 확인되지 않은 조건 {len(asked)}건을 되묻기로 함"))

    resp = ExtractResponse(
        request_id=request_id, degraded=degraded,
        postings=[ExtractedPosting(id=pid, fields=fields[pid], region=regions[pid]) for pid in sorted(fields)],
        questions=questions,
        trace=[TraceStep(step=i + 1, type=t, name=n, summary=s) for i, (t, n, s) in enumerate(trace)])
    _log(request_id, "extract", started, degraded=degraded)
    return JSONResponse(dump(resp))


@app.post("/api/compare")
def compare(req: CompareRequest, request: Request):
    started = time.perf_counter()
    request_id = new_request_id()
    check_rate_limit(request)
    try:
        llm = get_llm()
    except Exception:
        llm = None
    result = run_compare(req, build_deps(llm), request_id=request_id)
    _log(request_id, "compare", started, degraded=getattr(result, "degraded", None),
         needsInput=getattr(result, "needs_input", False))
    return JSONResponse(dump(result))


# 화면 (app/web). API 경로를 먼저 등록한 뒤에 붙인다.
if (config.WEB_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
