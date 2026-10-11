<p align="center">
  <a href="https://data4researchers.kr/">
    <img src="docs/assets/logo.svg" alt="기후데이터 길잡이 로고" width="120">
  </a>
</p>

<h1 align="center">기후데이터 길잡이</h1>

<p align="center">
  <b>대기·해양·해빙 연구자를 위한 기후자료 안내서</b><br>
  <a href="https://data4researchers.kr/">한국어</a> · <a href="https://data4researchers.kr/en/">English</a>
</p>

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.23300923"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.23300923.svg" alt="DOI 10.5281/zenodo.23300923"></a>
  <a href="https://creativecommons.org/licenses/by/4.0/"><img src="https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg" alt="CC BY 4.0"></a>
  <img src="https://img.shields.io/badge/datasets-63-1f6f8b.svg" alt="63 datasets">
</p>

---

## 기후데이터 길잡이

**👉 [data4researchers.kr](https://data4researchers.kr/)**

재분석자료나 위성자료를 쓰다 보면 이런 일이 생깁니다.

- 쓰던 자료가 어느 날 **갱신을 멈추거나**, 다운로드 서비스가 **이전**됩니다.
- 같은 "3시간 자료"인데 어떤 변수는 **순간값**, 어떤 변수는 **3시간 누적**입니다.
- 논문에 넣을 **DOI와 인용 문구**를 찾느라 제공 기관 사이트를 몇 번씩 뒤집니다.
- 새 버전으로 바꾸려는데 **이전 버전과 무엇이 달라졌는지** 한눈에 정리된 곳이 없습니다.

기후데이터 길잡이는 이런 정보를 **공식 출처에서 직접 확인해** 자료마다 한 페이지로 정리합니다. 자료를 보관하지 않고, 모든 항목은 공식 출처로 연결됩니다.

### 자료마다 정리하는 것

| | |
|---|---|
| 📥 **받는 방법** | 공식 제공처, 계정 필요 여부, Python 예시 코드 |
| 🗂️ **변수와 시간 특성** | 변수 이름·단위와 **순간값 · 평균 · 누적** 구분, 시간 표기 규칙 |
| 📐 **기간과 해상도** | 공식 문서의 원본 격자와 실제 제공 격자 |
| 📚 **논문용 레퍼런스** | 데이터셋 DOI, 기술 논문, BibTeX, 사사 작성 요령 |
| 📢 **중요 공지** | 제공 중단, 서비스 이전, 품질 문제, 버전 교체 — 원문 링크와 함께 |
| 🔁 **세대별 비교** | ERA-Interim → ERA5, JRA-55 → JRA-3Q처럼 바뀐 점과 바꿔 쓸 때 주의할 점 |

### 이런 기능이 있습니다

- **자료 비교** — 최대 4개 자료의 기간·해상도·상태·DOI를 한 표로, "강수"처럼 변수도 나란히 비교
- **중요 공지 알림 메일** — 원하는 자료와 공지 구분(중요·주의·안내)만 골라서 받기
- **엑셀로 저장** — 사이트의 모든 표를 화면에 보이는 그대로 .xlsx로
- **정보 오류 신고** — 페이지마다 버튼 하나로 운영자에게 전달
- **영어판** — [data4researchers.kr/en](https://data4researchers.kr/en/) (공식 영어 출처를 바탕으로 따로 작성)

### 수록 자료 (63개)

| 분야 | 분류 | 자료 |
|---|---|---|
| 대기 | 재분석 | ERA5, ERA6(공개 예정), ERA-Interim, JRA-55, JRA-3Q, MERRA-2, NCEP/NCAR R1, NCEP–DOE R2, CFSR/CFSv2, CORe, ERA-15, ERA-40, JRA-25, MERRA |
| | 지역 재분석 | CARRA2, CARRA |
| | 위성 관측 미동화 재분석 | 20CR v3, ERA-20C, CERA-20C, JRA-55C |
| | 육상 재분석 | ERA5-Land |
| | 강수 | GPCP, GPM IMERG, APHRODITE |
| | 기온 | HadCRUT5, GISTEMP, Berkeley Earth, CRU TS |
| | 복사 | CERES EBAF |
| 해양 | 재분석 | GLORYS12, ORAS5, ORAS6(공개 예정), ECCO v4, SODA4, SODA3, GODAS, TOPAZ4b |
| | 해수면온도 | OISST, ERSST v6, ERSST v5, COBE-SST2, COBE-SST3, HadISST, OSTIA, HadSST4, ESA CCI SST |
| | 수온·염분 | EN4, WOA23 |
| | 위성 | DUACS (해수면 고도) |
| | 모델 강제력 | JRA55-do |
| 해빙 | 재분석 | PIOMAS, GIOMAS, neXtSIM, TOPAZ4b |
| | 위성 | OSI SAF (해빙 농도), NOAA/NSIDC CDR, CryoSat-2, CS3SMOS, CS2SMOS, ESA CCI, ICESat-2 |
| | 해빙 이동 | Polar Pathfinder, OSI SAF (해빙 이동) |
| | 해빙 지수 | Sea Ice Index |

필요한 자료가 없다면 사이트의 **[데이터셋 제안](https://data4researchers.kr/suggest/)** 으로 알려주세요.

### 인용하기

연구에 도움이 되었다면 논문의 사사(Acknowledgements)에 아래 문장을 넣어주세요.

```text
Information on the datasets used in this study was compiled with the help of the Korean Climate Data Guide (Sim, 2026; https://doi.org/10.5281/zenodo.23300923).
```

<details>
<summary>BibTeX</summary>

```bibtex
@misc{sim2026kcdg,
  author    = {Sim, Ji-Han},
  title     = {Korean Climate Data Guide},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.23300923},
  url       = {https://doi.org/10.5281/zenodo.23300923}
}
```
</details>

### 문의 · 오류 신고

- 사이트 각 페이지 아래의 **정보 오류 신고** 버튼
- 메일: [data4researchers@gmail.com](mailto:data4researchers@gmail.com)

> 기후데이터 길잡이는 개인이 운영하는 비공식 프로젝트이며, 운영자의 소속 기관이나 자료 제공 기관의 공식 입장이 아닙니다. 논문·보고서에 쓰기 전에는 DOI·인용 형식·기간·변수 정의를 반드시 공식 출처에서 다시 확인해 주세요.

---

## Korean Climate Data Guide (English)

**👉 [data4researchers.kr/en](https://data4researchers.kr/en/)**

A guide to climate, ocean and sea-ice datasets for researchers. For each of **63 datasets** — ERA5, JRA-3Q, MERRA-2, CARRA2, GPCP, IMERG, HadCRUT5, OISST, ERSST, GLORYS12, ECCO, EN4, WOA23, DUACS, OSI SAF, NSIDC CDR, CryoSat-2, ICESat-2 and more — it brings together, from the official sources:

- **How to get the data** — providers, account requirements, example Python code
- **Variables and their time convention** — names, units, and whether each is **instantaneous, mean or accumulated**
- **Period and resolution** — the native grid and the grid you actually download
- **What to cite** — dataset DOIs, reference papers, BibTeX, acknowledgement wording
- **Notices** — end of production, service migrations, quality issues and version changes, with links to the original announcements
- **Generation changes** — what changed from ERA-Interim to ERA5, JRA-55 to JRA-3Q and so on, and what to watch when switching

Also: side-by-side comparison of up to four datasets, email alerts for the notices you choose, Excel export of every table, and an error-report button on every page. The English pages are written from the official English sources rather than translated from Korean.

**Cite:** please acknowledge the guide as *Sim, 2026; https://doi.org/10.5281/zenodo.23300923* (see the sentence and BibTeX above).

**Contact:** [data4researchers@gmail.com](mailto:data4researchers@gmail.com) · the *Report an error* button on any page.

> This is an unofficial project run by an individual and does not represent any employer or data provider. Always re-check DOIs, citation formats, periods and variable definitions against the official sources before using them in a paper.

---

<sub>콘텐츠 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · 코드 MIT · 각 자료의 이용 조건은 제공 기관의 약관을 따릅니다. · 사이트 운영·수정 방법은 [MAINTAINING.md](MAINTAINING.md)</sub>
