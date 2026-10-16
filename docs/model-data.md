---
title: "모델 자료 받기 — CMIP6·CMIP7 가용성 표와 받기·합치기 Python 스크립트"
description: "CMIP6·CMIP7 모델별로 실험·멤버·격자·달력·파일 크기를 한 표로 보고, intake-esgf로 받아 기간·영역을 자르고 달력·격자를 맞춰 하나로 합치는 Python 스크립트를 만들어 줍니다."
hide:
  - toc
---

# 모델 자료 받기

CMIP 자료는 **모델 · 실험 · 멤버(variant) · 격자(gn/gr) · 버전 · 시간 조각**마다 파일이 따로 나뉘어 있고, 모델마다 달력(`noleap`·`360_day`·`standard` …)과 격자도 다릅니다.
이 페이지에서는 ① 어떤 모델이 무엇을 갖고 있는지 **가용성 표**로 확인하고, ② 고른 조건으로 **받기·합치기 Python 스크립트**를 만들어 내 컴퓨터에서 돌릴 수 있습니다.
이 사이트는 자료를 보관하지 않으며, 스크립트는 ESGF(지구시스템 그리드 연합)에서 직접 받습니다.

<!-- MODEL_DATA_APP -->

## 쓰는 법

1. **자료 고르기** — 프로젝트(CMIP6·CMIP7), 빈도(월·일), 변수, 실험을 고릅니다. "고른 실험이 모두 있는 모델만 보기"를 켜면 historical과 시나리오가 다 있는 모델만 남습니다.
2. **가용성 표** — 모델마다 기관·멤버 수·격자·공칭 해상도·달력·파일 수·크기·최신 버전과 실험별 멤버 수·기간이 나옵니다. 열 이름을 누르면 정렬되고, 왼쪽 칸으로 스크립트에 넣을 모델을 고릅니다.
3. **스크립트 옵션** — 멤버, 기간, 영역(기본 한반도 주변), 달력 통일, 재격자, 단위 변환, 출력 방식을 정합니다.
4. **스크립트** — 두 가지 중 하나를 복사하거나 `.py`로 저장해 돌립니다.
    - **ESGF에서 받아 합치기**: [intake-esgf](https://intake-esgf.readthedocs.io/en/latest/)로 찾아 받은 뒤 기간·영역을 자르고 이어 붙입니다. 원본은 `~/.esgf/`에 남아 다시 돌리면 받지 않습니다.
    - **이미 받은 파일 폴더 합치기**: 다른 방법(웹 검색 화면, wget 스크립트, Globus 등)으로 받아 둔 폴더의 파일 이름을 읽어 묶고 합칩니다.

```bash
pip install "intake-esgf>=2026.9.28" xarray netCDF4 cftime dask
python cmip6_tas_amon_download.py        # 끝에 모델별 성공·실패 요약이 나옵니다
```

스크립트는 실패를 숨기지 않습니다. 검색 결과가 없거나 노드가 응답하지 않는 모델, 겹치거나 빈 구간, 버전이 여럿인 경우를 하나하나 알려 주고, 마지막에 모델별 결과를 정리합니다.
결과 파일은 `cmip_out/`에 `변수_테이블_모델_실험_멤버_격자_기간.nc` 이름으로 저장됩니다.

## 주의할 점

!!! warning "합치기 전에 꼭 확인하세요"
    - **달력** — 모델마다 `noleap`(365일), `360_day`, `standard`·`proleptic_gregorian`처럼 다릅니다. 여러 모델을 한 시간 축에 놓으려면 달력을 통일해야 합니다.
      일 자료를 `360_day`에서 바꾸면 해마다 날짜를 고르게 늘리거나 줄이므로(xarray `convert_calendar`의 `align_on="year"`) 하루 이틀 어긋나고 새로 생긴 날은 비어(NaN) 있습니다. 월 자료는 같은 연·월의 15일로 다시 적습니다.
    - **격자** — `gn`은 모델 원래 격자, `gr`은 기관이 다시 만든 격자입니다(CMIP7은 `g100` 같은 등록 번호). 해양·해빙 변수는 위경도가 2차원인 곡선 격자가 많아 상자를 자르면 상자 밖 값은 비워 둡니다.
      여러 모델을 한 파일로 묶으려면 공통 격자로 재격자해야 하며, 이때 [xESMF](https://xesmf.readthedocs.io/)가 필요합니다(`conda install -c conda-forge xesmf`). 강수·플럭스처럼 총량이 중요하면 conservative를 권합니다.
    - **멤버** — `r1i1p1f1`의 `f`(강제력)·`p`(물리) 번호가 다르면 실험 설정이 다릅니다. "첫 멤버"는 고른 실험에 모두 있는 멤버 중 가장 앞 번호이고, historical과 시나리오는 **같은 멤버끼리만** 이어 붙입니다.
    - **버전** — 같은 데이터셋이 고쳐지면 새 버전(`v20210101` 같은)으로 다시 올라옵니다. 가용성 표와 스크립트는 최신(latest)만 쓰고, 폴더 합치기는 버전이 여럿이면 최신만 씁니다. 논문에는 사용한 버전을 적으세요.
    - **정오표** — 오류가 알려진 자료는 철회(retracted)되거나 [ESGF 정오표](https://errata.esgf.io/)에 올라갑니다. 쓰기 전에 확인하세요.
    - **단위** — CMIP 강수 `pr`은 kg m⁻² s⁻¹(= mm s⁻¹)이라 86400을 곱하면 mm/day입니다. 기온은 K입니다.
    - **historical과 시나리오의 경계** — CMIP6은 historical이 2014년까지, SSP가 2015년부터이고, CMIP7은 historical이 2021년까지, scen7-*이 2022년부터입니다. 겹치는 시각이 있으면 historical 값을 쓰고 알려 줍니다.

!!! info "가용성 표는 요약입니다"
    표는 매주 ESGF 검색 색인(CMIP6: ORNL ESGF 1.5 색인, CMIP7: ESGF-NG STAC 색인)을 자동으로 확인해 만듭니다. 달력은 색인에 없어서 모델마다 파일 하나의 머리글만 원격으로 읽어 적었습니다.
    색인과 자료 노드 상태는 수시로 바뀌니, 받을 때 실제로 있는 자료는 조금 다를 수 있습니다. 크기는 고른 실험의 모든 멤버를 합친 값이라 실제로 받는 양(첫 멤버, 기간)은 훨씬 작습니다.

## 인용·사사

CMIP 자료를 논문에 쓰면 사용한 모델 자료를 인용하고 정해진 사사 문장을 넣어야 합니다. 생성된 스크립트 맨 위에도 안내 주소가 들어갑니다.

- CMIP6: [CMIP6 이용 약관](https://pcmdi.llnl.gov/CMIP6/TermsOfUse/TermsOfUse6-2.html), 이 사이트의 [CMIP6](datasets/cmip6.md) 페이지 '논문에 넣을 레퍼런스'
- CMIP7: [CMIP7 자료 이용자 안내](https://wcrp-cmip.github.io/cmip7-guidance/docs/CMIP7/Guidance_for_users/), [CMIP7 인용 검색](https://cmip7-citations.ceda.ac.uk/citations/), 이 사이트의 [CMIP7](datasets/cmip7.md) 페이지

## 다른 길 — 이미 정리된 자료 쓰기

여러 모델을 직접 받아 맞추는 대신, 이미 같은 격자·달력·변수 이름으로 정리된 자료를 쓰면 훨씬 간단할 때가 많습니다.

| 자료 | 특징 |
|---|---|
| [NEX-GDDP-CMIP6](datasets/nex-gddp-cmip6.md) | CMIP6 모델 35개를 편이보정·상세화한 0.25° 일 자료 (기온·강수·습도·복사·풍속 9개 변수), 계정 없이 받기 |
| [ISIMIP3b](datasets/isimip3b.md) | 영향모델 입력용으로 W5E5에 맞춰 편이보정한 0.5° 일 자료 (CMIP6 모델 10개) |
| [CORDEX-CMIP6](datasets/cordex-cmip6.md) | 지역기후모델로 상세화한 대륙별 영역 자료 (동아시아 EAS 영역 포함) |
| [CMIP6](datasets/cmip6.md) — Copernicus CDS | 주요 변수 46개를 영역·기간 잘라 받기 (CDS 계정 필요) |
| [CMIP6](datasets/cmip6.md) — Pangeo 클라우드 사본 | 일부 핵심 자료를 Zarr로 바꿔 둔 클라우드 사본 (intake-esm으로 열기) |
