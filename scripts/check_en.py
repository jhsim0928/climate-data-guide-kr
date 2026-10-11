"""영어판 빌드 결과(site/en)에 남은 한국어를 찾아 보여줍니다.

    mkdocs build -f mkdocs.en.yml && python scripts/check_en.py

언어 선택 메뉴의 '한국어'와 한국어판 링크 안내는 제외합니다.
"""
import html as h
import re
import sys
from collections import Counter
from pathlib import Path

site = Path(__file__).resolve().parent.parent / "site" / "en"
allow = {"한국어"}
hits = Counter()
pages = {}
for f in site.rglob("*.html"):
    t = f.read_text(encoding="utf-8")
    t = re.sub(r"<script(?![^>]*application/json).*?</script>", " ", t, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = h.unescape(t)
    for m in re.finditer(r"[^\s<>]{0,25}[가-힣][^<>\n]{0,40}", t):
        seg = m.group(0).strip()
        if seg in allow or "(한국어)" in seg:
            continue
        hits[seg] += 1
        pages.setdefault(seg, f.relative_to(site).as_posix())
for seg, n in hits.most_common(int(sys.argv[1]) if len(sys.argv) > 1 else 80):
    print(f"{n:4d}  {seg[:70]}   [{pages[seg]}]")
print("total distinct:", len(hits))
