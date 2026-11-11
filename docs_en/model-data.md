---
title: "Model data download — CMIP6/CMIP7 availability table and download-and-merge Python scripts"
description: "See which CMIP6 and CMIP7 models have each experiment, with members, grids, calendars and file sizes, and generate a Python script that downloads with intake-esgf, subsets, harmonises calendars and grids and merges the files."
hide:
  - toc
---

# Model data download

CMIP output is split into separate files for every **model · experiment · member (variant) · grid (gn/gr) · version · time chunk**, and models differ in calendar (`noleap`, `360_day`, `standard` …) and grid.
On this page you can ① check in an **availability table** which models have what, and ② generate a **download-and-merge Python script** for your selection to run on your own computer.
This site does not host any data; the scripts download directly from the Earth System Grid Federation (ESGF).

<!-- MODEL_DATA_APP -->

## How to use

1. **Choose data** — pick the project (CMIP6 or CMIP7), frequency (monthly or daily), variable and experiments. "Only models that have all chosen experiments" keeps only models with both historical and the scenarios.
2. **Availability table** — for each model: institution, number of members, grid, nominal resolution, calendar, number of files, size and latest version, plus members and period for each experiment. Click a column header to sort, and use the left-hand boxes to choose the models that go into the script.
3. **Script options** — members, years, region (default: around the Korean Peninsula), calendar, regridding, unit conversion and output layout.
4. **Script** — copy one of the two scripts or save it as `.py` and run it.
    - **Download from ESGF and merge**: searches and downloads with [intake-esgf](https://intake-esgf.readthedocs.io/en/latest/), then subsets the years and region and joins the pieces. Originals stay in `~/.esgf/`, so a re-run does not download them again.
    - **Merge a folder of downloaded files**: reads the file names in a folder you filled some other way (the ESGF web search, wget scripts, Globus …), groups them and merges them.

```bash
pip install "intake-esgf>=2026.9.28" xarray netCDF4 cftime dask
python cmip6_tas_amon_download.py        # prints a success/failure summary per model at the end
```

The scripts do not hide failures. They report models with no search results or unresponsive data nodes, overlapping or missing periods and duplicate versions as they go, and finish with a per-model summary.
Output goes to `cmip_out/` as `variable_table_model_experiment_member_grid_period.nc`.

## Things to check

!!! warning "Before you merge"
    - **Calendars** — models use `noleap` (365 days), `360_day`, `standard` or `proleptic_gregorian`. Put several models on one time axis only after unifying the calendar.
      Converting daily `360_day` data spreads the extra or missing days evenly over the year (xarray `convert_calendar` with `align_on="year"`), so values shift by a day or two and inserted days are empty (NaN). Monthly data are re-stamped at the 15th of the same month.
    - **Grids** — `gn` is the model's native grid and `gr` a grid regridded by the modelling centre (CMIP7 uses registered numbers such as `g100`). Ocean and sea-ice variables are often on curvilinear grids with 2-D latitude and longitude; when cutting a box, values outside it are left empty.
      To combine models in one file they must be regridded to a common grid, which needs [xESMF](https://xesmf.readthedocs.io/) (`conda install -c conda-forge xesmf`). Use conservative regridding for precipitation and fluxes when totals matter.
    - **Members** — different `f` (forcing) or `p` (physics) indices in `r1i1p1f1` mean a different set-up. "First member" is the lowest-numbered member present in every chosen experiment, and historical and scenario runs are joined **only for the same member**.
    - **Versions** — corrected datasets are republished as a new version (such as `v20210101`). The table and the download script use the latest version only, and the folder merge keeps only the latest when it finds several. Report the version you used in your paper.
    - **Errata** — datasets with known problems are retracted or listed in the [ESGF errata service](https://errata.esgf.io/). Check before use.
    - **Units** — CMIP precipitation `pr` is in kg m⁻² s⁻¹ (= mm s⁻¹); multiply by 86400 for mm/day. Temperatures are in K.
    - **Where historical meets the scenarios** — in CMIP6 historical ends in 2014 and the SSPs start in 2015; in CMIP7 historical ends in 2021 and scen7-* start in 2022. Any overlapping time steps keep the historical values and are reported.

!!! info "The availability table is a summary"
    The table is rebuilt every week from the ESGF search indices (CMIP6: ORNL ESGF 1.5 index; CMIP7: ESGF-NG STAC index). Calendars are not in the indices, so they were read remotely from the header of one file per model.
    Index and data-node status change all the time, so what you can actually download may differ slightly. Sizes add up every member of the chosen experiments; what you download (first member, chosen years) is much smaller.

## Citation and acknowledgement

If you use CMIP data in a paper you must cite the model output you used and include the required acknowledgement. The generated scripts carry these links at the top too.

- CMIP6: [CMIP6 terms of use](https://pcmdi.llnl.gov/CMIP6/TermsOfUse/TermsOfUse6-2.html), and "References for your paper" on the [CMIP6](datasets/cmip6.md) page of this site
- CMIP7: [CMIP7 guidance for data users](https://wcrp-cmip.github.io/cmip7-guidance/docs/CMIP7/Guidance_for_users/), [CMIP7 citation search](https://cmip7-citations.ceda.ac.uk/citations/), and the [CMIP7](datasets/cmip7.md) page of this site

## Other routes — ready-made products

Instead of downloading and harmonising many models yourself, a product already on a common grid, calendar and variable naming is often much simpler.

| Dataset | What it offers |
|---|---|
| [NEX-GDDP-CMIP6](datasets/nex-gddp-cmip6.md) | 35 CMIP6 models, bias-adjusted and downscaled to a 0.25° daily grid (9 variables: temperature, precipitation, humidity, radiation, wind), no account needed |
| [ISIMIP3b](datasets/isimip3b.md) | 0.5° daily data bias-adjusted to W5E5 for impact models (10 CMIP6 models) |
| [CORDEX-CMIP6](datasets/cordex-cmip6.md) | Regional climate model downscaling over continental domains (including East Asia, EAS) |
| [CMIP6](datasets/cmip6.md) — Copernicus CDS | 46 key variables, cut to your region and period (CDS account needed) |
| [CMIP6](datasets/cmip6.md) — Pangeo cloud copy | Zarr copies of a core subset in the cloud (open with intake-esm) |
