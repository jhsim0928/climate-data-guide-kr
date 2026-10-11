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
import os
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
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
TIMEOUT = 40
MAX_ADDED_LINES = 80        # 한 페이지에서 보고할 새 줄 수 상한
MAX_ADDED_CHARS = 6000
FAIL_REPORT_AFTER = 3       # 연속 실패가 이 횟수 이상이면 보고
KEEP_HISTORY_DAYS = 30

# 공지와 무관하게 자주 바뀌는 줄 (방문자 수, 갱신 시각, 저작권 연도 등)
NOISE = re.compile(
    r"^(©|copyright\b|all rights reserved|last (updated|modified|reviewed)|page (last )?(updated|modified)|"
    r"updated:|modified:|this page was|generated (on|at)|current time|server time|"
    r"\d+\s+(views?|replies|reads?|users? online)|loading|skip to (main )?content|cookie)"
    # 페이지를 열 때마다 바뀌는 서버 정보 (Confluence 요청 ID, 서버 시각 등)
    r"|requestcorrelationid|serverduration|^\(confluence-\d+: [0-9a-f]+\)$|local time: ?\d|^utc: ?\d",
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


def lhash(line: str) -> str:
    return hashlib.sha1(line[:600].encode()).hexdigest()[:12]


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


def fetch(url: str, retry: bool = True):
    import requests
    import time
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"}, timeout=TIMEOUT)
        if r.status_code in (401, 403, 406, 429):
            # 자동 수집기를 막는 사이트는 일반 브라우저 식별값으로 한 번 더 시도
            r = requests.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                           "Accept-Language": "en-US,en;q=0.9"}, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        lines = extract_lines(r.content, r.headers.get("content-type", ""))
        if not lines:
            return None, "본문이 비어 있음"
        return lines, None
    except Exception as e:  # noqa: BLE001 — 어떤 오류든 '접속 실패'로 기록
        if retry:  # 일시적인 연결 오류는 잠시 뒤 한 번 더
            time.sleep(15)
            return fetch(url, retry=False)
        return None, type(e).__name__ + ": " + str(e)[:200]


def needs_browser(lines, err) -> bool:
    """자바스크립트로 화면을 그리는 페이지(본문이 거의 비어 옴)나 수집기를 막는 페이지"""
    if err:
        return err.startswith("HTTP 4") or err == "본문이 비어 있음"
    return len(lines) <= 3 and not lines[0].startswith("[PDF")


def render_all(urls: list[str]) -> dict[str, tuple]:
    """실제 브라우저(Chromium)로 열어 화면에 보이는 글자를 읽음. GitHub Actions에서만 설치되어 있음"""
    out: dict[str, tuple] = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {u: (None, "브라우저 없음") for u in urls}
    debug = bool(os.environ.get("WATCH_DEBUG"))
    log = (STATE / "browser-debug.txt").open("w", encoding="utf-8") if debug else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1280, "height": 2000})
        for url in urls:
            page = ctx.new_page()
            if debug:
                page.on("response", lambda r: ("json" in (r.headers.get("content-type") or "")) and log.write(f"   [json] {r.status} {r.url}\n"))
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2500)
                status = resp.status if resp else 0
                page.evaluate("""() => document.querySelectorAll('script,style,noscript,svg,nav,footer,header,form,iframe,button').forEach(e => e.remove())""")
                text = page.inner_text("body")
                lines = extract_lines(text.encode(), "text/plain")
                if status >= 400:
                    out[url] = (None, f"HTTP {status} (브라우저)")
                elif len(lines) <= 3:
                    out[url] = (None, "브라우저로도 본문이 비어 있음")
                else:
                    out[url] = (lines, None)
            except Exception as e:  # noqa: BLE001
                out[url] = (None, "브라우저: " + type(e).__name__ + ": " + str(e)[:150])
            finally:
                page.close()
            if debug:
                log.write(f"[browser] {url} → {out[url][1] or str(len(out[url][0])) + '줄'}\n")
        browser.close()
    if log:
        log.close()
    return out


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
    modes = {u: "http" for u in targets}
    hard = [u for u, (lines, err) in results.items() if needs_browser(lines, err)]
    if hard:
        for u, res in render_all(hard).items():
            if res[0]:
                results[u], modes[u] = res, "browser"
            elif results[u][0] is None or needs_browser(*results[u]):
                results[u] = (None, res[1] if results[u][1] is None else results[u][1] + " / " + res[1])

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
        mode_changed = meta.get("mode", "http") != modes[url]
        meta.update({"fails": 0, "last_ok": now.date().isoformat(), "file": snap.name, "mode": modes[url]})
        meta.pop("last_error", None)
        seen_path = STATE / (slug(url) + ".seen")
        seen = set(seen_path.read_text().split()) if seen_path.exists() else set()
        if snap.exists() and not mode_changed:   # 읽는 방식이 바뀐 날은 새 기준으로 저장만 함
            old = snap.read_text(encoding="utf-8").splitlines()[1:]
            # 예전에 한 번이라도 보였던 줄(돌아가며 바뀌는 추천 목록 등)은 새 줄로 치지 않음
            add = [x for x in added_lines(old, lines) if x.startswith("…") or lhash(x) not in seen]
            if add == ["… (이하 생략)"]:
                add = []
            if add:
                changes.append({"url": url, "datasets": datasets, "added": add,
                                "removed_count": len(set(old) - set(lines))})
                meta["last_change"] = now.date().isoformat()
        if not args.dry_run:
            snap.write_text("# " + url + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
            seen |= {lhash(x) for x in lines}
            seen_path.write_text("\n".join(sorted(seen)[-20000:]) + "\n")
        index[url] = meta

    # 더 이상 감시하지 않는 주소의 저장본 정리
    for url in [u for u in index if u not in targets]:
        if not args.only:
            (STATE / (slug(url) + ".txt")).unlink(missing_ok=True)
            (STATE / (slug(url) + ".seen")).unlink(missing_ok=True)
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
