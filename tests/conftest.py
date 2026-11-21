"""테스트 공통 설정.

테스트의 기대값은 설명용 샘플 스냅샷(data/rent_stats.sample.json) 기준이다.
실제 수집본(data/rent_stats.json)이 생겨도 결과가 바뀌지 않도록, 실제 수집본을 뺀 data 폴더 사본을 쓴다.
"""
import shutil

import pytest

from app import config
from app.data import regions, rent

REAL_DATA_DIR = config.DATA_DIR


@pytest.fixture(autouse=True)
def sample_data_dir(tmp_path_factory, monkeypatch):
    data = tmp_path_factory.mktemp("data")
    shutil.copy(REAL_DATA_DIR / "regions.csv", data / "regions.csv")
    shutil.copy(REAL_DATA_DIR / "rent_stats.sample.json", data / "rent_stats.sample.json")
    shutil.copytree(REAL_DATA_DIR / "samples", data / "samples")
    monkeypatch.setattr(config, "DATA_DIR", data)
    rent.reload(); regions.reload()
    yield data
    monkeypatch.undo()
    rent.reload(); regions.reload()
