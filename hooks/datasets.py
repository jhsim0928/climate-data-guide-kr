"""MkDocs hook: data/datasets/*.yaml 파일로 사이트의 데이터 관련 페이지를 모두 자동 생성합니다.

- 각 YAML → datasets/<id>.md (가상 파일, 디스크에 쓰지 않음)
- 분야별 소개 → domains/<atmosphere|ocean|seaice>.md
- 전체 목록 → datasets/index.md, 중요 공지 → notices.md
- 위쪽 메뉴(대기·해양·해빙)도 YAML의 domain/group/order 값으로 자동 구성
- 본문의 <!-- DOMAIN_SUMMARY -->, <!-- RECENT_NOTICES -->, <!-- SUBSCRIBE_FORM -->, <!-- SUGGEST_FORM --> 자리를 채움

YAML에 필수 항목이 빠졌거나 값이 잘못되면 빌드가 실패합니다.
(자동화가 만든 PR도 이 검증을 통과해야 머지할 수 있게 하기 위함)
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
import html
import json
from urllib.parse import quote, urlencode, urlparse

import yaml
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "datasets"
DATA_DIR_EN = ROOT / "data" / "datasets_en"  # 영어판: 공식 영어 출처를 바탕으로 쓴 같은 구조의 YAML
KO_DOCS = ROOT / "docs"  # 영어판 빌드 때 그림·스크립트·스타일은 한국어판 docs/ 것을 그대로 씀

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("cdg_i18n_en", Path(__file__).resolve().parent / "i18n_en.py")
EN = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(EN)
_lang = "ko"  # on_config 에서 theme.language 로 정함 (ko / en)
_UI_SORTED = sorted(EN.UI.items(), key=lambda kv: -len(kv[0]))


def is_en() -> bool:
    return _lang == "en"


def loc(text: str) -> str:
    """영어판일 때 화면 문구(한국어)를 영어로 바꿉니다. 한국어판에서는 그대로."""
    if not is_en():
        return text
    for ko, en in _UI_SORTED:
        text = text.replace(ko, en)
    return text


def g_label(g: str) -> str:
    return EN.GROUP.get(g, g) if is_en() else g


def t_label(t: str) -> str:
    return EN.TEMPORAL.get(t, t) if is_en() else t


def cat_label(c: str) -> str:
    return EN.CATEGORY[c] if is_en() else CATEGORY[c]


def level_label(lv: str) -> str:
    return EN.LEVEL[lv] if is_en() else LEVEL[lv][0]


def kind_label(k: str) -> str:
    return EN.KIND[k] if is_en() else KIND[k]


def tags_label(tags) -> str:
    return ", ".join(EN.DOMAIN_TAG.get(x, x) if is_en() else x for x in (tags or []))


def yes_no(v: bool) -> str:
    return ("Yes" if v else "No") if is_en() else ("예" if v else "아니오")


def domain_intro(dom: str) -> str:
    return EN.DOMAIN_INTRO[dom] if is_en() else DOMAIN_INTRO[dom]


def group_intro(g: str):
    return (EN.GROUP_INTRO if is_en() else GROUP_INTRO).get(g)


def disclaimer() -> str:
    return EN.DISCLAIMER if is_en() else DISCLAIMER

# 위쪽 메뉴 탭(분야)과 그 안의 소분류 — 순서대로 표시됩니다
DOMAINS = {
    "atmosphere": ("대기", ["재분석", "지역 재분석", "위성 관측 미동화 재분석", "육상 재분석", "강수 자료", "기온 자료", "복사 자료"]),
    "ocean": ("해양", ["재분석", "해수면온도 분석장", "수온·염분 분석장", "위성 관측 자료", "모델 강제력"]),
    "seaice": ("해빙", ["재분석", "관측 기반 분석장", "위성 관측 자료", "해빙 이동", "해빙 지수"]),
}
DOMAIN_INTRO = {
    "atmosphere": "대기 재분석(전지구·지역·육상)과 관측 기반 강수·기온·복사 자료입니다. 현역 자료와 함께, 옛 논문 재현이나 비교 연구에 필요한 이전 세대 자료도 정리했습니다.",
    "ocean": "해양 재분석·상태 추정, 해수면온도(SST) 분석장, 3차원 수온·염분 분석장, 위성 해수면 고도, 해양·해빙 모델 구동용 대기 강제력 자료입니다.",
    "seaice": "해빙 농도·두께·부피·이동 자료입니다. 모델 기반 재분석, 관측 기반 분석장, 위성 관측 자료, 해빙 이동 벡터, 해빙 면적·범위 지수로 나눠 정리했습니다.",
}
# 소분류 아래에 붙는 한 줄 설명 (없으면 생략)
GROUP_INTRO = {
    "위성 관측 미동화 재분석": "위성 관측을 쓰지 않고 지표기압·해상풍 같은 전통 관측만 동화한 재분석입니다. "
                       "관측 체계 변화의 영향을 줄여 20세기 전체 또는 장기 변동 연구에 씁니다.",
    "지역 재분석": "특정 지역만 전지구 재분석보다 촘촘한 격자로 다시 분석한 자료입니다. 경계 조건은 전지구 재분석에서 받습니다.",
    "육상 재분석": "대기 재분석의 강제력으로 지면 모델만 더 촘촘하게 다시 돌린 자료입니다. 토양수분·눈·지표 플럭스 연구에 씁니다.",
    "수온·염분 분석장": "현장 관측(Argo·CTD·XBT 등)으로 만든 3차원 수온·염분 격자 자료와 기후값입니다.",
    "해빙 이동": "위성 영상에서 추적한 해빙 이동 벡터(표류 속도) 자료입니다.",
    "해빙 지수": "위성 해빙 농도에서 계산한 해빙 면적·범위 같은 요약 지수입니다.",
}
NAV_PLACEHOLDER = "__DATA_SECTIONS__"

STATUS = {
    "active": ("정상 제공", "status-active"),
    "delayed": ("갱신 지연", "status-delayed"),
    "deprecated": ("지원 축소·대체 예정", "status-deprecated"),
    "ended": ("갱신 종료", "status-ended"),
    "upcoming": ("공개 예정", "status-upcoming"),
}
CATEGORY = {
    "reanalysis": "재분석자료",
    "analysis": "관측 기반 분석장",
    "satellite": "위성자료",
    "forcing": "모델 강제력",
    "in_situ": "현장관측",
    "model_output": "모델 산출물",
    "model_source": "모델 소스코드",
}
LEVEL = {
    "critical": ("중요", "danger"),
    "warning": ("주의", "warning"),
    "info": ("안내", "info"),
}
REQUIRED = [
    "id", "name", "category", "domain", "group", "provider", "status", "period",
    "summary", "access", "variables", "citations", "last_verified",
]
DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")

# 자료 간 비교를 쉽게 하기 위한 대표 해상도 표기 (세부 내용은 각 데이터셋 페이지에)
SPATIAL_SHORT_RE = re.compile(r"^\d+(\.\d+)? km \(\d+(\.\d+)?°(×\d+(\.\d+)?°)?\)$")
TEMPORAL_SHORT = ["30분", "1시간", "3시간", "6시간", "1일", "5일", "7일", "1개월", "1년"]
TEMPORAL_HOURS = {"30분": 0.5, "1시간": 1, "3시간": 3, "6시간": 6, "1일": 24, "5일": 120, "7일": 168, "1개월": 720, "1년": 8760}

# 해상도 표기 주의 — 목록·비교·데이터셋 페이지에 접힌 상자로 표시
RES_NOTE = [
    "**제공 해상도**는 모델 원본 해상도가 아니라, 주 제공처에서 기본으로 내려받는 격자 간격입니다. 같은 자료도 제공처·제품에 따라 다른 격자로 제공될 수 있으니, 실제로 받은 파일의 격자를 꼭 확인하세요.",
    "km 값은 **적도 기준 근사값**(1° ≈ 111 km)입니다. 경도 방향 간격은 위도가 높아질수록 cos(위도)만큼 줄어, 위도 60°에서는 절반(0.25° ≈ 14 km)이 됩니다. 그래서 \"28 km\"는 어디서나 정확히 28 km가 아닙니다.",
    "가우시안 격자는 위도 간격이 일정하지 않고, 해양 모델 격자(삼극·곡선 격자)는 지역마다 간격이 다릅니다. 위경도 간격이 다른 격자는 `0.5°×0.625°`(위도×경도)처럼 적었습니다.",
    "해빙 위성자료의 극 평사도법·EASE2 격자는 km가 기준이고, 괄호 속 각도는 단순 환산값입니다. NSIDC 극 평사도법은 위도 70°에서만 표기 간격과 같고, 다른 위도에서는 실제 간격이 조금씩 다릅니다.",
    "격자 간격이 곧 **실제로 구분되는 현상의 크기(실효 해상도)는 아닙니다.** 보통 격자 간격의 몇 배 크기부터 제대로 표현되며, 원본보다 촘촘하게 보간한 격자는 정보가 늘지 않습니다.",
    "시간 해상도는 **가장 짧은 제공 간격**입니다. 변수마다 간격과 순간값·평균·누적 여부가 다를 수 있으니 각 자료 페이지의 '활용 가능한 변수'를 확인하세요.",
]


def res_note(collapsed: bool = True) -> list[str]:
    if is_en():
        return [f'??? warning "{EN.RES_NOTE_TITLE}"', ""] + [f"    - {x}" for x in EN.RES_NOTE] + [""]
    head = '??? warning "해상도 표기 주의 — 꼭 읽어주세요"' if collapsed else '!!! warning "해상도 표기 주의"'
    return [head, ""] + [f"    - {x}" for x in RES_NOTE] + [""]


# 데이터셋 상세 페이지용 — 상세 페이지는 공식 격자 정보를 그대로 적고, 단순 환산값(km·°)은 쓰지 않음
DETAIL_RES_NOTE = [
    "수평 해상도에는 공식 문서의 **모델 원본 격자**와 실제로 내려받는 **제공 격자**를 함께 적었습니다. 같은 자료도 제공처·제품에 따라 격자가 다를 수 있으니, 받은 파일의 격자를 꼭 확인하세요.",
    "격자 간격이 곧 **실제로 구분되는 현상의 크기(실효 해상도)는 아닙니다.** 원본보다 촘촘하게 보간한 제공 격자는 정보가 늘지 않습니다.",
    "시간 간격과 순간값·평균·누적 여부는 변수마다 다를 수 있으니 아래 '활용 가능한 변수'를 확인하세요.",
    "목록·비교표의 '제공 해상도'는 여러 자료를 한눈에 비교하려고 km·° 대표값으로 단순화한 것입니다. 정확한 값은 이 페이지를 기준으로 하세요.",
]


def detail_res_note() -> list[str]:
    if is_en():
        return [f'??? note "{EN.DETAIL_RES_NOTE_TITLE}"', ""] + [f"    - {x}" for x in EN.DETAIL_RES_NOTE] + [""]
    return ['??? note "해상도 읽는 법"', ""] + [f"    - {x}" for x in DETAIL_RES_NOTE] + [""]


# 변수의 시간 특성 — 3시간 자료라도 순간값인지, 3시간 평균인지, 누적인지 구분하기 위함
KIND = {
    "instant": "순간값",
    "mean": "평균",
    "accum": "누적",
    "max": "최대",
    "min": "최소",
    "static": "고정값",
}
# 모든 변수에 시간 특성을 반드시 적도록 검사 (True면 빠진 항목이 있을 때 빌드 실패)
REQUIRE_KIND = os.environ.get("CDG_ALLOW_MISSING_KIND") != "1"


def norm_item(it, group: dict) -> dict:
    """변수 항목은 문자열 또는 {text, kind, period, note}. 그룹의 kind/period를 기본값으로 씁니다."""
    if isinstance(it, str):
        it = {"text": it}
    return {
        "text": str(it.get("text") or ""),
        "kind": it.get("kind") or group.get("kind"),
        "period": it.get("period") or group.get("period"),
        "note": it.get("note"),
    }
PERIOD_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

_datasets: list[dict] = []
_ko_datasets: list[dict] = []
_site_url = ""

# 모든 페이지 하단과 소개·인용 페이지에 쓰이는 면책 문구
DISCLAIMER = (
    "기후데이터 길잡이는 개인이 운영하는 비공식 프로젝트이며, 운영자의 소속 기관이나 자료 제공 기관의 공식 입장이 아닙니다. "
    "모든 정보는 확인 시점 기준이며 바뀔 수 있으니, 논문·보고서에 쓰기 전에 DOI·인용 형식·기간·변수 정의를 반드시 공식 출처에서 다시 확인해 주세요."
)


def site_page_url(d: dict) -> str:
    return f"{_site_url}datasets/{d['id']}/"


# ── 유틸 ────────────────────────────────────────────────────
def nt(text: str) -> str:
    """번역되면 안 되는 고유명사(데이터셋 이름 등)를 감쌉니다."""
    return f'<span class="notranslate" translate="no">{text}</span>'


def badge(status: str) -> str:
    label, cls = STATUS[status]
    if is_en():
        label = EN.STATUS[status]
    return f'<span class="status-badge {cls}">{label}</span>'


def doi_link(doi: str) -> str:
    return f'[{nt(doi)}](https://doi.org/{doi})'


def oneline(text: str) -> str:
    return " ".join(str(text).split())


def period_text(p: dict) -> str:
    end = ("present" if is_en() else "현재") if str(p.get("end")) == "present" else p.get("end")
    return f"{p['start']} ~ {end}"


def domain_label(key: str) -> str:
    return EN.DOMAIN_LABEL[key] if is_en() else DOMAINS[key][0]


# ── 검증 ────────────────────────────────────────────────────
def validate(d: dict, src: Path) -> None:
    if not isinstance(d, dict):
        raise PluginError(f"{src.name}: YAML 내용을 읽을 수 없어요 (들여쓰기·콜론을 확인하세요)")
    errors = [f"필수 항목 누락: {k}" for k in REQUIRED if k not in d]
    if d.get("id") and d["id"] != src.stem:
        errors.append(f"id({d['id']})와 파일명({src.stem})이 달라요")
    if d.get("status") not in STATUS:
        errors.append(f"status는 {list(STATUS)} 중 하나여야 해요")
    if d.get("category") not in CATEGORY:
        errors.append(f"category는 {list(CATEGORY)} 중 하나여야 해요")
    dom = d.get("domain")
    if dom not in DOMAINS:
        errors.append(f"domain은 {list(DOMAINS)} 중 하나여야 해요")
    elif d.get("group") not in DOMAINS[dom][1]:
        errors.append(f"{dom}의 group은 {DOMAINS[dom][1]} 중 하나여야 해요")
    for i, x in enumerate(d.get("also_in") or []):
        if x.get("domain") not in DOMAINS or x.get("group") not in DOMAINS[x["domain"]][1]:
            errors.append(f"also_in[{i}]의 domain/group 값이 올바르지 않아요")
    p = d.get("period") or {}
    if not PERIOD_RE.match(str(p.get("start", ""))):
        errors.append('period.start 형식은 "YYYY", "YYYY-MM" 또는 "YYYY-MM-DD"')
    if str(p.get("end")) != "present" and not PERIOD_RE.match(str(p.get("end", ""))):
        errors.append('period.end는 present 또는 날짜 형식')
    v = d.get("variables") or {}
    upcoming = d.get("status") == "upcoming"  # 공개 전 자료는 변수·시간 규칙이 확정 전일 수 있음
    if upcoming and not v.get("groups"):
        pass
    elif not v.get("groups") or not all(g.get("name") and g.get("items") for g in v["groups"]):
        errors.append("variables.groups에 name과 items가 있는 그룹을 하나 이상 적어주세요")
    for gi, g in enumerate(v.get("groups") or []):
        if g.get("kind") and g["kind"] not in KIND:
            errors.append(f"variables.groups[{gi}].kind는 {list(KIND)} 중 하나")
        for ii, it in enumerate(g.get("items") or []):
            it = norm_item(it, g)
            if not it["text"]:
                errors.append(f"variables.groups[{gi}].items[{ii}]에 text가 없어요")
            if it["kind"] and it["kind"] not in KIND:
                errors.append(f"variables.groups[{gi}].items[{ii}].kind는 {list(KIND)} 중 하나")
            if REQUIRE_KIND and not it["kind"]:
                errors.append(f"variables '{g.get('name')}'의 '{it['text'][:30]}'에 시간 특성(kind)이 없어요")
    if REQUIRE_KIND and not upcoming and not (d.get("time_convention") or {}).get("summary"):
        errors.append("time_convention.summary(시간 표기 규칙 요약)가 없어요")
    r = d.get("resolution") or {}
    if not SPATIAL_SHORT_RE.match(str(r.get("spatial_short", ""))):
        errors.append('resolution.spatial_short는 "28 km (0.25°)" 또는 "56 km (0.5°×0.625°)" 형식으로 적어주세요')
    if r.get("temporal_short") not in TEMPORAL_SHORT:
        errors.append(f"resolution.temporal_short는 {TEMPORAL_SHORT} 중 하나")
    if not DATE_RE.match(str(d.get("last_verified", ""))):
        errors.append("last_verified 형식은 YYYY-MM-DD")
    if d.get("status") == "ended" and not d.get("successor"):
        errors.append("status가 ended이면 successor(후속 자료)를 적어주세요 (없다면 name: 없음)")
    for i, n in enumerate(d.get("notices") or []):
        if not DATE_RE.match(str(n.get("date", ""))):
            errors.append(f"notices[{i}].date 형식은 YYYY-MM 또는 YYYY-MM-DD")
        if n.get("level") not in LEVEL:
            errors.append(f"notices[{i}].level은 {list(LEVEL)} 중 하나")
        if not n.get("source"):
            errors.append(f"notices[{i}]에 출처(source) URL이 없어요")
    for key in ("tips",):
        for i, x in enumerate(d.get(key) or []):
            if not isinstance(x, str):
                errors.append(f"{key}[{i}]가 문장이 아니라 다른 형식으로 읽혀요 — '예: ' 같은 콜론이 있으면 전체를 따옴표로 감싸세요")
    for i, t in enumerate(d.get("transitions") or []):
        for j, x in enumerate(t.get("impacts") or []):
            if not isinstance(x, str):
                errors.append(f"transitions[{i}].impacts[{j}]가 문장이 아니에요 — 따옴표로 감싸세요")
    for i, a in enumerate(d.get("access") or []):
        if not a.get("url"):
            errors.append(f"access[{i}]에 url이 없어요")
    cit = d.get("citations") or {}
    if not (cit.get("dataset") or cit.get("papers")):
        errors.append("citations에 dataset 또는 papers 중 하나는 있어야 해요")
    for i, t in enumerate(d.get("transitions") or []):
        for k in ("from", "to", "status", "summary", "changes", "sources"):
            if not t.get(k):
                errors.append(f"transitions[{i}]에 {k}가 없어요")
        if t.get("status") not in ("completed", "planned"):
            errors.append(f"transitions[{i}].status는 completed 또는 planned")
        for j, c in enumerate(t.get("changes") or []):
            if not all(c.get(k) for k in ("aspect", "before", "after")):
                errors.append(f"transitions[{i}].changes[{j}]에 aspect·before·after가 모두 필요해요")
        if not all(s.get("url") for s in t.get("sources") or []):
            errors.append(f"transitions[{i}].sources 각 항목에 url이 필요해요")
    if errors:
        raise PluginError(f"{src.name} 검증 실패:\n  - " + "\n  - ".join(errors))


# 표·메뉴 기본 순서 (같은 분류 안에서):
#   1) 현역 자료(정상·지연·대체 예정·공개 예정)를 먼저, 제공 기관별로 묶음
#      — 기관 순서는 그 기관 자료 중 가장 작은 order, 기관 안에서는 order 순
#   2) 갱신 종료 자료는 아래에, 종료 시점이 최근인 것부터
ORG_RULES = [  # (provider에 들어 있는 말, 기관) — provider 글에서 가장 앞에 나오는 기관을 씀(생산 기관이 보통 맨 앞)
    ("NERSC", "NERSC"), ("AWI", "AWI"), ("Alfred Wegener", "AWI"), ("EUMETSAT", "EUMETSAT"),
    ("ECMWF", "ECMWF"), ("Copernicus Climate Change", "ECMWF"), ("JMA", "JMA"), ("Japan Meteorological", "JMA"),
    ("NASA", "NASA"), ("NOAA", "NOAA"), ("Met Office", "Met Office"), ("Copernicus Marine", "CMEMS"),
    ("Mercator", "CMEMS"), ("ESA", "ESA"), ("Maryland", "UMD"), ("Washington", "UW"),
    ("East Anglia", "UEA"), ("Berkeley Earth", "Berkeley Earth"), ("APHRODITE", "APHRODITE"),
]


def org_of(d: dict) -> str:
    prov = str(d.get("provider") or "")
    hits = [(prov.find(key), org) for key, org in ORG_RULES if key in prov]
    if hits:
        return min(hits)[1]
    return prov.split()[0] if prov else d["id"]


def order_in_group(items: list, ds=lambda x: x) -> list:
    """같은 분류(표 하나)에 들어갈 항목들을 위 규칙으로 정렬. ds: 항목 → 자료 dict"""
    live = [ds(x) for x in items if ds(x)["status"] != "ended"]
    rank: dict[str, int] = {}
    for d in live:
        o = org_of(d)
        rank[o] = min(rank.get(o, 10**6), d.get("order", 999))

    def key(x):
        d = ds(x)
        if d["status"] != "ended":
            return (0, rank[org_of(d)], org_of(d), d.get("order", 999), d["name"].lower())
        end = str((d.get("period") or {}).get("end") or "")
        return (1, "".join(chr(0x10FFFF - ord(c)) for c in end), d.get("order", 999), d["name"].lower())
    return sorted(items, key=key)


def sort_datasets(ds_list: list[dict]) -> list[dict]:
    out = []
    for dom, (_label, groups) in DOMAINS.items():
        for g in groups:
            out += order_in_group([d for d in ds_list if d["domain"] == dom and d["group"] == g])
    return out


def load_datasets(paths=None, data_dir=None) -> list[dict]:
    out = []
    for src in sorted(paths or (data_dir or DATA_DIR).glob("*.yaml")):
        src = Path(src)
        try:
            d = yaml.safe_load(src.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise PluginError(f"{src.name}: YAML 문법 오류 — {e}")
        validate(d, src)
        d.setdefault("variables", {}).setdefault("groups", [])
        if d["variables"] is None:
            d["variables"] = {"groups": []}
        d["notices"] = sorted(d.get("notices") or [], key=lambda n: str(n["date"]), reverse=True)
        out.append(d)
    ids = [d["id"] for d in out]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise PluginError(f"id가 겹쳐요: {dup}")
    if paths is None:  # 전체 검사일 때만: 전환 정보가 가리키는 페이지가 실제로 있는지
        bad = [
            f"{d['id']}: transitions의 to_id '{t['to_id']}'에 해당하는 파일이 없어요"
            for d in out for t in d.get("transitions") or []
            if t.get("to_id") and t["to_id"] not in ids
        ]
        if bad:
            raise PluginError("\n".join(bad))
    return sort_datasets(out)


def transition_anchor(t: dict) -> str:
    return "to-" + re.sub(r"[^a-z0-9]+", "-", str(t.get("to_id") or t["to"]).lower()).strip("-")


def incoming_transitions(target_id: str):
    """다른 데이터셋 페이지에 적힌 '→ 이 데이터셋' 전환 정보"""
    return [
        (d, t) for d in _datasets for t in d.get("transitions") or []
        if t.get("to_id") == target_id and d["id"] != target_id
    ]


def placements(datasets: list[dict]):
    """(domain, group) → [(dataset, 표시 이름, 교차수록 여부)]"""
    out: dict[tuple, list] = {}
    for d in datasets:
        out.setdefault((d["domain"], d["group"]), []).append((d, d["name"], False))
        for x in d.get("also_in") or []:
            out.setdefault((x["domain"], x["group"]), []).append((d, x.get("label") or d["name"], True))
    return {k: order_in_group(v, ds=lambda e: e[0]) for k, v in out.items()}


# ── 페이지 생성 ──────────────────────────────────────────────
def citation_block(items: list[dict], heading: str) -> list[str]:
    if not items:
        return []
    lines = [f"### {heading}", ""]
    for c in items:
        lines.append(f"**{c.get('label', '')}** — DOI {doi_link(c['doi'])}" if c.get("doi") else f"**{c.get('label', '')}**")
        lines.append("")
        lines.append('<div class="citation-text notranslate" translate="no" markdown>')
        lines.append(oneline(c["text"]))
        lines.append("</div>")
        lines.append("")
        if c.get("bibtex"):
            lines += ['??? quote "BibTeX 보기"', "", "    ```bibtex"]
            lines += ["    " + ln for ln in c["bibtex"].rstrip().splitlines()]
            lines += ["    ```", ""]
    return lines


def transition_block(d: dict, t: dict, heading: str = "###", link_prefix: str = "") -> list[str]:
    """후속 자료(또는 새 버전)와의 차이 — 비교표, 분석에 미치는 영향, 출처"""
    to = nt(t["to"])
    if t.get("to_id") and t["to_id"] != d["id"]:
        to = f"[{to}]({link_prefix}{t['to_id']}.md)"
    planned = ' <span class="status-badge status-delayed">예정</span>' if t["status"] == "planned" else ""
    L = [f"{heading} {nt(t['from'])} → {to}{planned} {{#{transition_anchor(t)}}}", ""]
    if t.get("date"):
        L += [f"*전환 시점:* {t['date']}", ""]
    L += [oneline(t["summary"]), ""]
    L += [f"| 항목 | {nt(t['from'])} | {nt(t['to'])} |", "|---|---|---|"]
    L += [f"| {oneline(c['aspect'])} | {oneline(c['before'])} | {oneline(c['after'])} |" for c in t["changes"]]
    L.append("")
    if t.get("impacts"):
        L += ['!!! warning "바꿔 쓸 때 주의할 점"', ""]
        L += [f"    - {oneline(x)}" for x in t["impacts"]]
        L.append("")
    L.append("출처: " + " · ".join(f"[{s.get('name') or s['url']}]({s['url']})" for s in t["sources"]))
    L.append("")
    if t.get("to_id") and t["to_id"] != d["id"]:
        up = "../../" if link_prefix == "" else "../"
        L += [f'<a class="act act-compare" href="{up}compare/?ids={d["id"]},{t["to_id"]}">두 자료를 비교표로 나란히 보기</a>', ""]
    return L


def kind_badge(it: dict) -> str:
    if not it.get("kind"):
        return ""
    label = kind_label(it["kind"])
    if it.get("period") and it["kind"] in ("mean", "accum", "max", "min"):
        label = f"{it['period']} {label}"
    elif it.get("period") and it["kind"] == "instant":
        label = f"{label} ({it['period']})"
    return f' <span class="kind kind-{it["kind"]}">{label}</span>'


def variables_block(v: dict, tc: dict | None = None) -> list[str]:
    L = ["## 활용 가능한 변수", ""]
    if not v.get("groups"):
        L += [oneline(v.get("note") or "아직 공개 전이라 변수 목록이 확정되지 않았습니다. 공개되면 정리하겠습니다."), ""]
        return L
    if v.get("note"):
        L += [oneline(v["note"]), ""]
    if tc:
        L += ['!!! info "시간 표기 규칙 — 순간값인가, 평균인가, 누적인가"', ""]
        L += ["    " + oneline(tc["summary"]), ""]
        L += [f"    - {oneline(p)}" for p in tc.get("points") or []]
        if tc.get("source"):
            L += ["", f"    근거: [{tc.get('source_name') or '공식 문서'}]({tc['source']})"]
        L.append("")
    L += [
        '<p class="kind-legend">'
        + " ".join(f'<span class="kind kind-{k}">{kind_label(k)}</span>' for k in KIND)
        + ' <span class="hint">— 순간값: 표시 시각의 값 · 평균/누적/최대/최소: 표시된 구간 동안의 값 · 고정값: 시간에 따라 변하지 않음</span></p>',
        "",
    ]
    for g in v["groups"]:
        L += [f"### {g['name']}", "", '<div class="var-list" markdown>', ""]
        for it in g["items"]:
            it = norm_item(it, g)
            line = f"- {oneline(it['text'])}{kind_badge(it)}"
            if it.get("note"):
                line += f' <span class="hint">— {oneline(it["note"])}</span>'
            L.append(line)
        L += ["", "</div>", ""]
    if v.get("full_list"):
        L += [f"전체 변수 목록은 [공식 문서]({v['full_list']})에서 확인하세요.", ""]
    return L


def site_citation_lines(c: dict, bibtex: bool = True) -> list[str]:
    """사이트 인용 안내 — 영어 사사(Acknowledgements) 문장 (소개 페이지는 BibTeX도). 소개 페이지와 데이터셋 페이지 하단 공통."""
    if not c or not c.get("ack_en"):
        return []
    L = ["**Acknowledgements**", "", "```text", c["ack_en"], "```", ""]
    if bibtex and c.get("bibtex"):
        L += [loc("**BibTeX** (참고문헌 관리 프로그램용)"), "", "```bibtex", c["bibtex"].rstrip(), "```", ""]
    return ['<div class="cite-block" markdown="1">', ""] + L + ["</div>", ""]


def render_dataset(d: dict, site_cite: dict) -> str:
    L: list[str] = []
    L += [f"# {nt(d['name'])}", ""]
    if d.get("full_name"):
        L += [f"*{d['full_name']}*", ""]
    L += [
        badge(d["status"]),
        "",
        '<div class="page-actions">'
        f'<a class="act act-subscribe" href="../../subscribe/?dataset={d["id"]}">중요 공지 알림 받기</a>'
        f'<a class="act act-compare" href="../../compare/?ids={d["id"]}">다른 자료와 비교</a>'
        f'<a class="act act-report" href="#report" data-report="{html.escape(d["name"])}">정보 오류 신고</a>'
        "</div>",
        "",
    ]

    # 상태 경고
    if d["status"] != "active" or d.get("status_note"):
        kind = {"active": "note", "delayed": "warning", "deprecated": "warning", "ended": "danger", "upcoming": "info"}[d["status"]]
        title = {"active": "현재 상태", "delayed": "갱신 지연", "deprecated": "대체 예정", "ended": "갱신 종료", "upcoming": "공개 예정"}[d["status"]]
        if is_en():
            title = EN.STATUS_TITLE[d["status"]]
        L += [f'!!! {kind} "{title}"', ""]
        L += ["    " + oneline(d.get("status_note", "")), ""]
        s = d.get("successor")
        if s and s.get("name") not in (None, "없음", "None"):
            target = f"[{nt(s['name'])}]({s['url']})" if s.get("url") else nt(s["name"])
            L += [f"    **후속 자료:** {target} — {oneline(s.get('note', ''))}", ""]

    # 한눈에 보기
    r = d.get("resolution") or {}
    where = f"{domain_label(d['domain'])} › {g_label(d['group'])}"
    for x in d.get("also_in") or []:
        where += f" (교차 수록: {domain_label(x['domain'])} › {g_label(x['group'])})"
    rows = [
        ("분류", where),
        ("종류", cat_label(d["category"])),
        ("분야", tags_label(d.get("domains"))),
        ("제공 기관", nt(d["provider"])),
        ("기간", period_text(d["period"])),
        ("수평 해상도", r.get("spatial")),
        ("연직 해상도", r.get("vertical")),
        ("시간 해상도", r.get("temporal")),
        ("갱신 주기", d.get("update")),
        ("라이선스", d.get("license")),
        ("계정 필요", yes_no(d.get("account_required"))),
    ]
    L += ["## 한눈에 보기", "", "| 항목 | 내용 |", "|---|---|"]
    L += [f"| {k} | {oneline(v)} |" for k, v in rows if v]
    if d["period"].get("note"):
        L += ["", f"*기간 참고:* {oneline(d['period']['note'])}"]
    L += [""] + detail_res_note()
    L += ["", "## 개요", "", oneline(d["summary"]), ""]

    # 이전 자료 → 이 자료로 넘어온 경우: 비교 내용이 있는 곳으로 안내
    inc = incoming_transitions(d["id"])
    if inc:
        L += ['!!! abstract "이전 자료와 무엇이 달라졌나"', ""]
        for src, t in inc:
            L += [f"    - [{nt(t['from'])} → {nt(t['to'])} 비교 보기]({src['id']}.md#{transition_anchor(t)})"]
        L.append("")

    # 이 자료 → 후속 자료(또는 새 버전)
    trs = d.get("transitions") or []
    if trs:
        L += ["## 후속 자료와 무엇이 달라졌나", ""]
        for t in trs:
            L += transition_block(d, t)

    L += variables_block(d["variables"], d.get("time_convention"))

    # 받는 방법
    L += ["## 받는 방법", ""]
    for a in d["access"]:
        L.append(f"- **[{a['name']}]({a['url']})** — {a.get('method', '')}")
        if a.get("note"):
            L.append(f"    - {oneline(a['note'])}")
    L.append("")
    ex = d.get("example")
    if ex:
        L += ["### 예시 코드", ""]
        if ex.get("note"):
            L += [oneline(ex["note"]), ""]
        L += [f"```{ex.get('lang', '')}", ex["code"].rstrip(), "```", ""]

    if d.get("tips"):
        L += ["## 실전 팁", ""]
        L += [f"- {oneline(t)}" for t in d["tips"]]
        L.append("")

    # 공지
    L += ["## 공지 및 변경 이력", ""]
    if d["notices"]:
        for n in d["notices"]:
            label, kind = level_label(n["level"]), LEVEL[n["level"]][1]
            L += [f'!!! {kind} "{n["date"]} · {label} · {n["title"]}"', ""]
            if n.get("body"):
                L += ["    " + oneline(n["body"]), ""]
            L += [f"    [원문 보기]({n['source']})", ""]
    else:
        L += ["등록된 공지가 없습니다.", ""]

    # 인용
    cit = d["citations"]
    L += ["## 논문에 넣을 레퍼런스", ""]
    L += [
        '!!! warning "논문에 쓰기 전에 꼭 다시 확인하세요"',
        "",
        "    아래 인용 정보는 운영자가 정리한 것으로 오류가 있을 수 있습니다. DOI, 저자, 연도, 접근 날짜 표기 방식은 "
        "제공 기관의 공식 데이터셋 페이지와 학술지 투고 규정에서 **반드시 더블체크**한 뒤 사용하세요.",
        "",
    ]
    L += citation_block(cit.get("dataset", []), "데이터셋 인용")
    L += citation_block(cit.get("papers", []), "논문 인용")
    if cit.get("acknowledgement"):
        L += ["### 사사(Acknowledgements) 작성", "", oneline(cit["acknowledgement"]), ""]
    if site_cite:
        L += ['!!! tip "이 정리가 도움이 되셨다면 기후데이터 길잡이도 인용해 주세요"', ""]
        L += ["    논문의 사사(Acknowledgements)에 아래 문장을 넣어주세요.", ""]
        L += ["    " + x if x else "" for x in site_citation_lines(site_cite, bibtex=False)]
        L.append("")

    if d.get("links"):
        L += ["## 참고 링크", ""]
        L += [f"- [{x['name']}]({x['url']})" for x in d["links"]]
        L.append("")

    return loc("\n".join(L))


STATUS_ORDER = {"active": 0, "delayed": 1, "deprecated": 2, "ended": 3, "upcoming": 4}


def _first_value(text: str, rules) -> float | str:
    """문장에서 가장 먼저 나오는 값 (rules: [(정규식, 변환 함수)])"""
    hits = []
    for pat, conv in rules:
        for m in re.finditer(pat, str(text or "")):
            hits.append((m.start(), conv(m)))
    return round(min(hits)[1], 2) if hits else ""


def spatial_km(text: str):
    """수평 해상도 정렬용 값: 처음 표기된 대표 격자를 km로 환산 (1° ≈ 111 km)"""
    return _first_value(text, [
        (r"(\d+)/(\d+)\s*°", lambda m: 111 * float(m.group(1)) / float(m.group(2))),
        (r"(?<![\d/.])(\d+(?:\.\d+)?)\s*°", lambda m: 111 * float(m.group(1))),
        (r"(\d+(?:\.\d+)?)\s*km", lambda m: float(m.group(1))),
    ])


def temporal_hours(text: str):
    """시간 해상도 정렬용 값: 처음 표기된 간격을 시간 단위로"""
    return _first_value(text, [
        (r"(\d+(?:\.\d+)?)\s*시간", lambda m: float(m.group(1))),
        (r"(\d+)\s*일", lambda m: 24 * float(m.group(1))),
        (r"(?<!\d)(매일|하루|일평균|일별|일·|일\b|일 )", lambda m: 24.0),
        (r"주간|주별|주\b", lambda m: 168.0),
        (r"월평균|월별|월\b|매월", lambda m: 720.0),
    ])


def short_res(d: dict):
    r = d.get("resolution") or {}
    sp, tm = r.get("spatial_short", "-"), r.get("temporal_short", "-")
    km = float(sp.split(" km")[0]) if " km" in sp else ""
    return sp, tm, km, TEMPORAL_HOURS.get(tm, "")


def group_table(entries, href_prefix: str, compare_href: str) -> list[str]:
    """분야·전체 목록 표 (열 머리를 누르면 정렬, 체크해서 바로 비교). href_prefix는 데이터셋 페이지까지의 경로"""
    rows = ""
    for d, label, cross in entries:
        r = d.get("resolution") or {}
        sp, tm, km, hrs = short_res(d)
        mark = ' <span class="hint" title="다른 분야에도 실린 자료">↔</span>' if cross else ""
        rows += (
            f'<tr data-id="{d["id"]}">'
            f'<td data-sort="{html.escape(label)}"><a href="{href_prefix}{d["id"]}/">{nt(html.escape(label))}</a>{mark}</td>'
            f"<td>{cat_label(d['category'])}</td>"
            f'<td class="nowrap" data-sort="{d["period"]["start"]}">{period_text(d["period"])}</td>'
            f'<td class="nowrap" data-sort="{km}" title="{html.escape(oneline(r.get("spatial") or ""))}">{sp}</td>'
            f'<td class="nowrap" data-sort="{hrs}" title="{html.escape(oneline(r.get("temporal") or ""))}">{t_label(tm)}</td>'
            f'<td data-sort="{STATUS_ORDER[d["status"]]}">{badge(d["status"])}</td>'
            "</tr>"
        )
    return [
        f'<div class="list-table" data-compare="{compare_href}"><table>'
        "<thead><tr><th>자료</th><th>종류</th><th>기간</th>"
        '<th title="주 제공처에서 받는 격자 간격 (km는 적도 기준 근사)">제공 해상도</th>'
        '<th title="가장 짧은 제공 간격 (세부는 각 자료 페이지)">시간 간격</th><th>상태</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    ]


def render_index(datasets: list[dict]) -> str:
    L = [
        "---", "hide:", "  - navigation", "  - toc", "---", "",
        "# 전체 데이터셋 목록", "",
        f"모두 {len(datasets)}개 자료를 공식 출처에서 직접 확인해 정리했습니다. 이후 바뀌었을 수 있으니 쓰기 전에 공식 출처를 다시 확인하세요.", "",
        "표의 열 이름을 누르면 정렬되고, 왼쪽 칸을 2개 이상 체크하면 **바로 비교**할 수 있습니다. "
        "해상도는 쉽게 비교하도록 **주 제공처에서 받는 격자** 기준 대표 값만 적었고(시간 해상도는 가장 짧은 제공 간격), 세부 내용은 각 자료 페이지에 있습니다. "
        "↔ 표시는 다른 분야에도 함께 실린 자료입니다.", "",
    ] + res_note()
    pl = placements(datasets)
    # 분야 바로가기 (대기 · 해양 · 해빙)
    chips = "".join(
        f'<a class="domain-chip domain-{dom}" href="#{dom}"><strong>{domain_label(dom)}</strong>'
        f'<span>{sum(len(pl.get((dom, g), [])) for g in groups)}개</span></a>'
        for dom, (label, groups) in DOMAINS.items()
    )
    L[L.index("# 전체 데이터셋 목록") + 2:L.index("# 전체 데이터셋 목록") + 2] = [f'<nav class="domain-jump">{chips}</nav>', ""]
    for dom, (label, groups) in DOMAINS.items():
        n = sum(len(pl.get((dom, g), [])) for g in groups)
        L += [f'<h2 class="domain-head domain-{dom}" id="{dom}">{domain_label(dom)}<span class="domain-count">{n}개 자료</span></h2>', ""]
        for g in groups:
            if (dom, g) in pl:
                L += [f"### {g_label(g)} {{ .group-head }}", ""]
                if group_intro(g):
                    L += [f'<p class="group-intro">{group_intro(g)}</p>', ""]
                L += group_table(pl[(dom, g)], "", "../compare/") + [""]
    return loc("\n".join(L) + "\n")


def render_domain(dom: str, datasets: list[dict]) -> str:
    label, groups = DOMAINS[dom]
    pl = placements(datasets)
    L = ["---", "hide:", "  - navigation", "  - toc", "---", "", f"# {domain_label(dom)}", "", domain_intro(dom), "",
         "표의 왼쪽 칸을 2개 이상 체크하면 바로 비교할 수 있고, 열 이름을 누르면 정렬됩니다.", ""] + res_note()
    for g in groups:
        if (dom, g) in pl:
            L += [f"## {g_label(g)} {{ .group-head }}", ""]
            if group_intro(g):
                L += [f'<p class="group-intro">{group_intro(g)}</p>', ""]
            L += group_table(pl[(dom, g)], "../../datasets/", "../../compare/") + [""]
    if any(cross for g in groups for _, _, cross in pl.get((dom, g), [])):
        L += ["↔ 다른 분야 페이지에도 함께 실린 자료입니다.", ""]
    return loc("\n".join(L) + "\n")


def all_notices(datasets: list[dict]) -> list[tuple[dict, dict]]:
    pairs = [(d, n) for d in datasets for n in d["notices"]]
    return sorted(pairs, key=lambda p: str(p[1]["date"]), reverse=True)


def notice_rows(pairs, link_prefix: str) -> list[str]:
    L = ["| 날짜 | 데이터셋 | 구분 | 내용 |", "|---|---|---|---|"]
    for d, n in pairs:
        label = level_label(n["level"])
        L.append(
            f"| {n['date']} | [{nt(d['name'])}]({link_prefix}{d['id']}.md) "
            f"| <span class=\"level-{n['level']}\">{label}</span> | [{n['title']}]({n['source']}) |"
        )
    return [loc(x) for x in L]


def render_notices(datasets: list[dict]) -> str:
    """중요 공지 — 데이터셋·공지 구분으로 걸러 볼 수 있는 표"""
    pairs = all_notices(datasets)
    opts = ""
    for dom, (label, _) in DOMAINS.items():
        items = [d for d in datasets if d["domain"] == dom and d["notices"]]
        if items:
            opts += f'<optgroup label="{domain_label(dom)}">' + "".join(
                f'<option value="{d["id"]}">{html.escape(d["name"])} ({len(d["notices"])})</option>' for d in items
            ) + "</optgroup>"
    lv = "".join(
        f'<label class="check"><input type="checkbox" name="nlevel" value="{k}" checked> '
        f'<span class="level-{k}">{level_label(k)}</span></label>'
        for k in LEVEL
    )
    rows = "".join(
        f'<tr data-dataset="{d["id"]}" data-level="{n["level"]}">'
        f'<td class="nowrap">{n["date"]}</td>'
        f'<td><a href="../datasets/{d["id"]}/">{nt(html.escape(d["name"]))}</a></td>'
        f'<td><span class="level-{n["level"]}">{level_label(n["level"])}</span></td>'
        f'<td><a href="{html.escape(n["source"])}" target="_blank" rel="noopener">{html.escape(n["title"])}</a></td></tr>'
        for d, n in pairs
    )
    return loc("\n".join([
        "# 중요 공지", "",
        "데이터 제공 중단, 서비스 이전, 품질 문제처럼 **분석에 영향을 주는 공지**를 최신순으로 모았습니다.",
        "각 항목의 링크는 원문 공지로 연결됩니다. 새 공지를 메일로 받고 싶다면 [중요 공지 알림 신청](subscribe.md)을 이용하세요.", "",
        '<section class="notice-filter cdg-form" id="notice-filter" data-search-exclude>'
        '<label class="field">데이터셋<select id="nf-dataset"><option value="">전체 데이터셋</option>' + opts + "</select></label>"
        f'<div class="nf-levels"><span class="nf-label">구분</span>{lv}</div>'
        f'<p class="hint" id="nf-count">{("All " + str(len(pairs))) if is_en() else ("전체 " + str(len(pairs)) + "건")}</p></section>',
        "",
        '<div data-search-exclude><table id="notice-table">'
        "<thead><tr><th>날짜</th><th>데이터셋</th><th>구분</th><th>내용</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>",
        '<p class="hint" id="nf-empty" hidden data-search-exclude>조건에 맞는 공지가 없습니다.</p>',
        "",
    ]) + "\n")


def lineage_chains(datasets: list[dict]) -> list[list[tuple]]:
    """to_id로 이어지는 세대 계보 (예: ERA-15 → ERA-40 → ERA-Interim → ERA5 → ERA6)"""
    by_id = {d["id"]: d for d in datasets}
    nxt, has_prev = {}, set()
    for d in datasets:
        for t in d.get("transitions") or []:
            if t.get("to_id") and t["to_id"] != d["id"]:
                nxt[d["id"]] = t
                has_prev.add(t["to_id"])
    chains = []
    for start in [i for i in nxt if i not in has_prev]:
        chain, cur = [(by_id[start]["name"], start, False)], start
        while cur in nxt:
            cur = nxt[cur]["to_id"]
            chain.append((by_id[cur]["name"], cur, False))
        # 마지막 자료에 예정된 후속(사이트 밖)이 있으면 덧붙임
        for t in by_id[cur].get("transitions") or []:
            if t["status"] == "planned" and not t.get("to_id"):
                chain.append((t["to"], None, True))
        chains.append(chain)
    return chains


def transition_key(d: dict, t: dict) -> str:
    return "g-" + d["id"] + "-" + transition_anchor(t)


def render_transitions(datasets: list[dict]) -> str:
    """세대별 비교 — 표에서 항목을 누르면 그 변화만 아래에 표시"""
    pairs = [(d, t) for d in datasets for t in d.get("transitions") or []]
    L = [
        "---", "hide:", "  - navigation", "  - toc", "---", "",
        "# 세대별 비교", "",
        "재분석자료와 관측 자료는 세대가 바뀌거나 새 버전이 나오면 기간, 해상도, 관측 입력, 변수 이름이 함께 바뀝니다.",
        "아래 표에서 **항목을 누르면** 무엇이 달라졌는지와 바꿔 쓸 때 주의할 점이 표 아래에 나타납니다.", "",
    ]
    chains = lineage_chains(datasets)
    if chains:
        L += ['<div class="lineage">', '<p class="lineage-title">자료 계보</p>']
        for ch in chains:
            parts = []
            for name, did, planned in ch:
                if did:
                    parts.append(f'<a href="../datasets/{did}/">{nt(html.escape(name))}</a>')
                else:
                    parts.append(f'<span class="planned">{nt(html.escape(name))} (예정)</span>')
            L.append('<p class="lineage-chain">' + ' <span class="arrow">→</span> '.join(parts) + "</p>")
        L += ["</div>", ""]
    rows = ""
    for d, t in pairs:
        state = "예정" if t["status"] == "planned" else "완료"
        key = transition_key(d, t)
        rows += (
            f'<tr data-key="{key}">'
            f'<td data-sort="{html.escape(t["from"])}"><button type="button" class="gen-open" data-key="{key}">'
            f'{nt(html.escape(t["from"]))} <span class="arrow">→</span> {nt(html.escape(t["to"]))}</button></td>'
            f"<td>{domain_label(d['domain'])}</td>"
            f'<td data-sort="{0 if t["status"] == "completed" else 1}">'
            f'<span class="status-badge {"status-active" if state == "완료" else "status-delayed"}">{state}</span></td>'
            f'<td class="nowrap">{html.escape(str(t.get("date") or "-"))}</td>'
            "</tr>"
        )
    L += [
        '<div class="gen-table"><table>'
        "<thead><tr><th>세대 변화</th><th>분야</th><th>상태</th><th>전환 시점</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>",
        "",
        '<p class="hint" id="gen-empty">표에서 비교할 항목을 누르세요.</p>',
        "",
    ]
    for d, t in pairs:
        key = transition_key(d, t)
        block = transition_block(d, t, "##", "datasets/")
        # 제목을 h2가 아닌 문단으로: 숨긴 영역의 제목이 사이트 검색에 빈 결과로 잡히지 않도록
        title = re.sub(r"\{#[^}]*\}", "", block[0]).rstrip()[3:]
        block[0] = f'<p class="gen-title" markdown="span">{title}</p>'
        L += [f'<section class="gen-detail" id="{key}" markdown="1" hidden data-search-exclude>', ""]
        L += block
        L += [f"[{nt(d['name'])} 페이지에서 보기 →](datasets/{d['id']}.md)", "", "</section>", ""]
    return loc("\n".join(L) + "\n")


def compare_data(datasets: list[dict]) -> list[dict]:
    out = []
    for d in datasets:
        r = d.get("resolution") or {}
        cit = d["citations"]
        dois = [c["doi"] for c in (cit.get("dataset") or []) + (cit.get("papers") or []) if c.get("doi")]
        groups = []
        for g in d["variables"]["groups"]:
            items = []
            for it in g["items"]:
                it = norm_item(it, g)
                items.append({"t": oneline(it["text"]), "k": it["kind"], "b": kind_badge(it).strip()})
            groups.append({"n": g["name"], "i": items})
        s = d.get("successor") or {}
        out.append({
            "id": d["id"], "name": d["name"], "domain": domain_label(d["domain"]), "group": g_label(d["group"]),
            "category": cat_label(d["category"]), "provider": d["provider"], "status": badge(d["status"]),
            "period": period_text(d["period"]), "spatial": r.get("spatial_short") or "-",
            "spatial_d": oneline(r.get("spatial") or "-"),
            "temporal_s": t_label(r.get("temporal_short") or "-"),
            "vertical": oneline(r.get("vertical") or "-"), "temporal": oneline(r.get("temporal") or "-"),
            "update": oneline(d.get("update") or "-"), "license": oneline(d.get("license") or "-"),
            "account": yes_no(d.get("account_required")),
            "time": oneline((d.get("time_convention") or {}).get("summary") or "-"),
            "nvars": sum(len(g["items"]) for g in d["variables"]["groups"]),
            "doi": dois[:2], "successor": s.get("name") or "-", "groups": groups,
        })
    return out


def compare_app(datasets: list[dict]) -> str:
    opts = ""
    for dom, (label, groups) in DOMAINS.items():
        items = [d for d in datasets if d["domain"] == dom]
        opts += f'<optgroup label="{domain_label(dom)}">' + "".join(
            f'<option value="{d["id"]}">{html.escape(d["name"])}</option>' for d in items
        ) + "</optgroup>"
    selects = "".join(
        f'<label class="field">{"Dataset" if is_en() else "자료"} {i + 1}<select class="cmp-select" data-slot="{i}">'
        f'<option value="">— 선택 —</option>{opts}</select></label>'
        for i in range(4)
    )
    chips = "".join(
        f'<button type="button" class="chip" data-q="{q}">{q}</button>'
        for q in (["precipitation", "temperature", "wind", "pressure", "radiation", "humidity", "sea surface temperature", "sea ice", "salinity", "flux"]
                  if is_en() else ["강수", "기온", "바람", "기압", "복사", "습도", "해수면온도", "해빙", "염분", "플럭스"])
    )
    data = json.dumps(compare_data(datasets), ensure_ascii=False).replace("</", "<\\/")
    return loc(
        '<section class="cdg-form compare-controls" data-search-exclude><div class="cmp-selects">' + selects + "</div>"
        '<label class="field">변수 찾기 <span class="hint">— 고른 자료들에서 같은 종류의 변수를 나란히 봅니다 (한국어 이름이나 변수명)</span>'
        '<input type="text" id="cmp-q" placeholder="예) 강수, tp, prate, sea ice"></label>'
        f'<div class="chips">{chips}</div></section>'
        '<p class="hint" id="cmp-empty" data-search-exclude>위에서 비교할 자료를 2개 이상 골라주세요. 고른 내용은 주소에 저장되어 그대로 공유할 수 있습니다.</p>'
        '<div class="table-scroll" data-search-exclude><table id="cmp-table" hidden></table></div>'
    ) + f'<script type="application/json" id="cmp-data">{data}</script>'


def domain_summary(datasets: list[dict]) -> str:
    L = ["| 분야 | 자료 수 | 정상 제공 | 갱신 종료 | 기타 |", "|---|---|---|---|---|"]
    pl = placements(datasets)
    for dom, (label, groups) in DOMAINS.items():
        ds = {d["id"]: d for g in groups for d, _, _ in pl.get((dom, g), [])}.values()
        n = len(ds)
        act = sum(d["status"] == "active" for d in ds)
        end = sum(d["status"] == "ended" for d in ds)
        L.append(f"| [{label}](domains/{dom}.md) | {n} | {act} | {end} | {n - act - end} |")
    return "\n".join(L)


# ── 메뉴(nav) 자동 구성 ──────────────────────────────────────
def build_nav_sections(datasets: list[dict], base_path: str) -> list[dict]:
    pl = placements(datasets)
    sections = []
    for dom, (label, groups) in DOMAINS.items():
        items: list = [{("Overview" if is_en() else "개요"): f"domains/{dom}.md"}]
        for g in groups:
            entries = []
            for d, name, cross in pl.get((dom, g), []):
                if cross:  # 같은 페이지를 두 번 넣지 않고 링크로 연결
                    entries.append({f"{name} ↔": f"{base_path}datasets/{d['id']}/"})
                else:
                    entries.append({name: f"datasets/{d['id']}.md"})
            if entries:
                items.append({g_label(g): entries})
        sections.append({domain_label(dom): items})
    return sections


def on_config(config):
    global _datasets, _site_url, _lang, _ko_datasets
    _lang = "en" if str(config["theme"].get("language", "ko")).startswith("en") else "ko"
    _datasets = load_datasets(data_dir=DATA_DIR_EN if is_en() else DATA_DIR)
    _ko_datasets = load_datasets() if is_en() else _datasets
    if is_en():
        missing = sorted({d["id"] for d in _ko_datasets} - {d["id"] for d in _datasets})
        if missing:
            raise PluginError(f"영어판 YAML이 없는 자료가 있어요 (data/datasets_en/): {missing}")
    _site_url = config.get("site_url") or "/"
    config["extra"]["disclaimer"] = disclaimer()
    base = urlparse(config.get("site_url") or "/").path or "/"
    if not base.endswith("/"):
        base += "/"
    nav = config.get("nav") or []
    new_nav = []
    for item in nav:
        if isinstance(item, dict) and NAV_PLACEHOLDER in item:
            new_nav += build_nav_sections(_datasets, base)
        else:
            new_nav.append(item)
    config["nav"] = new_nav
    return config


def on_files(files, config):
    site_cite = config.get("extra", {}).get("site_citation") or {}
    if not isinstance(site_cite, dict):
        site_cite = {}

    def add(uri: str, content: str):
        existing = files.get_file_from_path(uri)
        if existing:
            files.remove(existing)
        files.append(File.generated(config, uri, content=content))

    # 영어판: 그림·스크립트·스타일은 한국어판 docs/ 의 파일을 그대로 함께 배포 (중복 보관하지 않음)
    if is_en():
        for sub in ("assets", "javascripts", "stylesheets"):
            for f in sorted((KO_DOCS / sub).rglob("*")):
                rel = f.relative_to(KO_DOCS).as_posix()
                if f.is_file() and not files.get_file_from_path(rel):
                    files.append(File(rel, str(KO_DOCS), config["site_dir"], config["use_directory_urls"]))

    for d in _datasets:
        add(f"datasets/{d['id']}.md", render_dataset(d, site_cite))
    for dom in DOMAINS:
        add(f"domains/{dom}.md", render_domain(dom, _datasets))
    add("datasets/index.md", render_index(_datasets))
    add("notices.md", render_notices(_datasets))
    add("transitions.md", render_transitions(_datasets))
    add("assets/notices.json", notices_json(_datasets))
    add("feed.xml", notices_rss(_datasets, config))
    return files


def notices_json(datasets: list[dict]) -> str:
    """메일 알림용 공지 목록 (mailing/Code.gs 가 하루 한 번 읽어 새 공지만 발송).
    key 가 처음 보이는 공지만 '새 공지'로 취급하므로, 이미 올린 공지의 날짜·제목을 고치면 다시 발송됩니다."""
    # 영어판 공지도 한국어판과 같은 key 를 써야 발송 기록이 하나로 관리됨 (같은 자료 안 같은 순서의 공지끼리 짝지음)
    ko_by_id = {d["id"]: d for d in _ko_datasets}

    def key_of(d, n):
        if is_en() and d["id"] in ko_by_id:
            i = d["notices"].index(n)
            kn = ko_by_id[d["id"]]["notices"]
            if i < len(kn):
                return f"{d['id']}|{kn[i]['date']}|{kn[i]['title']}"
        return f"{d['id']}|{n['date']}|{n['title']}"

    out = []
    for d, n in all_notices(datasets):
        out.append({
            "key": key_of(d, n),
            "date": str(n["date"]),
            "level": n["level"],
            "dataset_id": d["id"],
            "dataset_name": d["name"],
            "title": n["title"],
            "body": re.sub(r"\s+", " ", str(n.get("body") or "")).strip(),
            "source": n.get("source", ""),
            "url": site_page_url(d),
        })
    # datasets: 사이트에 있는 모든 자료 id — 새로 추가된 자료의 기존 공지는 메일로 보내지 않고 기록만 하기 위해 씀
    return json.dumps({"generated": date.today().isoformat(), "datasets": sorted(d["id"] for d in datasets),
                       "notices": out}, ensure_ascii=False, indent=1)


def notices_rss(datasets: list[dict], config) -> str:
    """중요 공지 RSS (최근 50건) — 네이버 서치어드바이저 RSS 제출·피드 리더 구독용"""
    from email.utils import format_datetime
    from datetime import datetime, timezone
    from xml.sax.saxutils import escape as x

    base = config.get("site_url") or "/"

    def pub(dstr):
        parts = [int(v) for v in str(dstr).split("-")] + [1, 1]
        return format_datetime(datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc))

    items = []
    for d, n in all_notices(datasets)[:50]:
        link = f"{base}datasets/{d['id']}/"
        items.append(
            "<item>"
            f"<title>{x('[' + d['name'] + '] ' + n['title'])}</title>"
            f"<link>{x(link)}</link>"
            f"<guid isPermaLink=\"false\">{x(d['id'] + '|' + str(n['date']) + '|' + str(datasets.index(d)) + '|' + n['title'][:60])}</guid>"
            f"<pubDate>{pub(n['date'])}</pubDate>"
            f"<category>{x(level_label(n['level']))}</category>"
            f"<description>{x(oneline(n.get('body') or n['title']))}</description>"
            "</item>"
        )
    title = config.get("site_name") + (" — Notices" if is_en() else " — 중요 공지")
    desc = ("Discontinuation, change and quality notices for climate datasets" if is_en()
            else "기후·해양·해빙 자료의 제공 중단·변경·품질 공지")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{x(title)}</title><link>{x(base)}notices/</link><description>{x(desc)}</description>"
        f"<language>{'en' if is_en() else 'ko'}</language>"
        f'<atom:link href="{x(base)}feed.xml" rel="self" type="application/rss+xml"/>'
        + "".join(items) + "</channel></rss>\n"
    )


# ── 폼 ──────────────────────────────────────────────────────
def _forms_config(config) -> dict:
    return (config.get("extra") or {}).get("forms") or {}


def subscribe_form(config) -> str:
    """알림 신청 폼. 데이터셋 체크박스는 YAML 목록에서 분야별로 자동 생성됩니다."""
    endpoint = _forms_config(config).get("subscribe_endpoint") or ""
    pre = ""
    if not endpoint:
        pre = (
            '!!! info "메일 알림은 준비 중입니다"\n\n'
            "    신청 양식은 미리 둘러보실 수 있지만, 아직 메일 발송을 시작하지 않아 신청이 저장되지 않습니다.\n"
            "    오픈하면 이 페이지에서 바로 신청할 수 있어요. 그전까지는 [중요 공지](notices.md)을 확인해 주세요.\n\n"
        )
    ds = ""
    for dom, (label, _) in DOMAINS.items():
        items = [d for d in _datasets if d["domain"] == dom]
        if not items:
            continue
        ds += f'<p class="check-group-title">{domain_label(dom)}</p><div class="check-grid">'
        ds += "".join(
            f'<label class="check"><input type="checkbox" name="datasets" value="{d["id"]}"> '
            f'{nt(d["name"])} {badge(d["status"])}</label>'
            for d in items
        )
        ds += "</div>"
    lv = "".join(
        f'<label class="check"><input type="checkbox" name="levels" value="{key}"> '
        f'<span class="level-{key}">{level_label(key)}</span><span class="hint"> — {desc}</span></label>'
        for key, desc in [
            ("critical", "제공 중단, 서비스 종료처럼 분석에 바로 영향을 주는 공지"),
            ("warning", "품질 문제, 재처리, 종료 예고"),
            ("info", "주소 이전, 라이선스 변경, 새 자료 공개"),
        ]
    )
    html = (
        f'<form id="subscribe-form" class="cdg-form" data-search-exclude data-endpoint="{endpoint}" novalidate>'
        '<fieldset><legend>1. 알림 받을 데이터셋</legend>'
        '<label class="check check-all"><input type="checkbox" data-all="datasets"> '
        '<strong>전체</strong><span class="hint"> — 앞으로 추가되는 데이터셋 포함</span></label>'
        f'{ds}</fieldset>'
        '<fieldset><legend>2. 받을 공지 구분</legend>'
        '<label class="check check-all"><input type="checkbox" data-all="levels"> <strong>전체</strong></label>'
        f'<div class="check-list">{lv}</div></fieldset>'
        '<fieldset><legend>3. 받을 이메일</legend>'
        '<input type="email" name="email" placeholder="name@example.ac.kr" autocomplete="email" required>'
        '</fieldset>'
        '<div class="hp-field" aria-hidden="true"><label>웹사이트 (비워 두세요)<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
        '<div class="consent-row"><label class="check consent"><input type="checkbox" name="consent" required> '
        '<span>개인정보 수집·이용에 동의합니다 (필수)</span></label>'
        '<a class="consent-link" href="../privacy/" target="_blank" rel="noopener">처리방침 보기 ↗</a></div>'
        '<div class="form-actions"><button type="submit" class="md-button md-button--primary">알림 신청</button></div>'
        '<p class="hint">신청하면 <strong>확인 메일</strong>이 갑니다. 메일의 <em>신청 확인하기</em>를 눌러야 등록이 끝납니다. 받은편지함에 없으면 <strong>스팸함</strong>을 확인해 주세요. '
        '알림 메일마다 아래쪽에 수신 거부 링크가 있어 언제든 해지할 수 있습니다.</p>'
        '<p class="form-message" role="status" aria-live="polite"></p>'
        '</form>'
    )
    return loc(pre + html)


def suggest_form(config) -> str:
    """데이터셋 추가 제안 폼. 운영자 메일(Apps Script)로 바로 보냅니다."""
    endpoint = _forms_config(config).get("suggest_endpoint") or ""
    cats = "".join(f'<option value="{cat_label(k)}">{cat_label(k)}</option>' for k in CATEGORY)
    existing = ", ".join(nt(d["name"]) for d in _datasets)
    pre = "" if endpoint else (
        '!!! info "제안 접수는 준비 중입니다"\n\n'
        "    그동안은 data4researchers@gmail.com 으로 메일을 보내주세요.\n\n"
    )
    return loc(pre + (
        f'<details class="hint" data-search-exclude><summary>이미 있는 데이터셋 {len(_datasets)}개 보기</summary><p>{existing}</p></details>'
        f'<form id="suggest-form" class="cdg-form" data-search-exclude data-endpoint="{endpoint}" novalidate>'
        '<fieldset><legend>데이터셋 정보</legend>'
        '<label class="field">데이터셋 이름 <em>필수</em>'
        '<input type="text" name="name" placeholder="예) ERA5-Land, SMAP 토양수분" required></label>'
        f'<label class="field">종류<select name="category">{cats}</select></label>'
        '<label class="field">공식 페이지 주소 <em>필수</em>'
        '<input type="url" name="url" placeholder="https://" required></label>'
        '</fieldset>'
        '<fieldset><legend>왜 필요한가요</legend>'
        '<label class="field">어떤 연구에 쓰시나요?'
        '<textarea name="reason" rows="3" placeholder="예) 북극 해빙 변화와 대기 순환 연구에 ERA5와 비교용으로 사용"></textarea></label>'
        '<label class="field">알고 계신 중단·변경 소식 (선택)'
        '<textarea name="notes" rows="2" placeholder="예) 내년부터 새 버전으로 전환 예정이라고 들었어요"></textarea></label>'
        '<label class="field">제안하신 분 (선택)'
        '<input type="text" name="contact" placeholder="이름·소속, 답장이 필요하면 이메일도 적어주세요"></label>'
        '</fieldset>'
        '<div class="hp-field" aria-hidden="true"><label>웹사이트 (비워 두세요)<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
        '<div class="form-actions">'
        '<button type="submit" class="md-button md-button--primary"' + ("" if endpoint else " disabled") + '>제안 보내기</button></div>'
        '<p class="hint">제안은 운영자에게만 전달되며 공개되지 않습니다.</p>'
        '<p class="form-message" role="status" aria-live="polite"></p>'
        '</form>'
    ))


def feedback_form(config) -> str:
    """사이트 의견 보내기 폼. 운영자 메일(Apps Script)로 바로 보내며 공개되지 않습니다."""
    endpoint = _forms_config(config).get("feedback_endpoint") or ""
    kinds = [("idea", "기능 제안"), ("improve", "사이트 개선"), ("thanks", "칭찬·응원"), ("other", "기타")]
    opts = "".join(f'<option value="{k}">{v}</option>' for k, v in kinds)
    return loc(
        f'<form id="feedback-form" class="cdg-form" data-search-exclude data-endpoint="{endpoint}" novalidate>'
        '<fieldset><legend>의견</legend>'
        f'<label class="field">의견 종류<select name="kind">{opts}</select></label>'
        '<label class="field">내용 <em>필수</em>'
        '<textarea name="message" rows="6" placeholder="예) 자료 비교표에 라이선스도 다시 보였으면 좋겠어요 / ○○ 자료 페이지가 연구에 큰 도움이 됐어요"></textarea></label>'
        '<label class="field">답변 받을 이메일 (선택)'
        '<input type="email" name="contact" placeholder="name@example.ac.kr" autocomplete="email"></label>'
        '</fieldset>'
        '<div class="hp-field" aria-hidden="true"><label>웹사이트 (비워 두세요)<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
        '<div class="form-actions"><button type="submit" class="md-button md-button--primary"'
        + ("" if endpoint else " disabled") + '>의견 보내기</button></div>'
        '<p class="hint">의견은 운영자에게만 전달되며 공개되지 않습니다.</p>'
        '<p class="form-message" role="status" aria-live="polite"></p>'
        '</form>'
    )


def domain_counts(datasets: list[dict]) -> str:
    """홈 소개 문구용 분야별 개수 (메뉴 기준: 교차 수록 포함) — 예) 대기 29 · 해양 21 · 해빙 16"""
    n = {k: 0 for k in DOMAINS}
    for (dom, _g), entries in placements(datasets).items():
        n[dom] = n.get(dom, 0) + len(entries)
    parts = []
    for k, v in n.items():
        label = domain_label(k)
        parts.append(f"{label.lower() if is_en() else label} {v}")
    return " · ".join(parts)


def on_page_markdown(markdown, page, config, files):
    if "<!-- SUBSCRIBE_FORM -->" in markdown:
        markdown = markdown.replace("<!-- SUBSCRIBE_FORM -->", subscribe_form(config))
    if "<!-- FEEDBACK_FORM -->" in markdown:
        markdown = markdown.replace("<!-- FEEDBACK_FORM -->", feedback_form(config))
    if "<!-- SUGGEST_FORM -->" in markdown:
        markdown = markdown.replace("<!-- SUGGEST_FORM -->", suggest_form(config))
    if "<!-- DOMAIN_SUMMARY -->" in markdown:
        markdown = markdown.replace("<!-- DOMAIN_SUMMARY -->", domain_summary(_datasets))
    if "<!-- RECENT_NOTICES -->" in markdown:
        markdown = markdown.replace("<!-- RECENT_NOTICES -->", "\n".join(notice_rows(all_notices(_datasets)[:6], "datasets/")))
    if "<!-- COMPARE_APP -->" in markdown:
        markdown = markdown.replace("<!-- COMPARE_APP -->", compare_app(_datasets))
    if "<!-- RES_NOTE -->" in markdown:
        markdown = markdown.replace("<!-- RES_NOTE -->", "\n".join(res_note()))
    if "<!-- DISCLAIMER -->" in markdown:
        markdown = markdown.replace("<!-- DISCLAIMER -->", disclaimer())
    if "<!-- DATASET_COUNT -->" in markdown:
        markdown = markdown.replace("<!-- DATASET_COUNT -->", str(len(_datasets)))
    if "<!-- DOMAIN_COUNTS -->" in markdown:
        markdown = markdown.replace("<!-- DOMAIN_COUNTS -->", domain_counts(_datasets))
    if "<!-- SITE_CITATION -->" in markdown:
        c = (config.get("extra") or {}).get("site_citation") or {}
        markdown = markdown.replace("<!-- SITE_CITATION -->", "\n".join(site_citation_lines(c if isinstance(c, dict) else {})))
    if "<!-- SITE_DOI -->" in markdown:
        c = (config.get("extra") or {}).get("site_citation") or {}
        doi = c.get("doi", "") if isinstance(c, dict) else ""
        markdown = markdown.replace("<!-- SITE_DOI -->", f"`{doi}`" if doi else "")  # 링크 없이 글자로만
    if "<!-- BUILD_DATE -->" in markdown:
        markdown = markdown.replace("<!-- BUILD_DATE -->", date.today().isoformat())
    return markdown


def _cut(text: str, n: int = 150) -> str:
    """검색 결과 설명용: n자 안에서 문장 단위로 자름"""
    t = oneline(re.sub(r"`|\*\*|\*", "", str(text or ""))).replace('"', "'").replace("<", "‹").replace(">", "›")
    if len(t) <= n:
        return t
    cut = t[:n]
    for sep in (". ", "다. ", "요. ", "; "):
        i = cut.rfind(sep)
        if i > n * 0.5:
            return cut[: i + len(sep)].strip()
    return cut.rstrip() + "…"


def _ld(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


# 검색 결과 제목·설명 (데이터셋 외 자동 생성 페이지)
PAGE_SEO = {
    "datasets/index.md": (("전체 데이터셋 목록 — 재분석·위성·관측 기후자료 한눈에 비교", "All datasets — compare reanalyses, satellite and observational climate data"),
                          ("대기·해양·해빙 재분석, 위성자료, 관측 기반 분석장을 기간·해상도·시간 간격·제공 상태로 한 표에서 비교하고, 원하는 자료를 골라 나란히 볼 수 있습니다.",
                           "Compare atmospheric, ocean and sea-ice reanalyses, satellite products and observational analyses by period, resolution, interval and status, and put any of them side by side.")),
    "notices.md": (("중요 공지 — 기후자료 제공 중단·서비스 이전·품질 문제 모음", "Notices — discontinuations, service migrations and quality issues of climate datasets"),
                   ("ERA5·JRA-3Q·NCEP 재분석, OISST·ERSST, 해빙 위성자료 등의 제공 중단, 버전 교체, 서비스 이전, 품질 문제 공지를 원문 링크와 함께 최신순으로 모았습니다.",
                    "Discontinuations, version changes, service migrations and quality issues for ERA5, JRA-3Q, NCEP reanalyses, OISST, ERSST, sea-ice satellite products and more, newest first with links to the original announcements.")),
    "transitions.md": (("세대별 비교 — 재분석·관측 자료 버전이 바뀌면 무엇이 달라지나", "Generation changes — what changes between dataset generations and versions"),
                       ("ERA-Interim→ERA5, JRA-55→JRA-3Q, ERSST v5→v6, CS2SMOS→CS3SMOS 등 세대·버전이 바뀔 때 기간·해상도·관측 입력·변수가 어떻게 달라지는지와 바꿔 쓸 때 주의할 점.",
                        "ERA-Interim→ERA5, JRA-55→JRA-3Q, ERSST v5→v6, CS2SMOS→CS3SMOS and more: how period, resolution, observational input and variables change, and what to watch when switching.")),
}


def on_page_context(context, page, config, nav):
    """연필(수정) 버튼을 숨기고(저장소 비노출), 검색엔진용 제목·설명·구조화 데이터를 붙입니다."""
    page.edit_url = None
    if page.meta is None:
        page.meta = {}
    src = page.file.src_uri
    site = config.get("site_name")
    lang = "en" if is_en() else "ko"
    base = config.get("site_url") or "/"
    m = re.match(r"^datasets/(.+)\.md$", src)
    by_id = {d["id"]: d for d in _datasets}
    if m and m.group(1) in by_id:
        d = by_id[m.group(1)]
        page.meta["title"] = (f"{d['name']} — access, variables, citation & notices" if is_en()
                              else f"{d['name']} — 받는 방법·변수·인용·공지 정리")
        lead = (f"{d['name']}: access, variables, resolution, citation/DOIs and notices. "
                if is_en() else f"{d['name']} 받는 방법, 변수(순간값·평균·누적), 해상도, 논문 인용·DOI, 최신 공지 정리. ")
        room = 165 - len(lead)
        page.meta["description"] = (lead + _cut(d["summary"], room)).strip() if room > 40 else lead.strip()
        cit = d["citations"]
        dois = [f"https://doi.org/{c['doi']}" for c in (cit.get("dataset") or []) + (cit.get("papers") or []) if c.get("doi")]
        p = d["period"]
        end = ".." if str(p.get("end")) == "present" else str(p.get("end"))
        dataset = {
            "@type": "Dataset",
            "name": d["name"],
            "description": _cut(d["summary"], 400),
            "creator": {"@type": "Organization", "name": oneline(d["provider"])},
            "temporalCoverage": f"{p['start']}/{end}",
        }
        if d.get("full_name"):
            dataset["alternateName"] = oneline(d["full_name"])
        if dois:
            dataset["identifier"] = dois[:3]
        official = [a["url"] for a in d.get("access") or [] if a.get("url")]
        if official:
            dataset["url"] = official[0]
            dataset["sameAs"] = official[:3]
        page.meta["jsonld"] = _ld({
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": page.meta["title"],
            "description": page.meta["description"],
            "inLanguage": lang,
            "url": page.canonical_url,
            "isPartOf": {"@type": "WebSite", "name": site, "url": base},
            "about": dataset,
        })
    elif src.startswith("domains/"):
        dom = src.split("/")[1].removesuffix(".md")
        names = ", ".join(d["name"] for d in _datasets if d["domain"] == dom)
        page.meta["title"] = (f"{domain_label(dom)} datasets — reanalyses, satellite and observational data"
                              if is_en() else f"{domain_label(dom)} 자료 — 재분석·위성·관측 자료 목록")
        page.meta["description"] = _cut(domain_intro(dom) + " " + names, 160)
    elif src in PAGE_SEO:
        (tko, ten), (dko, den) = PAGE_SEO[src]
        page.meta["title"] = ten if is_en() else tko
        page.meta["description"] = den if is_en() else dko
    if page.is_homepage:
        other = "기후데이터 길잡이" if is_en() else "Korean Climate Data Guide"
        c = (config.get("extra") or {}).get("site_citation") or {}
        page.meta["jsonld"] = _ld({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site,
            "alternateName": [other, "data4researchers"],
            "url": base,
            "inLanguage": lang,
            "description": config.get("site_description"),
            **({"sameAs": [f"https://doi.org/{c['doi']}"]} if isinstance(c, dict) and c.get("doi") else {}),
        })
    return context


def on_serve(server, config, builder):
    # 로컬 미리보기(mkdocs serve) 중 YAML을 고치면 바로 다시 빌드
    server.watch(str(DATA_DIR_EN if is_en() else DATA_DIR))
    return server
