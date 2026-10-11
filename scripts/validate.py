"""데이터셋 YAML 검증 도구 (한국어판 + 영어판).

사용법:
    python scripts/validate.py                          # 한국어판·영어판 전체 검사
    python scripts/validate.py data/datasets/era5.yaml  # 특정 파일만 검사 (영어판 파일도 가능)

사이트 빌드와 같은 규칙으로 검사하므로, 여기서 통과하면 빌드에서도 통과합니다.
영어판(data/datasets_en)은 한국어판과 같은 id 의 파일이 모두 있어야 하고, 공지 개수가 같아야 합니다
(메일 알림이 두 언어의 공지를 순서대로 짝지어 같은 공지로 취급하기 때문).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

from datasets import load_datasets, DATA_DIR, DATA_DIR_EN  # noqa: E402
from mkdocs.exceptions import PluginError  # noqa: E402


def show(ds, tag):
    for d in ds:
        nvar = sum(len(g["items"]) for g in d["variables"]["groups"])
        print(f"OK {tag} {d['id']:<24} {d['domain']}/{d['group']}  status={d['status']}  변수 {nvar}개  공지 {len(d['notices'])}건")


paths = [Path(p) for p in sys.argv[1:]] or None
try:
    if paths:
        show(load_datasets(paths), "  ")
    else:
        ko = load_datasets()
        show(ko, "ko")
        if DATA_DIR_EN.exists():
            en = load_datasets(data_dir=DATA_DIR_EN)
            show(en, "en")
            en_by = {d["id"]: d for d in en}
            problems = []
            for d in ko:
                e = en_by.get(d["id"])
                if not e:
                    problems.append(f"{d['id']}: 영어판 파일이 없어요 (data/datasets_en/{d['id']}.yaml)")
                    continue
                if len(e["notices"]) != len(d["notices"]):
                    problems.append(f"{d['id']}: 공지 개수가 달라요 (한국어 {len(d['notices'])}건, 영어 {len(e['notices'])}건)")
                if [n["date"] for n in e["notices"]] != [n["date"] for n in d["notices"]]:
                    problems.append(f"{d['id']}: 공지 날짜·순서가 한국어판과 달라요")
                for k in ("status", "domain", "group", "category"):
                    if e.get(k) != d.get(k):
                        problems.append(f"{d['id']}: {k} 값이 한국어판과 달라요 ({d.get(k)} / {e.get(k)})")
            if problems:
                raise PluginError("한국어판·영어판 불일치:\n  - " + "\n  - ".join(problems))
except PluginError as e:
    print("검증 실패\n" + str(e))
    sys.exit(1)
