#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==========================================================================
#  CMIP7 download-and-merge script (intake-esgf)
#  Generated: 2026-10-16 · Korean Climate Data Navigator, Model data download https://data4researchers.kr/en/model-data/
# --------------------------------------------------------------------------
#  Selected options
#    Variable   : tas_tavg-h2m-hxy-u (mon, glb)
#    Experiments: historical  (historical + scenario joined)
#    Models     : 1 — UKESM1-3-LL
#    Members    : first member per model (lowest-numbered member present in all chosen experiments)
#    Years      : 2000–2014
#    Region     : lat 30–45°, lon 120–135°
#    Calendar   : unified to noleap
#    Regridding : none (native model grid)
#    Units      : unchanged
#    Output     : one file per model and member → /home/runner/work/climate-data-guide-kr/climate-data-guide-kr/ci-results/smoke/CMIP7_UKESM1-3-LL/cmip_out/
# --------------------------------------------------------------------------
#  Install (Python 3.10 or later)
#    pip install "intake-esgf>=2026.9.28" xarray netCDF4 cftime dask
#    Regridding also needs xESMF (hard to install with pip; conda recommended):
#    conda install -c conda-forge xesmf intake-esgf xarray netCDF4 cftime dask
#  Run
#    python smoke.py
#    Original files are cached in ~/.esgf/ (change with CACHE_DIR below); files already there are not downloaded again.
# --------------------------------------------------------------------------
#  Please note
#    This is a helper written by the Korean Climate Data Navigator, not an official tool. Check data content, availability
#    and terms of use against ESGF and each modelling centre. Some models may fail depending on index and data-node status;
#    a per-model success/failure summary is printed at the end. Check the merged output (calendar, grid, units, version, errata) yourself.
#  Citation and acknowledgement — check before publishing
#    CMIP7 guidance for data users (citation, acknowledgement): https://wcrp-cmip.github.io/cmip7-guidance/docs/CMIP7/Guidance_for_users/
#    CMIP7 citation search: https://cmip7-citations.ceda.ac.uk/citations/
#    CMIP7 on this site (citation, notices): https://data4researchers.kr/en/datasets/cmip7/
# ==========================================================================
import sys
from pathlib import Path

# ── Settings (edit as needed) ────────────────────────────────────────
LANG = "en"
PROJECT = "CMIP7"
VARIABLES = [{"key": "mon.tas_tavg-h2m-hxy-u", "var": "tas", "freq": "mon", "name": "tas_tavg-h2m-hxy-u_mon_glb", "label": "tas_tavg-h2m-hxy-u (mon, glb)", "branding_suffix": "tavg-h2m-hxy-u", "region": "glb"}]
EXPERIMENTS = ["historical"]
MODELS = ["UKESM1-3-LL"]
MEMBERS = "first"  # "first" first member per model / "all" / ["r1i1p1f1", ...]
YEARS = (2000, 2014)  # (first, last) year — None for all
BOX = {"lat": (30, 45), "lon": (120, 135)}  # lat/lon box (longitude -180..360, west to east) — None for global
CALENDAR = "noleap"  # None unchanged / "noleap" / "standard"
REGRID = None  # None / "bilinear" / "conservative" (needs xESMF)
RES = 1  # regridding step (degrees)
PR_TO_MM_DAY = False  # pr kg m-2 s-1 → mm/day
K_TO_C = False  # temperature K → °C
JOIN_HISTORICAL = True  # join historical + scenario (same member only)
OUTPUT = "per_model"  # "per_model" / "ensemble" (one file with a model dimension)
OUT_DIR = Path("/home/runner/work/climate-data-guide-kr/climate-data-guide-kr/ci-results/smoke/CMIP7_UKESM1-3-LL/cmip_out")
STREAM = False  # True: read only what is needed over OPeNDAP (no download; may fail on some nodes)
CACHE_DIR = None  # where original files are stored (None: ~/.esgf/)

# ── 공통 처리 / common processing (보통은 고치지 않아도 됩니다) ─────────────
import re
import traceback
import warnings
from collections import OrderedDict, defaultdict
from datetime import date

import numpy as np
import xarray as xr
import cftime

warnings.filterwarnings("ignore", category=xr.SerializationWarning)
warnings.filterwarnings("ignore", message=".*Converting a CFTimeIndex.*")
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass
import importlib.util
CHUNKS = {} if importlib.util.find_spec("dask") else None  # dask가 있으면 큰 자료를 나눠 읽음 / lazy reading with dask

CAL_CANON = {"365_day": "noleap", "gregorian": "standard", "366_day": "all_leap"}
TEMP_VARS = {"tas", "tasmax", "tasmin", "ts", "tos", "tob", "ta", "thetao", "tsl"}


def _(ko, en):
    return ko if LANG == "ko" else en


def short(e, n=300):
    s = (type(e).__name__ + ": " + str(e)).replace("\n", " ")
    return s[:n]


class Report:
    """모델별 성공·실패 기록 / per-model success and failure log"""
    MARK = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}

    def __init__(self):
        self.items = []

    def add(self, kind, what, msg):
        self.items.append((kind, what, msg))
        print("  [%s] %s: %s" % (self.MARK[kind], what, msg), flush=True)

    def ok(self, what, msg):
        self.add("ok", what, msg)

    def warn(self, what, msg):
        self.add("warn", what, msg)

    def fail(self, what, msg):
        self.add("fail", what, msg)

    def summary(self):
        by = OrderedDict()
        for kind, what, msg in self.items:
            model = what.split()[0] if what else "-"
            by.setdefault(model, {"ok": 0, "warn": 0, "fail": 0})[kind] += 1
        print("\n" + "=" * 72)
        print(_("모델별 결과", "Result by model"))
        print("-" * 72)
        for model, n in by.items():
            st = _("실패", "FAILED") if n["fail"] and not n["ok"] else (_("일부 실패", "PARTLY") if n["fail"] else (_("경고", "WARN") if n["warn"] else _("성공", "OK")))
            print("  %-10s %-26s %s %d · %s %d · %s %d" % (st, model, _("저장", "saved"), n["ok"], _("경고", "warnings"), n["warn"], _("실패", "failed"), n["fail"]))
        fails = [(w, m) for k, w, m in self.items if k == "fail"]
        if fails:
            print("-" * 72)
            print(_("실패한 것", "Failures"))
            for w, m in fails:
                print("  - %s: %s" % (w, m))
        n_ok = sum(1 for k, _w, _m in self.items if k == "ok")
        print("=" * 72)
        print(_("저장한 파일 %d개 · 실패 %d건 · 결과 폴더: %s", "%d file(s) saved · %d failure(s) · output folder: %s") % (n_ok, len(fails), OUT_DIR))
        return 1 if (fails or n_ok == 0) else 0


def member_key(m):
    nums = [int(x) for x in re.findall(r"\d+", str(m))]
    return (nums[-4:] if len(nums) >= 4 else nums), str(m)


def choose(groups, members, rep):
    """격자·멤버 고르기 / pick one grid and the requested members"""
    by = defaultdict(list)
    for g in groups:
        by[(g["vkey"], g["source"], g["exp"], g["member"])].append(g)
    one = []
    for k, gs in by.items():
        gs.sort(key=lambda g: (g["grid"] != "gn", g["grid"]))
        if len(gs) > 1:
            rep.warn("%s %s %s" % (k[1], k[3], k[2]), _("격자가 여럿(%s)이라 %s 하나만 씁니다", "several grids (%s); using %s only") % (", ".join(g["grid"] for g in gs), gs[0]["grid"]))
        one.append(gs[0])
    if members == "all":
        return one
    by_model = defaultdict(list)
    for g in one:
        by_model[(g["vkey"], g["source"])].append(g)
    out = []
    for (vkey, src), gs in by_model.items():
        exps = sorted({g["exp"] for g in gs})
        sets = {e: {g["member"] for g in gs if g["exp"] == e} for e in exps}
        if isinstance(members, (list, tuple)):
            keep = set(members)
            sel = [g for g in gs if g["member"] in keep]
            for e in exps:
                miss = keep - sets[e]
                if miss:
                    rep.warn("%s %s" % (src, e), _("없는 멤버: %s", "members not available: %s") % ", ".join(sorted(miss, key=member_key)))
            out += sel
            continue
        common = set.intersection(*sets.values()) if sets else set()
        if common:
            m = min(common, key=member_key)
            out += [g for g in gs if g["member"] == m]
        else:
            rep.warn(src, _("고른 실험에 모두 있는 멤버가 없어 실험마다 첫 멤버를 따로 골랐습니다 (이어 붙이지 않음)", "no member is present in every chosen experiment; picked the first member of each experiment separately (not joined)"))
            for e in exps:
                m = min(sets[e], key=member_key)
                out += [g for g in gs if g["exp"] == e and g["member"] == m]
    return out


def open_nc(path):
    try:
        kw = {"decode_times": xr.coders.CFDatetimeCoder(use_cftime=True)}
    except AttributeError:  # 옛 xarray
        kw = {"use_cftime": True}
    return xr.open_dataset(path, chunks=CHUNKS, decode_timedelta=False, **kw)


def calendar_of(ds):
    t = ds["time"]
    cal = None
    try:
        cal = t.dt.calendar
    except Exception:
        pass
    cal = cal or t.encoding.get("calendar") or t.attrs.get("calendar") or "standard"
    return CAL_CANON.get(cal, cal)


def tstr(t, freq="day"):
    try:
        return ("%04d-%02d" % (t.year, t.month)) if freq in ("mon", "yr") else ("%04d-%02d-%02d" % (t.year, t.month, t.day))
    except Exception:
        return str(t)[:10]


def time_step(ds):
    t = ds["time"].values
    if len(t) < 2:
        return None
    try:
        d = sorted(t[i + 1] - t[i] for i in range(min(len(t) - 1, 60)))
        return d[len(d) // 2]
    except Exception:
        return None


def has_gap(prev_end, nxt, freq, step):
    try:
        if freq == "mon":
            return (nxt.year * 12 + nxt.month) - (prev_end.year * 12 + prev_end.month) > 1
        if freq == "yr":
            return nxt.year - prev_end.year > 1
        return step is not None and (nxt - prev_end) > step * 1.5
    except Exception:
        return False


def keep_vars(d, var):
    extra = [v for v in d.data_vars if v != var and (v.endswith("_bnds") or v.endswith("_bounds") or v.startswith("vertices"))]
    return d[[var] + extra]


def concat_time(items, label, rep, freq):
    """시간 순 정렬 → 겹침은 앞 자료 값 사용·경고 → 빈 구간 경고 → 이어 붙이기
    sort by time, drop overlaps (keep the earlier piece, warn), warn about gaps, concatenate"""
    items = [(n, d) for n, d in items if "time" in d.dims and d.sizes["time"] > 0]
    if not items:
        raise ValueError(_("시간 축이 있는 자료가 없습니다", "nothing with a time axis"))
    items.sort(key=lambda x: x[1]["time"].values[0])
    kept = [items[0]]
    for name, d in items[1:]:
        pname, prev = kept[-1]
        pend = prev["time"].values[-1]
        t = d["time"].values
        if t[0] <= pend:
            n = int(sum(1 for x in t if x <= pend))
            rep.warn(label, _("%s: 앞 자료(%s)와 %d개 시각이 겹쳐(%s–%s) 겹친 부분은 앞 자료 값을 썼습니다",
                              "%s overlaps %s at %d time steps (%s–%s); kept the earlier values") % (name, pname, n, tstr(t[0], freq), tstr(pend, freq)))
            if n >= len(t):
                continue
            d = d.isel(time=slice(n, None))
        elif has_gap(pend, t[0], freq, time_step(prev)):
            rep.warn(label, _("빈 구간: %s 다음이 %s입니다 (%s → %s)", "gap: %s is followed by %s (%s → %s)") % (tstr(pend, freq), tstr(t[0], freq), pname, name))
        kept.append((name, d))
    if len(kept) == 1:
        return kept[0][1]
    return xr.concat([d for _n, d in kept], dim="time", data_vars="minimal", coords="minimal",
                     compat="override", join="override", combine_attrs="override")


def open_group(g, rep, label):
    """한 데이터셋(모델·실험·멤버·격자)의 파일들을 열어 시간 순으로 이어 붙임"""
    pieces, tids = [], []
    for f in g["files"]:
        name = Path(str(f)).name
        try:
            d = open_nc(f)
        except Exception as e:
            rep.warn(label, _("파일을 열지 못해 뺐습니다: %s (%s)", "could not open, skipped: %s (%s)") % (name, short(e, 150)))
            continue
        if g["var"] not in d.data_vars:
            rep.warn(label, _("%s 안에 변수 %s가 없어 뺐습니다", "%s has no variable %s; skipped") % (name, g["var"]))
            continue
        if "time" not in d.dims:
            rep.warn(label, _("%s에 시간 축이 없어 뺐습니다", "%s has no time axis; skipped") % name)
            continue
        if d.attrs.get("tracking_id"):
            tids.append(str(d.attrs["tracking_id"]))
        d = keep_vars(d, g["var"]).sortby("time")
        if YEARS:
            d = d.sel(time=slice("%04d" % YEARS[0], "%04d" % YEARS[1]))
            if d.sizes["time"] == 0:
                continue
        pieces.append((name, d))
    if not pieces:
        raise ValueError(_("고른 기간에 해당하는 자료가 없습니다", "no data in the chosen years"))
    ds = concat_time(pieces, label, rep, g["freq"])
    ds.attrs["source_files"] = " ".join(n for n, _d in pieces)
    if tids:
        ds.attrs["tracking_ids"] = " ".join(tids)
    ds.attrs.pop("tracking_id", None)
    return ds


def join_experiments(dsx, rep, src, mem, freq):
    """historical + 시나리오를 같은 멤버끼리 이어 붙임 (esm-scen* 은 esm-hist 와)"""
    if not JOIN_HISTORICAL:
        return list(dsx.items())
    out, used = [], set()
    for exp in sorted(dsx):
        if exp in ("historical", "esm-hist"):
            continue
        base = "esm-hist" if exp.startswith("esm-") else "historical"
        if base not in EXPERIMENTS:
            out.append((exp, dsx[exp]))
            continue
        if base not in dsx:
            rep.warn("%s %s %s" % (src, mem, exp), _("같은 멤버의 %s가 없어 이어 붙이지 않았습니다", "no %s for the same member; not joined") % base)
            out.append((exp, dsx[exp]))
            continue
        label = "%s %s %s+%s" % (src, mem, base, exp)
        out.append(("%s+%s" % (base, exp), concat_time([(base, dsx[base]), (exp, dsx[exp])], label, rep, freq)))
        used.add(base)
    for base in ("historical", "esm-hist"):
        if base in dsx and base not in used:
            out.append((base, dsx[base]))
    return out


def coord_name(ds, kind):
    names = {"lat": ("lat", "latitude", "nav_lat"), "lon": ("lon", "longitude", "nav_lon")}[kind]
    std = {"lat": "latitude", "lon": "longitude"}[kind]
    cands = list(ds.coords) + list(ds.data_vars)
    for n in cands:
        if str(n).lower() in names:
            return n
    for n in cands:
        if ds[n].attrs.get("standard_name") == std and ds[n].ndim in (1, 2):
            return n
    return None


def bounds_vars(ds):
    out = []
    for kind in ("lat", "lon"):
        n = coord_name(ds, kind)
        if n is not None and ds[n].attrs.get("bounds") in ds:
            out.append(ds[n].attrs["bounds"])
    return out + [v for v in ("lat_bnds", "lon_bnds", "vertices_latitude", "vertices_longitude") if v in ds and v not in out]


def subset_box(ds, box, var, margin=0.0):
    """위경도 상자 잘라내기 — 일반 위경도 격자·곡선 격자(해양)·비정형 격자"""
    latn, lonn = coord_name(ds, "lat"), coord_name(ds, "lon")
    if latn is None or lonn is None:
        raise ValueError(_("위경도 좌표를 찾지 못했습니다", "could not find latitude/longitude"))
    la0, la1 = box["lat"][0] - margin, box["lat"][1] + margin
    lo0, lo1 = box["lon"][0] - margin, box["lon"][1] + margin
    full = (lo1 - lo0) >= 360
    width = (lo1 - lo0) % 360
    lat, lon = ds[latn].load(), ds[lonn].load()
    lat_ok = (lat >= la0) & (lat <= la1)
    lon_ok = None if full else (((lon - lo0) % 360) <= width)
    nothing = _("상자 안에 격자점이 없습니다", "no grid points inside the box")
    if lat.ndim == 1 and lon.ndim == 1 and lat.dims != lon.dims:
        yi = np.where(lat_ok.values)[0]
        xi = np.arange(lon.size) if full else np.where(lon_ok.values)[0]
        if not len(yi) or not len(xi):
            raise ValueError(nothing)
        ds = ds.isel({lat.dims[0]: yi, lon.dims[0]: xi})
        if not full:  # 경도를 상자 기준으로 이어지게 (예: 350–370° = 350–10°)
            old = ds[lonn].values
            new = lo0 + np.mod(old - lo0, 360.0)
            b = ds[lonn].attrs.get("bounds")
            if b in ds and ds[b].dims[0] == ds[lonn].dims[0]:
                ds[b] = ds[b].copy(data=ds[b].values + (new - old)[:, None])
            attrs = ds[lonn].attrs
            ds = ds.assign_coords({lonn: (ds[lonn].dims, new, attrs)})
            ds = ds.sortby(lonn)
        return ds
    mask = lat_ok if full else (lat_ok & lon_ok)
    if lat.ndim == 1:  # 비정형 격자 (unstructured)
        idx = np.where(mask.values)[0]
        if not len(idx):
            raise ValueError(nothing)
        return ds.isel({lat.dims[0]: idx})
    ys, xs = np.where(mask.values)  # 곡선 격자 (curvilinear) — 상자를 감싸는 범위만 남기고 밖은 NaN
    if not len(ys):
        raise ValueError(nothing)
    d0, d1 = lat.dims
    sl = {d0: slice(int(ys.min()), int(ys.max()) + 1), d1: slice(int(xs.min()), int(xs.max()) + 1)}
    ds = ds.isel(sl)
    ds[var] = ds[var].where(mask.isel(sl))
    return ds


def set_time(ds, times, calendar):
    tb = ds["time"].attrs.get("bounds")
    drop = [v for v in (tb, "time_bnds", "time_bounds") if v and v in ds]
    ds = ds.drop_vars(drop)
    ds = ds.assign_coords(time=("time", np.array(times, dtype=object), {k: v for k, v in ds["time"].attrs.items() if k != "bounds"}))
    ds["time"].encoding = {"units": "days since 1850-01-01", "calendar": calendar}
    return ds


def unify_calendar(ds, target, freq, rep, label):
    src = calendar_of(ds)
    if not target or src == target:
        return ds
    if freq in ("mon", "yr"):
        # 월·연 자료: 같은 연·월의 가운데(15일)로 다시 적음 / monthly: re-stamp at the 15th of the same month
        t = [cftime.datetime(x.year, x.month if freq == "mon" else 7, 15 if freq == "mon" else 1, calendar=target) for x in ds["time"].values]
        rep.warn(label, _("달력 %s → %s: 월 자료라 같은 연·월의 15일로 다시 적었습니다 (시간 경계 변수는 뺌)",
                          "calendar %s → %s: monthly data re-stamped at the 15th of each month (time bounds dropped)") % (src, target))
        return set_time(ds, t, target)
    tb = ds["time"].attrs.get("bounds")
    ds = ds.drop_vars([v for v in (tb, "time_bnds", "time_bounds") if v and v in ds])
    align = "year" if "360_day" in (src, target) else None
    n0 = ds.sizes["time"]
    try:
        out = ds.convert_calendar(target, align_on=align, missing=np.nan, use_cftime=True)
    except Exception:
        out = ds.convert_calendar(target, align_on=align, use_cftime=True)
    msg = _("달력 %s → %s: 시각 %d개 → %d개", "calendar %s → %s: %d → %d time steps") % (src, target, n0, out.sizes["time"])
    if align == "year":
        msg += _(" — 360_day 변환은 해마다 날짜를 고르게 늘리거나 줄인 것이라 일별 값의 날짜가 하루 이틀 어긋나고, 새로 생긴 날은 NaN입니다",
                 " — 360_day conversion spreads the missing/extra days over the year, so daily values shift by a day or two; inserted days are NaN")
    elif out.sizes["time"] > n0:
        msg += _(" (새로 생긴 2월 29일은 NaN)", " (inserted 29 February values are NaN)")
    elif out.sizes["time"] < n0:
        msg += _(" (2월 29일을 뺌)", " (29 February dropped)")
    rep.warn(label, msg)
    out["time"].encoding = {"units": "days since 1850-01-01", "calendar": target}
    return out


def convert_units(ds, var, rep, label):
    da = ds[var]
    u = str(da.attrs.get("units", "")).strip()
    if PR_TO_MM_DAY and var == "pr":
        if u.replace(" ", "") in ("kgm-2s-1", "kg/m2/s", "kgm**-2s**-1", "kg/m^2/s"):
            ds[var] = (da * 86400.0).assign_attrs(dict(da.attrs, units="mm day-1"))
        else:
            rep.warn(label, _("pr 단위가 %r라 mm/day로 바꾸지 않았습니다", "pr units are %r; not converted to mm/day") % u)
    if K_TO_C and var in TEMP_VARS and u == "K":
        ds[var] = (da - 273.15).assign_attrs(dict(da.attrs, units="degC"))
    return ds


def regrid(ds, var, method, rep, label):
    try:
        import xesmf as xe
    except ImportError:
        raise RuntimeError(_("재격자에는 xESMF가 필요합니다: conda install -c conda-forge xesmf", "regridding needs xESMF: conda install -c conda-forge xesmf"))
    if BOX:
        tgt = xe.util.cf_grid_2d(BOX["lon"][0], BOX["lon"][1], RES, BOX["lat"][0], BOX["lat"][1], RES)
    else:
        tgt = xe.util.cf_grid_2d(-180, 180, RES, -90, 90, RES)
    src = ds[[var] + [b for b in bounds_vars(ds) if b in ds]]
    err = None
    for m in ([method] if method == "bilinear" else [method, "bilinear"]):
        try:
            rg = xe.Regridder(src, tgt, m, periodic=BOX is None, ignore_degenerate=True, unmapped_to_nan=True)
            out = rg(src[var], keep_attrs=True, skipna=True, na_thres=0.5)
            if m != method:
                rep.warn(label, _("%s 재격자에 실패해 bilinear로 했습니다 (%s)", "%s regridding failed, used bilinear (%s)") % (method, short(err, 150)))
            res = out.to_dataset(name=var)
            res.attrs = dict(ds.attrs, regrid="xESMF %s to a %g degree grid" % (m, RES))
            return res
        except Exception as e:
            err = e
    raise err


def finish(ds, g, rep, label):
    var, freq = g["var"], g["freq"]
    if YEARS:
        ds = ds.sel(time=slice("%04d" % YEARS[0], "%04d" % YEARS[1]))
        if ds.sizes["time"] == 0:
            raise ValueError(_("고른 기간에 해당하는 자료가 없습니다", "no data in the chosen years"))
        t = ds["time"].values
        if t[0].year > YEARS[0] or t[-1].year < YEARS[1]:
            rep.warn(label, _("자료 기간 %s–%s가 고른 기간(%d–%d)보다 짧습니다", "data cover %s–%s, shorter than the chosen %d–%d") % (tstr(t[0], freq), tstr(t[-1], freq), YEARS[0], YEARS[1]))
    if BOX:
        ds = subset_box(ds, BOX, var, margin=(2 * RES + 1) if REGRID else 0)
    ds = unify_calendar(ds, CALENDAR, freq, rep, label)
    ds = convert_units(ds, var, rep, label)
    if REGRID:
        ds = regrid(ds, var, REGRID, rep, label)
    return ds


def period_tag(ds, freq):
    t = ds["time"].values
    f = (lambda x: "%04d%02d" % (x.year, x.month)) if freq in ("mon", "yr") else (lambda x: "%04d%02d%02d" % (x.year, x.month, x.day))
    return "%s-%s" % (f(t[0]), f(t[-1]))


def clean_encoding(ds, var):
    # 시간·경계 변수는 작으니 메모리로 읽어 둠 (dask 날짜 배열은 인코딩 지정이 까다로움)
    for v in list(ds.variables):
        if v != var and (v == "time" or "bnds" in v or "bounds" in v or v.startswith("vertices")):
            ds[v] = ds[v].load()
    for v in ds.variables:
        enc = ds[v].encoding
        keep = ("dtype", "_FillValue", "units", "calendar") if v != var else ()
        ds[v].encoding = {k: enc[k] for k in keep if k in enc}
        ds[v].attrs.pop("missing_value", None)
        ds[v].attrs.pop("_FillValue", None)
    for v in ("time",) + tuple(x for x in ds.variables if x.startswith("time_b")):
        if v in ds.variables:
            ds[v].encoding.pop("dtype", None)
    if "time" in ds.variables:
        ds["time"].encoding.setdefault("units", "days since 1850-01-01")
        ds["time"].encoding["calendar"] = calendar_of(ds)
    ds[var].encoding = {"zlib": True, "complevel": 4, "dtype": "float32", "_FillValue": np.float32(1e20)}
    return ds


def save(ds, var, path, rep, label, freq):
    path.parent.mkdir(parents=True, exist_ok=True)
    ds = clean_encoding(ds, var)
    hist = "%s: %s (%s)" % (date.today().isoformat(), "subset/merged by the model-data script of data4researchers.kr", "https://data4researchers.kr/model-data/")
    ds.attrs["history"] = hist + ("\n" + ds.attrs["history"] if ds.attrs.get("history") else "")
    tmp = path.with_name(path.name + ".part")
    ds.to_netcdf(tmp)
    tmp.replace(path)
    with open_nc(path) as chk:
        dims = " × ".join("%s %d" % (k, v) for k, v in chk[var].sizes.items())
        info = "%s · %s · %s–%s · %.1f MB" % (dims, calendar_of(chk), tstr(chk["time"].values[0], freq), tstr(chk["time"].values[-1], freq), path.stat().st_size / 1e6)
    rep.ok(label, "%s (%s)" % (path, info))


def same_grid(a, b):
    for kind in ("lat", "lon"):
        na, nb = coord_name(a, kind), coord_name(b, kind)
        if na is None or nb is None or a[na].shape != b[nb].shape:
            return False
        if not np.allclose(np.asarray(a[na].values, float), np.asarray(b[nb].values, float), atol=1e-4):
            return False
    return True


def make_ensemble(items, var, freq):
    """여러 모델을 model 차원으로 묶기 / stack models along a 'model' dimension"""
    cals = sorted({calendar_of(d) for _s, _m, d in items})
    if len(cals) > 1:
        raise ValueError(_("모델마다 달력이 달라(%s) 하나로 묶을 수 없습니다 — CALENDAR를 정하세요", "calendars differ (%s); set CALENDAR to combine") % ", ".join(cals))
    ref = items[0][2]
    for s, m, d in items[1:]:
        if not same_grid(ref, d):
            raise ValueError(_("%s의 격자가 다른 모델과 달라 묶을 수 없습니다 — REGRID를 정하세요", "%s is on a different grid; set REGRID to combine") % s)
    cal = cals[0]
    das = []
    for s, m, d in items:
        if freq == "mon":
            t = [cftime.datetime(x.year, x.month, 15, calendar=cal) for x in d["time"].values]
        else:
            t = [cftime.datetime(x.year, x.month, x.day, 12 if freq == "day" else x.hour, calendar=cal) for x in d["time"].values]
        d = set_time(d[[var]], t, cal)
        latn, lonn = coord_name(ref, "lat"), coord_name(ref, "lon")
        if latn in d.coords and d[latn].ndim == 1 and latn in d.dims:
            d = d.assign_coords({latn: ref[latn].values, lonn: ref[lonn].values})
        label = s if all(x[0] != s or x[1] == m for x in items) else "%s_%s" % (s, m)
        das.append(d[var].expand_dims(model=[label]).assign_coords(source_id=("model", [s]), member_id=("model", [m])))
    out = xr.concat(das, dim="model", join="outer", coords="minimal", compat="override", combine_attrs="drop")
    ds = out.to_dataset(name=var)
    a = items[0][2][var].attrs
    ds[var].attrs = {k: a[k] for k in ("standard_name", "long_name", "units", "cell_methods") if k in a}
    ds["time"].encoding = {"units": "days since 1850-01-01", "calendar": cal}
    ds.attrs = {"title": "%s multi-model collection" % var, "project": PROJECT, "models": " ".join(x[0] for x in items),
                "note": "time re-stamped to a common day per %s step across models" % freq}
    return ds


def process(groups, rep):
    units = defaultdict(dict)
    for g in groups:
        units[(g["vkey"], g["source"], g["member"], g["grid"])][g["exp"]] = g
    ens = defaultdict(list)
    for (vkey, src, mem, grid), by_exp in sorted(units.items(), key=lambda kv: (kv[0][0], kv[0][1].lower(), member_key(kv[0][2]))):
        g0 = next(iter(by_exp.values()))
        print("\n[%s %s %s] %s" % (src, mem, grid, g0["label"]), flush=True)
        dsx = {}
        for exp, g in sorted(by_exp.items()):
            try:
                dsx[exp] = open_group(g, rep, "%s %s %s" % (src, mem, exp))
            except Exception as e:
                rep.fail("%s %s %s" % (src, mem, exp), short(e))
        for explabel, ds in join_experiments(dsx, rep, src, mem, g0["freq"]):
            label = "%s %s %s" % (src, mem, explabel)
            try:
                ds = finish(ds, g0, rep, label)
                if OUTPUT == "ensemble":
                    ens[(vkey, explabel)].append((src, mem, ds))
                    continue
                name = "%s_%s_%s_%s_%s_%s%s%s.nc" % (g0["name"], src, explabel, mem, grid, period_tag(ds, g0["freq"]),
                                                     "_box" if BOX else "", ("_%gdeg" % RES) if REGRID else "")
                save(ds, g0["var"], OUT_DIR / name, rep, label, g0["freq"])
            except Exception as e:
                rep.fail(label, short(e))
                if "-v" in sys.argv:
                    traceback.print_exc()
    for (vkey, explabel), items in ens.items():
        g0 = next(g for g in groups if g["vkey"] == vkey)
        var, freq = g0["var"], g0["freq"]
        print("\n[ensemble] %s %s: %d" % (g0["label"], explabel, len(items)), flush=True)
        try:
            ds = make_ensemble(items, var, freq)
            name = "%s_multimodel_%s_%s%s%s.nc" % (g0["name"], explabel, period_tag(ds, freq), "_box" if BOX else "", ("_%gdeg" % RES) if REGRID else "")
            save(ds, var, OUT_DIR / name, rep, "ensemble %s" % explabel, freq)
        except Exception as e:
            rep.warn("ensemble %s" % explabel, _("하나로 묶지 못해 모델별 파일로 저장합니다: %s", "could not combine, saving one file per model instead: %s") % short(e))
            for s, m, d in items:
                try:
                    name = "%s_%s_%s_%s_%s.nc" % (g0["name"], s, explabel, m, period_tag(d, freq))
                    save(d, var, OUT_DIR / name, rep, "%s %s %s" % (s, m, explabel), freq)
                except Exception as e2:
                    rep.fail("%s %s %s" % (s, m, explabel), short(e2))


# ── ESGF에서 찾아 받기 / search ESGF and download ───────────────────
def search_and_download(rep):
    try:
        import intake_esgf
        from intake_esgf import ESGFCatalog
    except ImportError:
        print(_("intake-esgf가 필요합니다: pip install intake-esgf", "intake-esgf is required: pip install intake-esgf"))
        sys.exit(1)
    if PROJECT == "CMIP6":
        # 새 STAC 색인의 CMIP6 항목에는 member_id 오류가 있어 끕니다 (intake-esgf 권장)
        intake_esgf.conf.set(indices={"discovery.east.esgf.io": False, "discovery.west.esgf.io": False})
    intake_esgf.conf.set(break_on_error=False)
    if CACHE_DIR:
        intake_esgf.conf.set(local_cache=[str(Path(CACHE_DIR).expanduser())])
    mfacet = "member_id" if PROJECT == "CMIP6" else "variant_label"
    groups = []
    for v in VARIABLES:
        for model in MODELS:
            facets = {"project": PROJECT, "source_id": model, "experiment_id": EXPERIMENTS, "variable_id": v["var"]}
            if PROJECT == "CMIP6":
                facets["table_id"] = v["table"]
            else:
                facets.update(frequency=v["freq"], region=v["region"], variable_branding_suffix=v["branding_suffix"])
            if isinstance(MEMBERS, (list, tuple)):
                facets[mfacet] = list(MEMBERS)
            kw = {"file_start": "%04d-01-01" % YEARS[0], "file_end": "%04d-12-31" % YEARS[1]} if YEARS else {}
            print("\n[%s] %s — %s" % (model, v["label"], _("ESGF 검색", "searching ESGF")), flush=True)
            try:
                cat = ESGFCatalog()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    cat.search(quiet=True, **kw, **facets)
            except Exception as e:
                rep.fail(model, _("검색 결과가 없거나 검색에 실패했습니다", "no search results or search failed") + " (%s)" % short(e, 200))
                continue
            df = cat.df
            cands = []
            for i, r in df.iterrows():
                cands.append({"idx": i, "vkey": v["key"], "var": v["var"], "freq": v["freq"], "name": v["name"], "label": v["label"],
                              "source": model, "exp": str(r["experiment_id"]), "member": str(r[mfacet]), "grid": str(r.get("grid_label", ""))})
            miss = [e for e in EXPERIMENTS if e not in {c["exp"] for c in cands}]
            if miss:
                rep.warn(model, _("색인에 없는 실험: %s", "experiments not in the index: %s") % ", ".join(miss))
            chosen = choose(cands, MEMBERS, rep)
            if not chosen:
                rep.fail(model, _("고른 조건에 맞는 데이터셋이 없습니다", "no dataset matches the selection"))
                continue
            cat.df = df.loc[[c["idx"] for c in chosen]].copy()
            print("  " + _("받을 데이터셋 %d개: %s", "%d dataset(s) to fetch: %s") % (len(chosen), ", ".join("%s %s" % (c["exp"], c["member"]) for c in chosen)), flush=True)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    paths = cat.to_path_dict(prefer_streaming=STREAM, minimal_keys=False, quiet=False)
            except Exception as e:
                rep.fail(model, _("파일 정보를 얻거나 내려받지 못했습니다", "could not get file information or download") + " (%s)" % short(e, 200))
                continue
            for c in chosen:
                key = cat.df.loc[c["idx"], "key"]
                files = sorted(paths.get(key) or [], key=lambda p: Path(str(p)).name)
                if not files:
                    rep.fail("%s %s %s" % (model, c["member"], c["exp"]), _("파일을 받지 못했습니다", "no files could be fetched"))
                    continue
                c["files"] = files
                groups.append(c)
    return groups


if __name__ == "__main__":
    rep = Report()
    groups = search_and_download(rep)
    if groups:
        process(groups, rep)
    sys.exit(rep.summary())
