// 모델 자료 받기 — 가용성 표 + 받기·합치기 Python 스크립트 만들기 (docs/model-data.md)
// 카탈로그는 hooks/datasets.py 가 data/model-catalog/catalog.json 을 읽어 <script id="model-catalog"> 로 넣습니다.
// 위쪽: 스크립트를 만드는 순수 함수 buildScript(cfg)·buildMergeScript(cfg) — node 에서도 require 해서 시험할 수 있음
// 아래쪽: 브라우저 화면(DOM) 코드
(function (root) {
  "use strict";

  // ── Python 값 쓰기 ──────────────────────────────────────────
  function py(v) {
    if (v === null || v === undefined) return "None";
    if (v === true) return "True";
    if (v === false) return "False";
    if (typeof v === "number") return isFinite(v) ? String(v) : "None";
    if (typeof v === "string") return JSON.stringify(v);
    if (Array.isArray(v)) return "[" + v.map(py).join(", ") + "]";
    return "{" + Object.keys(v).map(function (k) { return JSON.stringify(k) + ": " + py(v[k]); }).join(", ") + "}";
  }
  function oneLine(s) { return String(s == null ? "" : s).replace(/[\r\n]+/g, " ").trim(); }

  var SITE = "https://data4researchers.kr/";
  var CITE = {
    CMIP6: [
      ["CMIP6 이용 약관 (인용·사사 문장)", "CMIP6 terms of use (citation and acknowledgement)", "https://pcmdi.llnl.gov/CMIP6/TermsOfUse/TermsOfUse6-2.html"],
      ["이 사이트의 CMIP6 정리 (인용·공지)", "CMIP6 on this site (citation, notices)", "datasets/cmip6/"]
    ],
    CMIP7: [
      ["CMIP7 자료 이용자 안내 (인용·사사)", "CMIP7 guidance for data users (citation, acknowledgement)", "https://wcrp-cmip.github.io/cmip7-guidance/docs/CMIP7/Guidance_for_users/"],
      ["CMIP7 인용 검색", "CMIP7 citation search", "https://cmip7-citations.ceda.ac.uk/citations/"],
      ["이 사이트의 CMIP7 정리 (인용·공지)", "CMIP7 on this site (citation, notices)", "datasets/cmip7/"]
    ]
  };

  function normCfg(cfg) {
    var c = {};
    Object.keys(cfg || {}).forEach(function (k) { c[k] = cfg[k]; });
    c.lang = c.lang === "en" ? "en" : "ko";
    c.project = c.project === "CMIP7" ? "CMIP7" : "CMIP6";
    c.variables = (c.variables || []).map(function (v) {
      var o = { key: v.id || v.key, var: v["var"], freq: v.freq };
      if (c.project === "CMIP6") { o.table = v.table; o.name = v["var"] + "_" + v.table; o.label = v["var"] + " (" + v.table + ")"; }
      else {
        o.branding_suffix = v.branding_suffix; o.region = v.region || "glb";
        o.name = v["var"] + "_" + v.branding_suffix + "_" + v.freq + "_" + o.region;
        o.label = (v.branded || (v["var"] + "_" + v.branding_suffix)) + " (" + v.freq + ", " + o.region + ")";
      }
      o.long_name = v.long_name || ""; o.units = v.units || "";
      return o;
    });
    c.experiments = (c.experiments || []).slice();
    c.models = (c.models || []).slice();
    c.members = c.members === "all" ? "all" : (Array.isArray(c.members) ? c.members.slice() : "first");
    c.years = c.years && c.years.length === 2 && c.years[0] != null && c.years[1] != null ? [+c.years[0], +c.years[1]] : null;
    c.box = c.box ? { lat: [+c.box.lat[0], +c.box.lat[1]], lon: [+c.box.lon[0], +c.box.lon[1]] } : null;
    c.calendar = c.calendar === "noleap" || c.calendar === "standard" ? c.calendar : null;
    c.regrid = c.regrid === "bilinear" || c.regrid === "conservative" ? c.regrid : null;
    c.res = +c.res > 0 ? +c.res : 1.0;
    c.prMmDay = !!c.prMmDay;
    c.kToC = !!c.kToC;
    c.join = c.join !== false;
    c.output = c.output === "ensemble" ? "ensemble" : "per_model";
    c.outDir = c.outDir || "cmip_out";
    c.stream = !!c.stream;
    c.folder = c.folder || "./cmip_files";
    c.generated = c.generated || new Date().toISOString().slice(0, 10);
    return c;
  }

  // ── 스크립트 맨 위 안내 ────────────────────────────────────────
  function header(c, kind) {
    var ko = c.lang === "ko";
    function L(a, b) { return ko ? a : b; }
    var base = SITE + (ko ? "" : "en/");
    var y = c.years ? c.years[0] + "–" + c.years[1] : L("전체 기간", "full period");
    var box = c.box ? L("위도 ", "lat ") + c.box.lat[0] + "–" + c.box.lat[1] + "°, " + L("경도 ", "lon ") + c.box.lon[0] + "–" + c.box.lon[1] + "°" : L("전지구", "global");
    var mem = c.members === "first" ? L("모델별 첫 멤버 (고른 실험에 모두 있는 멤버 중 가장 앞 번호)", "first member per model (lowest-numbered member present in all chosen experiments)")
      : c.members === "all" ? L("전부", "all") : c.members.join(", ");
    var cal = c.calendar ? L(c.calendar + " 로 통일", "unified to " + c.calendar) : L("모델 원래 달력 그대로", "model's own calendar (unchanged)");
    var rg = c.regrid ? L("공통 " + c.res + "° 격자, " + c.regrid + " (xESMF)", "common " + c.res + "° grid, " + c.regrid + " (xESMF)") : L("없음 (모델 원래 격자)", "none (native model grid)");
    var units = [];
    if (c.prMmDay) units.push("pr → mm/day");
    if (c.kToC) units.push(L("기온 K → °C", "temperature K → °C"));
    var out = c.output === "ensemble" ? L("여러 모델을 model 차원으로 묶은 한 파일", "one file per variable/experiment with a model dimension")
      : L("모델·멤버별 파일", "one file per model and member");
    var vars = c.variables.map(function (v) { return v.label + (v.long_name ? " — " + v.long_name : "") + (v.units ? " [" + v.units + "]" : ""); });
    var title = kind === "search"
      ? L(c.project + " 자료 받기·합치기 스크립트 (intake-esgf)", c.project + " download-and-merge script (intake-esgf)")
      : L("이미 받은 " + c.project + " 파일 폴더 합치기 스크립트", "Merge script for " + c.project + " files you already downloaded");
    var H = [
      "#!/usr/bin/env python3",
      "# -*- coding: utf-8 -*-",
      "# " + "=".repeat(74),
      "#  " + title,
      "#  " + L("만든 날: ", "Generated: ") + c.generated + L(" · 기후데이터 길잡이 '모델 자료 받기' ", " · Korean Climate Data Navigator, Model data download ") + base + "model-data/",
      c.catalogDate ? "#  " + L("가용성 표(카탈로그) 기준: ", "Availability table (catalog) as of: ") + c.catalogDate : null,
      "# " + "-".repeat(74),
      "#  " + L("고른 조건", "Selected options"),
      "#    " + L("변수  : ", "Variable   : ") + vars.map(oneLine).join("; "),
      "#    " + L("실험  : ", "Experiments: ") + c.experiments.join(", ") + (c.join ? L("  (historical + 시나리오 이어 붙이기)", "  (historical + scenario joined)") : ""),
      kind === "search"
        ? "#    " + L("모델  : ", "Models     : ") + c.models.length + L("개 — ", " — ") + c.models.join(", ")
        : "#    " + L("폴더  : ", "Folder     : ") + c.folder,
      "#    " + L("멤버  : ", "Members    : ") + mem,
      "#    " + L("기간  : ", "Years      : ") + y,
      "#    " + L("영역  : ", "Region     : ") + box,
      "#    " + L("달력  : ", "Calendar   : ") + cal,
      "#    " + L("재격자: ", "Regridding : ") + rg,
      "#    " + L("단위  : ", "Units      : ") + (units.join(", ") || L("원래 단위 그대로", "unchanged")),
      "#    " + L("출력  : ", "Output     : ") + out + " → " + c.outDir + "/",
      "# " + "-".repeat(74),
      "#  " + L("설치 (Python 3.10 이상)", "Install (Python 3.10 or later)"),
      "#    pip install " + (kind === "search" ? "\"intake-esgf>=2026.9.28\" " : "") + "xarray netCDF4 cftime dask",
      "#    " + L("재격자를 쓰면 xESMF도 필요합니다 (pip로는 설치가 어려워 conda를 권합니다):", "Regridding also needs xESMF (hard to install with pip; conda recommended):"),
      "#    conda install -c conda-forge xesmf" + (kind === "search" ? " intake-esgf" : "") + " xarray netCDF4 cftime dask",
      "#  " + L("실행", "Run"),
      "#    python " + (c.fileName || "this_script.py"),
      kind === "search"
        ? "#    " + L("받은 원본 파일은 ~/.esgf/ 에 쌓이고(아래 CACHE_DIR로 바꿀 수 있음), 다시 실행하면 이미 받은 파일은 건너뜁니다.", "Original files are cached in ~/.esgf/ (change with CACHE_DIR below); files already there are not downloaded again.")
        : "#    " + L("파일 이름이 CMIP6·CMIP7 규칙(DRS)을 따라야 묶을 수 있습니다. 하위 폴더도 찾습니다.", "File names must follow the CMIP6/CMIP7 naming rules (DRS). Sub-folders are searched too."),
      "# " + "-".repeat(74),
      "#  " + L("주의", "Please note"),
      "#    " + L("이 스크립트는 기후데이터 길잡이가 만든 보조 도구이며 공식 도구가 아닙니다. 자료의 내용·가용성·이용 조건은", "This is a helper written by the Korean Climate Data Navigator, not an official tool. Check data content, availability"),
      "#    " + L("ESGF와 각 모델링 센터의 공식 출처에서 확인하세요. 색인·자료 노드 상태에 따라 일부 모델은 실패할 수 있고,", "and terms of use against ESGF and each modelling centre. Some models may fail depending on index and data-node status;"),
      "#    " + L("끝에 모델별 성공·실패 요약이 나옵니다. 합친 결과(달력·격자·단위·버전·정오표)는 직접 확인하세요.", "a per-model success/failure summary is printed at the end. Check the merged output (calendar, grid, units, version, errata) yourself."),
      "#  " + L("인용·사사 — 논문에 쓰기 전에 꼭 확인하세요", "Citation and acknowledgement — check before publishing")
    ].filter(function (x) { return x !== null; });
    (CITE[c.project] || []).forEach(function (r) {
      H.push("#    " + (ko ? r[0] : r[1]) + ": " + (/^https?:/.test(r[2]) ? r[2] : base + r[2]));
    });
    H.push("# " + "=".repeat(74), "");
    return H.join("\n");
  }

  function configBlock(c, kind) {
    var ko = c.lang === "ko";
    function L(a, b) { return ko ? a : b; }
    var R = [
      "import sys",
      "from pathlib import Path",
      "",
      "# ── " + L("설정 (필요하면 고쳐 쓰세요)", "Settings (edit as needed)") + " " + "─".repeat(40),
      "LANG = " + py(c.lang),
      "PROJECT = " + py(c.project),
      "VARIABLES = " + py(c.variables.map(function (v) {
        var o = { key: v.key, var: v["var"], freq: v.freq, name: v.name, label: v.label };
        if (c.project === "CMIP6") o.table = v.table; else { o.branding_suffix = v.branding_suffix; o.region = v.region; }
        return o;
      })),
      "EXPERIMENTS = " + py(c.experiments)
    ];
    if (kind === "search") {
      R.push("MODELS = " + py(c.models));
    } else {
      R.push("FOLDER = " + py(c.folder) + "  # " + L("받은 파일이 있는 폴더 (하위 폴더 포함)", "folder with the downloaded files (sub-folders included)"));
      R.push("MODELS = None  # " + L("None: 폴더에 있는 모델 모두 / 예) ", "None: every model in the folder / e.g. ") + py(c.models.slice(0, 3)));
    }
    R.push(
      "MEMBERS = " + py(c.members) + "  # \"first\" " + L("모델별 첫 멤버", "first member per model") + " / \"all\" / [\"r1i1p1f1\", ...]",
      "YEARS = " + (c.years ? "(" + c.years[0] + ", " + c.years[1] + ")" : "None") + "  # " + L("(시작, 끝) 연도 — None 이면 전체", "(first, last) year — None for all"),
      "BOX = " + (c.box ? "{\"lat\": (" + c.box.lat[0] + ", " + c.box.lat[1] + "), \"lon\": (" + c.box.lon[0] + ", " + c.box.lon[1] + ")}" : "None") +
        "  # " + L("위경도 상자 (경도는 -180~360, 서→동) — None 이면 전지구", "lat/lon box (longitude -180..360, west to east) — None for global"),
      "CALENDAR = " + py(c.calendar) + "  # None " + L("그대로", "unchanged") + " / \"noleap\" / \"standard\"",
      "REGRID = " + py(c.regrid) + "  # None / \"bilinear\" / \"conservative\" (" + L("xESMF 필요", "needs xESMF") + ")",
      "RES = " + py(c.res) + "  # " + L("재격자 간격 (도)", "regridding step (degrees)"),
      "PR_TO_MM_DAY = " + py(c.prMmDay) + "  # pr kg m-2 s-1 → mm/day",
      "K_TO_C = " + py(c.kToC) + "  # " + L("기온 K → °C", "temperature K → °C"),
      "JOIN_HISTORICAL = " + py(c.join) + "  # " + L("historical + 시나리오 이어 붙이기 (같은 멤버끼리)", "join historical + scenario (same member only)"),
      "OUTPUT = " + py(c.output) + "  # \"per_model\" / \"ensemble\" (" + L("model 차원으로 묶은 한 파일", "one file with a model dimension") + ")",
      "OUT_DIR = Path(" + py(c.outDir) + ")"
    );
    if (kind === "search") {
      R.push(
        "STREAM = " + py(c.stream) + "  # True: " + L("OPeNDAP으로 필요한 부분만 원격으로 읽기 (내려받지 않음, 노드에 따라 실패할 수 있음)", "read only what is needed over OPeNDAP (no download; may fail on some nodes)"),
        "CACHE_DIR = None  # " + L("원본 파일 저장 위치 (None: ~/.esgf/)", "where original files are stored (None: ~/.esgf/)")
      );
    }
    R.push("");
    return R.join("\n");
  }

  // ── 공통 처리 (Python) ─────────────────────────────────────────
  var PY_LIB = String.raw`
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
`;

  // ── (가) intake-esgf 로 받기 ────────────────────────────────────
  var PY_SEARCH = String.raw`

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
`;

  // ── (나) 이미 받은 폴더 합치기 ──────────────────────────────────
  var PY_FOLDER = String.raw`

# ── 폴더의 파일 이름(DRS) 읽어 묶기 / group files by their DRS file names ──
CMIP6_RE = re.compile(r"^(?P<var>[^_]+)_(?P<table>[^_]+)_(?P<source>[^_]+)_(?P<exp>[^_]+)_(?P<member>[^_]+)_(?P<grid>g[^_]*)(?:_(?P<t0>\d+)-(?P<t1>\d+)(?:-clim)?)?\.nc$")
CMIP7_RE = re.compile(r"^(?P<var>[^_]+)_(?P<branding>[^_]+)_(?P<freq>[^_]+)_(?P<region>[^_]+)_(?P<grid>g[^_]*)_(?P<source>[^_]+)_(?P<exp>[^_]+)_(?P<member>[^_]+)(?:_(?P<t0>\d+)-(?P<t1>\d+))?\.nc$")
VERSION_RE = re.compile(r"^v(\d{8})$")


def table_freq(table):
    t = table.lower()
    for key, f in (("mon", "mon"), ("day", "day"), ("6hr", "6hr"), ("3hr", "3hr"), ("1hr", "1hr"), ("subhr", "subhr"), ("yr", "yr"), ("fx", "fx")):
        if key in t:
            return f
    return "unknown"


def version_of(p):
    for part in reversed(p.parent.parts):
        m = VERSION_RE.match(part)
        if m:
            return m.group(1)
    return None


def scan_folder(rep):
    root = Path(FOLDER).expanduser()
    if not root.is_dir():
        print(_("폴더가 없습니다: %s", "folder not found: %s") % root)
        sys.exit(1)
    files = sorted(p for p in root.rglob("*.nc") if p.is_file())
    print(_("%s에서 netCDF 파일 %d개를 찾았습니다", "found %d netCDF file(s) in %s") % ((root, len(files)) if LANG == "ko" else (len(files), root)), flush=True)
    want_vars = {v["key"] for v in VARIABLES} if VARIABLES else None
    groups, other = OrderedDict(), []
    for p in files:
        m, proj = CMIP7_RE.match(p.name), "CMIP7"
        if not m:
            m, proj = CMIP6_RE.match(p.name), "CMIP6"
        if not m:
            other.append(p.name)
            continue
        d = m.groupdict()
        if proj == "CMIP6":
            freq, vkey, name, lab = table_freq(d["table"]), "%s.%s" % (d["table"], d["var"]), "%s_%s" % (d["var"], d["table"]), "%s (%s)" % (d["var"], d["table"])
        else:
            freq = d["freq"]
            vkey = "%s.%s_%s%s" % (freq, d["var"], d["branding"], "" if d["region"] == "glb" else "." + d["region"])
            name, lab = "%s_%s_%s_%s" % (d["var"], d["branding"], freq, d["region"]), "%s_%s (%s, %s)" % (d["var"], d["branding"], freq, d["region"])
        if PROJECT and proj != PROJECT:
            continue
        if freq == "fx" or (want_vars and vkey not in want_vars) or (EXPERIMENTS and d["exp"] not in EXPERIMENTS) or (MODELS and d["source"] not in MODELS):
            continue
        if YEARS and d.get("t0") and d.get("t1"):
            if int(d["t1"][:4]) < YEARS[0] or int(d["t0"][:4]) > YEARS[1]:
                continue
        key = (vkey, d["source"], d["exp"], d["member"], d["grid"])
        g = groups.setdefault(key, {"vkey": vkey, "var": d["var"], "freq": freq, "name": name, "label": lab, "source": d["source"],
                                    "exp": d["exp"], "member": d["member"], "grid": d["grid"], "by_version": defaultdict(list)})
        g["by_version"][version_of(p)].append(p)
    if other:
        print(_("이름 규칙(DRS)에 맞지 않아 건너뛴 파일 %d개 (예: %s)", "%d file(s) skipped because the name does not follow the DRS (e.g. %s)") % (len(other), ", ".join(other[:3])))
    out = []
    for key, g in groups.items():
        vers = g.pop("by_version")
        what = "%s %s %s" % (g["source"], g["member"], g["exp"])
        if len(vers) > 1:
            known = sorted(v for v in vers if v)
            latest = known[-1] if known else None
            dropped = sum(len(fs) for v, fs in vers.items() if v != latest)
            rep.warn(what, _("버전이 여럿이라 최신 v%s만 씁니다 (다른 버전 파일 %d개 제외)", "several versions; using the latest v%s only (%d file(s) of other versions ignored)") % (latest, dropped))
            fs = vers[latest]
        else:
            latest, fs = next(iter(vers.items()))
        byname = OrderedDict()
        for p in sorted(fs, key=lambda x: x.name):
            if p.name in byname:
                rep.warn(what, _("같은 이름 파일이 두 곳에 있어 하나만 씁니다: %s", "same file name in two places, using one: %s") % p.name)
                continue
            byname[p.name] = p
        g["files"] = list(byname.values())
        g["version"] = latest
        out.append(g)
    print(_("묶음 %d개 (변수·모델·실험·멤버·격자)", "%d group(s) (variable, model, experiment, member, grid)") % len(out), flush=True)
    return choose(out, MEMBERS, rep)


if __name__ == "__main__":
    rep = Report()
    groups = scan_folder(rep)
    if groups:
        process(groups, rep)
    else:
        print(_("합칠 파일이 없습니다 — FOLDER·VARIABLES·EXPERIMENTS 설정을 확인하세요", "nothing to merge — check FOLDER, VARIABLES and EXPERIMENTS"))
    sys.exit(rep.summary())
`;

  function buildScript(cfg) {
    var c = normCfg(cfg);
    return header(c, "search") + configBlock(c, "search") + PY_LIB + PY_SEARCH;
  }
  function buildMergeScript(cfg) {
    var c = normCfg(cfg);
    return header(c, "merge") + configBlock(c, "merge") + PY_LIB + PY_FOLDER;
  }

  // ── 카탈로그 다루기 (화면·시험 공용) ─────────────────────────────
  var EF = ["members", "n_members", "grids", "nominal_resolution", "version", "files", "size_bytes", "start", "end", "data_nodes"];
  function entryObj(arr, fields) {
    var f = fields || EF, o = {};
    f.forEach(function (k, i) { o[k] = arr ? arr[i] : null; });
    return o;
  }
  function expandMembers(s) {
    var out = [];
    String(s || "").split(/\s+/).filter(Boolean).forEach(function (part) {
      var m = /^r([\d,\-]+)(i\d+p\d+f\d+)$/.exec(part);
      if (!m) { out.push(part); return; }
      m[1].split(",").forEach(function (run) {
        var ab = run.split("-"), a = +ab[0], b = +(ab[1] || ab[0]);
        for (var r = a; r <= b; r++) out.push("r" + r + m[2]);
      });
    });
    return out;
  }
  function humanSize(b) {
    if (!b) return "-";
    var u = ["B", "KB", "MB", "GB", "TB", "PB"], i = 0;
    while (b >= 1000 && i < u.length - 1) { b /= 1000; i++; }
    return (b >= 100 || i === 0 ? Math.round(b) : b.toFixed(1)) + " " + u[i];
  }
  // 모델별 요약 행 (고른 변수·실험 기준)
  function modelRows(proj, varKey, exps) {
    var av = (proj.avail || {})[varKey] || {};
    var fields = proj.entry_fields || EF;
    var vinfo = (proj.variables || []).filter(function (v) { return v.id === varKey; })[0] || {};
    var grp = vinfo.group || "atmos";
    return Object.keys(av).sort(function (a, b) { return a.toLowerCase() < b.toLowerCase() ? -1 : 1; }).map(function (model) {
      var per = {}, members = {}, grids = {}, res = {}, files = 0, size = 0, version = "";
      exps.forEach(function (e) {
        var x = av[model][e];
        if (!x) return;
        var o = entryObj(x, fields);
        per[e] = o;
        expandMembers(o.members).forEach(function (m) { members[m] = 1; });
        (o.grids || []).forEach(function (g) { grids[g] = 1; });
        if (o.nominal_resolution) String(o.nominal_resolution).split(" / ").forEach(function (r) { res[r] = 1; });
        files += o.files || 0; size += o.size_bytes || 0;
        if ((o.version || "") > version) version = o.version;
      });
      var info = (proj.models || {})[model] || {};
      var cal = (info.calendar || {})[grp] || (info.calendar || {})[grp === "atmos" ? "ocean" : "atmos"] || {};
      var mlist = Object.keys(members).sort(function (a, b) {
        var na = (a.match(/\d+/g) || []).map(Number), nb = (b.match(/\d+/g) || []).map(Number);
        for (var i = 0; i < Math.max(na.length, nb.length); i++) { if ((na[i] || 0) !== (nb[i] || 0)) return (na[i] || 0) - (nb[i] || 0); }
        return a < b ? -1 : 1;
      });
      return {
        model: model, institution: info.institution || "", per: per, nExp: Object.keys(per).length,
        members: mlist, grids: Object.keys(grids).sort(), res: Object.keys(res).join(" / "),
        calendar: cal.value || "", calNote: cal.note || "", files: files, size: size, version: version
      };
    });
  }

  var api = { buildScript: buildScript, buildMergeScript: buildMergeScript, modelRows: modelRows, expandMembers: expandMembers, humanSize: humanSize, py: py };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.KCDNModelData = api;

  // ── 브라우저 화면 ──────────────────────────────────────────────
  if (typeof document === "undefined") return;

  var IS_EN = (document.documentElement.lang || "").toLowerCase().indexOf("en") === 0;
  function L(ko, en) { return IS_EN ? en : ko; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }
  function $(id) { return document.getElementById(id); }

  var DEFAULT_EXPS = { CMIP6: ["historical", "ssp245"], CMIP7: ["historical", "scen7-m"] };
  var DEFAULT_VAR = { CMIP6: "Amon.tas", CMIP7: "mon.tas_tavg-h2m-hxy-u" };
  var EXP_NOTE = {
    historical: L("과거 재현", "historical"), "esm-hist": L("과거 재현 (배출 구동)", "historical, emission-driven"),
    ssp126: "SSP1-2.6", ssp245: "SSP2-4.5", ssp370: "SSP3-7.0", ssp585: "SSP5-8.5"
  };

  function setup() {
    var app = $("mdd-app");
    var dataEl = $("model-catalog");
    if (!app || !dataEl || app.dataset.bound) return;
    app.dataset.bound = "1";
    var CAT;
    try { CAT = JSON.parse(dataEl.textContent); } catch (e) { return; }
    var projects = Object.keys(CAT.projects || {}).filter(function (p) { return Object.keys((CAT.projects[p] || {}).avail || {}).length; });
    if (!projects.length) return;
    var state = { project: projects[0], freq: null, varKey: null, exps: {}, onlyAll: false, off: {}, sortCol: null, sortAsc: true, tab: "search" };
    var el = {
      meta: $("mdd-meta"), project: $("mdd-project"), freq: $("mdd-freq"), variable: $("mdd-var"), exps: $("mdd-exps"),
      onlyAll: $("mdd-only-all"), table: $("mdd-table"), count: $("mdd-count"), notes: $("mdd-notes"),
      codeA: $("mdd-code-search"), codeB: $("mdd-code-merge"), warn: $("mdd-warn")
    };
    var opt = app.querySelector("#mdd-options");

    function proj() { return CAT.projects[state.project]; }
    function vars() { return proj().variables || []; }
    function vinfo() { return vars().filter(function (v) { return v.id === state.varKey; })[0]; }
    function selectedExps() { return (proj().experiments || []).filter(function (e) { return state.exps[e]; }); }

    el.meta.innerHTML = L("가용성 표 기준: ", "Availability as of: ") + "<b>" + esc(String(CAT.generated || "").slice(0, 10)) + "</b> (UTC) · " +
      projects.map(function (p) {
        var x = CAT.projects[p];
        return esc(p) + " " + L("색인", "index") + ": <code>" + esc(String(x.index || "").replace(/^https?:\/\//, "")) + "</code>" +
          (x.stale ? ' <span class="mdd-bad">' + L("(이번 갱신 실패 — 지난 결과)", "(last update failed — previous result)") + "</span>" : "");
      }).join(" · ");

    el.project.innerHTML = projects.map(function (p) { return '<option value="' + p + '">' + p + " (" + L("모델 ", "") + Object.keys(CAT.projects[p].models || {}).length + L("개)", " models)") + "</option>"; }).join("");
    el.project.value = state.project;

    function fillVars(keepFreq) {
      var vs = vars();
      var freqs = [];
      vs.forEach(function (v) { if (freqs.indexOf(v.freq) < 0) freqs.push(v.freq); });
      var FREQ = { mon: L("월 (mon)", "monthly (mon)"), day: L("일 (day)", "daily (day)") };
      el.freq.innerHTML = freqs.map(function (f) { return '<option value="' + f + '">' + esc(FREQ[f] || f) + "</option>"; }).join("");
      if (!keepFreq || freqs.indexOf(state.freq) < 0) {
        var dv = vs.filter(function (v) { return v.id === DEFAULT_VAR[state.project]; })[0];
        state.freq = dv ? dv.freq : freqs[0];
      }
      el.freq.value = state.freq;
      var list = vs.filter(function (v) { return v.freq === state.freq; });
      el.variable.innerHTML = list.map(function (v) {
        var name = state.project === "CMIP6" ? v["var"] + " · " + v.table : v.branded + (v.region && v.region !== "glb" ? " · " + v.region : "");
        var n = Object.keys((proj().avail || {})[v.id] || {}).length;
        return '<option value="' + esc(v.id) + '">' + esc(name) + " — " + esc(v.long_name || "") + (v.units ? " [" + esc(v.units) + "]" : "") + " (" + n + ")</option>";
      }).join("");
      if (!list.some(function (v) { return v.id === state.varKey; })) {
        state.varKey = list.some(function (v) { return v.id === DEFAULT_VAR[state.project]; }) ? DEFAULT_VAR[state.project] : (list[0] || {}).id;
      }
      el.variable.value = state.varKey;
    }
    function fillExps() {
      var all = proj().experiments || [];
      var av = (proj().avail || {})[state.varKey] || {};
      if (!Object.keys(state.exps).some(function (e) { return state.exps[e] && all.indexOf(e) >= 0; })) {
        state.exps = {};
        (DEFAULT_EXPS[state.project] || all.slice(0, 1)).forEach(function (e) { if (all.indexOf(e) >= 0) state.exps[e] = true; });
      }
      el.exps.innerHTML = all.map(function (e) {
        var n = Object.keys(av).filter(function (m) { return av[m][e]; }).length;
        return '<label class="check"><input type="checkbox" value="' + esc(e) + '"' + (state.exps[e] ? " checked" : "") + "> <span><code>" + esc(e) + "</code>" +
          (EXP_NOTE[e] ? ' <span class="hint">' + esc(EXP_NOTE[e]) + "</span>" : "") + ' <span class="hint">· ' + L("모델 ", "") + n + L("개", " models") + "</span></span></label>";
      }).join("");
    }

    // ── 가용성 표 ──
    var COLS = [
      { k: "pick", t: "", nosort: true },
      { k: "model", t: L("모델", "Model") }, { k: "institution", t: L("기관", "Institution") },
      { k: "members", t: L("멤버 수", "Members") }, { k: "grids", t: L("격자", "Grid") },
      { k: "res", t: L("공칭 해상도", "Nominal res.") }, { k: "calendar", t: L("달력", "Calendar") },
      { k: "files", t: L("파일 수", "Files") }, { k: "size", t: L("크기", "Size") }, { k: "version", t: L("최신 버전", "Latest version") }
    ];
    function resKm(s) { var m = /([\d.]+)\s*km/.exec(s || ""); return m ? +m[1] : ""; }
    function rowsNow() {
      var exps = selectedExps();
      var rows = modelRows(proj(), state.varKey, exps).filter(function (r) { return r.nExp > 0 && (!state.onlyAll || r.nExp === exps.length); });
      if (state.sortCol) {
        var k = state.sortCol;
        rows.sort(function (a, b) {
          var x = sortVal(a, k), y = sortVal(b, k);
          if (x === "" && y !== "") return 1;
          if (y === "" && x !== "") return -1;
          var c = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "ko", { numeric: true, sensitivity: "base" });
          return state.sortAsc ? c : -c;
        });
      }
      return rows;
    }
    function sortVal(r, k) {
      if (k === "members") return r.members.length;
      if (k === "grids") return r.grids.join(" ");
      if (k === "res") return resKm(r.res);
      if (k.indexOf("exp:") === 0) { var o = r.per[k.slice(4)]; return o ? o.n_members : ""; }
      return r[k] == null ? "" : r[k];
    }
    function renderTable() {
      var exps = selectedExps();
      var rows = rowsNow();
      var cols = COLS.concat(exps.map(function (e) { return { k: "exp:" + e, t: e, exp: true }; }));
      var h = "<thead><tr>" + cols.map(function (c) {
        if (c.k === "pick") return '<th class="pick-col" data-nosort="1"><input type="checkbox" id="mdd-pick-all" aria-label="' + L("모두 고르기", "Select all") + '"></th>';
        var s = state.sortCol === c.k ? (state.sortAsc ? "ascending" : "descending") : "none";
        return '<th class="sort-th" tabindex="0" aria-sort="' + s + '" data-k="' + esc(c.k) + '" title="' + L("눌러서 정렬", "Click to sort") + '">' +
          (c.exp ? "<code>" + esc(c.t) + "</code>" : esc(c.t)) + "</th>";
      }).join("") + "</tr></thead><tbody>";
      rows.forEach(function (r) {
        var on = !state.off[r.model];
        var mshow = r.members.slice(0, 3).join(", ") + (r.members.length > 3 ? " …" : "");
        h += '<tr data-model="' + esc(r.model) + '"' + (on ? "" : ' class="is-off"') + ">" +
          '<td class="pick-col"><input type="checkbox" class="mdd-pick" value="' + esc(r.model) + '"' + (on ? " checked" : "") + ' aria-label="' + esc(r.model) + '"></td>' +
          '<td><span class="notranslate" translate="no"><b>' + esc(r.model) + "</b></span></td>" +
          "<td>" + esc(r.institution) + "</td>" +
          '<td data-sort="' + r.members.length + '"><b>' + r.members.length + '</b> <span class="hint">' + esc(mshow) + "</span></td>" +
          "<td>" + esc(r.grids.join(", ")) + "</td>" +
          '<td data-sort="' + resKm(r.res) + '">' + esc(r.res || "-") + "</td>" +
          "<td" + (r.calNote ? ' title="' + esc(r.calNote) + '"' : "") + ">" + (r.calendar ? "<code>" + esc(r.calendar) + "</code>" : '<span class="hint">' + L("확인 못 함", "unknown") + "</span>") + "</td>" +
          '<td data-sort="' + r.files + '">' + r.files.toLocaleString() + "</td>" +
          '<td data-sort="' + r.size + '">' + humanSize(r.size) + "</td>" +
          "<td>" + esc(r.version ? "v" + r.version : "-") + "</td>" +
          exps.map(function (e) {
            var o = r.per[e];
            if (!o) return '<td class="mdd-no" data-sort="">–</td>';
            var tip = o.members + " · " + (o.start || "?") + "–" + (o.end || "?") + " · " + L("파일 ", "") + o.files + L("개", " files") + " · " + humanSize(o.size_bytes) + " · " + L("노드 ", "") + o.data_nodes + L("곳", " nodes");
            return '<td class="mdd-yes" data-sort="' + o.n_members + '" title="' + esc(tip) + '">✓ ' + o.n_members + '<br><span class="hint">' + esc((o.start || "").slice(0, 4) + "–" + (o.end || "").slice(0, 4)) + "</span></td>";
          }).join("") + "</tr>";
      });
      el.table.innerHTML = h + "</tbody>";
      var nOn = rows.filter(function (r) { return !state.off[r.model]; }).length;
      el.count.textContent = L("모델 " + rows.length + "개 표시 · " + nOn + "개 선택", rows.length + " models shown · " + nOn + " selected");
      var all = $("mdd-pick-all");
      if (all) { all.checked = nOn === rows.length && rows.length > 0; all.indeterminate = nOn > 0 && nOn < rows.length; }
      return rows;
    }

    // ── 스크립트 옵션 읽기 ──
    function val(name) { var x = opt.querySelector('[name="' + name + '"]:checked'); return x ? x.value : ""; }
    function num(id) { var x = $(id); return x && x.value !== "" ? +x.value : null; }
    function readCfg(rows) {
      var v = vinfo();
      var memberMode = val("mdd-members");
      var custom = ($("mdd-members-custom").value || "").split(/[\s,]+/).filter(Boolean);
      var y0 = num("mdd-y0"), y1 = num("mdd-y1");
      var cfg = {
        lang: IS_EN ? "en" : "ko", project: state.project, catalogDate: String(CAT.generated || "").slice(0, 10),
        variables: v ? [v] : [], experiments: selectedExps(),
        models: rows.filter(function (r) { return !state.off[r.model]; }).map(function (r) { return r.model; }),
        members: memberMode === "custom" ? (custom.length ? custom : "first") : memberMode,
        years: y0 != null && y1 != null ? [Math.min(y0, y1), Math.max(y0, y1)] : null,
        box: val("mdd-region") === "box" ? { lat: [num("mdd-lat0"), num("mdd-lat1")], lon: [num("mdd-lon0"), num("mdd-lon1")] } : null,
        calendar: $("mdd-cal").value || null, regrid: $("mdd-regrid").value || null,
        prMmDay: $("mdd-pr").checked, kToC: $("mdd-k").checked, join: $("mdd-join").checked,
        output: val("mdd-output") || "per_model", stream: $("mdd-stream").checked,
        folder: $("mdd-folder").value || "./cmip_files", outDir: "cmip_out"
      };
      return cfg;
    }
    function fileName(cfg, kind) {
      var v = cfg.variables[0] || {};
      var base = (cfg.project + "_" + (v["var"] || "var") + "_" + (cfg.project === "CMIP6" ? v.table : v.freq)).toLowerCase();
      return base + (kind === "search" ? "_download.py" : "_merge.py");
    }
    function warnings(cfg, rows) {
      var W = [];
      if (!cfg.models.length) W.push(L("표에서 모델을 하나 이상 고르세요.", "Tick at least one model in the table."));
      if (!cfg.experiments.length) W.push(L("실험을 하나 이상 고르세요.", "Pick at least one experiment."));
      var picked = rows.filter(function (r) { return !state.off[r.model]; });
      var cals = {}; picked.forEach(function (r) { if (r.calendar) cals[r.calendar] = 1; });
      var calList = Object.keys(cals);
      if (cfg.output === "ensemble" && !cfg.calendar && calList.length > 1)
        W.push(L("고른 모델의 달력이 서로 달라(" + calList.join(", ") + ") 한 파일로 묶으려면 달력 통일을 고르세요. 그대로 두면 스크립트가 모델별 파일로 저장합니다.",
                 "The chosen models use different calendars (" + calList.join(", ") + "). Pick a calendar to combine them into one file; otherwise the script saves one file per model."));
      var grids = {}; picked.forEach(function (r) { grids[r.res + "|" + r.grids.join(",") + "|" + r.model.split("-")[0]] = 1; });
      if (cfg.output === "ensemble" && !cfg.regrid && picked.length > 1)
        W.push(L("모델마다 격자가 다르면 재격자 없이는 한 파일로 묶을 수 없습니다(그때는 모델별 파일로 저장).", "Models on different grids cannot be combined without regridding (the script then saves one file per model)."));
      if (cfg.calendar && cals["360_day"])
        W.push(L("360_day 달력 모델이 있습니다. 일 자료를 noleap·standard로 바꾸면 해마다 날짜를 고르게 늘리는 방식(align_on=\"year\")이라 날짜가 하루 이틀 어긋나고 새로 생긴 날은 NaN입니다. 월 자료는 같은 연·월의 15일로 다시 적습니다.",
                 "Some chosen models use a 360_day calendar. Converting daily data to noleap/standard spreads the extra days over the year (align_on=\"year\"), so values shift by a day or two and inserted days are NaN. Monthly data are re-stamped at the 15th of each month."));
      if (cfg.regrid) W.push(L("재격자에는 xESMF가 필요합니다. pip로는 설치가 어려우니 conda install -c conda-forge xesmf 를 쓰세요." + (cfg.regrid === "conservative" ? " conservative는 격자 경계 정보가 필요해 일부 해양 곡선 격자에서 실패할 수 있으며, 그때 스크립트가 bilinear로 다시 하고 알려 줍니다." : ""),
                               "Regridding needs xESMF, which is hard to install with pip: use conda install -c conda-forge xesmf." + (cfg.regrid === "conservative" ? " Conservative regridding needs cell bounds and may fail on some curvilinear ocean grids; the script then falls back to bilinear and tells you." : "")));
      if (cfg.box && (cfg.box.lat[0] == null || cfg.box.lat[1] == null || cfg.box.lon[0] == null || cfg.box.lon[1] == null || cfg.box.lat[0] >= cfg.box.lat[1] || cfg.box.lon[0] >= cfg.box.lon[1]))
        W.push(L("영역 상자의 위경도를 확인하세요 (남 < 북, 서 < 동 — 날짜변경선을 넘으면 170~190처럼 적기).", "Check the box (south < north, west < east — across the date line write e.g. 170 to 190)."));
      var hist = cfg.experiments.filter(function (e) { return e === "historical" || e === "esm-hist"; }).length;
      var scen = cfg.experiments.length - hist;
      if (cfg.join && hist && scen) W.push(L("historical과 시나리오를 같은 멤버끼리 이어 붙입니다. 겹치는 시각이 있으면 historical 값을 쓰고 알려 줍니다.", "historical and each scenario are joined for the same member; any overlapping time steps keep the historical values and are reported."));
      if (cfg.years) {
        var tooEarly = cfg.experiments.every(function (e) { return e !== "historical" && e !== "esm-hist"; }) && cfg.years[0] < (state.project === "CMIP7" ? 2022 : 2015);
        if (tooEarly) W.push(L("시나리오 실험은 " + (state.project === "CMIP7" ? "2022" : "2015") + "년부터입니다. 그 전 기간은 historical을 함께 고르세요.", "Scenario experiments start in " + (state.project === "CMIP7" ? "2022" : "2015") + "; add historical for earlier years."));
      }
      return W;
    }

    var lastRows = [];
    function renderScripts() {
      var cfg = readCfg(lastRows);
      var W = warnings(cfg, lastRows);
      el.warn.innerHTML = W.length ? "<ul>" + W.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>" : "";
      el.warn.hidden = !W.length;
      cfg.fileName = fileName(cfg, "search");
      el.codeA.textContent = buildScript(cfg);
      el.codeA.dataset.file = cfg.fileName;
      cfg.fileName = fileName(cfg, "merge");
      el.codeB.textContent = buildMergeScript(cfg);
      el.codeB.dataset.file = cfg.fileName;
      $("mdd-sum").textContent = L("모델 " + cfg.models.length + "개 · 실험 " + cfg.experiments.join(", ") + " · 변수 " + ((cfg.variables[0] || {})["var"] || "-"),
                                    cfg.models.length + " models · " + cfg.experiments.join(", ") + " · " + ((cfg.variables[0] || {})["var"] || "-"));
    }
    function renderAll() {
      lastRows = renderTable();
      renderScripts();
    }

    // ── 이벤트 ──
    el.project.addEventListener("change", function () {
      state.project = el.project.value; state.exps = {}; state.off = {}; state.sortCol = null;
      fillVars(false); fillExps(); renderAll();
    });
    el.freq.addEventListener("change", function () { state.freq = el.freq.value; fillVars(true); fillExps(); renderAll(); });
    el.variable.addEventListener("change", function () { state.varKey = el.variable.value; fillExps(); renderAll(); });
    el.exps.addEventListener("change", function (e) {
      if (e.target.type !== "checkbox") return;
      state.exps[e.target.value] = e.target.checked; renderAll();
    });
    el.onlyAll.addEventListener("change", function () { state.onlyAll = el.onlyAll.checked; renderAll(); });
    el.table.addEventListener("change", function (e) {
      if (e.target.id === "mdd-pick-all") {
        lastRows.forEach(function (r) { if (e.target.checked) delete state.off[r.model]; else state.off[r.model] = 1; });
        renderAll(); return;
      }
      if (!e.target.classList.contains("mdd-pick")) return;
      if (e.target.checked) delete state.off[e.target.value]; else state.off[e.target.value] = 1;
      renderAll();
    });
    function sortBy(th) {
      var k = th.getAttribute("data-k");
      if (!k) return;
      if (state.sortCol === k) state.sortAsc = !state.sortAsc; else { state.sortCol = k; state.sortAsc = true; }
      renderAll();
    }
    el.table.addEventListener("click", function (e) { var th = e.target.closest("th.sort-th"); if (th) sortBy(th); });
    el.table.addEventListener("keydown", function (e) {
      var th = e.target.closest && e.target.closest("th.sort-th");
      if (th && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); sortBy(th); }
    });
    opt.addEventListener("input", renderScripts);
    opt.addEventListener("change", function () {
      $("mdd-box").hidden = val("mdd-region") !== "box";
      $("mdd-members-custom").disabled = val("mdd-members") !== "custom";
      renderScripts();
    });
    $("mdd-folder").addEventListener("input", renderScripts);

    // 탭
    var tabs = app.querySelectorAll(".mdd-tab");
    tabs.forEach(function (b) {
      b.addEventListener("click", function () {
        tabs.forEach(function (x) {
          var on = x === b;
          x.setAttribute("aria-selected", on ? "true" : "false");
          x.classList.toggle("is-on", on);
          $(x.getAttribute("aria-controls")).hidden = !on;
        });
      });
    });
    // 복사·저장
    app.querySelectorAll("[data-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var code = $(b.getAttribute("data-copy"));
        var done = function () { var t = b.textContent; b.textContent = L("복사했습니다 ✓", "Copied ✓"); setTimeout(function () { b.textContent = t; }, 1500); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(code.textContent).then(done, function () { fallbackCopy(code); done(); });
        else { fallbackCopy(code); done(); }
      });
    });
    function fallbackCopy(code) {
      var r = document.createRange(); r.selectNodeContents(code);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      try { document.execCommand("copy"); } catch (e) {}
      s.removeAllRanges();
    }
    app.querySelectorAll("[data-save]").forEach(function (b) {
      b.addEventListener("click", function () {
        var code = $(b.getAttribute("data-save"));
        var blob = new Blob([code.textContent], { type: "text/x-python;charset=utf-8" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = code.dataset.file || "model_data.py";
        document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      });
    });

    el.table.dataset.sortable = "1";  // site.js 공통 정렬 대신 이 표 전용 정렬(같은 모양) 사용 — 표를 다시 그려도 유지되도록
    fillVars(false); fillExps();
    $("mdd-box").hidden = val("mdd-region") !== "box";
    $("mdd-members-custom").disabled = val("mdd-members") !== "custom";
    app.hidden = false;
    var loading = $("mdd-loading");
    if (loading) loading.hidden = true;
    renderAll();
  }

  if (typeof document$ !== "undefined") document$.subscribe(setup);
  else document.addEventListener("DOMContentLoaded", setup);
})(typeof window !== "undefined" ? window : this);
