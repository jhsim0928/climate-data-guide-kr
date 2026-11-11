"""'모델 자료 받기' 스크립트 생성기 시험 — node로 docs/javascripts/model-data.js 의 buildMergeScript/buildScript 를 불러
가짜 CMIP 파일(make_fake_cmip.py)에 (나) 합치기 스크립트를 실제로 돌리고 결과를 검사합니다. (가) 스크립트는 문법 검사만.

    python scripts/tests/test_merge_script.py [작업 폴더]

필요: node, xarray, netCDF4, cftime, numpy (dask 선택)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "docs" / "javascripts" / "model-data.js"
WORK = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="kcdn-model-test-"))
PY = sys.executable
FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def gen(kind, cfg, path):
    code = ("const m=require(%s);process.stdout.write(m.%s(%s));" % (json.dumps(str(JS)), kind, json.dumps(cfg)))
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    path.write_text(out, encoding="utf-8")
    subprocess.run([PY, "-m", "py_compile", str(path)], check=True)
    return path


def run(script, expect_rc=0):
    r = subprocess.run([PY, str(script)], capture_output=True, text=True, cwd=WORK)
    print("\n".join("    | " + line for line in (r.stdout + r.stderr).strip().splitlines()[-40:]))
    check(r.returncode == expect_rc, f"{script.name}: exit code {r.returncode} (expected {expect_rc})")
    return r.stdout


def open_(p):
    return xr.open_dataset(p, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))


V6 = {"id": "Amon.tas", "var": "tas", "table": "Amon", "freq": "mon", "long_name": "Near-Surface Air Temperature", "units": "K"}
V6D = {"id": "day.tas", "var": "tas", "table": "day", "freq": "day"}
V6P = {"id": "Amon.pr", "var": "pr", "table": "Amon", "freq": "mon"}
V7 = {"id": "mon.tas_tavg-h2m-hxy-u", "var": "tas", "branded": "tas_tavg-h2m-hxy-u", "branding_suffix": "tavg-h2m-hxy-u", "freq": "mon", "region": "glb"}


def main():
    fake = WORK / "fake"
    shutil.rmtree(fake, ignore_errors=True)
    subprocess.run([PY, str(ROOT / "scripts" / "tests" / "make_fake_cmip.py"), str(fake)], check=True)

    # ── 1) 월 자료: 모델별 파일, historical+ssp245 이어 붙이기, 첫 멤버, 한반도 상자, 달력 그대로, K→°C ──
    print("\n[1] CMIP6 monthly per-model, join, box, K→°C")
    out = WORK / "out1"
    cfg = {"lang": "ko", "project": "CMIP6", "variables": [V6], "experiments": ["historical", "ssp245"], "members": "first",
           "years": [1995, 2025], "box": {"lat": [30, 45], "lon": [120, 135]}, "calendar": None, "kToC": True,
           "folder": str(fake), "outDir": str(out)}
    s = gen("buildMergeScript", cfg, WORK / "merge1.py")
    log = run(s)
    a = sorted(out.glob("tas_Amon_MODA_historical+ssp245_r1i1p1f1_gn_*.nc"))
    check(len(a) == 1, "MODA joined file exists: %s" % [p.name for p in out.glob("*.nc")])
    if a:
        d = open_(a[0])
        t = d["time"].values
        check(d["time"].dt.calendar == "noleap", "MODA calendar noleap")
        check(len(t) == 31 * 12, "MODA 1995-01..2025-12 = 372 months (got %d)" % len(t))
        diffs = [(t[i + 1].year * 12 + t[i + 1].month) - (t[i].year * 12 + t[i].month) for i in range(len(t) - 1)]
        check(all(x == 1 for x in diffs), "MODA strictly monthly, no duplicates/gaps")
        v = d["tas"].isel(lat=0, lon=0).values
        exp = np.array([x.year * 100 + x.month for x in t], "f4")
        check(np.allclose(v, exp, atol=1e-2), "MODA values match time (overlap kept earlier piece, °C conversion)")
        check(d["tas"].attrs.get("units") == "degC", "MODA units degC")
        check(float(d.lat.min()) >= 30 and float(d.lat.max()) <= 45 and float(d.lon.min()) >= 120 and float(d.lon.max()) <= 135, "MODA box subset")
        check(d.sizes["lat"] == 6 and d.sizes["lon"] == 6, "MODA box size 6×6 (got %s)" % dict(d.sizes))
    check("v20200101" in log and ("최신" in log), "warned about two versions, used latest")
    check("겹쳐" in log, "warned about overlap 2005–2009")
    b = sorted(out.glob("tas_Amon_MODB_historical+ssp245_r1i1p1f2_gn_*.nc"))
    check(len(b) == 1, "MODB joined file exists")
    if b:
        d = open_(b[0])
        check(d["time"].dt.calendar == "360_day", "MODB calendar kept 360_day")
        check("latitude" in d.coords and d["tas"].ndim == 3, "MODB curvilinear subset kept 2-D coords")
        lat = d["latitude"].values
        m = np.isfinite(d["tas"].isel(time=0).values)
        check(m.any() and lat[m].min() >= 30 and lat[m].max() <= 45, "MODB values outside box are NaN")
    check("빈 구간" in log, "warned about MODB gap 2001")
    check(not list(out.glob("*r2i1p1f1*")), "first member only (no r2i1p1f1)")
    check("CMIP7" not in "".join(p.name for p in out.glob("*.nc")), "CMIP7 files ignored for CMIP6 project")
    check("모델별 결과" in log, "per-model summary printed")

    # ── 2) 월 자료 앙상블 + noleap 통일 (360_day 포함) ──
    print("\n[2] CMIP6 monthly ensemble, calendar → noleap, English")
    out = WORK / "out2"
    cfg2 = dict(cfg, lang="en", calendar="noleap", output="ensemble", kToC=False, outDir=str(out), box={"lat": [30, 45], "lon": [120, 135]})
    s = gen("buildMergeScript", cfg2, WORK / "merge2.py")
    log = run(s)
    # 격자가 달라 하나로 못 묶고 모델별로 저장해야 함 (경고)
    check("could not combine" in log, "ensemble across different grids falls back with warning")
    files = sorted(out.glob("*.nc"))
    check(len(files) == 2, "two per-model files after fallback (%d)" % len(files))
    for f in files:
        d = open_(f)
        check(d["time"].dt.calendar == "noleap", "%s calendar → noleap" % f.name)

    # ── 3) 같은 격자 모델만 앙상블 (MODA historical r1 + ssp245 r1/r2 all members) ──
    print("\n[3] ensemble of one grid, members=all, no join")
    out = WORK / "out3"
    cfg3 = {"lang": "ko", "project": "CMIP6", "variables": [V6], "experiments": ["ssp245"], "members": "all", "years": [2015, 2020],
            "output": "ensemble", "folder": str(fake), "outDir": str(out), "join": False}
    s = gen("buildMergeScript", cfg3, WORK / "merge3.py")
    s.write_text(s.read_text().replace("MODELS = None", 'MODELS = ["MODA"]'))
    log = run(s)
    e = sorted(out.glob("tas_Amon_multimodel_ssp245_*.nc"))
    check(len(e) == 1, "ensemble file exists")
    if e:
        d = open_(e[0])
        check(d.sizes.get("model") == 2, "model dimension = 2 members (got %s)" % dict(d.sizes))
        check(list(d["member_id"].values) == ["r1i1p1f1", "r2i1p1f1"], "member_id coordinate")
        check(d.sizes["time"] == 72, "2015–2020 = 72 months")

    # ── 4) 일 자료: 360_day → noleap, noleap 유지, 이어 붙이기 ──
    print("\n[4] CMIP6 daily, calendar → noleap")
    out = WORK / "out4"
    cfg4 = {"lang": "ko", "project": "CMIP6", "variables": [V6D], "experiments": ["historical", "ssp245"], "members": "first",
            "years": [2013, 2016], "calendar": "noleap", "folder": str(fake), "outDir": str(out)}
    s = gen("buildMergeScript", cfg4, WORK / "merge4.py")
    log = run(s)
    a = sorted(out.glob("tas_day_MODA_historical+ssp245_*.nc"))
    b = sorted(out.glob("tas_day_MODB_historical_*.nc"))
    check(len(a) == 1 and len(b) == 1, "daily files: %s" % [p.name for p in out.glob("*.nc")])
    if a:
        d = open_(a[0])
        check(d.sizes["time"] == 4 * 365, "MODA 2013–2016 noleap = 1460 days (got %d)" % d.sizes["time"])
    if b:
        d = open_(b[0])
        check(d["time"].dt.calendar == "noleap" and d.sizes["time"] == 2 * 365, "MODB 360_day → noleap 730 days (got %s %d)" % (d["time"].dt.calendar, d.sizes["time"]))
        check("360_day" in log and "align" not in log or "고르게" in log, "360_day conversion warning printed")
    check("historical" in log and "ssp245" in log, "daily log mentions experiments")

    # ── 5) standard 달력 + pr mm/day ──
    print("\n[5] pr → mm/day, calendar → standard (daily-free monthly)")
    out = WORK / "out5"
    cfg5 = {"lang": "en", "project": "CMIP6", "variables": [V6P], "experiments": ["historical"], "members": "first", "years": [2000, 2001],
            "calendar": "standard", "prMmDay": True, "folder": str(fake), "outDir": str(out)}
    s = gen("buildMergeScript", cfg5, WORK / "merge5.py")
    run(s)
    p = sorted(out.glob("pr_Amon_MODA_historical_*.nc"))
    check(len(p) == 1, "pr file")
    if p:
        d = open_(p[0])
        check(d["pr"].attrs.get("units") == "mm day-1" and np.allclose(float(d["pr"].isel(time=0, lat=0, lon=0)), 0.864, atol=1e-3), "pr converted to mm/day")
        check(d["time"].dt.calendar in ("standard", "gregorian"), "calendar standard")

    # ── 6) CMIP7 이름 규칙 ──
    print("\n[6] CMIP7 DRS file names")
    out = WORK / "out6"
    cfg6 = {"lang": "ko", "project": "CMIP7", "variables": [V7], "experiments": ["historical"], "members": "first", "folder": str(fake), "outDir": str(out)}
    s = gen("buildMergeScript", cfg6, WORK / "merge6.py")
    run(s)
    c = sorted(out.glob("tas_tavg-h2m-hxy-u_mon_glb_MODC_historical_r1i1p1f1_g110_200001-202112.nc"))
    check(len(c) == 1, "CMIP7 merged file: %s" % [x.name for x in out.glob("*.nc")])
    if c:
        d = open_(c[0])
        check(d.sizes["time"] == 22 * 12 and d["time"].dt.calendar == "proleptic_gregorian", "CMIP7 264 months, proleptic_gregorian")

    # ── 7) 실패를 숨기지 않음: 없는 폴더·조건 ──
    print("\n[7] nothing to merge → non-zero exit")
    cfg7 = dict(cfg6, experiments=["scen7-m"], outDir=str(WORK / "out7"))
    s = gen("buildMergeScript", cfg7, WORK / "merge7.py")
    run(s, expect_rc=1)

    # ── (가) intake-esgf 스크립트: 문법·import 검사 ──
    print("\n[search] intake-esgf script compile + import check")
    for i, (lang, proj, v) in enumerate([("ko", "CMIP6", V6), ("en", "CMIP7", V7)]):
        s = gen("buildScript", {"lang": lang, "project": proj, "variables": [v], "experiments": ["historical"], "models": ["X"],
                                "years": [2000, 2014], "box": {"lat": [30, 45], "lon": [120, 135]}, "calendar": "noleap", "regrid": "conservative"},
                WORK / f"search{i}.py")
        r = subprocess.run([PY, "-c", "import ast,sys; ast.parse(open(sys.argv[1]).read()); "
                            "src=open(sys.argv[1]).read().split('if __name__ ==')[0]; exec(compile(src, sys.argv[1], 'exec'), {'__name__': 'x'}); print('imports ok')", str(s)],
                           capture_output=True, text=True)
        check(r.returncode == 0 and "imports ok" in r.stdout, f"search script {proj}/{lang} imports ok {r.stderr[-300:]}")
    try:
        import intake_esgf  # noqa: F401
        check(True, "intake_esgf importable")
    except ImportError:
        print("  (intake-esgf not installed here — skipped)")

    print("\n" + ("ALL PASSED" if not FAILS else "FAILED: %d\n - " % len(FAILS) + "\n - ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
