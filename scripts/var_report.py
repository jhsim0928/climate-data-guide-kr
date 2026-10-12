"""표준 변수 묶음 점검 — 어떤 변수가 어느 표준 변수로 묶였는지, 묶이지 않은 변수는 무엇인지

    python scripts/var_report.py            # 요약
    python scripts/var_report.py --json out.json   # 검토용 전체 목록
"""
import importlib.util, json, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("h", ROOT / "hooks" / "datasets.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)

ds = h.load_datasets()
h._ko_datasets = ds
sv = h.std_vars()
by = collections.defaultdict(list)
untagged, multi = [], []
total = 0
for d in ds:
    tags = h.std_tag_dataset(d)
    for gi, g in enumerate(d["variables"]["groups"]):
        for ii, it in enumerate(g["items"]):
            total += 1
            t = it if isinstance(it, str) else it.get("text", "")
            tg = tags[gi][ii]
            if not tg:
                untagged.append((d["id"], g["name"], t))
            if len(tg) > 1:
                multi.append((d["id"], t, tg))
            for c in tg:
                by[c].append((d["id"], d["name"], t))
print(f"변수 {total}개 중 묶인 것 {total-len(untagged)}개, 안 묶인 것 {len(untagged)}개, 둘 이상에 묶인 것 {len(multi)}개")
for c in sv["concepts"]:
    n = len({x[0] for x in by[c['id']]})
    print(f"{c['id']:18} {c['ko']:24} 자료 {n:2}  변수 {len(by[c['id']]):3}")
if "--json" in sys.argv:
    out = {"concepts": [{k: v for k, v in c.items() if not k.startswith('_')} | {"items": by[c["id"]]} for c in sv["concepts"]],
           "untagged": untagged, "multi": multi}
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
