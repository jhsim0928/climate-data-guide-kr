"""'모델 자료 받기' 합치기 스크립트 시험용 가짜 CMIP 파일 만들기

    python scripts/tests/make_fake_cmip.py <폴더>

만드는 것 (값 = 연*100 + 월 처럼 시각을 알 수 있게 넣어 이어 붙이기를 확인할 수 있음)
- MODA (noleap, 일반 위경도 격자 2.5°): historical 3조각(1990–1999, 2000–2009, 2005–2014 ← 2005–2009 겹침), 버전 2개(v20190101 일부, v20200101 전체)
                                        ssp245 2015–2030 (멤버 r1i1p1f1, r2i1p1f1 — r2 는 historical 없음)
- MODB (360_day, 곡선 격자 lat(y,x)/lon(y,x)): historical 2조각 사이 빈 구간(2000-12 → 2002-01), ssp245 2015–2030, 멤버 r1i1p1f2
- MODA 일 자료 (noleap) historical 2010–2014 + ssp245 2015–2016 (일별 달력 변환 시험)
- MODB 일 자료 (360_day) historical 2013–2014 (360_day → noleap 변환 시험)
- CMIP7 이름 규칙 파일 1개 묶음 (MODC, proleptic_gregorian, 2조각)
- 이름 규칙에 맞지 않는 파일 1개
"""
import sys
from pathlib import Path

import cftime
import numpy as np
import xarray as xr

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "fake_cmip")


def month_times(y0, y1, cal):
    t, b = [], []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            a = cftime.datetime(y, m, 1, calendar=cal)
            z = cftime.datetime(y + (m == 12), m % 12 + 1, 1, calendar=cal)
            t.append(a + (z - a) / 2)
            b.append((a, z))
    return t, b


def day_times(y0, y1, cal):
    t, b = [], []
    a = cftime.datetime(y0, 1, 1, calendar=cal)
    end = cftime.datetime(y1 + 1, 1, 1, calendar=cal)
    one = cftime.datetime(2000, 1, 2, calendar=cal) - cftime.datetime(2000, 1, 1, calendar=cal)
    while a < end:
        t.append(a + one / 2)
        b.append((a, a + one))
        a = a + one
    return t, b


def regular_grid():
    lat = np.arange(-88.75, 90, 2.5)
    lon = np.arange(1.25, 360, 2.5)
    return lat, lon


def write(path, var, times, bnds, cal, grid, attrs, freq):
    path.parent.mkdir(parents=True, exist_ok=True)
    nt = len(times)
    vals = np.array([t.year * 100 + t.month + (t.day / 100 if freq == "day" else 0) for t in times], dtype="f4")
    if grid == "regular":
        lat, lon = regular_grid()
        data = vals[:, None, None] + np.zeros((nt, lat.size, lon.size), "f4")
        data = data + 273.15 * (var == "tas")
        ds = xr.Dataset({var: (("time", "lat", "lon"), data)},
                        coords={"lat": ("lat", lat, {"standard_name": "latitude", "units": "degrees_north", "bounds": "lat_bnds"}),
                                "lon": ("lon", lon, {"standard_name": "longitude", "units": "degrees_east", "bounds": "lon_bnds"})})
        ds["lat_bnds"] = (("lat", "bnds"), np.stack([lat - 1.25, lat + 1.25], 1))
        ds["lon_bnds"] = (("lon", "bnds"), np.stack([lon - 1.25, lon + 1.25], 1))
    else:  # 곡선 격자 (회전된 격자 흉내)
        ny, nx = 40, 60
        j, i = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
        lat2 = -80 + j * 4.0 + 0.3 * np.sin(i / 5)
        lon2 = (i * 6.0 + 0.5 * j) % 360
        data = vals[:, None, None] + np.zeros((nt, ny, nx), "f4") + 273.15 * (var in ("tas", "tos"))
        ds = xr.Dataset({var: (("time", "j", "i"), data)},
                        coords={"latitude": (("j", "i"), lat2, {"standard_name": "latitude", "units": "degrees_north"}),
                                "longitude": (("j", "i"), lon2, {"standard_name": "longitude", "units": "degrees_east"})})
    ds[var].attrs = {"standard_name": "air_temperature", "units": "K", "long_name": "Near-Surface Air Temperature"}
    if var == "pr":
        ds[var] = ds[var] * 0 + 1e-5
        ds[var].attrs = {"standard_name": "precipitation_flux", "units": "kg m-2 s-1"}
    ds = ds.assign_coords(time=("time", np.array(times, dtype=object), {"standard_name": "time", "bounds": "time_bnds"}))
    ds["time_bnds"] = (("time", "bnds"), np.array(bnds, dtype=object))
    ds.attrs = dict(attrs, tracking_id="hdl:21.14100/fake-%s" % path.stem)
    enc = {"time": {"units": "days since 1850-01-01", "calendar": cal}, "time_bnds": {"units": "days since 1850-01-01", "calendar": cal}}
    ds.to_netcdf(path, encoding=enc)


def cmip6(model, exp, mem, grid_label, table, var, y0, y1, cal, grid, version, sub=""):
    freq = "day" if table == "day" else "mon"
    t, b = (day_times if freq == "day" else month_times)(y0, y1, cal)
    tag = ("%04d0101-%04d1231" % (y0, y1)) if freq == "day" else ("%04d01-%04d12" % (y0, y1))
    d = ROOT / "CMIP6" / model / exp / mem / table / var / grid_label / ("v" + version)
    name = f"{var}_{table}_{model}_{exp}_{mem}_{grid_label}_{tag}.nc"
    write(d / name, var, t, b, cal, grid, {"source_id": model, "experiment_id": exp, "variant_label": mem}, freq)


def main():
    # MODA: noleap, 일반 격자
    for y0, y1 in [(1990, 1999), (2000, 2009)]:
        cmip6("MODA", "historical", "r1i1p1f1", "gn", "Amon", "tas", y0, y1, "noleap", "regular", "20190101")
    for y0, y1 in [(1990, 1999), (2000, 2009), (2005, 2014)]:
        cmip6("MODA", "historical", "r1i1p1f1", "gn", "Amon", "tas", y0, y1, "noleap", "regular", "20200101")
    for mem in ("r1i1p1f1", "r2i1p1f1"):
        cmip6("MODA", "ssp245", mem, "gn", "Amon", "tas", 2015, 2030, "noleap", "regular", "20200101")
    cmip6("MODA", "historical", "r1i1p1f1", "gn", "Amon", "pr", 2000, 2014, "noleap", "regular", "20200101")
    # MODB: 360_day, 곡선 격자, 빈 구간
    cmip6("MODB", "historical", "r1i1p1f2", "gn", "Amon", "tas", 1990, 2000, "360_day", "curvi", "20210301")
    cmip6("MODB", "historical", "r1i1p1f2", "gn", "Amon", "tas", 2002, 2014, "360_day", "curvi", "20210301")
    cmip6("MODB", "ssp245", "r1i1p1f2", "gn", "Amon", "tas", 2015, 2030, "360_day", "curvi", "20210301")
    # 일 자료
    cmip6("MODA", "historical", "r1i1p1f1", "gn", "day", "tas", 2010, 2014, "noleap", "regular", "20200101")
    cmip6("MODA", "ssp245", "r1i1p1f1", "gn", "day", "tas", 2015, 2016, "noleap", "regular", "20200101")
    cmip6("MODB", "historical", "r1i1p1f2", "gn", "day", "tas", 2013, 2014, "360_day", "curvi", "20210301")
    # CMIP7 이름 규칙
    for y0, y1 in [(2000, 2009), (2010, 2021)]:
        t, b = month_times(y0, y1, "proleptic_gregorian")
        name = f"tas_tavg-h2m-hxy-u_mon_glb_g110_MODC_historical_r1i1p1f1_{y0:04d}01-{y1:04d}12.nc"
        write(ROOT / "CMIP7" / "v20261001" / name, "tas", t, b, "proleptic_gregorian", "regular", {"source_id": "MODC"}, "mon")
    (ROOT / "readme_not_drs.nc").write_bytes(b"not a netcdf")
    print("fake files:", len(list(ROOT.rglob("*.nc"))), "in", ROOT)


if __name__ == "__main__":
    main()
