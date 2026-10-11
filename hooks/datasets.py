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

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "datasets"

# 위쪽 메뉴 탭(분야)과 그 안의 소분류 — 순서대로 표시됩니다
DOMAINS = {
    "atmosphere": ("대기", ["재분석", "위성 관측 미동화 재분석"]),
    "ocean": ("해양", ["재분석", "관측 기반 분석장", "모델 강제력"]),
    "seaice": ("해빙", ["재분석", "관측 기반 분석장", "위성 관측 자료"]),
}
DOMAIN_INTRO = {
    "atmosphere": "전지구 대기 재분석자료입니다. 현역 자료와 함께, 옛 논문 재현이나 비교 연구에 필요한 이전 세대 자료도 정리했습니다.",
    "ocean": "해양 재분석, 관측 기반 해수면온도(SST) 분석장, 해양·해빙 모델 구동용 대기 강제력 자료입니다.",
    "seaice": "해빙 농도·두께·부피 자료입니다. 모델 기반 재분석, 관측 기반 분석장, 위성 관측 자료로 나눠 정리했습니다.",
}
# 소분류 아래에 붙는 한 줄 설명 (없으면 생략)
GROUP_INTRO = {
    "위성 관측 미동화 재분석": "위성 관측을 쓰지 않고 지표기압·해상풍 같은 전통 관측만 동화한 재분석입니다. "
                       "관측 체계 변화의 영향을 줄여 20세기 전체 또는 장기 변동 연구에 씁니다.",
}
NAV_PLACEHOLDER = "__DATA_SECTIONS__"

STATUS = {
    "active": ("정상 제공", "status-active"),
    "delayed": ("갱신 지연", "status-delayed"),
    "deprecated": ("지원 축소·대체 예정", "status-deprecated"),
    "ended": ("갱신 종료", "status-ended"),
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
TEMPORAL_SHORT = ["1시간", "3시간", "6시간", "1일", "7일", "1개월"]
TEMPORAL_HOURS = {"1시간": 1, "3시간": 3, "6시간": 6, "1일": 24, "7일": 168, "1개월": 720}

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
    head = '??? warning "해상도 표기 주의 — 꼭 읽어주세요"' if collapsed else '!!! warning "해상도 표기 주의"'
    return [head, ""] + [f"    - {x}" for x in RES_NOTE] + [""]


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
    return f'<span class="status-badge {cls}">{label}</span>'


def doi_link(doi: str) -> str:
    return f'[{nt(doi)}](https://doi.org/{doi})'


def oneline(text: str) -> str:
    return " ".join(str(text).split())


def period_text(p: dict) -> str:
    end = "현재" if str(p.get("end")) == "present" else p.get("end")
    return f"{p['start']} ~ {end}"


def domain_label(key: str) -> str:
    return DOMAINS[key][0]


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
    if not v.get("groups") or not all(g.get("name") and g.get("items") for g in v["groups"]):
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
    if REQUIRE_KIND and not (d.get("time_convention") or {}).get("summary"):
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


def sort_key(d: dict):
    dom = list(DOMAINS).index(d["domain"])
    grp = DOMAINS[d["domain"]][1].index(d["group"])
    return (dom, grp, d.get("order", 999), d["name"].lower())


def load_datasets(paths=None) -> list[dict]:
    out = []
    for src in sorted(paths or DATA_DIR.glob("*.yaml")):
        src = Path(src)
        try:
            d = yaml.safe_load(src.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise PluginError(f"{src.name}: YAML 문법 오류 — {e}")
        validate(d, src)
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
    return sorted(out, key=sort_key)


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
    return out


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
    label = KIND[it["kind"]]
    if it.get("period") and it["kind"] in ("mean", "accum", "max", "min"):
        label = f"{it['period']} {label}"
    elif it.get("period") and it["kind"] == "instant":
        label = f"{label} ({it['period']})"
    return f' <span class="kind kind-{it["kind"]}">{label}</span>'


def variables_block(v: dict, tc: dict | None = None) -> list[str]:
    L = ["## 활용 가능한 변수", ""]
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
        + " ".join(f'<span class="kind kind-{k}">{lab}</span>' for k, lab in KIND.items())
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
        L += ["**BibTeX** (참고문헌 관리 프로그램용)", "", "```bibtex", c["bibtex"].rstrip(), "```", ""]
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
        kind = {"active": "note", "delayed": "warning", "deprecated": "warning", "ended": "danger"}[d["status"]]
        title = {"active": "현재 상태", "delayed": "갱신 지연", "deprecated": "대체 예정", "ended": "갱신 종료"}[d["status"]]
        L += [f'!!! {kind} "{title}"', ""]
        L += ["    " + oneline(d.get("status_note", "")), ""]
        s = d.get("successor")
        if s and s.get("name") not in (None, "없음"):
            target = f"[{nt(s['name'])}]({s['url']})" if s.get("url") else nt(s["name"])
            L += [f"    **후속 자료:** {target} — {oneline(s.get('note', ''))}", ""]

    # 한눈에 보기
    r = d.get("resolution") or {}
    where = f"{domain_label(d['domain'])} › {d['group']}"
    for x in d.get("also_in") or []:
        where += f" (교차 수록: {domain_label(x['domain'])} › {x['group']})"
    rows = [
        ("분류", where),
        ("종류", CATEGORY[d["category"]]),
        ("분야", ", ".join(d.get("domains") or [])),
        ("제공 기관", nt(d["provider"])),
        ("기간", period_text(d["period"])),
        ("제공 해상도", f"{r.get('spatial_short')} · {r.get('temporal_short')} 간격 (km는 적도 기준 근사)"),
        ("수평 해상도 (세부)", r.get("spatial")),
        ("연직 해상도", r.get("vertical")),
        ("시간 해상도 (세부)", r.get("temporal")),
        ("갱신 주기", d.get("update")),
        ("라이선스", d.get("license")),
        ("계정 필요", "예" if d.get("account_required") else "아니오"),
    ]
    L += ["## 한눈에 보기", "", "| 항목 | 내용 |", "|---|---|"]
    L += [f"| {k} | {oneline(v)} |" for k, v in rows if v]
    if d["period"].get("note"):
        L += ["", f"*기간 참고:* {oneline(d['period']['note'])}"]
    L += [""] + res_note()
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
            label, kind = LEVEL[n["level"]]
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

    return "\n".join(L)


STATUS_ORDER = {"active": 0, "delayed": 1, "deprecated": 2, "ended": 3}


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
            f"<td>{CATEGORY[d['category']]}</td>"
            f'<td class="nowrap" data-sort="{d["period"]["start"]}">{period_text(d["period"])}</td>'
            f'<td class="nowrap" data-sort="{km}" title="{html.escape(oneline(r.get("spatial") or ""))}">{sp}</td>'
            f'<td class="nowrap" data-sort="{hrs}" title="{html.escape(oneline(r.get("temporal") or ""))}">{tm}</td>'
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
        f'<a class="domain-chip domain-{dom}" href="#{dom}"><strong>{label}</strong>'
        f'<span>{sum(len(pl.get((dom, g), [])) for g in groups)}개</span></a>'
        for dom, (label, groups) in DOMAINS.items()
    )
    L[L.index("# 전체 데이터셋 목록") + 2:L.index("# 전체 데이터셋 목록") + 2] = [f'<nav class="domain-jump">{chips}</nav>', ""]
    for dom, (label, groups) in DOMAINS.items():
        n = sum(len(pl.get((dom, g), [])) for g in groups)
        L += [f'<h2 class="domain-head domain-{dom}" id="{dom}">{label}<span class="domain-count">{n}개 자료</span></h2>', ""]
        for g in groups:
            if (dom, g) in pl:
                L += [f"### {g} {{ .group-head }}", ""]
                if g in GROUP_INTRO:
                    L += [f'<p class="group-intro">{GROUP_INTRO[g]}</p>', ""]
                L += group_table(pl[(dom, g)], "", "../compare/") + [""]
    return "\n".join(L) + "\n"


def render_domain(dom: str, datasets: list[dict]) -> str:
    label, groups = DOMAINS[dom]
    pl = placements(datasets)
    L = ["---", "hide:", "  - navigation", "  - toc", "---", "", f"# {label}", "", DOMAIN_INTRO[dom], "",
         "표의 왼쪽 칸을 2개 이상 체크하면 바로 비교할 수 있고, 열 이름을 누르면 정렬됩니다.", ""] + res_note()
    for g in groups:
        if (dom, g) in pl:
            L += [f"## {g} {{ .group-head }}", ""]
            if g in GROUP_INTRO:
                L += [f'<p class="group-intro">{GROUP_INTRO[g]}</p>', ""]
            L += group_table(pl[(dom, g)], "../../datasets/", "../../compare/") + [""]
    if any(cross for g in groups for _, _, cross in pl.get((dom, g), [])):
        L += ["↔ 다른 분야 페이지에도 함께 실린 자료입니다.", ""]
    return "\n".join(L) + "\n"


def all_notices(datasets: list[dict]) -> list[tuple[dict, dict]]:
    pairs = [(d, n) for d in datasets for n in d["notices"]]
    return sorted(pairs, key=lambda p: str(p[1]["date"]), reverse=True)


def notice_rows(pairs, link_prefix: str) -> list[str]:
    L = ["| 날짜 | 데이터셋 | 구분 | 내용 |", "|---|---|---|---|"]
    for d, n in pairs:
        label, _ = LEVEL[n["level"]]
        L.append(
            f"| {n['date']} | [{nt(d['name'])}]({link_prefix}{d['id']}.md) "
            f"| <span class=\"level-{n['level']}\">{label}</span> | [{n['title']}]({n['source']}) |"
        )
    return L


def render_notices(datasets: list[dict]) -> str:
    """중요 공지 — 데이터셋·공지 구분으로 걸러 볼 수 있는 표"""
    pairs = all_notices(datasets)
    opts = ""
    for dom, (label, _) in DOMAINS.items():
        items = [d for d in datasets if d["domain"] == dom and d["notices"]]
        if items:
            opts += f'<optgroup label="{label}">' + "".join(
                f'<option value="{d["id"]}">{html.escape(d["name"])} ({len(d["notices"])})</option>' for d in items
            ) + "</optgroup>"
    lv = "".join(
        f'<label class="check"><input type="checkbox" name="nlevel" value="{k}" checked> '
        f'<span class="level-{k}">{LEVEL[k][0]}</span></label>'
        for k in LEVEL
    )
    rows = "".join(
        f'<tr data-dataset="{d["id"]}" data-level="{n["level"]}">'
        f'<td class="nowrap">{n["date"]}</td>'
        f'<td><a href="../datasets/{d["id"]}/">{nt(html.escape(d["name"]))}</a></td>'
        f'<td><span class="level-{n["level"]}">{LEVEL[n["level"]][0]}</span></td>'
        f'<td><a href="{html.escape(n["source"])}" target="_blank" rel="noopener">{html.escape(n["title"])}</a></td></tr>'
        for d, n in pairs
    )
    return "\n".join([
        "# 중요 공지", "",
        "데이터 제공 중단, 서비스 이전, 품질 문제처럼 **분석에 영향을 주는 공지**를 최신순으로 모았습니다.",
        "각 항목의 링크는 원문 공지로 연결됩니다. 새 공지를 메일로 받고 싶다면 [중요 공지 알림 신청](subscribe.md)을 이용하세요.", "",
        '<div class="notice-filter cdg-form" id="notice-filter">'
        '<label class="field">데이터셋<select id="nf-dataset"><option value="">전체 데이터셋</option>' + opts + "</select></label>"
        f'<div class="nf-levels"><span class="nf-label">구분</span>{lv}</div>'
        f'<p class="hint" id="nf-count">전체 {len(pairs)}건</p></div>',
        "",
        '<div><table id="notice-table">'
        "<thead><tr><th>날짜</th><th>데이터셋</th><th>구분</th><th>내용</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>",
        '<p class="hint" id="nf-empty" hidden>조건에 맞는 공지가 없습니다.</p>',
        "",
    ]) + "\n"


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
        block[0] = re.sub(r"\{#[^}]*\}", "", block[0]).rstrip()
        L += [f'<div class="gen-detail" id="{key}" markdown="1" hidden>', ""]
        L += block
        L += [f"[{nt(d['name'])} 페이지에서 보기 →](datasets/{d['id']}.md)", "", "</div>", ""]
    return "\n".join(L) + "\n"


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
            "id": d["id"], "name": d["name"], "domain": domain_label(d["domain"]), "group": d["group"],
            "category": CATEGORY[d["category"]], "provider": d["provider"], "status": badge(d["status"]),
            "period": period_text(d["period"]), "spatial": r.get("spatial_short") or "-",
            "temporal_s": r.get("temporal_short") or "-",
            "vertical": oneline(r.get("vertical") or "-"), "temporal": oneline(r.get("temporal") or "-"),
            "update": oneline(d.get("update") or "-"), "license": oneline(d.get("license") or "-"),
            "account": "예" if d.get("account_required") else "아니오",
            "time": oneline((d.get("time_convention") or {}).get("summary") or "-"),
            "nvars": sum(len(g["items"]) for g in d["variables"]["groups"]),
            "doi": dois[:2], "successor": s.get("name") or "-", "groups": groups,
        })
    return out


def compare_app(datasets: list[dict]) -> str:
    opts = ""
    for dom, (label, groups) in DOMAINS.items():
        items = [d for d in datasets if d["domain"] == dom]
        opts += f'<optgroup label="{label}">' + "".join(
            f'<option value="{d["id"]}">{html.escape(d["name"])}</option>' for d in items
        ) + "</optgroup>"
    selects = "".join(
        f'<label class="field">자료 {i + 1}<select class="cmp-select" data-slot="{i}">'
        f'<option value="">— 선택 —</option>{opts}</select></label>'
        for i in range(4)
    )
    chips = "".join(
        f'<button type="button" class="chip" data-q="{q}">{q}</button>'
        for q in ["강수", "기온", "바람", "기압", "복사", "습도", "해수면온도", "해빙", "염분", "플럭스"]
    )
    data = json.dumps(compare_data(datasets), ensure_ascii=False).replace("</", "<\\/")
    return (
        '<div class="cdg-form compare-controls"><div class="cmp-selects">' + selects + "</div>"
        '<label class="field">변수 찾기 <span class="hint">— 고른 자료들에서 같은 종류의 변수를 나란히 봅니다 (한국어 이름이나 변수명)</span>'
        '<input type="text" id="cmp-q" placeholder="예) 강수, tp, prate, sea ice"></label>'
        f'<div class="chips">{chips}</div></div>'
        '<p class="hint" id="cmp-empty">위에서 비교할 자료를 2개 이상 골라주세요. 고른 내용은 주소에 저장되어 그대로 공유할 수 있습니다.</p>'
        '<div class="table-scroll"><table id="cmp-table" hidden></table></div>'
        f'<script type="application/json" id="cmp-data">{data}</script>'
    )


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
        items: list = [{"개요": f"domains/{dom}.md"}]
        for g in groups:
            entries = []
            for d, name, cross in pl.get((dom, g), []):
                if cross:  # 같은 페이지를 두 번 넣지 않고 링크로 연결
                    entries.append({f"{name} ↔": f"{base_path}datasets/{d['id']}/"})
                else:
                    entries.append({name: f"datasets/{d['id']}.md"})
            if entries:
                items.append({g: entries})
        sections.append({label: items})
    return sections


def on_config(config):
    global _datasets, _site_url
    _datasets = load_datasets()
    _site_url = config.get("site_url") or "/"
    config["extra"]["disclaimer"] = DISCLAIMER
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

    for d in _datasets:
        add(f"datasets/{d['id']}.md", render_dataset(d, site_cite))
    for dom in DOMAINS:
        add(f"domains/{dom}.md", render_domain(dom, _datasets))
    add("datasets/index.md", render_index(_datasets))
    add("notices.md", render_notices(_datasets))
    add("transitions.md", render_transitions(_datasets))
    add("assets/notices.json", notices_json(_datasets))
    return files


def notices_json(datasets: list[dict]) -> str:
    """메일 알림용 공지 목록 (mailing/Code.gs 가 하루 한 번 읽어 새 공지만 발송).
    key 가 처음 보이는 공지만 '새 공지'로 취급하므로, 이미 올린 공지의 날짜·제목을 고치면 다시 발송됩니다."""
    out = []
    for d, n in all_notices(datasets):
        out.append({
            "key": f"{d['id']}|{n['date']}|{n['title']}",
            "date": str(n["date"]),
            "level": n["level"],
            "dataset_id": d["id"],
            "dataset_name": d["name"],
            "title": n["title"],
            "body": re.sub(r"\s+", " ", str(n.get("body") or "")).strip(),
            "source": n.get("source", ""),
            "url": site_page_url(d),
        })
    return json.dumps({"generated": date.today().isoformat(), "notices": out}, ensure_ascii=False, indent=1)


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
        ds += f'<p class="check-group-title">{label}</p><div class="check-grid">'
        ds += "".join(
            f'<label class="check"><input type="checkbox" name="datasets" value="{d["id"]}"> '
            f'{nt(d["name"])} {badge(d["status"])}</label>'
            for d in items
        )
        ds += "</div>"
    lv = "".join(
        f'<label class="check"><input type="checkbox" name="levels" value="{key}"> '
        f'<span class="level-{key}">{LEVEL[key][0]}</span><span class="hint"> — {desc}</span></label>'
        for key, desc in [
            ("critical", "제공 중단, 서비스 종료처럼 분석에 바로 영향을 주는 공지"),
            ("warning", "품질 문제, 재처리, 종료 예고"),
            ("info", "주소 이전, 라이선스 변경, 새 자료 공개"),
        ]
    )
    html = (
        f'<form id="subscribe-form" class="cdg-form" data-endpoint="{endpoint}" novalidate>'
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
    return pre + html


def suggest_form(config) -> str:
    """데이터셋 추가 제안 폼. 운영자 메일(Apps Script)로 바로 보냅니다."""
    endpoint = _forms_config(config).get("suggest_endpoint") or ""
    cats = "".join(f'<option value="{v}">{v}</option>' for v in CATEGORY.values())
    existing = ", ".join(nt(d["name"]) for d in _datasets)
    pre = "" if endpoint else (
        '!!! info "제안 접수는 준비 중입니다"\n\n'
        "    그동안은 data4researchers@gmail.com 으로 메일을 보내주세요.\n\n"
    )
    return pre + (
        f'<details class="hint"><summary>이미 있는 데이터셋 {len(_datasets)}개 보기</summary><p>{existing}</p></details>'
        f'<form id="suggest-form" class="cdg-form" data-endpoint="{endpoint}" novalidate>'
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
    )


def on_page_markdown(markdown, page, config, files):
    if "<!-- SUBSCRIBE_FORM -->" in markdown:
        markdown = markdown.replace("<!-- SUBSCRIBE_FORM -->", subscribe_form(config))
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
        markdown = markdown.replace("<!-- DISCLAIMER -->", DISCLAIMER)
    if "<!-- DATASET_COUNT -->" in markdown:
        markdown = markdown.replace("<!-- DATASET_COUNT -->", str(len(_datasets)))
    if "<!-- SITE_CITATION -->" in markdown:
        c = (config.get("extra") or {}).get("site_citation") or {}
        markdown = markdown.replace("<!-- SITE_CITATION -->", "\n".join(site_citation_lines(c if isinstance(c, dict) else {})))
    if "<!-- SITE_DOI -->" in markdown:
        c = (config.get("extra") or {}).get("site_citation") or {}
        doi = c.get("doi", "") if isinstance(c, dict) else ""
        markdown = markdown.replace("<!-- SITE_DOI -->", f"[{doi}](https://doi.org/{doi})" if doi else "")
    if "<!-- BUILD_DATE -->" in markdown:
        markdown = markdown.replace("<!-- BUILD_DATE -->", date.today().isoformat())
    return markdown


def on_page_context(context, page, config, nav):
    """연필(수정) 버튼을 모든 페이지에서 숨깁니다 — 방문자에게 저장소를 노출하지 않음."""
    page.edit_url = None
    return context


def on_serve(server, config, builder):
    # 로컬 미리보기(mkdocs serve) 중 YAML을 고치면 바로 다시 빌드
    server.watch(str(DATA_DIR))
    return server
