"""영어판(mkdocs.en.yml) 빌드 때 쓰는 화면 문구 번역표.

hooks/datasets.py 가 만드는 페이지·폼·메뉴의 한국어 화면 문구를 영어로 바꿉니다.
데이터셋 내용 자체는 data/datasets_en/*.yaml (공식 영어 출처 기반으로 작성)에서 옵니다.
새 화면 문구를 hooks/datasets.py 에 추가하면 여기에도 영어를 넣어주세요.
(영어판 빌드 뒤 scripts/check_en.py 로 남은 한국어를 찾을 수 있습니다)
"""

DOMAIN_LABEL = {"atmosphere": "Atmosphere", "ocean": "Ocean", "seaice": "Sea ice"}

GROUP = {
    "재분석": "Reanalyses",
    "지역 재분석": "Regional reanalyses",
    "위성 관측 미동화 재분석": "Reanalyses without satellite data",
    "육상 재분석": "Land reanalyses",
    "강수 자료": "Precipitation",
    "기온 자료": "Surface temperature",
    "복사 자료": "Radiation",
    "해수면온도 분석장": "Sea surface temperature analyses",
    "수온·염분 분석장": "Temperature & salinity analyses",
    "위성 관측 자료": "Satellite products",
    "모델 강제력": "Model forcing",
    "관측 기반 분석장": "Observation-based analyses",
    "해빙 이동": "Sea-ice drift",
    "해빙 지수": "Sea-ice indices",
}

DOMAIN_INTRO = {
    "atmosphere": "Atmospheric reanalyses (global, regional and land) and observation-based precipitation, surface temperature and radiation datasets. Older generations needed to reproduce published work or for comparison studies are included alongside current products.",
    "ocean": "Ocean reanalyses and state estimates, sea surface temperature analyses, 3-D temperature and salinity analyses, satellite sea level, and atmospheric forcing for ocean–sea-ice models.",
    "seaice": "Sea-ice concentration, thickness, volume and drift: model-based reanalyses, observation-based analyses, satellite products, drift vectors and extent/area indices.",
}

GROUP_INTRO = {
    "위성 관측 미동화 재분석": "Reanalyses that assimilate only conventional observations such as surface pressure and marine winds, without satellite data. Keeping the observing system stable reduces spurious jumps, which makes them suited to century-long and low-frequency studies.",
    "지역 재분석": "Reanalyses of a limited region on a finer grid than global reanalyses, with boundary conditions taken from a global reanalysis.",
    "육상 재분석": "Land-surface model reruns at higher resolution, driven by atmospheric reanalysis forcing. Used for soil moisture, snow and surface-flux studies.",
    "수온·염분 분석장": "Gridded 3-D temperature and salinity fields and climatologies built from in-situ profiles (Argo, CTD, XBT, …).",
    "해빙 이동": "Sea-ice motion (drift) vectors tracked from satellite imagery.",
    "해빙 지수": "Summary indices such as sea-ice extent and area computed from satellite sea-ice concentration.",
}

DOMAIN_TAG = {"대기": "Atmosphere", "해양": "Ocean", "해빙": "Sea ice", "육지": "Land", "극지": "Polar",
              "해양파랑": "Ocean waves", "원격탐사": "Remote sensing", "빙상": "Ice sheets", "수문": "Hydrology", "에어로졸": "Aerosols"}

TEMPORAL = {"30분": "30 min", "1시간": "1 h", "3시간": "3 h", "6시간": "6 h", "1일": "1 day",
            "5일": "5 days", "7일": "7 days", "1개월": "1 month", "1년": "1 year"}

STATUS = {"active": "Available", "delayed": "Update delayed", "deprecated": "Being replaced",
          "ended": "Discontinued", "upcoming": "Upcoming"}
STATUS_TITLE = {"active": "Current status", "delayed": "Update delayed", "deprecated": "Being replaced",
                "ended": "No longer updated", "upcoming": "Not yet released"}
CATEGORY = {"reanalysis": "Reanalysis", "analysis": "Observation-based analysis", "satellite": "Satellite product",
            "forcing": "Model forcing", "in_situ": "In-situ observations", "model_output": "Model output",
            "model_source": "Model source code"}
LEVEL = {"critical": "Critical", "warning": "Warning", "info": "Info"}
KIND = {"instant": "instantaneous", "mean": "mean", "accum": "accumulated", "max": "maximum",
        "min": "minimum", "static": "static"}

RES_NOTE = [
    "**Provided resolution** is the grid spacing you download from the main provider, not the model's native resolution. The same dataset can come on different grids from different providers or products, so always check the grid of the file you actually downloaded.",
    "km values are **approximations at the equator** (1° ≈ 111 km). Longitude spacing shrinks with cos(latitude): at 60° it is half (0.25° ≈ 14 km), so \"28 km\" is not 28 km everywhere.",
    "Gaussian grids have uneven latitude spacing, and ocean model grids (tripolar, curvilinear) vary from place to place. Grids with different latitude and longitude spacing are written as `0.5°×0.625°` (lat × lon).",
    "Polar-stereographic and EASE2 grids of sea-ice satellite products are defined in km; the degree value in brackets is a simple conversion. The NSIDC polar stereographic grid matches its nominal spacing only at 70° latitude.",
    "Grid spacing is **not the size of the smallest feature actually resolved (effective resolution).** Features are typically resolved only at several times the grid spacing, and interpolating to a finer grid adds no information.",
    "Temporal resolution is the **shortest interval provided**. Intervals and whether a value is instantaneous, mean or accumulated differ between variables — see 'Available variables' on each dataset page.",
]
RES_NOTE_TITLE = "About resolution values — please read"

DETAIL_RES_NOTE = [
    "Horizontal resolution lists both the **native model grid** and the **grid you download**, as given in the official documentation. The same dataset can come on different grids from different providers or products, so check the grid of your downloaded file.",
    "Grid spacing is **not the effective resolution.** A provided grid that is finer than the native one carries no extra information.",
    "Intervals and whether a value is instantaneous, mean or accumulated differ between variables — see 'Available variables' below.",
    "The 'provided resolution' in lists and the comparison table is a simplified km/degree value for quick comparison. Use this page for exact values.",
]
DETAIL_RES_NOTE_TITLE = "How to read the resolution"

DISCLAIMER = (
    "The Korean Climate Data Guide is an unofficial project run by an individual and does not represent the views of the "
    "maintainer's employer or of any data provider. All information reflects the date it was checked and may change — always "
    "re-check DOIs, citation formats, periods and variable definitions against the official sources before using them in a paper or report."
)

# 화면 문구 — 긴 것부터 차례로 바꿉니다 (부분 문자열이 먼저 바뀌는 일을 막기 위해 길이순 정렬)
UI = {
    # 데이터셋 페이지
    "중요 공지 알림 받기": "Get notice alerts",
    "다른 자료와 비교": "Compare with other datasets",
    "정보 오류 신고": "Report an error",
    "후속 자료:": "Successor:",
    "교차 수록:": "also listed in:",
    "한눈에 보기": "At a glance",
    "| 항목 | 내용 |": "| Item | Details |",
    "| 분류 |": "| Section |",
    "| 항목 | ": "| Aspect | ",
    "| 종류 |": "| Type |",
    "| 분야 |": "| Domains |",
    "| 제공 기관 |": "| Provider |",
    "| 기간 |": "| Period |",
    "| 수평 해상도 |": "| Horizontal resolution |",
    "| 연직 해상도 |": "| Vertical resolution |",
    "| 시간 해상도 |": "| Temporal resolution |",
    "| 갱신 주기 |": "| Update frequency |",
    "| 라이선스 |": "| Licence |",
    "| 계정 필요 |": "| Account required |",
    "*기간 참고:*": "*Note on period:*",
    "## 개요": "## Overview",
    "이전 자료와 무엇이 달라졌나": "What changed from the previous dataset",
    "비교 보기": "see comparison",
    "후속 자료와 무엇이 달라졌나": "What changes with the successor",
    "*전환 시점:*": "*Transition:*",
    "바꿔 쓸 때 주의할 점": "Things to watch when switching",
    "출처:": "Sources:",
    "두 자료를 비교표로 나란히 보기": "Compare the two side by side",
    "## 활용 가능한 변수": "## Available variables",
    "아직 공개 전이라 변수 목록이 확정되지 않았습니다. 공개되면 정리하겠습니다.": "Not released yet, so the variable list is not final. It will be added after release.",
    "시간 표기 규칙 — 순간값인가, 평균인가, 누적인가": "Time-stamp convention — instantaneous, mean or accumulated?",
    "근거:": "Source:",
    "공식 문서": "official documentation",
    "— 순간값: 표시 시각의 값 · 평균/누적/최대/최소: 표시된 구간 동안의 값 · 고정값: 시간에 따라 변하지 않음":
        "— instantaneous: value at the time stamp · mean/accumulated/maximum/minimum: over the indicated interval · static: does not change with time",
    "전체 변수 목록은": "The full variable list is in the",
    "에서 확인하세요.": ".",
    "## 받는 방법": "## How to get the data",
    "### 예시 코드": "### Example code",
    "## 실전 팁": "## Practical tips",
    "## 공지 및 변경 이력": "## Notices and change history",
    "원문 보기": "Read the original",
    "등록된 공지가 없습니다.": "No notices yet.",
    "## 논문에 넣을 레퍼런스": "## References for your paper",
    "논문에 쓰기 전에 꼭 다시 확인하세요": "Double-check before using in a paper",
    "아래 인용 정보는 운영자가 정리한 것으로 오류가 있을 수 있습니다. DOI, 저자, 연도, 접근 날짜 표기 방식은 제공 기관의 공식 데이터셋 페이지와 학술지 투고 규정에서 **반드시 더블체크**한 뒤 사용하세요.":
        "The citations below were compiled by the maintainer and may contain errors. **Always double-check** DOIs, authors, years and access-date formats against the provider's official dataset page and your journal's guidelines.",
    "### 데이터셋 인용": "### Dataset citation",
    "### 논문 인용": "### Reference papers",
    "### 사사(Acknowledgements) 작성": "### Acknowledgements",
    "BibTeX 보기": "Show BibTeX",
    "이 정리가 도움이 되셨다면 기후데이터 길잡이도 인용해 주세요": "If this page helped, please acknowledge the Korean Climate Data Guide",
    "논문의 사사(Acknowledgements)에 아래 문장을 넣어주세요.": "Please add the sentence below to the Acknowledgements of your paper.",
    "(참고문헌 관리 프로그램용)": "(for reference managers)",
    "## 참고 링크": "## Links",
    # 목록
    "# 전체 데이터셋 목록": "# All datasets",
    "개 자료를 공식 출처에서 직접 확인해 정리했습니다. 이후 바뀌었을 수 있으니 쓰기 전에 공식 출처를 다시 확인하세요.":
        " datasets, each checked against its official sources. Things may have changed since, so re-check the official source before use.",
    "모두 ": "",
    "표의 열 이름을 누르면 정렬되고, 왼쪽 칸을 2개 이상 체크하면 **바로 비교**할 수 있습니다. 해상도는 쉽게 비교하도록 **주 제공처에서 받는 격자** 기준 대표 값만 적었고(시간 해상도는 가장 짧은 제공 간격), 세부 내용은 각 자료 페이지에 있습니다. ↔ 표시는 다른 분야에도 함께 실린 자료입니다.":
        "Click a column header to sort, and tick two or more boxes on the left to **compare** them directly. For easy comparison only a representative value for the **grid provided by the main provider** is shown (temporal resolution = shortest interval provided); details are on each dataset page. ↔ marks datasets that are also listed in another section.",
    "표의 왼쪽 칸을 2개 이상 체크하면 바로 비교할 수 있고, 열 이름을 누르면 정렬됩니다.":
        "Tick two or more boxes on the left to compare them; click a column header to sort.",
    "↔ 다른 분야 페이지에도 함께 실린 자료입니다.": "↔ Also listed in another section.",
    "다른 분야에도 실린 자료": "Also listed in another section",
    "<th>비교</th>": "<th>Compare</th>",
    "<th>자료</th>": "<th>Dataset</th>",
    "<th>종류</th>": "<th>Type</th>",
    "<th>기간</th>": "<th>Period</th>",
    "주 제공처에서 받는 격자 간격 (km는 적도 기준 근사)": "Grid spacing provided by the main provider (km approximate at the equator)",
    ">제공 해상도</th>": ">Provided resolution</th>",
    "가장 짧은 제공 간격 (세부는 각 자료 페이지)": "Shortest interval provided (details on each dataset page)",
    ">시간 간격</th>": ">Interval</th>",
    "<th>상태</th>": "<th>Status</th>",
    "개 자료</span>": " datasets</span>",
    "개</span>": "</span>",
    # 공지
    "# 중요 공지": "# Notices",
    "데이터 제공 중단, 서비스 이전, 품질 문제처럼 **분석에 영향을 주는 공지**를 최신순으로 모았습니다.":
        "**Notices that can affect your analysis** — end of production, service migrations, quality issues — newest first.",
    "각 항목의 링크는 원문 공지로 연결됩니다. 새 공지를 메일로 받고 싶다면 [중요 공지 알림 신청](subscribe.md)을 이용하세요.":
        "Each link goes to the original announcement. To get new notices by email, sign up for [notice alerts](subscribe.md).",
    ">데이터셋<select": ">Dataset<select",
    "전체 데이터셋": "All datasets",
    '<span class="nf-label">구분</span>': '<span class="nf-label">Level</span>',
    "<th>날짜</th>": "<th>Date</th>",
    "<th>데이터셋</th>": "<th>Dataset</th>",
    "<th>구분</th>": "<th>Level</th>",
    "<th>내용</th>": "<th>Notice</th>",
    "조건에 맞는 공지가 없습니다.": "No notices match the filter.",
    "| 날짜 | 데이터셋 | 구분 | 내용 |": "| Date | Dataset | Level | Notice |",
    # 세대별 비교
    "# 세대별 비교": "# Generation changes",
    "재분석자료와 관측 자료는 세대가 바뀌거나 새 버전이 나오면 기간, 해상도, 관측 입력, 변수 이름이 함께 바뀝니다.":
        "When a reanalysis or observational dataset moves to a new generation or version, its period, resolution, observational input and variable names often change together.",
    "아래 표에서 **항목을 누르면** 무엇이 달라졌는지와 바꿔 쓸 때 주의할 점이 표 아래에 나타납니다.":
        "**Click a row** in the table below to see what changed and what to watch out for when switching.",
    "자료 계보": "Dataset lineages",
    " (예정)</span>": " (planned)</span>",
    ">예정</span>": ">Planned</span>",
    ">완료</span>": ">Done</span>",
    "<th>세대 변화</th>": "<th>Change</th>",
    "<th>분야</th>": "<th>Domain</th>",
    "<th>전환 시점</th>": "<th>When</th>",
    "표에서 비교할 항목을 누르세요.": "Click a row to show the comparison.",
    "페이지에서 보기 →": "page →",
    # 비교
    "— 선택 —": "— Select —",
    "변수 찾기": "Find a variable",
    "— 고른 자료들에서 같은 종류의 변수를 나란히 봅니다 (한국어 이름이나 변수명)": "— shows matching variables side by side (English name or short name)",
    "예) 강수, tp, prate, sea ice": "e.g. precipitation, tp, prate, sea ice",
    "위에서 비교할 자료를 2개 이상 골라주세요. 고른 내용은 주소에 저장되어 그대로 공유할 수 있습니다.":
        "Choose two or more datasets above. Your selection is kept in the page address, so you can share the link.",
    # 폼 — 알림 신청
    "메일 알림은 준비 중입니다": "Email alerts are not available yet",
    "1. 알림 받을 데이터셋": "1. Datasets",
    "2. 받을 공지 구분": "2. Notice levels",
    "3. 받을 이메일": "3. Your email",
    "<strong>전체</strong>": "<strong>All</strong>",
    "— 앞으로 추가되는 데이터셋 포함": "— including datasets added later",
    "— 제공 중단, 서비스 종료처럼 분석에 바로 영향을 주는 공지": "— end of production or service shutdowns that directly affect analyses",
    "— 품질 문제, 재처리, 종료 예고": "— quality issues, reprocessing, announced end dates",
    "— 주소 이전, 라이선스 변경, 새 자료 공개": "— address changes, licence changes, new releases",
    "웹사이트 (비워 두세요)": "Website (leave empty)",
    "개인정보 수집·이용에 동의합니다 (필수)": "I agree to the collection and use of my personal information (required)",
    "처리방침 보기 ↗": "Privacy policy ↗",
    ">알림 신청</button>": ">Subscribe</button>",
    "신청하면 <strong>확인 메일</strong>이 갑니다. 메일의 <em>신청 확인하기</em>를 눌러야 등록이 끝납니다. 받은편지함에 없으면 <strong>스팸함</strong>을 확인해 주세요. 알림 메일마다 아래쪽에 수신 거부 링크가 있어 언제든 해지할 수 있습니다.":
        "You will receive a <strong>confirmation email</strong>; your subscription is active only after you click <em>Confirm subscription</em>. If it is not in your inbox, check your <strong>spam folder</strong>. Every alert has an unsubscribe link at the bottom.",
    # 폼 — 제안
    "제안 접수는 준비 중입니다": "Suggestions are not open yet",
    "그동안은 data4researchers@gmail.com 으로 메일을 보내주세요.": "Meanwhile, please email data4researchers@gmail.com.",
    "이미 있는 데이터셋 ": "Datasets already listed: ",
    "개 보기</summary>": "</summary>",
    "<legend>데이터셋 정보</legend>": "<legend>Dataset</legend>",
    "데이터셋 이름 <em>필수</em>": "Dataset name <em>required</em>",
    "예) ERA5-Land, SMAP 토양수분": "e.g. ERA5-Land, SMAP soil moisture",
    '<label class="field">종류<select': '<label class="field">Type<select',
    "공식 페이지 주소 <em>필수</em>": "Official page URL <em>required</em>",
    "<legend>왜 필요한가요</legend>": "<legend>Why it is needed</legend>",
    "어떤 연구에 쓰시나요?": "What do you use it for?",
    "예) 북극 해빙 변화와 대기 순환 연구에 ERA5와 비교용으로 사용": "e.g. comparing with ERA5 in a study of Arctic sea-ice loss and atmospheric circulation",
    "알고 계신 중단·변경 소식 (선택)": "Any news about discontinuation or changes (optional)",
    "예) 내년부터 새 버전으로 전환 예정이라고 들었어요": "e.g. I heard it moves to a new version next year",
    "제안하신 분 (선택)": "Your name (optional)",
    "이름·소속, 답장이 필요하면 이메일도 적어주세요": "Name and affiliation; add an email if you would like a reply",
    ">제안 보내기</button>": ">Send suggestion</button>",
    "제안은 운영자에게만 전달되며 공개되지 않습니다.": "Suggestions go only to the maintainer and are not published.",
    # 메뉴
    "개요": "Overview",
    # 짧은 값
    "~ 현재": "~ present",
}

YES_NO = {"예": "Yes", "아니오": "No"}
