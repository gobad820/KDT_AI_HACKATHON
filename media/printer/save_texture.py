"""receipt_texture.js 결과(JSON 문자열, dataURL 포함)를 receipt.png 와 receipt.json 으로 푼다.

사용: python3 media/printer/save_texture.py media/printer/out/receipt_texture.json
"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
d = json.loads(Path(sys.argv[1]).read_text().strip())
if isinstance(d, str):
    d = json.loads(d)
(HERE / "receipt.png").write_bytes(base64.b64decode(d["url"].split(",", 1)[1]))
(HERE / "receipt.json").write_text(json.dumps({k: d[k] for k in ("rows", "H", "W", "scale")}))
print("saved", d["W"], "x", d["H"], "dots,", len(d["rows"]), "rows")
