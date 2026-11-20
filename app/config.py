"""실행 설정. 값은 환경변수로만 바꾼다. 키와 비밀번호는 .env 에만 둔다."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", REPO_ROOT / "data"))
WEB_DIR = REPO_ROOT / "app" / "web"

APP_ENV = os.environ.get("APP_ENV", "dev")             # dev | prod
EXTRACT_TIMEOUT_S = float(os.environ.get("EXTRACT_TIMEOUT_S", "20"))
COMPARE_TIMEOUT_S = float(os.environ.get("COMPARE_TIMEOUT_S", "40"))
MAX_POSTING_CHARS = int(os.environ.get("MAX_POSTING_CHARS", "8000"))
RATE_LIMIT_PER_IP_PER_DAY = int(os.environ.get("RATE_LIMIT_PER_IP_PER_DAY", "0"))   # 0 이면 끔
RATE_LIMIT_TOTAL_PER_DAY = int(os.environ.get("RATE_LIMIT_TOTAL_PER_DAY", "0"))     # 0 이면 끔
