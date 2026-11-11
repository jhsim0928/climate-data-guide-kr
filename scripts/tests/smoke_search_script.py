"""'모델 자료 받기' (가) intake-esgf 스크립트 실제 실행 시험 — GitHub Actions에서 (ESGF 접속 필요)

카탈로그에서 작은 모델을 골라 docs/javascripts/model-data.js 의 buildScript 로 스크립트를 만들고 실제로 돌려
결과 파일의 차원·달력·크기를 확인합니다. 조건: Amon tas(CMIP7은 mon tas_tavg-h2m-hxy-u), historical, 2000–2014,
첫 멤버, 한반도 상자(30–45N, 120–135E), 달력 noleap, 재격자 없음.

    python scripts/tests/smoke_search_script.py --catalog data/model-catalog/catalog.json --out smoke [--cmip6 2] [--cmip7 1]

결과: <out>/smoke.json (모델별 성공/실패, 파일 차원·달력·크기), 종료 코드 0 = CMIP6 모델이 하나 이상 성공
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "docs" / "javascripts" / "model-data.js"


def pick(cat, project, vkey, exp, n, prefer=()):
    p = (cat.get("projects") or {}).get(project) or {}
    av = (p.get("avail") or {}).get(vkey) or {}
    f = p.get("entry_fields") or []
    i_files, i_size, i_n = f.index("files"), f.index("size_bytes"), f.index("n_members")
    rows = []
    for model, ex in av.items():
        e = ex.get(exp)
        if not e:
            continue
        per_member = e[i_size] / max(1, e[i_n])
        rows.append((model not in prefer, per_member, e[i_files] / max(1, e[i_n]), model))
    rows.sort()
    return [r[-1] for r in rows[: n * 3]], {r[-1]: r[1] for r in rows}


def gen(cfg, path):
    code = "const m=require(%s);process.stdout.write(m.buildScript(%s));" % (json.dumps(str(JS)), json.dumps(cfg))
    path.write_text(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    subprocess.run([sys.executable, "-m", "py_compile", str(path)], check=True)


def inspect(nc):
    import xarray as xr
    with xr.open_dataset(nc, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True)) as d:
        var = [v for v in d.data_vars if d[v].ndim >= 3][0]
        t = d["time"].values
        return {"file": nc.name, "var": var, "dims": {k: int(v) for k, v in d[var].sizes.items()}, "calendar": d["time"].dt.calendar,
                "first": str(t[0])[:10], "last": str(t[-1])[:10], "units": d[var].attrs.get("units"), "size_mb": round(nc.stat().st_size / 1e6, 3),
                "lat_range": [float(d[c].min()) for c in d.coords if "lat" in c.lower()][:1] + [float(d[c].max()) for c in d.coords if "lat" in c.lower()][:1],
                "mean": float(d[var].mean())}


def run_one(project, var, model, out, timeout):
    work = out / f"{project}_{model}"
    work.mkdir(parents=True, exist_ok=True)
    cfg = {"lang": "en", "project": project, "variables": [var], "experiments": ["historical"], "models": [model], "members": "first",
           "years": [2000, 2014], "box": {"lat": [30, 45], "lon": [120, 135]}, "calendar": "noleap", "regrid": None,
           "outDir": str(work / "cmip_out"), "fileName": "smoke.py"}
    script = work / "smoke.py"
    gen(cfg, script)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=timeout, cwd=work)
        rc, log = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        rc, log = -9, (e.stdout or b"").decode(errors="replace") + "\nTIMEOUT"
    (work / "run.log").write_text(log, encoding="utf-8")
    files = sorted((work / "cmip_out").glob("*.nc"))
    res = {"project": project, "model": model, "rc": rc, "sec": round(time.time() - t0), "outputs": []}
    for f in files:
        try:
            res["outputs"].append(inspect(f))
        except Exception as e:  # noqa: BLE001
            res["outputs"].append({"file": f.name, "error": repr(e)[:300]})
    res["ok"] = rc == 0 and bool(files) and all("error" not in o and o["calendar"] == "noleap" for o in res["outputs"])
    res["log_tail"] = log.strip().splitlines()[-25:]
    print(json.dumps({k: v for k, v in res.items() if k != "log_tail"}, ensure_ascii=False), flush=True)
    print("\n".join("    | " + x for x in res["log_tail"]), flush=True)
    for f in files:
        f.unlink()  # 결과 파일은 커밋하지 않음 (요약만)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(ROOT / "data" / "model-catalog" / "catalog.json"))
    ap.add_argument("--out", default="smoke")
    ap.add_argument("--cmip6", type=int, default=2)
    ap.add_argument("--cmip7", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    results = []
    plan = [
        ("CMIP6", {"id": "Amon.tas", "var": "tas", "table": "Amon", "freq": "mon"}, a.cmip6, ("CanESM5", "MIROC6", "IPSL-CM6A-LR")),
        ("CMIP7", {"id": "mon.tas_tavg-h2m-hxy-u", "var": "tas", "branded": "tas_tavg-h2m-hxy-u", "branding_suffix": "tavg-h2m-hxy-u",
                   "freq": "mon", "region": "glb"}, a.cmip7, ()),
    ]
    for project, var, n, prefer in plan:
        if n <= 0:
            continue
        cands, sizes = pick(cat, project, var["id"], "historical", n, prefer)
        print(f"\n[{project}] candidates: " + ", ".join(f"{m} ({sizes[m] / 1e6:.0f} MB/member)" for m in cands), flush=True)
        ok = 0
        for m in cands:
            if ok >= n:
                break
            r = run_one(project, var, m, out, a.timeout)
            results.append(r)
            ok += r["ok"]
    summary = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results,
               "ok": {p: sum(r["ok"] for r in results if r["project"] == p) for p in ("CMIP6", "CMIP7")}}
    (out / "smoke.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nsummary:", summary["ok"])
    return 0 if summary["ok"]["CMIP6"] >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
