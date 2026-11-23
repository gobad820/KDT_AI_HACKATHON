"""테스트 30건 실행과 결과표 생성 (docs/agent-spec.md 12장, docs/tasks/W2-agent-tests.md).

이름이 test_ 로 시작하지 않아 pytest 가 모으지 않는다(실제 Gemini 를 부르지 않게, W2 6번).

사용법 (저장소 루트에서):
  python3 tests/cases/run_cases.py                       # 모의(mock). 네트워크·LLM 없음. 결과표만 다시 만든다
  python3 tests/cases/run_cases.py --mode live           # 실측: .env 의 LLM 설정으로 실제 모델 호출(가상 공고만 보냄)
  python3 tests/cases/run_cases.py --mode live --repeat 3 --sleep 1
  python3 tests/cases/run_cases.py --mode remote --base-url https://nammeun-don.vercel.app --sleep 1
  python3 tests/cases/run_cases.py --report-only         # 저장된 결과로 RESULTS.md 만 다시 만든다
  python3 tests/cases/run_cases.py --only T10,T13 --mode live --no-save   # 일부만, 결과 저장 없이 화면에만

- 결과 JSON: tests/cases/results/mock.json, live-YYYYMMDD-HHMMSS.json, remote-YYYYMMDD-HHMMSS.json
- 결과표: tests/cases/RESULTS.md (모의 + 가장 최근 실측 + 가장 최근 원격)
- 키·공고 원문·LLM 요청 본문은 출력하거나 저장하지 않는다. 모델명은 설정값(LLM_MODEL 등)만 적는다.
  어댑터가 실제로 응답한 모델(대체 모델로 넘어갔는지)은 기록하지 않으므로 '설정'으로만 표시한다.
- live·remote 는 사용량 한도(429)에 걸릴 수 있다. --sleep 으로 간격을 둔다.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.cases import evaluate as ev  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT = Path(__file__).resolve().parent / "RESULTS.md"
KST = timezone(timedelta(hours=9))
TEAM_MODEL_NOTE = ("팀 현황(CLAUDE.md, 11/21) 기재 설정: gemini-flash-lite-latest → 대체 gemini-3.5-flash-lite → gemini-3.1-flash-lite. "
                   "배포 API 응답에는 모델명이 없어 이번 실행에서 직접 확인하지 못함")


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() + ("+작업 중 변경" if dirty.stdout.strip() else "")
    except Exception:
        return "unknown"


def _prompt_versions() -> dict:
    from app.agent import classify, explain, extract
    return {"extract": extract.PROMPT_VERSION, "classify": classify.PROMPT_VERSION, "explain": explain.PROMPT_VERSION}


def _meta(mode: str, base_url: str = "", repeat: int = 1) -> dict:
    meta = {"mode": mode, "runAt": datetime.now(KST).isoformat(timespec="seconds"), "commit": _git_commit(),
            "prompts": _prompt_versions(), "repeat": repeat}
    if mode == "live":
        meta["model"] = {"provider": os.environ.get("LLM_PROVIDER", ""), "configured": os.environ.get("LLM_MODEL", ""),
                         "fallbacks": os.environ.get("LLM_MODEL_FALLBACKS", ""),
                         "note": "설정값. 어느 모델이 실제로 응답했는지는 기록하지 않음"}
    elif mode == "remote":
        meta["baseUrl"] = base_url
        meta["model"] = {"note": TEAM_MODEL_NOTE}
        meta["deployedVersion"] = "API로 확인 불가. commit 은 평가기를 돌린 로컬 저장소의 커밋이며 배포본의 커밋이 아니다"
    else:
        meta["model"] = {"note": "모의: FakeLLM(Claude Code가 미리 작성한 가정 응답). 실제 모델을 부르지 않음"}
    return meta


def run(mode: str, base_url: str, only, repeat: int, sleep_s: float) -> dict:
    # 서버와 같은 설정 로더(app.config: 저장소 루트 .env → 환경변수, 이미 있는 환경변수 우선)를 먼저 실행한다.
    # 값은 읽어 출력하지 않는다. 이 import 가 없으면 live 에서 get_llm 이 LLM_PROVIDER 를 보지 못한다
    from app import config  # noqa: F401
    runner_kw = {}
    if mode == "live":
        from app.agent.llm import LLMUnavailable, get_llm
        try:
            llm = get_llm()
        except LLMUnavailable as exc:
            llm, why = None, str(exc)
        else:
            why = "LLM_PROVIDER 가 비어 있음(.env 또는 환경변수)"
        if llm is None:
            print(f"[미측정] 실측을 할 수 없습니다: {why}")
            return {"meta": dict(_meta(mode), unavailable=why), "runs": []}
        runner_kw = {"llm": llm, "sleep_s": sleep_s}
    elif mode == "remote":
        import httpx
        if not base_url.startswith("http"):
            raise SystemExit("--mode remote 에는 --base-url https://... 가 필요합니다")
        runner_kw = {"client": httpx.Client(headers={"User-Agent": "nammeun-don-case-eval"}), "base_url": base_url,
                     "sleep_s": sleep_s}
    runs = []
    for i in range(repeat):
        print(f"== {mode} 실행 {i + 1}/{repeat}")
        runner = ev.Runner(mode, **runner_kw)
        runs.append(ev.run_all(runner, only, on_result=_print_result))
    return {"meta": _meta(mode, base_url, repeat), "runs": runs}


def _print_result(r: dict) -> None:
    name = r["id"] + (f" [{r['variant']}]" if r.get("variant") else "")
    extra = f" 실패: {', '.join(r['failed'])}" if r["failed"] else ""
    if r.get("error"):
        extra += f" 오류: {r['error']}"
    print(f"  {name:<34} {r['verdict']}{extra}")


# ---- 결과표 ----

def _latest(prefix: str):
    """같은 방식의 결과 파일을 오래된 것부터 읽고, 케이스(변형)마다 가장 최근 결과를 남긴다.
    --only 로 일부만 다시 돌려도 나머지 결과가 남는다. 실측을 할 수 없었던 실행(unavailable)은 결과를 덮지 않는다."""
    files = sorted(RESULTS_DIR.glob(f"{prefix}-*.json"))
    if not files:
        return None
    by_key, metas = {}, []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        ids = sorted({r["id"] for run_ in d.get("runs", []) for r in run_})
        metas.append(dict(d["meta"], file=f.name, ids=ids))
        if d["meta"].get("unavailable"):
            continue
        this_file = {}
        for run_ in d.get("runs", []):
            for r in run_:
                this_file.setdefault(_key(r), []).append(r)
        by_key.update(this_file)
    return {"metas": metas, "runs": [[r for rs in by_key.values() for r in rs]]}


def _key(r):
    return (r["id"], r.get("variant") or "")


def _cell(results_by_key, key, case_id):
    """실측 칸: 변형별 결과가 있으면 그것, 없으면 케이스 단위 결과."""
    rs = results_by_key.get(key) or results_by_key.get((case_id, ""))
    if not rs:
        return None
    verdicts = Counter(r["verdict"] for r in rs)
    text = " / ".join(f"{v}×{n}" if len(rs) > 1 else v for v, n in verdicts.items())
    if len(verdicts) > 1:
        text += " (실행마다 다름)"
    return text, rs


def _diff_note(rs, known) -> str:
    """실측 실패 목록이 모의 knownGaps 와 다르면 '모의와 다름'으로 적는다."""
    notes = []
    for r in rs:
        if r["verdict"] in (ev.NOT_RUN, ev.CODE_ONLY, ev.NOT_IMPL):
            continue
        if r.get("error"):
            notes.append(f"오류 {r['error']}")
            continue
        extra = sorted(set(r["failed"]) - set(known))
        fixed = sorted(set(known) - set(r["failed"]))
        if extra:
            notes.append("모의에 없던 실패: " + ", ".join(extra))
        if fixed:
            notes.append("모의의 차이가 실측에서 없음: " + ", ".join(fixed))
    return "; ".join(dict.fromkeys(notes))


def _fmt(v) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= 140 else s[:137] + "..."


def _criteria_summary(data, mi, li, ri) -> list:
    """docs/agent-spec.md 12장 '통과 기준(제안)'과 비교. 결과에서 확인한 항목만 세고, 재지 않은 항목은 미측정으로 적는다."""
    def vid(r):
        return r["id"] + (f"({r['variant']})" if r.get("variant") else "")

    out = ["## 통과 기준 요약 (docs/agent-spec.md 12장 '통과 기준(제안)')", "",
           "| 기준 | 모의 | 실측(로컬 LLM) | 원격(배포 API) |", "|---|---|---|---|"]
    rowsets = []
    for idx in (mi, li, ri):
        rows = [r for rs in idx.values() for r in rs if r["verdict"] not in (ev.NOT_RUN, ev.CODE_ONLY)]
        rowsets.append(rows)

    def cell(rows, fn):
        return fn(rows) if rows else "미측정"

    def numbers(rows):
        rs = [r for r in rows if r["id"] in ("T23", "T24", "T25")]
        if not rs:
            return "미측정"
        bad = [f"{vid(r)}: {', '.join(r['failed'])}" for r in rs if r["failed"] or r.get("error")]
        return f"{len(bad)}건 (확인 {len(rs)}행)" + (" — " + "; ".join(bad) if bad else "")

    def estimate(rows):
        rs = [r for r in rows if r["id"] in ("T04", "T05", "T10")]
        if not rs:
            return "미측정"
        bad = [f"{vid(r)}: {', '.join(r['failed'])}" for r in rs if r["failed"] or r.get("error")]
        return f"{len(bad)}건 (확인 {len(rs)}행)" + (" — " + "; ".join(bad) if bad else "")

    def evidence(rows):
        rs = [r for r in rows if any(c["name"] == "invariant:extractedHasEvidence" for c in r["checks"])]
        if not rs:
            return "미측정"
        bad = [vid(r) for r in rs if "invariant:extractedHasEvidence" in r["failed"]]
        return f"{len(bad)}건 (확인 {len(rs)}행)" + (" — " + ", ".join(bad) if bad else "")

    def safety(rows):
        parts, all_ok = [], True
        for cid in ("T26", "T27", "T30"):
            rs = [r for r in rows if r["id"] == cid]
            if not rs:
                parts.append(f"{cid} 미측정")
                all_ok = False
                continue
            vs = sorted({r["verdict"] for r in rs})
            all_ok &= vs == [ev.PASS]
            parts.append(f"{cid} {'/'.join(vs)}")
        return ("전부 통과" if all_ok else "전부 통과 아님") + " — " + ", ".join(parts)

    out.append("| 숫자 불일치 0건 (T23~T25) | " + " | ".join(cell(r, numbers) for r in rowsets) + " |")
    out.append("| 금액 추정 0건 (T04, T05, T10) | " + " | ".join(cell(r, estimate) for r in rowsets) + " |")
    out.append("| 근거가 원문과 맞지 않는데 extracted 로 남은 필드 0건 | " + " | ".join(cell(r, evidence) for r in rowsets) + " |")
    out.append("| 안전 2건(T26, T27)과 장애 1건(T30) 전부 통과 | " + " | ".join(cell(r, safety) for r in rowsets) + " |")
    out.append("| 추출 필드 정확도 90% 이상 | 미측정(모의 응답은 미리 작성한 값이라 정확도 지표가 아님) | 미측정 | "
               "미측정(필드별 정답 대조를 하지 않음) |")
    out += ["", "- 셀의 'n건'은 기준을 어긴 행 수다. '확인 n행'은 그 방식으로 실제 판정한 행 수다(미측정·코드 결정 행은 세지 않음).", ""]
    return out


def build_report() -> str:
    data = ev.load_cases()
    mock = json.loads((RESULTS_DIR / "mock.json").read_text(encoding="utf-8")) if (RESULTS_DIR / "mock.json").exists() else None
    live, remote = _latest("live"), _latest("remote")

    def index(res):
        out = {}
        for run_ in (res or {}).get("runs", []):
            for r in run_:
                out.setdefault(_key(r), []).append(r)
        return out
    mi, li, ri = index(mock), index(live), index(remote)

    L = ["# 테스트 30건 결과표", "",
         "`tests/cases/run_cases.py`가 만든 파일이다. 손으로 고치지 않는다. 케이스와 기대값은 `tests/cases/cases.json`, 판정 코드는 `tests/cases/evaluate.py`.", "",
         "## 읽는 법", "",
         "- **모의**: Claude Code가 미리 작성한 '가정한 LLM 응답'을 넣고 실제 코드(근거 대조, 환산, 지역, 질문, 감면 판정, 계산, 숫자 검증)를 검사한 결과다. 모델의 실제 읽기 품질은 보여 주지 않는다. `python -m pytest`가 같은 검사를 돌린다.",
         "- **실측(로컬 LLM)**: 저장소 `.env`의 LLM 설정으로 같은 가상 공고를 실제 모델에 보낸 결과다.",
         "- **원격(배포 API)**: 배포 URL에 HTTP로 보낸 결과다. 모델명은 API에 나오지 않는다.",
         "- 판정: 통과 / 명세 차이(검사 실패, 아래 상세) / 미구현 / 오류 / 미측정(그 방식으로 재지 않았거나 잴 수 없음) / 코드 결정(LLM 무관, 모의와 같은 코드).",
         "- '모의와 다름'은 실측의 실패 목록이 모의에서 확인한 명세 차이와 다를 때 적는다(불일치).",
         "- 가정 응답만 다른 변형(T10, T26)은 실측·원격에서 공고 하나를 한 번만 보낸다. 그 결과를 변형 행마다 같이 보여 준다.", ""]
    L.append("## 실행 정보")
    L.append("")
    for label, res in (("모의", mock), ("실측(로컬 LLM)", live), ("원격(배포 API)", remote)):
        if not res:
            L.append(f"- {label}: 미측정(결과 파일 없음)")
            continue
        for m in res.get("metas") or [res["meta"]]:
            where = f" `{m['file']}`" if m.get("file") else ""
            if m.get("unavailable"):
                L.append(f"- {label}{where}: 미측정 — {m['unavailable']} ({m['runAt']})")
                continue
            model = m.get("model", {})
            model_s = ", ".join(f"{k}={v}" for k, v in model.items() if v)
            L.append(f"- {label}{where}: {m['runAt']}, 평가기 커밋 {m['commit']}, 평가기 쪽 프롬프트 {m['prompts']}, 반복 {m['repeat']}회"
                     + (f", URL {m['baseUrl']}" if m.get("baseUrl") else "") + f". 모델: {model_s}"
                     + (f". 배포본 버전: {m['deployedVersion']}" if m.get("deployedVersion") else "")
                     + (f". 배치: {m['batch']}" if m.get("batch") else "")
                     + (f". 포함 케이스 {len(m['ids'])}개({m['ids'][0]}~{m['ids'][-1]})" if m.get("ids") and len(m["ids"]) > 5
                        else (f". 포함 케이스: {', '.join(m['ids'])}" if m.get("ids") else "")))
    if remote and len(remote.get("metas", [])) > 1:
        L.append("- 원격은 여러 배치로 실행했다. 케이스(변형)마다 가장 최근 배치의 결과를 표에 쓴다.")
    if remote:
        L.append("- 원격 결과는 11/22 공개 배포본(extract_v2)의 동작 이력이다. 이 결과표의 모의 기준인 main 도 extract_v2 라서 "
                 "원격의 실패가 모의의 명세 차이(knownGaps)와 같은지 대조한다. W8(extract_v3) 병합 뒤 실제 재평가로 새 결과를 더한다.")

    L += _criteria_summary(data, mi, li, ri)
    rows_main, rows_var, details = [], [], []
    counts = Counter()
    for case in data["cases"]:
        variants = case.get("variants") or [None]
        per = []                                    # 변형마다 (이름, 모의, 실측, 원격, 메모)
        for v in variants:
            vname = v.get("name") if v else ""
            key = (case["id"], vname or "")
            known = (v or {}).get("knownGaps", case.get("knownGaps", []))
            mc = _cell(mi, key, case["id"])
            lc = _cell(li, key, case["id"])
            rc = _cell(ri, key, case["id"])
            if mc:
                counts[mc[0]] += 1
            notes = []
            for lab, c in (("실측", lc), ("원격", rc)):
                if c:
                    idx = li if lab == "실측" else ri
                    d = _diff_note(c[1], known if key in idx else case.get("knownGaps", []))
                    if d:
                        notes.append(f"{lab}: {d}")
            if mc and mc[1][0].get("note"):
                notes.append(mc[1][0]["note"])
            if rc and rc[1][0]["verdict"] != ev.NOT_RUN:
                rnote = (v or {}).get("remoteNote") or case.get("remoteNote")      # 결과 파일의 옛 문구 대신 현재 케이스 메모
                if rnote:
                    notes.append(f"원격: {rnote}")
            cells = [c[0] if c else "미측정" for c in (mc, lc, rc)]
            per.append((vname, cells, notes, [key in idx for idx in (mi, li, ri)]))
            idv = f"{case['id']}({vname})" if vname else case["id"]
            if vname:
                rows_var.append(f"| {idv} | {cells[0]} | {cells[1]} | {cells[2]} | {_fmt('; '.join(notes)) if notes else ''} |")
            for lab, c, idx in (("모의", mc, mi), ("실측", lc, li), ("원격", rc, ri)):
                if not c:
                    continue
                did = idv if key in idx else f"{case['id']}(변형 없이 케이스 단위 실행)"
                for r in c[1]:
                    for chk in r["checks"]:
                        if not chk["ok"]:
                            details.append(f"| {lab} | {did} | `{chk['name']}` | {_fmt(chk['expected'])} | {_fmt(chk['actual'])} |")
                    if r.get("error"):
                        details.append(f"| {lab} | {did} | 오류 | | {_fmt(r['error'])} |")
        merged = []
        for i in range(3):
            vals = [cells[i] for _, cells, _, _ in per]
            exact = any(e[i] for _, _, _, e in per)
            if len(per) == 1:
                merged.append(vals[0])
            elif not exact and vals[0] != "미측정":
                merged.append(f"{vals[0]} (변형 없이 케이스 단위 1회 실행)")
            elif len(set(vals)) == 1:
                merged.append(f"{vals[0]} (변형 {len(per)}개 모두)")
            else:
                merged.append("; ".join(f"{n}: {x}" for (n, _, _, _), x in zip(per, vals)))
        note = per[0][2] if len(per) == 1 else [f"변형 {len(per)}개, 아래 '변형별 결과' 참고"]
        rows_main.append(f"| {case['id']} | {case['category']} | {_fmt(case['summary'])} | {_fmt(case['spec'])} | "
                         f"{_fmt(merged[0])} | {_fmt(merged[1])} | {_fmt(merged[2])} | {_fmt('; '.join(note)) if note else ''} |")
    L += ["## 결과 (ID당 한 줄, 변형 결과는 같은 칸에 합침)", "",
          "| ID | 분류 | 입력 요약 | 명세 기대 | 모의 | 실측(로컬 LLM) | 원격(배포 API) | 차이·메모 |", "|---|---|---|---|---|---|---|---|"]
    L += rows_main
    L.append("")
    if counts:
        L.append("모의 집계(변형 포함 " + str(sum(counts.values())) + "행): " + ", ".join(f"{k} {n}" for k, n in counts.items()))
        L.append("")
    L += ["## 변형별 결과", "", "| 케이스(변형) | 모의 | 실측(로컬 LLM) | 원격(배포 API) | 차이·메모 |", "|---|---|---|---|---|"]
    L += rows_var
    L += ["", "## 명세 차이 상세 (실패한 검사의 기대값과 실제값)", "", "| 방식 | 케이스 | 검사 | 기대 | 실제 |", "|---|---|---|---|---|"]
    L += list(dict.fromkeys(details)) or ["| | | 없음 | | |"]
    L += ["", "## 설계와 현 구현 차이 (케이스 메모)", ""]
    for case in data["cases"]:
        if case.get("notes"):
            L.append(f"- **{case['id']}** {case['notes']}")
    L += ["", "## 다시 돌리기", "",
          "```bash",
          "python3 -m pytest tests/test_cases.py         # 모의 판정이 기록(knownGaps)과 같은지",
          "python3 tests/cases/run_cases.py                   # 모의 결과 저장 + 이 표 다시 만들기",
          "python3 tests/cases/run_cases.py --mode live --repeat 3 --sleep 1        # .env 의 LLM 이 있을 때만",
          "python3 tests/cases/run_cases.py --mode remote --base-url https://nammeun-don.vercel.app --sleep 1",
          "```", ""]
    return "\n".join(L)


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="테스트 30건 실행과 결과표 생성")
    ap.add_argument("--mode", choices=["mock", "live", "remote"], default="mock")
    ap.add_argument("--base-url", default="", help="remote 모드의 배포 주소 (예: https://nammeun-don.vercel.app)")
    ap.add_argument("--only", default="", help="쉼표로 구분한 케이스 ID (예: T10,T13)")
    ap.add_argument("--repeat", type=int, default=1, help="같은 케이스를 몇 번 돌릴지(실측 일관성 확인용)")
    ap.add_argument("--sleep", type=float, default=0.0, help="원격 요청 사이 대기(초)")
    ap.add_argument("--no-save", action="store_true", help="결과 파일과 결과표를 쓰지 않는다")
    ap.add_argument("--report-only", action="store_true", help="저장된 결과로 RESULTS.md 만 다시 만든다")
    args = ap.parse_args()
    logging.getLogger("app").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if not args.report_only:
        only = [x.strip() for x in args.only.split(",") if x.strip()] or None
        res = run(args.mode, args.base_url, only, max(1, args.repeat), args.sleep)
        if not args.no_save:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            if args.mode == "mock":
                if only:
                    print("일부만 돌린 모의 결과는 mock.json 에 저장하지 않습니다(--no-save 와 같음)")
                    return
                path = RESULTS_DIR / "mock.json"
            else:
                path = RESULTS_DIR / f"{args.mode}-{datetime.now(KST):%Y%m%d-%H%M%S}.json"
            path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"저장: {path.relative_to(ROOT)}")
        if args.no_save:
            return
    REPORT.write_text(build_report(), encoding="utf-8")
    print(f"결과표: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
