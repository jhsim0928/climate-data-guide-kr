"""공지 페이지 변경 감지 — 매일 GitHub Actions(.github/workflows/watch.yml)에서 실행

각 데이터셋 YAML의 watch_urls(자료 제공 기관의 공지·뉴스 페이지)를 받아 본문 글자만 뽑고,
지난번 저장본(watch/state/)과 비교해 새로 생긴 줄을 watch/changes.json에 남깁니다.

이 스크립트는 "무엇이 바뀌었는지"만 찾습니다. 진짜 공지인지 판단하고 사이트용 공지를 쓰는 일은
매일 아침 Claude 점검(watch/REVIEW.md)이 하고, 운영자가 승인(머지)해야 사이트와 구독자 메일에 반영됩니다.

    python scripts/watch.py            # 점검 (필요 패키지: requests, beautifulsoup4, PyYAML)
    python scripts/watch.py --dry-run  # 저장 없이 결과만 출력
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "datasets"
WATCH = ROOT / "watch"
STATE = WATCH / "state"
HISTORY = WATCH / "history"
KST = dt.timezone(dt.timedelta(hours=9))

UA = "Mozilla/5.0 (compatible; data4researchers-notice-watch/1.0; +https://data4researchers.kr/)"
TIMEOUT = 40
MAX_ADDED_LINES = 80        # 한 페이지에서 보고할 새 줄 수 상한
MAX_ADDED_CHARS = 6000
FAIL_REPORT_AFTER = 3       # 연속 실패가 이 횟수 이상이면 보고
KEEP_HISTORY_DAYS = 30

# 공지와 무관하게 자주 바뀌는 줄 (방문자 수, 갱신 시각, 저작권 연도 등)
NOISE = re.compile(
    r"^(©|copyright\b|all rights reserved|last (updated|modified|reviewed)|page (last )?(updated|modified)|"
    r"updated:|modified:|this page was|generated (on|at)|current time|server time|"
    r"\d+\s+(views?|replies|reads?|users? online)|loading|skip to (main )?content|cookie)",
    re.I,
)
ONLY_DATETIME = re.compile(r"^[\d\s:/.,\-–TZUTC()+]+$")


def load_targets() -> dict[str, list[str]]:
    """url → 이 주소를 감시하는 데이터셋 id 목록"""
    targets: dict[str, list[str]] = {}
    for f in sorted(DATA.glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for u in d.get("watch_urls") or []:
            targets.setdefault(str(u).strip(), []).append(d["id"])
    return targets


def slug(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def extract_lines(content: bytes, ctype: str) -> list[str]:
    """응답 본문을 비교용 줄 목록으로"""
    ctype = (ctype or "").lower()
    if "pdf" in ctype or content[:5] == b"%PDF-":
        # PDF는 글자 대신 내용 지문만 비교
        return ["[PDF sha1] " + hashlib.sha1(content).hexdigest()]
    text = content.decode("utf-8", errors="replace")
    if "html" in ctype or re.search(r"<html|<body|<div", text[:5000], re.I):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "form", "iframe", "button"]):
            t.decompose()
        text = soup.get_text("\n")
    out, prev = [], None
    for ln in text.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if len(ln) < 4 or ln == prev or NOISE.search(ln) or ONLY_DATETIME.match(ln):
            continue
        out.append(ln)
        prev = ln
    return out


def fetch(url: str):
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"}, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        lines = extract_lines(r.content, r.headers.get("content-type", ""))
        if not lines:
            return None, "본문이 비어 있음"
        return lines, None
    except Exception as e:  # noqa: BLE001 — 어떤 오류든 '접속 실패'로 기록
        return None, type(e).__name__ + ": " + str(e)[:200]


def added_lines(old: list[str], new: list[str]) -> list[str]:
    """예전에 없던 줄만 (순서 유지). 줄 이동·재배열은 변경으로 보지 않음"""
    seen = set(old)
    out, total = [], 0
    for ln in new:
        if ln in seen:
            continue
        seen.add(ln)
        out.append(ln[:600])
        total += len(out[-1])
        if len(out) >= MAX_ADDED_LINES or total >= MAX_ADDED_CHARS:
            out.append("… (이하 생략)")
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="이 문자열이 들어간 주소만 점검 (시험용)")
    args = ap.parse_args()

    targets = load_targets()
    if args.only:
        targets = {u: v for u, v in targets.items() if args.only in u}
    STATE.mkdir(parents=True, exist_ok=True)
    index_path = STATE / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    baseline = not any((STATE / (slug(u) + ".txt")).exists() for u in targets)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(zip(targets, ex.map(fetch, targets)))

    now = dt.datetime.now(KST)
    changes, errors, ok = [], [], 0
    for url, datasets in targets.items():
        lines, err = results[url]
        meta = index.get(url, {})
        snap = STATE / (slug(url) + ".txt")
        if err:
            meta["fails"] = meta.get("fails", 0) + 1
            meta["last_error"] = err
            if meta["fails"] >= FAIL_REPORT_AFTER:
                errors.append({"url": url, "datasets": datasets, "error": err, "fails": meta["fails"],
                               "last_ok": meta.get("last_ok")})
            index[url] = meta
            continue
        ok += 1
        meta.update({"fails": 0, "last_ok": now.date().isoformat(), "file": snap.name})
        meta.pop("last_error", None)
        if snap.exists():
            old = snap.read_text(encoding="utf-8").splitlines()[1:]
            add = added_lines(old, lines)
            if add:
                changes.append({"url": url, "datasets": datasets, "added": add,
                                "removed_count": len(set(old) - set(lines))})
                meta["last_change"] = now.date().isoformat()
        if not args.dry_run:
            snap.write_text("# " + url + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
        index[url] = meta

    # 더 이상 감시하지 않는 주소의 저장본 정리
    for url in [u for u in index if u not in targets]:
        if not args.only:
            (STATE / (slug(url) + ".txt")).unlink(missing_ok=True)
            index.pop(url)

    # 같은 날 다시 돌린 경우(수동 실행 등) 앞선 실행에서 찾은 변경을 잃지 않도록 합침
    prev_path = WATCH / "changes.json"
    if prev_path.exists():
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        if prev.get("date_kst") == now.date().isoformat():
            mine = {c["url"]: c for c in changes}
            for c in prev.get("changes", []):
                if c["url"] in mine:
                    mine[c["url"]]["added"] = c["added"] + [x for x in mine[c["url"]]["added"] if x not in c["added"]]
                else:
                    changes.append(c)
            baseline = baseline or prev.get("baseline", False)

    report = {
        "date_kst": now.date().isoformat(),
        "run_at": now.isoformat(timespec="seconds"),
        "baseline": baseline,
        "checked": len(targets), "ok": ok,
        "changes": changes, "errors": errors,
    }
    print(f"점검 {len(targets)}곳 · 성공 {ok} · 변경 {len(changes)} · 계속 실패 {len(errors)}"
          + (" (첫 점검: 기준 저장만 함)" if baseline else ""))
    for c in changes:
        print(" -", ", ".join(c["datasets"]), c["url"], f"새 줄 {len(c['added'])}")
    if args.dry_run:
        return 0

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (WATCH / "changes.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    HISTORY.mkdir(exist_ok=True)
    (HISTORY / (report["date_kst"] + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cutoff = (now.date() - dt.timedelta(days=KEEP_HISTORY_DAYS)).isoformat()
    for f in HISTORY.glob("*.json"):
        if f.stem < cutoff:
            f.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
