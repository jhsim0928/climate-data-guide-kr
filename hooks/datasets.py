"""MkDocs hook: data/datasets/*.yaml 파일로 데이터셋 페이지를 자동 생성합니다.

- 각 YAML → docs/datasets/<id>.md (가상 파일, 디스크에 쓰지 않음)
- 데이터셋 목록 → datasets/index.md
- 전체 공지 모음 → notices.md
- 본문에 있는 <!-- STATUS_SUMMARY -->, <!-- RECENT_NOTICES --> 자리를 채움

YAML에 필수 항목이 빠졌거나 값이 잘못되면 빌드가 실패합니다.
(자동화가 만든 PR도 이 검증을 통과해야 머지할 수 있게 하기 위함)
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "datasets"

STATUS = {
    "active": ("정상 제공", "status-active"),
    "delayed": ("갱신 지연", "status-delayed"),
    "deprecated": ("지원 축소·대체 예정", "status-deprecated"),
    "ended": ("갱신 종료", "status-ended"),
}
CATEGORY = {
    "reanalysis": "재분석자료",
    "satellite": "위성자료",
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
    "id", "name", "category", "provider", "status", "period",
    "summary", "access", "citations", "last_verified",
]
DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")

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


# ── 검증 ────────────────────────────────────────────────────
def validate(d: dict, src: Path) -> None:
    errors = [f"필수 항목 누락: {k}" for k in REQUIRED if k not in d]
    if d.get("id") and d["id"] != src.stem:
        errors.append(f"id({d['id']})와 파일명({src.stem})이 달라요")
    if d.get("status") not in STATUS:
        errors.append(f"status는 {list(STATUS)} 중 하나여야 해요")
    if d.get("category") not in CATEGORY:
        errors.append(f"category는 {list(CATEGORY)} 중 하나여야 해요")
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
    if errors:
        raise PluginError(f"{src.name} 검증 실패:\n  - " + "\n  - ".join(errors))


def load_datasets() -> list[dict]:
    out = []
    for src in sorted(DATA_DIR.glob("*.yaml")):
        d = yaml.safe_load(src.read_text(encoding="utf-8"))
        validate(d, src)
        d["notices"] = sorted(d.get("notices") or [], key=lambda n: str(n["date"]), reverse=True)
        out.append(d)
    return sorted(out, key=lambda d: d["name"].lower())


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


def render_dataset(d: dict, site_cite: str) -> str:
    L: list[str] = []
    L += [f"# {nt(d['name'])}", ""]
    if d.get("full_name"):
        L += [f"*{d['full_name']}*", ""]
    L += [badge(d["status"]) + f' <span class="verified">마지막 확인 {d["last_verified"]}</span>', ""]

    # 상태 경고
    if d["status"] != "active" or d.get("status_note"):
        kind = {"active": "note", "delayed": "warning", "deprecated": "warning", "ended": "danger"}[d["status"]]
        title = {"active": "현재 상태", "delayed": "갱신 지연", "deprecated": "대체 예정", "ended": "갱신 종료"}[d["status"]]
        L += [f'!!! {kind} "{title}"', ""]
        L += ["    " + oneline(d.get("status_note", "")), ""]
        s = d.get("successor")
        if s and s.get("name") not in (None, "없음"):
            L += [f"    **후속 자료:** [{nt(s['name'])}]({s['url']}) — {oneline(s.get('note', ''))}", ""]

    # 한눈에 보기
    r = d.get("resolution") or {}
    rows = [
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
    L += [f"| {k} | {v} |" for k, v in rows if v]
    if d["period"].get("note"):
        L += ["", f"*기간 참고:* {oneline(d['period']['note'])}"]
    L += ["", "## 개요", "", oneline(d["summary"]), ""]

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


def render_index(datasets: list[dict]) -> str:
    L = [
        "# 데이터셋 목록", "",
        "모든 정보는 공식 출처를 직접 확인해 정리했고, **마지막 확인** 날짜 이후 바뀌었을 수 있습니다.", "",
        "| 데이터셋 | 종류 | 기간 | 상태 | 마지막 확인 |",
        "|---|---|---|---|---|",
    ]
    for d in datasets:
        L.append(
            f"| [{nt(d['name'])}]({d['id']}.md) | {CATEGORY[d['category']]} | {period_text(d['period'])} "
            f"| {badge(d['status'])} | {d['last_verified']} |"
        )
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
        "각 항목의 링크는 원문 공지로 연결됩니다.", "",
    ]
    L += notice_rows(all_notices(datasets), "datasets/")
    return "\n".join(L) + "\n"


# ── MkDocs 이벤트 ────────────────────────────────────────────
def on_files(files, config):
    global _datasets
    _datasets = load_datasets()
    site_cite = config.get("extra", {}).get("site_citation", "")

    def add(uri: str, content: str):
        existing = files.get_file_from_path(uri)
        if existing:
            files.remove(existing)
        files.append(File.generated(config, uri, content=content))

    for d in _datasets:
        add(f"datasets/{d['id']}.md", render_dataset(d, site_cite))
    add("datasets/index.md", render_index(_datasets))
    add("notices.md", render_notices(_datasets))
    return files


def on_page_markdown(markdown, page, config, files):
    if "<!-- STATUS_SUMMARY -->" in markdown:
        L = ["| 데이터셋 | 상태 | 기간 |", "|---|---|---|"]
        L += [f"| [{nt(d['name'])}](datasets/{d['id']}.md) | {badge(d['status'])} | {period_text(d['period'])} |" for d in _datasets]
        markdown = markdown.replace("<!-- STATUS_SUMMARY -->", "\n".join(L))
    if "<!-- RECENT_NOTICES -->" in markdown:
        markdown = markdown.replace("<!-- RECENT_NOTICES -->", "\n".join(notice_rows(all_notices(_datasets)[:5], "datasets/")))
    if "<!-- BUILD_DATE -->" in markdown:
        markdown = markdown.replace("<!-- BUILD_DATE -->", date.today().isoformat())
    return markdown


def on_serve(server, config, builder):
    # 로컬 미리보기(mkdocs serve) 중 YAML을 고치면 바로 다시 빌드
    server.watch(str(DATA_DIR))
    return server
