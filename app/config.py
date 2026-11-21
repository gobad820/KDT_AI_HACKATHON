"""실행 설정. 값은 환경변수로만 바꾼다. 키와 비밀번호는 .env 에만 둔다."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """저장소 루트의 .env 를 읽어 환경변수로 넣는다. 이미 있는 환경변수가 우선한다. 값은 로그에 남기지 않는다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ.get("DATA_DIR", REPO_ROOT / "data"))
WEB_DIR = REPO_ROOT / "app" / "web"

APP_ENV = os.environ.get("APP_ENV", "dev")             # dev | prod
EXTRACT_TIMEOUT_S = float(os.environ.get("EXTRACT_TIMEOUT_S", "20"))
COMPARE_TIMEOUT_S = float(os.environ.get("COMPARE_TIMEOUT_S", "40"))
MAX_POSTING_CHARS = int(os.environ.get("MAX_POSTING_CHARS", "8000"))
RATE_LIMIT_PER_IP_PER_DAY = int(os.environ.get("RATE_LIMIT_PER_IP_PER_DAY", "0"))   # 0 이면 끔
RATE_LIMIT_TOTAL_PER_DAY = int(os.environ.get("RATE_LIMIT_TOTAL_PER_DAY", "0"))     # 0 이면 끔
