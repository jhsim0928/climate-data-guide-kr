"""데이터셋 YAML 검증 도구.

사용법:
    python scripts/validate.py                       # 전체 검사
    python scripts/validate.py data/datasets/era5.yaml  # 특정 파일만 검사

사이트 빌드와 같은 규칙으로 검사하므로, 여기서 통과하면 빌드에서도 통과합니다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from datasets import load_datasets  # noqa: E402
from mkdocs.exceptions import PluginError  # noqa: E402

paths = [Path(p) for p in sys.argv[1:]] or None
try:
    ds = load_datasets(paths)
except PluginError as e:
    print("검증 실패\n" + str(e))
    sys.exit(1)
for d in ds:
    nvar = sum(len(g["items"]) for g in d["variables"]["groups"])
    print(f"OK  {d['id']:<16} {d['domain']}/{d['group']}  status={d['status']}  변수 {nvar}개  공지 {len(d['notices'])}건")
