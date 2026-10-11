"""MkDocs hook: data/datasets/*.yaml 파일로 사이트의 데이터 관련 페이지를 모두 자동 생성합니다.

- 각 YAML → datasets/<id>.md (가상 파일, 디스크에 쓰지 않음)
- 분야별 소개 → domains/<atmosphere|ocean|seaice>.md
- 전체 목록 → datasets/index.md, 공지 모음 → notices.md
- 위쪽 메뉴(대기·해양·해빙)도 YAML의 domain/group/order 값으로 자동 구성
- 본문의 <!-- DOMAIN_SUMMARY -->, <!-- RECENT_NOTICES -->, <!-- SUBSCRIBE_FORM -->, <!-- SUGGEST_FORM --> 자리를 채움

YAML에 필수 항목이 빠졌거나 값이 잘못되면 빌드가 실패합니다.
(자동화가 만든 PR도 이 검증을 통과해야 머지할 수 있게 하기 위함)
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "datasets"

# 위쪽 메뉴 탭(분야)과 그 안의 소분류 — 순서대로 표시됩니다
DOMAINS = {
    "atmosphere": ("대기", ["재분석", "장기(20세기)·관측 제한 재분석"]),
    "ocean": ("해양", ["재분석", "관측 기반 분석장", "모델 강제력"]),
    "seaice": ("해빙", ["재분석", "관측 기반 분석장", "위성 관측 자료"]),
}
DOMAIN_INTRO = {
    "atmosphere": "전지구 대기 재분석자료입니다. 현역 자료와 함께, 옛 논문 재현이나 비교 연구에 필요한 이전 세대 자료도 정리했습니다.",
    "ocean": "해양 재분석, 관측 기반 해수면온도(SST) 분석장, 해양·해빙 모델 구동용 대기 강제력 자료입니다.",
    "seaice": "해빙 농도·두께·부피 자료입니다. 모델 기반 재분석, 관측 기반 분석장, 위성 관측 자료로 나눠 정리했습니다.",
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
PERIOD_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

_datasets: list[dict] = []


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
    return L


def variables_block(v: dict) -> list[str]:
    L = ["## 활용 가능한 변수", ""]
    if v.get("note"):
        L += [oneline(v["note"]), ""]
    for g in v["groups"]:
        L += [f"### {g['name']}", "", '<div class="var-list" markdown>', ""]
        L += [f"- {oneline(it)}" for it in g["items"]]
        L += ["", "</div>", ""]
    if v.get("full_list"):
        L += [f"전체 변수 목록은 [공식 문서]({v['full_list']})에서 확인하세요.", ""]
    return L


def render_dataset(d: dict, site_cite: str) -> str:
    L: list[str] = []
    L += [f"# {nt(d['name'])}", ""]
    if d.get("full_name"):
        L += [f"*{d['full_name']}*", ""]
    L += [
        badge(d["status"])
        + f' <span class="verified">마지막 확인 {d["last_verified"]}</span>'
        + f' <a class="subscribe-link" href="../../subscribe/?dataset={d["id"]}">이 데이터셋 변경 알림 받기</a>',
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
        ("수평 해상도", r.get("spatial")),
        ("연직 해상도", r.get("vertical")),
        ("시간 해상도", r.get("temporal")),
        ("갱신 주기", d.get("update")),
        ("라이선스", d.get("license")),
        ("계정 필요", "예" if d.get("account_required") else "아니오"),
    ]
    L += ["## 한눈에 보기", "", "| 항목 | 내용 |", "|---|---|"]
    L += [f"| {k} | {oneline(v)} |" for k, v in rows if v]
    if d["period"].get("note"):
        L += ["", f"*기간 참고:* {oneline(d['period']['note'])}"]
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

    L += variables_block(d["variables"])

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
    L += citation_block(cit.get("dataset", []), "데이터셋 인용")
    L += citation_block(cit.get("papers", []), "논문 인용")
    if cit.get("acknowledgement"):
        L += ["### 사사(Acknowledgements) 작성", "", oneline(cit["acknowledgement"]), ""]
    L += [
        '!!! tip "이 정리가 도움이 되셨다면"',
        "",
        f"    논문의 Data availability나 Acknowledgements에 이 사이트를 함께 적어주세요. {site_cite}",
        "",
    ]

    if d.get("links"):
        L += ["## 참고 링크", ""]
        L += [f"- [{x['name']}]({x['url']})" for x in d["links"]]
        L.append("")

    return "\n".join(L)


def group_table(entries, link_prefix: str) -> list[str]:
    L = ["| 자료 | 종류 | 기간 | 상태 | 마지막 확인 |", "|---|---|---|---|---|"]
    for d, label, cross in entries:
        mark = " ↔" if cross else ""
        L.append(
            f"| [{nt(label)}]({link_prefix}{d['id']}.md){mark} | {CATEGORY[d['category']]} | {period_text(d['period'])} "
            f"| {badge(d['status'])} | {d['last_verified']} |"
        )
    return L


def render_index(datasets: list[dict]) -> str:
    L = [
        "# 전체 데이터셋 목록", "",
        f"모두 {len(datasets)}개 자료를 공식 출처에서 직접 확인해 정리했습니다. **마지막 확인** 날짜 이후 바뀌었을 수 있습니다.", "",
        "↔ 표시는 다른 분야에도 함께 실린 자료입니다.", "",
    ]
    pl = placements(datasets)
    for dom, (label, groups) in DOMAINS.items():
        L += [f"## {label}", ""]
        for g in groups:
            if (dom, g) in pl:
                L += [f"### {g}", ""] + group_table(pl[(dom, g)], "") + [""]
    return "\n".join(L) + "\n"


def render_domain(dom: str, datasets: list[dict]) -> str:
    label, groups = DOMAINS[dom]
    pl = placements(datasets)
    L = [f"# {label}", "", DOMAIN_INTRO[dom], ""]
    for g in groups:
        if (dom, g) in pl:
            L += [f"## {g}", ""] + group_table(pl[(dom, g)], "../datasets/") + [""]
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
    L = [
        "# 공지 모음", "",
        "데이터 제공 중단, 서비스 이전, 품질 문제처럼 **분석에 영향을 주는 공지**를 최신순으로 모았습니다.",
        "각 항목의 링크는 원문 공지로 연결됩니다. 새 공지를 메일로 받고 싶다면 [알림 신청](subscribe.md)을 이용하세요.", "",
    ]
    L += notice_rows(all_notices(datasets), "datasets/")
    return "\n".join(L) + "\n"


def render_transitions(datasets: list[dict]) -> str:
    pairs = [(d, t) for d in datasets for t in d.get("transitions") or []]
    L = [
        "# 전환 가이드", "",
        "재분석자료와 관측 자료는 세대가 바뀌거나 새 버전이 나오면 기간, 해상도, 관측 입력, 변수 이름이 함께 바뀝니다.",
        "옛 자료로 쓴 분석을 새 자료로 옮기거나, 두 자료를 비교할 때 무엇이 달라지는지 정리했습니다.", "",
        "| 이전 | 이후 | 분야 | 상태 |", "|---|---|---|---|",
    ]
    for d, t in pairs:
        state = "예정" if t["status"] == "planned" else "완료"
        L.append(
            f"| [{nt(t['from'])}](datasets/{d['id']}.md#{transition_anchor(t)}) | {nt(t['to'])} "
            f"| {domain_label(d['domain'])} | {state} |"
        )
    L.append("")
    for dom, (label, _) in DOMAINS.items():
        sub = [(d, t) for d, t in pairs if d["domain"] == dom]
        if not sub:
            continue
        L += [f"## {label}", ""]
        for d, t in sub:
            block = transition_block(d, t, "###", "datasets/")
            # 가이드 페이지에서는 앵커가 겹치지 않도록 접두어를 붙임
            block[0] = block[0].replace("{#to-", "{#g-" + d["id"] + "-to-")
            L += block
            L += [f"[{nt(d['name'])} 페이지에서 자세히 보기 →](datasets/{d['id']}.md)", ""]
    return "\n".join(L) + "\n"


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
    global _datasets
    _datasets = load_datasets()
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
    site_cite = config.get("extra", {}).get("site_citation", "")

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
    return files


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
            "    오픈하면 이 페이지에서 바로 신청할 수 있어요. 그전까지는 [공지 모음](notices.md)을 확인해 주세요.\n\n"
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
        '<label class="check consent"><input type="checkbox" name="consent" required> '
        '<a href="../privacy/">개인정보 수집·이용</a>에 동의합니다 (필수)</label>'
        '<div class="form-actions"><button type="submit" class="md-button md-button--primary">알림 신청</button></div>'
        '<p class="form-message" role="status" aria-live="polite"></p>'
        '</form>'
    )
    return pre + html


def suggest_form(config) -> str:
    """데이터셋 추가 제안 폼. 지금은 내용을 채운 GitHub 이슈로 연결합니다."""
    repo = (config.get("repo_url") or "").rstrip("/")
    endpoint = _forms_config(config).get("suggest_endpoint") or ""
    cats = "".join(f'<option value="{v}">{v}</option>' for v in CATEGORY.values())
    existing = ", ".join(nt(d["name"]) for d in _datasets)
    direct = (
        '<button type="submit" class="md-button md-button--primary" data-action="direct">바로 보내기</button>'
        if endpoint else ""
    )
    return (
        f'<details class="hint"><summary>이미 있는 데이터셋 {len(_datasets)}개 보기</summary><p>{existing}</p></details>'
        f'<form id="suggest-form" class="cdg-form" data-repo="{repo}" data-endpoint="{endpoint}" novalidate>'
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
        '<input type="text" name="contact" placeholder="이름·소속 — 기여자 목록에 올려드려요"></label>'
        '</fieldset>'
        '<div class="form-actions">'
        f'{direct}'
        '<button type="submit" class="md-button' + ("" if endpoint else " md-button--primary") + '" data-action="github">'
        'GitHub 이슈로 제안하기</button></div>'
        '<p class="hint">GitHub 이슈로 제안하면 새 창에서 내용이 채워진 제안서가 열리고, 제출(<strong>Create</strong>) 버튼을 누르면 됩니다. '
        'GitHub 계정이 필요합니다.' + ("" if endpoint else " 계정 없이 보내는 기능은 메일 알림과 함께 추가될 예정입니다.") + '</p>'
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
    if "<!-- DATASET_COUNT -->" in markdown:
        markdown = markdown.replace("<!-- DATASET_COUNT -->", str(len(_datasets)))
    if "<!-- BUILD_DATE -->" in markdown:
        markdown = markdown.replace("<!-- BUILD_DATE -->", date.today().isoformat())
    return markdown


def on_page_context(context, page, config, nav):
    """페이지 제목 옆 연필(수정) 버튼이 실제로 고쳐야 할 파일을 열도록 맞춥니다."""
    repo = (config.get("repo_url") or "").rstrip("/")
    src = page.file.src_uri
    ids = {d["id"] for d in _datasets}
    m = re.match(r"^datasets/(.+)\.md$", src)
    if src in ("datasets/index.md", "notices.md", "transitions.md") or src.startswith("domains/"):
        page.edit_url = None  # 자동 생성 페이지 — 고칠 파일이 따로 없음
    elif m and m.group(1) in ids:
        page.edit_url = f"{repo}/edit/main/data/datasets/{m.group(1)}.yaml"
    return context


def on_serve(server, config, builder):
    # 로컬 미리보기(mkdocs serve) 중 YAML을 고치면 바로 다시 빌드
    server.watch(str(DATA_DIR))
    return server
