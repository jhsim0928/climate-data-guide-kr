"""모델 자료 가용성 표 만들기 — 매주 GitHub Actions(.github/workflows/model_catalog.yml)에서 실행

ESGF 검색 색인에 "어떤 모델이 어떤 실험·변수를 갖고 있는지" 물어 data/model-catalog/catalog.json 으로 저장합니다.
사이트의 '모델 자료 받기' 페이지(docs/model-data.md)가 이 파일로 가용성 표와 받기·합치기 스크립트를 만듭니다.

- CMIP6: ORNL ESGF 1.5 색인(Globus 기반, Solr 호환 응답) — https://esgf-node.ornl.gov/esgf-1-5-bridge
  (새 STAC 색인의 CMIP6 항목은 member_id 오류가 있어 쓰지 않음)
- CMIP7: ESGF-NG STAC 색인 — https://discovery.west.esgf.io (실패하면 discovery.east)
- 달력: 색인에 없어서 모델(대기·해양 묶음)마다 파일 하나의 헤더만 원격으로 읽음 (OPeNDAP → HTTPS 범위 읽기)

색인 하나가 실패해도 나머지는 저장하고, 실패한 부분은 지난번 값을 그대로 두고 사유를 JSON 'errors'에 남깁니다.
(JSON 안의 글은 영어로만 씁니다 — 영어판 페이지에도 그대로 들어가기 때문)

    python scripts/model_catalog.py              # 전체 (Actions)
    python scripts/model_catalog.py --quick      # 시험용: 변수·실험 일부만
    python scripts/model_catalog.py --no-calendar --out /tmp/c.json

필요 패키지: requests (달력 읽기: netCDF4, 실패 시 fsspec·aiohttp·h5netcdf·h5py)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import threading
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "model-catalog" / "catalog.json"
UA = "data4researchers-model-catalog/1.0 (+https://data4researchers.kr/; weekly availability table)"

SOLR = "https://esgf-node.ornl.gov/esgf-1-5-bridge"
STAC = ["https://discovery.west.esgf.io", "https://discovery.east.esgf.io"]

CMIP6_EXPS = ["historical", "ssp126", "ssp245", "ssp370", "ssp585"]
CMIP6_VARS = (
    [("Amon", v) for v in ["tas", "pr", "tasmax", "tasmin", "psl", "huss", "hurs", "sfcWind", "uas", "vas", "rsds", "rlds"]]
    + [("day", v) for v in ["tas", "pr", "tasmax", "tasmin", "sfcWind"]]
    + [("Omon", v) for v in ["tos", "sos", "zos"]]
    + [("SImon", "siconc")]
)
TABLE_FREQ = {"Amon": "mon", "day": "day", "Omon": "mon", "SImon": "mon"}
TABLE_GROUP = {"Amon": "atmos", "day": "atmos", "Omon": "ocean", "SImon": "ocean"}  # 달력 확인 묶음

CMIP7_VAR_IDS = ["tas", "pr", "psl", "huss", "hurs", "sfcWind", "uas", "vas", "rsds", "rlds", "tos", "sos", "zos", "siconc"]
CMIP7_FREQS = ["mon", "day"]
CMIP7_EXP_RE = re.compile(r"^(historical|esm-hist|(esm-)?scen7-[A-Za-z0-9-]+)$")
# LIKE 검색이 안 될 때 쓰는 후보 (CMIP7 ScenarioMIP 이름 + 배출 구동·연장판)
CMIP7_EXP_FALLBACK = ["historical", "esm-hist"] + [
    p + "scen7-" + s + e for p in ("", "esm-") for s in ("h", "hc", "hl", "m", "mc", "ml", "l", "ln", "vl", "vlho") for e in ("", "-ext")
]
CMIP7_OCEAN = {"tos", "sos", "zos", "siconc"}

ENTRY_FIELDS = ["members", "n_members", "grids", "nominal_resolution", "version", "files", "size_bytes", "start", "end", "data_nodes"]
CAL_ALIAS = {"365_day": "noleap", "gregorian": "standard", "366_day": "all_leap"}
CAL_TIMEOUT = 60


def log(*a):
    print(*a, flush=True)


# ── HTTP: 동시 요청 제한 + 재시도 + 타임아웃 ─────────────────────────
class Http:
    def __init__(self, max_conc: int = 3):
        self.local = threading.local()
        self.sem = threading.Semaphore(max_conc)
        self.count = 0

    def _session(self) -> requests.Session:
        s = getattr(self.local, "s", None)
        if s is None:
            s = requests.Session()
            s.headers["User-Agent"] = UA
            self.local.s = s
        return s

    def request(self, method: str, url: str, *, tries: int = 4, timeout=(20, 300), **kw) -> requests.Response:
        last: Exception | None = None
        for i in range(tries):
            with self.sem:
                self.count += 1
                try:
                    r = self._session().request(method, url, timeout=timeout, **kw)
                    if r.status_code in (429, 500, 502, 503, 504):
                        raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                    r.raise_for_status()
                    return r
                except requests.RequestException as e:
                    last = e
                    code = getattr(getattr(e, "response", None), "status_code", None)
                    if code in (400, 401, 403, 404, 405, 422):
                        break  # 다시 해도 같은 결과
            time.sleep(min(60, 5 * 2 ** i))
        raise last  # type: ignore[misc]


def first(v):
    return v[0] if isinstance(v, list) and v else v


def end_ym(s) -> str:
    """STAC end_datetime 은 구간 끝(다음 달 1일 00:00, 예 2022-01-01T00:00:00Z = 2021-12까지)으로 적혀 있어 마지막 달로 바꿈"""
    s = str(s or "")
    m = re.match(r"^(-?\d{1,4})-(\d{2})-01T00:00:00", s)
    if not m:
        return ym(s)
    y, mo = int(m.group(1)), int(m.group(2))
    y, mo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    return f"{y:04d}-{mo:02d}"


def ym(s) -> str:
    s = str(s or "")
    m = re.match(r"^(-?\d{1,4})-(\d{2})", s)
    return f"{int(m.group(1)):04d}-{m.group(2)}" if m else ""


# ── 멤버 목록 압축: r1i1p1f1 r2i1p1f1 r3i1p1f1 r5i1p1f1 → "r1-3,5i1p1f1" ──
MEMBER_RE = re.compile(r"^r(\d+)(i\d+p\d+f\d+)$")


def member_key(m: str):
    nums = [int(x) for x in re.findall(r"\d+", m)]
    return (nums[1:] + [0] * 4)[:3] + [nums[0] if nums else 0], m


def compress_members(members) -> str:
    groups: dict[str, list[int]] = defaultdict(list)
    other = []
    for m in set(members):
        mm = MEMBER_RE.match(m)
        if mm:
            groups[mm.group(2)].append(int(mm.group(1)))
        else:
            other.append(m)
    parts = []
    def ipf_key(s):
        return [int(x) for x in re.findall(r"\d+", s)]
    for ipf in sorted(groups, key=ipf_key):
        rs = sorted(groups[ipf])
        runs, start, prev = [], rs[0], rs[0]
        for r in rs[1:] + [None]:
            if r is not None and r == prev + 1:
                prev = r
                continue
            runs.append(f"{start}" if start == prev else f"{start}-{prev}")
            if r is not None:
                start = prev = r
        parts.append("r" + ",".join(runs) + ipf)
    return " ".join(parts + sorted(other))


def expand_members(s: str) -> list[str]:
    out = []
    for part in s.split():
        m = re.match(r"^r([\d,\-]+)(i\d+p\d+f\d+)$", part)
        if not m:
            out.append(part)
            continue
        for run in m.group(1).split(","):
            a, _, b = run.partition("-")
            for r in range(int(a), int(b or a) + 1):
                out.append(f"r{r}{m.group(2)}")
    return out


# ── 달력: 파일 헤더만 원격으로 읽기 ────────────────────────────────
_CAL_CODE = r"""
import sys
url, how = sys.argv[1], sys.argv[2]
if how == "dap":
    import netCDF4
    with netCDF4.Dataset(url) as nc:
        tv = nc.variables["time"]
        print(getattr(tv, "calendar", "") or "standard")
else:
    import fsspec, h5netcdf
    with fsspec.open(url, "rb", block_size=2 ** 18, client_kwargs={"headers": {"User-Agent": sys.argv[3]}}) as fh:
        with h5netcdf.File(fh, "r") as h:
            c = h.variables["time"].attrs.get("calendar")
            print((c.decode() if isinstance(c, bytes) else c) or "standard")
"""


def calendar_of(url: str, how: str) -> str:
    """파일 헤더의 time:calendar — netCDF C 라이브러리는 스레드에 안전하지 않아 따로 프로세스에서 읽고, 시간 제한을 둠"""
    import subprocess  # noqa: PLC0415
    try:
        r = subprocess.run([sys.executable, "-c", _CAL_CODE, url, how, UA], capture_output=True, text=True, timeout=CAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"no response within {CAL_TIMEOUT} s") from None
    if r.returncode != 0:
        msg = (r.stderr.strip().splitlines() or ["error"])[-1]
        raise RuntimeError(msg[:200])
    return r.stdout.strip()


def read_calendar(dap_urls: list[str], http_urls: list[str]) -> tuple[str, str, str]:
    """(달력, 읽은 주소, 실패 사유)"""
    errs = []
    for u in dap_urls[:3]:
        try:
            c = calendar_of(u, "dap")
            return CAL_ALIAS.get(c, c), u, ""
        except Exception as e:  # noqa: BLE001
            errs.append(f"OPeNDAP {urlparse(u).netloc}: {str(e)[:120]}")
    for u in http_urls[:2]:
        try:
            c = calendar_of(u, "https")
            return CAL_ALIAS.get(c, c), u, ""
        except Exception as e:  # noqa: BLE001
            errs.append(f"HTTPS {urlparse(u).netloc}: {str(e)[:120]}")
    return "", "", " / ".join(errs) or "no file URL to read"


def node_rank(url_or_node: str) -> int:
    s = str(url_or_node)
    return 0 if "esgf-node.ornl.gov" in s else (2 if "globus.org" in s else 1)


# ── CMIP6 (ORNL Solr 호환 색인) ────────────────────────────────────
def solr_datasets(http: Http, exp: str, table: str, var: str) -> list[dict]:
    docs: list[dict] = []
    offset = 0
    while True:
        params = {"project": "CMIP6", "type": "Dataset", "latest": "true", "experiment_id": exp, "table_id": table,
                  "variable_id": var, "limit": 1000, "offset": offset, "format": "application/solr+json"}
        j = http.request("GET", SOLR, params=params).json()
        resp = j["response"]
        batch = resp.get("docs") or []
        docs += batch
        offset += len(batch)
        if not batch or offset >= int(resp.get("numFound") or 0):
            return docs


def summarize_cmip6(docs: list[dict]):
    """같은 데이터셋의 여러 노드 사본을 하나로 묶고 모델별 요약"""
    by_inst: dict[str, dict] = {}
    for d in docs:
        if d.get("retracted") is True or str(d.get("retracted")).lower() == "true":
            continue
        inst = d.get("instance_id") or str(d.get("id", "")).split("|")[0]
        e = by_inst.setdefault(inst, {"docs": [], "nodes": set()})
        e["docs"].append(d)
        e["nodes"].add(d.get("data_node") or str(d.get("id", "")).split("|")[-1])
    # 같은 master_id 에 버전이 여럿이면 가장 최신만
    latest: dict[str, str] = {}
    for inst, e in by_inst.items():
        d = e["docs"][0]
        master = d.get("master_id") or inst.rsplit(".", 1)[0]
        v = str(d.get("version") or "")
        if master not in latest or v > str(first(by_inst[latest[master]]["docs"])["version"] or ""):
            latest[master] = inst
    models: dict[str, dict] = {}
    for inst in latest.values():
        e = by_inst[inst]
        d = sorted(e["docs"], key=lambda x: (x.get("replica") is True, node_rank(x.get("data_node", ""))))[0]
        src = first(d.get("source_id"))
        m = models.setdefault(src, {"inst": set(), "members": set(), "grids": set(), "res": set(), "version": "", "files": 0,
                                    "size": 0, "start": "", "end": "", "nodes": set(), "ids": []})
        m["inst"].add(first(d.get("institution_id")) or "")
        m["members"].add(first(d.get("member_id")) or first(d.get("variant_label")) or "")
        m["grids"].add(first(d.get("grid_label")) or "")
        if first(d.get("nominal_resolution")):
            m["res"].add(first(d.get("nominal_resolution")))
        m["version"] = max(m["version"], str(d.get("version") or ""))
        m["files"] += int(d.get("number_of_files") or 0)
        m["size"] += int(d.get("size") or 0)
        s, t = ym(d.get("datetime_start")), ym(d.get("datetime_end") or d.get("datetime_stop"))
        if s and (not m["start"] or s < m["start"]):
            m["start"] = s
        if t and t > m["end"]:
            m["end"] = t
        m["nodes"] |= e["nodes"]
        # 달력 확인용 데이터셋 id (노드 포함) — ORNL 먼저
        for x in sorted(e["docs"], key=lambda x: node_rank(x.get("data_node", ""))):
            m["ids"].append(x.get("id"))
    meta = {}
    if docs:
        d0 = docs[0]
        meta = {"long_name": first(d0.get("variable_long_name")) or "", "units": first(d0.get("variable_units")) or "",
                "realm": first(d0.get("realm")) or ""}
    return models, meta


def entry(m: dict) -> list:
    return [compress_members(m["members"]), len(m["members"]), sorted(g for g in m["grids"] if g), " / ".join(sorted(m["res"])),
            m["version"], m["files"], m["size"], m["start"], m["end"], len(m["nodes"])]


def cmip6_calendar(http: Http, ids: list[str]) -> tuple[str, str, str]:
    dap, hurl = [], []
    for did in ids[:4]:
        try:
            j = http.request("GET", SOLR, params={"type": "File", "dataset_id": did, "limit": 1, "format": "application/solr+json"},
                             tries=2).json()
        except Exception:  # noqa: BLE001
            continue
        for d in j["response"].get("docs") or []:
            for u in d.get("url") or []:
                href, _, kind = u.partition("|")
                kind = kind.split("|")[-1]
                if kind == "OPENDAP":
                    dap.append(href.removesuffix(".html"))
                elif kind == "HTTPServer":
                    hurl.append(href)
        if dap or hurl:
            if len(dap) >= 2:
                break
    dap.sort(key=node_rank)
    hurl.sort(key=node_rank)
    return read_calendar(dap, hurl)


def build_cmip6(http: Http, prev: dict | None, quick: bool, do_cal: bool) -> dict:
    exps = CMIP6_EXPS[:2] if quick else CMIP6_EXPS
    vars_ = [("Amon", "tas"), ("Omon", "tos")] if quick else CMIP6_VARS
    proj = {"index": SOLR, "index_name": "ORNL ESGF 1.5 index (Globus-based, Solr-compatible)",
            "query": {"project": "CMIP6", "latest": True, "type": "Dataset", "experiment_id": exps,
                      "variables": [f"{t}.{v}" for t, v in vars_]},
            "entry_fields": ENTRY_FIELDS, "experiments": exps, "variables": [], "models": {}, "avail": {}, "errors": []}
    prev_avail = (prev or {}).get("avail") or {}
    reps: dict[tuple[str, str], list[str]] = defaultdict(list)
    insts: dict[str, set] = defaultdict(set)
    var_meta: dict[str, dict] = {}

    def job(exp, table, var):
        t0 = time.time()
        docs = solr_datasets(http, exp, table, var)
        log(f"  CMIP6 {exp:>10} {table}.{var:<8} {len(docs):5d} docs  {time.time() - t0:5.1f}s")
        return docs

    tasks = [(exp, t, v) for t, v in vars_ for exp in exps]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(job, *t): t for t in tasks}
        results = {}
        for f, t in futs.items():
            try:
                results[t] = f.result()
            except Exception as e:  # noqa: BLE001
                results[t] = e
    for (exp, table, var) in tasks:
        key = f"{table}.{var}"
        res = results[(exp, table, var)]
        av = proj["avail"].setdefault(key, {})
        if isinstance(res, Exception):
            proj["errors"].append({"what": f"{exp} {key}", "error": f"{type(res).__name__}: {str(res)[:300]}", "kept_previous": True})
            for model, exps_ in (prev_avail.get(key) or {}).items():
                if exp in exps_:
                    av.setdefault(model, {})[exp] = exps_[exp]
            continue
        models, meta = summarize_cmip6(res)
        if meta and key not in var_meta:
            var_meta[key] = meta
        for model, m in models.items():
            av.setdefault(model, {})[exp] = entry(m)
            insts[model] |= {i for i in m["inst"] if i}
            reps[(model, TABLE_GROUP[table])] += m["ids"][:2]
    for t, v in vars_:
        key = f"{t}.{v}"
        mm = var_meta.get(key) or {}
        proj["variables"].append({"id": key, "var": v, "table": t, "freq": TABLE_FREQ[t], "group": TABLE_GROUP[t],
                                  "long_name": mm.get("long_name", ""), "units": mm.get("units", "")})
    models_all = sorted({m for a in proj["avail"].values() for m in a}, key=str.lower)
    prev_models = (prev or {}).get("models") or {}
    cal_jobs = []
    for model in models_all:
        info = {"institution": " / ".join(sorted(insts.get(model) or [])) or (prev_models.get(model) or {}).get("institution", ""),
                "calendar": {}}
        proj["models"][model] = info
        for grp in ("atmos", "ocean"):
            if (model, grp) in reps:
                cal_jobs.append((model, grp, reps[(model, grp)]))
    run_calendars(proj, cal_jobs, prev_models, do_cal, lambda ids: cmip6_calendar(http, ids))
    return proj


def run_calendars(proj, cal_jobs, prev_models, do_cal, fn):
    if not do_cal:
        for model, grp, _ in cal_jobs:
            old = ((prev_models.get(model) or {}).get("calendar") or {}).get(grp)
            if old:
                proj["models"][model]["calendar"][grp] = old
        return
    t0 = time.time()

    def go(job):
        model, grp, ids = job
        try:
            return job, fn(ids)
        except Exception as e:  # noqa: BLE001
            return job, ("", "", f"{type(e).__name__}: {str(e)[:150]}")
    with ThreadPoolExecutor(max_workers=4) as ex:
        for (model, grp, _), (cal, src, err) in ex.map(go, cal_jobs):
            c = {"value": cal, "source": urlparse(src).netloc if src else ""}
            if not cal:
                old = ((prev_models.get(model) or {}).get("calendar") or {}).get(grp) or {}
                if old.get("value"):
                    c = dict(old, note=f"this check failed, previous value kept ({err[:150]})")
                else:
                    c["note"] = err[:300]
            proj["models"][model]["calendar"][grp] = c
    ok = sum(1 for m in proj["models"].values() for c in m["calendar"].values() if c.get("value"))
    log(f"  달력: {ok}/{len(cal_jobs)} 확인  {time.time() - t0:.0f}s")


# ── CMIP7 (ESGF-NG STAC) ────────────────────────────────────────────
def stac_search(http: Http, base: str, body: dict) -> list[dict]:
    feats: list[dict] = []
    url, b = base + "/search", dict(body)
    for _ in range(500):
        j = http.request("POST", url, json=b).json()
        feats += j.get("features") or []
        nxt = [l for l in j.get("links") or [] if l.get("rel") == "next"]
        if not nxt or not (j.get("features") or []):
            return feats
        n = nxt[0]
        url = n.get("href") or url
        if (n.get("method") or "GET").upper() == "POST" and n.get("body"):
            b = n["body"]
        else:
            # GET 다음 페이지: 토큰만 바꿔 같은 질의로
            tok = re.search(r"[?&]token=([^&]+)", url)
            b = dict(body, token=tok.group(1)) if tok else None
            url = base + "/search"
            if b is None:
                return feats
    return feats


def cmip7_filter(var_ids, freqs, exp_clause):
    return {"op": "and", "args": [
        {"op": "in", "args": [{"property": "cmip7:variable_id"}, var_ids]},
        {"op": "in", "args": [{"property": "cmip7:frequency"}, freqs]},
        exp_clause,
    ]}


def cmip7_items(http: Http, base: str, var_ids, freqs) -> tuple[list[dict], str]:
    like = {"op": "or", "args": [
        {"op": "in", "args": [{"property": "cmip7:experiment_id"}, ["historical", "esm-hist"]]},
        {"op": "like", "args": [{"property": "cmip7:experiment_id"}, "scen7-%"]},
        {"op": "like", "args": [{"property": "cmip7:experiment_id"}, "esm-scen7-%"]},
    ]}
    body = {"collections": ["CMIP7"], "limit": 250, "filter-lang": "cql2-json"}
    try:
        feats = stac_search(http, base, dict(body, filter=cmip7_filter(var_ids, freqs, like)))
        bad = [f for f in feats if not CMIP7_EXP_RE.match(str(f["properties"].get("cmip7:experiment_id")))
               or f["properties"].get("cmip7:variable_id") not in var_ids]
        if not bad:
            return feats, "like"
        log(f"  CMIP7: LIKE 검색 결과에 조건 밖 항목 {len(bad)}개 → 실험 이름 목록으로 다시 검색")
    except Exception as e:  # noqa: BLE001
        log(f"  CMIP7: LIKE 검색 실패({str(e)[:120]}) → 실험 이름 목록으로 다시 검색")
    lst = {"op": "in", "args": [{"property": "cmip7:experiment_id"}, CMIP7_EXP_FALLBACK]}
    feats = stac_search(http, base, dict(body, filter=cmip7_filter(var_ids, freqs, lst)))
    return feats, "list"


def build_cmip7(http: Http, prev: dict | None, quick: bool, do_cal: bool) -> dict:
    var_ids = ["tas", "tos"] if quick else CMIP7_VAR_IDS
    freqs = ["mon"] if quick else CMIP7_FREQS
    errors = []
    feats, base, how = None, None, ""
    for b in STAC:
        try:
            t0 = time.time()
            feats, how = cmip7_items(http, b, var_ids, freqs)
            base = b
            log(f"  CMIP7 {b}: 항목 {len(feats)}개  {time.time() - t0:.1f}s ({how})")
            break
        except Exception as e:  # noqa: BLE001
            errors.append({"what": b, "error": f"{type(e).__name__}: {str(e)[:300]}"})
            log(f"  CMIP7 {b} 실패: {e}")
    if feats is None:
        if prev:
            out = dict(prev)
            out["errors"] = errors + [{"what": "CMIP7", "error": "all STAC indices failed, previous result kept", "kept_previous": True}]
            out["stale"] = True
            return out
        return {"index": STAC[0], "errors": errors, "experiments": [], "variables": [], "models": {}, "avail": {},
                "entry_fields": ENTRY_FIELDS}
    # 같은 데이터셋(base_id)은 최신 버전 하나만
    best: dict[str, dict] = {}
    for f in feats:
        p = f.get("properties") or {}
        if p.get("retracted") is True or p.get("latest") is False:
            continue
        if not CMIP7_EXP_RE.match(str(p.get("cmip7:experiment_id"))):
            continue
        bid = p.get("base_id") or f["id"].rsplit(".v", 1)[0]
        if bid not in best or str(p.get("version")) > str(best[bid]["properties"].get("version")):
            best[bid] = f
    proj = {"index": base, "index_name": "ESGF-NG STAC (collection CMIP7)",
            "query": {"collection": "CMIP7", "variable_id": var_ids, "frequency": freqs,
                      "experiment_id": "historical, esm-hist, scen7-*, esm-scen7-*", "latest": True, "retracted": False, "match": how},
            "entry_fields": ENTRY_FIELDS, "experiments": [], "variables": [], "models": {}, "avail": {}, "errors": errors}
    agg: dict[str, dict[str, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    vmeta: dict[str, dict] = {}
    reps: dict[tuple[str, str], list[str]] = defaultdict(list)
    insts: dict[str, set] = defaultdict(set)
    exps = set()
    for f in best.values():
        p = f["properties"]
        g = lambda k: first(p.get("cmip7:" + k))  # noqa: E731
        var, freq, region = g("variable_id"), g("frequency"), g("region") or "glb"
        branded = g("variable_branded_name") or f"{var}_{g('variable_branding_suffix')}"
        key = f"{freq}.{branded}" + ("" if region == "glb" else f".{region}")
        if key not in vmeta:
            vmeta[key] = {"id": key, "var": var, "branded": branded, "branding_suffix": g("variable_branding_suffix") or "",
                          "freq": freq, "region": region, "group": "ocean" if var in CMIP7_OCEAN else "atmos",
                          "long_name": g("variable_long_name") or "", "units": g("variable_units") or ""}
        src, exp = g("source_id"), g("experiment_id")
        exps.add(exp)
        insts[src].add(g("institution_id") or "")
        m = agg[key][src].setdefault(exp, {"members": set(), "grids": set(), "res": set(), "version": "", "files": 0, "size": 0,
                                           "start": "", "end": "", "nodes": set()})
        m["members"].add(g("variant_label") or "")
        m["grids"].add(g("grid_label") or "")
        if g("nominal_resolution"):
            m["res"].add(g("nominal_resolution"))
        m["version"] = max(m["version"], str(p.get("version") or ""))
        data_assets = {k: a for k, a in (f.get("assets") or {}).items() if "data" in (a.get("roles") or []) or str(a.get("href", "")).endswith(".nc")}
        names = {Path(str(a.get("file:local_path") or a.get("href") or k)).name for k, a in data_assets.items()}
        m["files"] += len(names)
        m["size"] += int(p.get("size") or sum(int(a.get("file:size") or 0) for a in data_assets.values()))
        s, t = ym(p.get("start_datetime")), end_ym(p.get("end_datetime"))
        if s and (not m["start"] or s < m["start"]):
            m["start"] = s
        if t and t > m["end"]:
            m["end"] = t
        m["nodes"] |= {urlparse(str(a.get("href"))).netloc for a in data_assets.values() if a.get("href")}
        hrefs = sorted((str(a.get("href")) for a in data_assets.values() if a.get("href")), key=node_rank)
        if hrefs and len(reps[(src, vmeta[key]["group"])]) < 3:
            reps[(src, vmeta[key]["group"])].append(hrefs[0])
    for key, models in agg.items():
        proj["avail"][key] = {src: {exp: entry(m) for exp, m in ex.items()} for src, ex in models.items()}
    proj["experiments"] = sorted(exps, key=lambda e: (e not in ("historical", "esm-hist"), e.startswith("esm-"), e))
    proj["variables"] = sorted(vmeta.values(), key=lambda v: (v["freq"] != "mon", CMIP7_VAR_IDS.index(v["var"]) if v["var"] in CMIP7_VAR_IDS else 99, v["id"]))
    prev_models = (prev or {}).get("models") or {}
    cal_jobs = []
    for src in sorted({m for a in proj["avail"].values() for m in a}, key=str.lower):
        proj["models"][src] = {"institution": " / ".join(sorted(i for i in insts[src] if i)), "calendar": {}}
        for grp in ("atmos", "ocean"):
            if (src, grp) in reps:
                cal_jobs.append((src, grp, reps[(src, grp)]))

    def cal7(hrefs):
        dap = [h.replace("/thredds/fileServer/", "/thredds/dodsC/") for h in hrefs if "/thredds/fileServer/" in h]
        return read_calendar(dap, hrefs)
    run_calendars(proj, cal_jobs, prev_models, do_cal, cal7)
    return proj


# ── 저장 ────────────────────────────────────────────────────────────
def strip_volatile(c: dict) -> dict:
    c = json.loads(json.dumps(c))
    for k in ("generated", "checked", "elapsed_sec", "requests"):
        c.pop(k, None)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--quick", action="store_true", help="시험용: 변수·실험 일부만")
    ap.add_argument("--no-calendar", action="store_true")
    ap.add_argument("--only", choices=["CMIP6", "CMIP7"])
    a = ap.parse_args()
    out = Path(a.out)
    prev = {}
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}
    t0 = time.time()
    http = Http(max_conc=3)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cat = {"schema": 1, "generated": now, "checked": now, "generator": "scripts/model_catalog.py",
           "site": "https://data4researchers.kr/model-data/", "projects": {}}
    builders = {"CMIP6": build_cmip6, "CMIP7": build_cmip7}
    for name, fn in builders.items():
        old = (prev.get("projects") or {}).get(name)
        if a.only and a.only != name:
            if old:
                cat["projects"][name] = old
            continue
        log(f"[{name}]")
        try:
            cat["projects"][name] = fn(http, old, a.quick, not a.no_calendar)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            err = {"what": name, "error": f"{type(e).__name__}: {str(e)[:300]}"}
            if old:
                cat["projects"][name] = dict(old, stale=True, errors=[err, {"what": name, "error": "previous result kept", "kept_previous": True}])
            else:
                cat["projects"][name] = {"errors": [err], "experiments": [], "variables": [], "models": {}, "avail": {}, "entry_fields": ENTRY_FIELDS}
        p = cat["projects"][name]
        p["counts"] = {"models": len(p.get("models") or {}), "variables": len(p.get("variables") or []),
                       "experiments": len(p.get("experiments") or []),
                       "entries": sum(len(e) for a_ in (p.get("avail") or {}).values() for e in a_.values())}
    cat["elapsed_sec"] = round(time.time() - t0)
    cat["requests"] = http.count
    if prev and strip_volatile(prev) == strip_volatile(cat):
        prev["checked"] = now
        cat = prev  # 내용이 같으면 날짜도 그대로 (커밋 안 생기게 '확인 시각'만 바꾸지 않음)
        log("바뀐 내용 없음 — 파일을 그대로 둡니다")
        summary(cat)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(cat, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    out.write_text(txt + "\n", encoding="utf-8")
    log(f"저장: {out}  {len(txt.encode()) / 1024:.0f} KB  요청 {http.count}회  {cat['elapsed_sec']}s")
    summary(cat)
    # 두 프로젝트 모두 비었으면 실패로 끝냄 (운영자가 알 수 있게)
    if not any((p.get("avail") or {}) for p in cat["projects"].values()):
        return 1
    return 0


def summary(cat):
    for name, p in cat["projects"].items():
        c = p.get("counts") or {}
        log(f"  {name}: 모델 {c.get('models')}개 · 변수 {c.get('variables')}개 · 실험 {c.get('experiments')}개 · 항목 {c.get('entries')}개"
            f" · 오류 {len(p.get('errors') or [])}건" + (" (지난번 결과)" if p.get("stale") else ""))


if __name__ == "__main__":
    sys.exit(main())
