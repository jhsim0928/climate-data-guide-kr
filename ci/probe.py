"""ESGF 접속 시험 (Actions에서) — 응답 시간·필드·페이지 크기 확인"""
import json, time, sys, traceback
import requests
UA = {"User-Agent": "data4researchers-model-catalog/0.1 (+https://data4researchers.kr/)"}
out = {}
def t(name, fn):
    t0 = time.time()
    try:
        r = fn()
        out[name] = {"ok": True, "sec": round(time.time() - t0, 1), "result": r}
    except Exception as e:
        out[name] = {"ok": False, "sec": round(time.time() - t0, 1), "error": repr(e)[:500], "tb": traceback.format_exc()[-800:]}
    print(name, json.dumps(out[name], ensure_ascii=False)[:1500], flush=True)

B = "https://esgf-node.ornl.gov/esgf-1-5-bridge"
def solr(params, timeout=180):
    p = {"format": "application/solr+json", "latest": "true", "type": "Dataset"}
    p.update(params)
    r = requests.get(B, params=p, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()

def q1():
    j = solr({"project": "CMIP6", "experiment_id": "historical", "variable_id": "tas", "table_id": "Amon", "limit": 1000,
              "fields": "instance_id,source_id,data_node,size,number_of_files"})
    d = j["response"]["docs"]
    return {"numFound": j["response"]["numFound"], "n": len(d), "keys": sorted(d[0].keys()) if d else [], "hdr": j.get("responseHeader", {}).get("params")}
t("solr_fields_1000", q1)
def q2():
    j = solr({"project": "CMIP6", "experiment_id": "historical", "variable_id": "tas", "table_id": "Amon", "limit": 1000, "offset": 1000})
    d = j["response"]["docs"]
    return {"numFound": j["response"]["numFound"], "n": len(d), "start": j["response"].get("start")}
t("solr_all_offset1000", q2)
def q3():
    j = solr({"project": "CMIP6", "experiment_id": "historical", "variable_id": "tas", "table_id": "Amon", "limit": 0,
              "facets": "source_id,data_node"})
    return {"numFound": j["response"]["numFound"], "facets": {k: len(v) for k, v in j.get("facet_counts", {}).get("facet_fields", {}).items()}}
t("solr_facets", q3)
def q3b():
    j = solr({"project": "CMIP6", "experiment_id": ["historical", "ssp245"], "variable_id": "tas", "table_id": "Amon", "limit": 0, "facets": "experiment_id"})
    return {"numFound": j["response"]["numFound"], "facet": j.get("facet_counts", {}).get("facet_fields", {})}
t("solr_multi_value", q3b)
def q4():
    j = solr({"project": "CMIP6", "experiment_id": "historical", "variable_id": "tas", "table_id": "Amon", "limit": 3, "distrib": "false"})
    return {"numFound": j["response"]["numFound"]}
t("solr_distrib_false", q4)
def q5():
    p = {"format": "application/solr+json", "type": "File", "project": "CMIP6", "source_id": "CanESM5", "experiment_id": "historical",
         "variable_id": "tas", "table_id": "Amon", "member_id": "r1i1p1f1", "latest": "true", "limit": 10}
    r = requests.get(B, params=p, headers=UA, timeout=120); r.raise_for_status(); j = r.json()
    return [{"node": d.get("data_node"), "url": d.get("url")} for d in j["response"]["docs"]]
t("solr_files", q5)

# 달력 읽기 (OPeNDAP / HTTPS 범위)
def cal_dap():
    import netCDF4
    u = "http://esgf-node.ornl.gov/thredds/dodsC/css03_data/CMIP6/CMIP/CCCma/CanESM5/historical/r1i1p1f1/Amon/tas/gn/v20190429/tas_Amon_CanESM5_historical_r1i1p1f1_gn_185001-201412.nc"
    with netCDF4.Dataset(u) as nc:
        tv = nc.variables["time"]
        return {"calendar": getattr(tv, "calendar", None), "units": tv.units, "len": len(tv)}
t("calendar_opendap_ornl", cal_dap)
def cal_https():
    import fsspec, h5netcdf
    u = "https://esgf-node.ornl.gov/thredds/fileServer/css03_data/CMIP6/CMIP/CCCma/CanESM5/historical/r1i1p1f1/Amon/tas/gn/v20190429/tas_Amon_CanESM5_historical_r1i1p1f1_gn_185001-201412.nc"
    with fsspec.open(u, "rb", block_size=2**18, headers=UA) as f:
        with h5netcdf.File(f, "r") as h:
            tv = h.variables["time"]
            return {"calendar": tv.attrs.get("calendar"), "units": tv.attrs.get("units")}
t("calendar_https_range_ornl", cal_https)

# STAC
S = "https://discovery.west.esgf.io"
def s1():
    body = {"collections": ["CMIP7"], "limit": 500,
            "filter-lang": "cql2-json",
            "filter": {"op": "and", "args": [
                {"op": "=", "args": [{"property": "cmip7:variable_id"}, "tas"]},
                {"op": "=", "args": [{"property": "cmip7:frequency"}, "mon"]},
                {"op": "in", "args": [{"property": "cmip7:experiment_id"}, ["historical", "scen7-h", "scen7-m", "scen7-vl"]]}]},
            "fields": {"include": ["id", "properties"], "exclude": ["assets", "links", "geometry"]}}
    r = requests.post(S + "/search", json=body, headers=UA, timeout=120); r.raise_for_status(); j = r.json()
    f = j["features"]
    return {"n": len(f), "matched": j.get("numberMatched"), "has_assets": bool(f and "assets" in f[0]),
            "next": [l for l in j.get("links", []) if l.get("rel") == "next"][:1],
            "sample": [(x["properties"].get("cmip7:source_id"), x["properties"].get("cmip7:experiment_id"), x["properties"].get("cmip7:variable_branded_name"),
                        x["properties"].get("cmip7:region"), x["properties"].get("cmip7:grid_label"), x["properties"].get("latest")) for x in f[:60]]}
t("stac_post", s1)
def s2():
    r = requests.get(S + "/collections/CMIP7/aggregate", params={"aggregations": "experiment_id_frequency,source_id_frequency",
        "filter-lang": "cql2-text", "filter": "cmip7:variable_id='tas' AND cmip7:frequency='mon'"}, headers=UA, timeout=120)
    r.raise_for_status(); return r.json()["aggregations"]
t("stac_aggregate_filtered", s2)
def s3():
    r = requests.get(S + "/aggregate", params={"collections": "CMIP7", "aggregations": "experiment_id_frequency,source_id_frequency",
        "filter-lang": "cql2-text", "filter": "cmip7:variable_id='tas' AND cmip7:frequency='mon'"}, headers=UA, timeout=120)
    r.raise_for_status(); return r.json()["aggregations"]
t("stac_aggregate_root_filtered", s3)
def s4():
    body = {"collections": ["CMIP7"], "limit": 2, "filter-lang": "cql2-json",
            "filter": {"op": "=", "args": [{"property": "cmip7:variable_id"}, "tas"]}}
    r = requests.post(S + "/search", json=body, headers=UA, timeout=120); r.raise_for_status(); j = r.json()
    f = j["features"][0]
    a = list(f["assets"].values())[0]
    return {"asset": a, "props": f["properties"]}
t("stac_asset_sample", s4)
def s5():
    j = requests.post(S + "/search", json={"collections": ["CMIP7"], "limit": 1, "filter-lang": "cql2-json",
        "filter": {"op": "=", "args": [{"property": "cmip7:variable_id"}, "tas"]}}, headers=UA, timeout=120).json()
    a = list(j["features"][0]["assets"].values())[0]["href"]
    import netCDF4
    dap = a.replace("/fileServer/", "/dodsC/")
    res = {"href": a}
    try:
        with netCDF4.Dataset(dap) as nc:
            res["dap_calendar"] = getattr(nc.variables["time"], "calendar", None)
    except Exception as e:
        res["dap_err"] = repr(e)[:300]
    try:
        import fsspec, h5netcdf
        with fsspec.open(a, "rb", block_size=2**18, headers=UA) as fh:
            with h5netcdf.File(fh, "r") as h:
                res["https_calendar"] = h.variables["time"].attrs.get("calendar")
    except Exception as e:
        res["https_err"] = repr(e)[:300]
    return res
t("stac_calendar", s5)
def s6():
    r = requests.get("https://discovery.east.esgf.io/collections", headers=UA, timeout=60); r.raise_for_status()
    return [c["id"] for c in r.json()["collections"]]
t("stac_east_collections", s6)

json.dump(out, open("ci-results/probe.json", "w"), indent=1, ensure_ascii=False, default=str)
