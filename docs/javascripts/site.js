// 자료 비교 · 공지 필터 · 페이지별 "정보 오류 신고" 링크
(function () {
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // `변수명` → <code>, 나머지는 이스케이프
  function codeText(s) {
    return esc(s).replace(/`([^`]+)`/g, '<code class="notranslate" translate="no">$1</code>');
  }

  // ── 자료 비교 ─────────────────────────────────────────────
  function setupCompare() {
    var dataEl = document.getElementById("cmp-data");
    var table = document.getElementById("cmp-table");
    if (!dataEl || !table || table.dataset.bound) return;
    table.dataset.bound = "1";
    var all = JSON.parse(dataEl.textContent);
    var byId = {};
    all.forEach(function (d) { byId[d.id] = d; });
    var selects = Array.prototype.slice.call(document.querySelectorAll(".cmp-select"));
    var q = document.getElementById("cmp-q");
    var empty = document.getElementById("cmp-empty");

    var params = new URLSearchParams(location.search);
    (params.get("ids") || "").split(",").filter(Boolean).slice(0, 4).forEach(function (id, i) {
      if (byId[id]) selects[i].value = id;
    });
    if (params.get("v")) q.value = params.get("v");

    var ROWS = [
      ["분류", function (d) { return esc(d.domain + " › " + d.group); }],
      ["상태", function (d) { return d.status; }],
      ["제공 기관", function (d) { return esc(d.provider); }],
      ["기간", function (d) { return esc(d.period); }],
      ["제공 해상도", function (d) { return esc(d.spatial) + ' <span class="hint">(km는 적도 기준 근사)</span>'; }],
      ["시간 간격", function (d) { return esc(d.temporal_s); }],
      ["연직 해상도", function (d) { return esc(d.vertical); }],
      ["시간 간격 (세부)", function (d) { return esc(d.temporal); }],
      ["시간 표기 규칙", function (d) { return codeText(d.time); }],
      ["갱신 주기", function (d) { return esc(d.update); }],
      ["라이선스", function (d) { return esc(d.license); }],
      ["계정 필요", function (d) { return esc(d.account); }],
      ["정리된 변수", function (d) { return d.nvars + "개"; }],
      ["대표 DOI", function (d) {
        return d.doi.map(function (x) { return '<a href="https://doi.org/' + esc(x) + '" target="_blank" rel="noopener">' + esc(x) + "</a>"; }).join("<br>") || "-";
      }],
      ["후속 자료", function (d) { return esc(d.successor); }]
    ];

    function matches(d, term) {
      var t = term.toLowerCase();
      var out = [];
      d.groups.forEach(function (g) {
        g.i.forEach(function (it) {
          if (it.t.toLowerCase().indexOf(t) !== -1) out.push({ g: g.n, it: it });
        });
      });
      return out;
    }

    function render() {
      var ids = selects.map(function (s) { return s.value; }).filter(Boolean);
      ids = ids.filter(function (id, i) { return ids.indexOf(id) === i; });
      var term = q.value.trim();
      var p = new URLSearchParams();
      if (ids.length) p.set("ids", ids.join(","));
      if (term) p.set("v", term);
      try { history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : "")); } catch (e) {}

      if (ids.length < 2) {
        table.hidden = true;
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      var ds = ids.map(function (id) { return byId[id]; });
      var h = "<thead><tr><th>항목</th>" + ds.map(function (d) {
        return '<th><a href="../datasets/' + d.id + '/"><span class="notranslate" translate="no">' + esc(d.name) + "</span></a></th>";
      }).join("") + "</tr></thead><tbody>";
      ROWS.forEach(function (r) {
        h += "<tr><th scope=\"row\">" + r[0] + "</th>" + ds.map(function (d) { return "<td>" + r[1](d) + "</td>"; }).join("") + "</tr>";
      });
      if (term) {
        h += '<tr class="cmp-var-row"><th scope="row">변수 찾기<br><span class="hint">“' + esc(term) + "”</span></th>" + ds.map(function (d) {
          var m = matches(d, term);
          if (!m.length) return '<td><span class="hint">정리된 변수 중 없음</span></td>';
          return "<td><ul class=\"cmp-vars\">" + m.slice(0, 8).map(function (x) {
            return "<li>" + codeText(x.it.t) + " " + (x.it.b || "") + '<br><span class="hint">' + esc(x.g) + "</span></li>";
          }).join("") + (m.length > 8 ? '<li class="hint">외 ' + (m.length - 8) + "개</li>" : "") + "</ul></td>";
        }).join("") + "</tr>";
      }
      table.innerHTML = h + "</tbody>";
      table.hidden = false;
    }

    selects.forEach(function (s) { s.addEventListener("change", render); });
    q.addEventListener("input", render);
    document.querySelectorAll(".chips .chip").forEach(function (b) {
      b.addEventListener("click", function () { q.value = b.getAttribute("data-q"); render(); });
    });
    render();
  }

  // ── 중요 공지 필터 ────────────────────────────────────────
  function setupNoticeFilter() {
    var box = document.getElementById("notice-filter");
    var table = document.getElementById("notice-table");
    if (!box || !table || box.dataset.bound) return;
    box.dataset.bound = "1";
    var sel = document.getElementById("nf-dataset");
    var count = document.getElementById("nf-count");
    var emptyMsg = document.getElementById("nf-empty");
    var pre = new URLSearchParams(location.search).get("dataset");
    if (pre && sel.querySelector('option[value="' + pre + '"]')) sel.value = pre;

    function apply() {
      var levels = Array.prototype.map.call(box.querySelectorAll('input[name="nlevel"]:checked'), function (e) { return e.value; });
      var n = 0;
      table.querySelectorAll("tbody tr").forEach(function (tr) {
        var ok = (!sel.value || tr.dataset.dataset === sel.value) && levels.indexOf(tr.dataset.level) !== -1;
        tr.hidden = !ok;
        if (ok) n++;
      });
      count.textContent = n + "건 표시 중";
      emptyMsg.hidden = n !== 0;
      try {
        var p = new URLSearchParams(location.search);
        if (sel.value) p.set("dataset", sel.value); else p.delete("dataset");
        history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : ""));
      } catch (e) {}
    }
    sel.addEventListener("change", apply);
    box.querySelectorAll('input[name="nlevel"]').forEach(function (c) { c.addEventListener("change", apply); });
    apply();
  }

  // ── 모든 페이지 하단: 정보 오류 신고 링크 ─────────────────
  function addReportLink() {
    var inner = document.querySelector(".md-content__inner");
    var src = document.querySelector("a.md-source");
    if (!inner || !src || inner.querySelector(".report-bar")) return;
    var repo = src.getAttribute("href").replace(/\/$/, "");
    var h1 = inner.querySelector("h1");
    var title = h1 ? h1.textContent.replace("¶", "").trim() : document.title;
    var body =
      "### 페이지\n" + location.href.split("?")[0] + "\n\n" +
      "### 어떤 정보가 틀렸나요?\n\n\n" +
      "### 올바른 정보\n\n\n" +
      "### 근거가 되는 공식 출처 (링크)\n\n";
    var url = repo + "/issues/new?" + new URLSearchParams({ title: "[정보 오류] " + title, body: body, labels: "data-error" });
    var bar = document.createElement("div");
    bar.className = "report-bar";
    bar.innerHTML =
      '<span>이 페이지에서 틀린 정보나 바뀐 내용을 발견하셨나요?</span> ' +
      '<a class="act act-report" target="_blank" rel="noopener" href="' + esc(url) + '">정보 오류 신고</a>' +
      '<span class="hint">GitHub 계정이 필요합니다</span>';
    inner.appendChild(bar);
  }

  // ── 모든 표: 열 이름을 누르면 정렬 ────────────────────────
  // 칸에 data-sort가 있으면 그 값으로, 없으면 글자로 정렬합니다 (숫자·날짜는 크기순, 한글은 가나다순)
  function sortKey(td) {
    if (!td) return "";
    return td.hasAttribute("data-sort") ? td.getAttribute("data-sort") : td.textContent.trim();
  }
  function compareKeys(a, b) {
    if (a === "" && b === "") return 0;
    if (a === "") return 1;           // 빈 값은 항상 아래로
    if (b === "") return -1;
    var na = Number(a), nb = Number(b);
    if (!isNaN(na) && !isNaN(nb)) return na - nb;
    return a.localeCompare(b, "ko", { numeric: true, sensitivity: "base" });
  }
  // ── 목록 표에서 체크해서 바로 비교 ─────────────────────────
  function setupPickCompare() {
    var wraps = document.querySelectorAll(".list-table[data-compare]");
    if (!wraps.length || document.getElementById("pick-bar")) return;
    var picked = [];
    var target = wraps[0].getAttribute("data-compare");
    var bar = document.createElement("div");
    bar.id = "pick-bar";
    bar.className = "pick-bar";
    bar.hidden = true;
    bar.innerHTML = '<span class="pick-count"></span>' +
      '<a class="pick-go" href="#">선택한 자료 비교하기</a>' +
      '<button type="button" class="pick-clear">선택 해제</button>';
    document.body.appendChild(bar);
    function update() {
      bar.hidden = picked.length === 0;
      bar.querySelector(".pick-count").textContent =
        picked.length + "개 선택" + (picked.length < 2 ? " — 1개 더 고르세요" : "") + " (최대 4개)";
      var go = bar.querySelector(".pick-go");
      go.href = target + "?ids=" + picked.join(",");
      go.classList.toggle("is-disabled", picked.length < 2);
      document.querySelectorAll(".pick-box").forEach(function (b) { b.checked = picked.indexOf(b.value) !== -1; });
    }
    bar.querySelector(".pick-go").addEventListener("click", function (e) { if (picked.length < 2) e.preventDefault(); });
    bar.querySelector(".pick-clear").addEventListener("click", function () { picked = []; update(); });
    wraps.forEach(function (w) {
      var table = w.querySelector("table");
      var th = document.createElement("th");
      th.className = "pick-col";
      th.setAttribute("data-nosort", "1");
      th.innerHTML = '<span title="체크해서 비교">비교</span>';
      table.tHead.rows[0].insertBefore(th, table.tHead.rows[0].firstChild);
      Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
        var td = document.createElement("td");
        td.className = "pick-col";
        td.innerHTML = '<input type="checkbox" class="pick-box" value="' + esc(tr.dataset.id) + '" aria-label="비교에 담기">';
        tr.insertBefore(td, tr.firstChild);
      });
      w.addEventListener("change", function (e) {
        if (!e.target.classList.contains("pick-box")) return;
        var id = e.target.value, i = picked.indexOf(id);
        if (e.target.checked && i === -1) {
          if (picked.length >= 4) { e.target.checked = false; alert("한 번에 4개까지 비교할 수 있어요."); return; }
          picked.push(id);
        } else if (!e.target.checked && i !== -1) {
          picked.splice(i, 1);
        }
        update();
      });
    });
  }

  function makeSortable(table) {
    if (table.dataset.sortable || table.id === "cmp-table") return;
    var head = table.tHead && table.tHead.rows[0];
    var body = table.tBodies[0];
    if (!head || !body || body.rows.length < 2) return;
    table.dataset.sortable = "1";
    Array.prototype.forEach.call(head.cells, function (th, col) {
      if (th.hasAttribute("data-nosort")) return;
      th.classList.add("sort-th");
      th.setAttribute("tabindex", "0");
      th.setAttribute("aria-sort", "none");
      th.title = (th.title ? th.title + " — " : "") + "눌러서 정렬";
      function sort() {
        var asc = th.getAttribute("aria-sort") !== "ascending";
        Array.prototype.forEach.call(head.cells, function (o) { if (o.classList.contains("sort-th")) o.setAttribute("aria-sort", "none"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var rows = Array.prototype.slice.call(body.rows);
        rows.forEach(function (r, i) { if (!r.dataset.orig) r.dataset.orig = i; });
        rows.sort(function (r1, r2) {
          var c = compareKeys(sortKey(r1.cells[col]), sortKey(r2.cells[col]));
          if (c === 0) return r1.dataset.orig - r2.dataset.orig;  // 같은 값은 원래 순서 유지
          return asc ? c : -c;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      }
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); }
      });
    });
  }
  function setupSortableTables() {
    document.querySelectorAll(".md-typeset table").forEach(makeSortable);
  }

  // ── 세대별 비교: 표에서 누른 항목만 아래에 표시 ─────────────
  function setupGenerations() {
    var opens = document.querySelectorAll(".gen-open");
    if (!opens.length || opens[0].dataset.bound) return;
    var details = document.querySelectorAll(".gen-detail");
    var empty = document.getElementById("gen-empty");
    function show(key, scroll) {
      var found = false;
      details.forEach(function (el) { el.hidden = el.id !== key; if (el.id === key) found = true; });
      document.querySelectorAll(".gen-table tr[data-key]").forEach(function (tr) {
        tr.classList.toggle("is-selected", tr.dataset.key === key);
      });
      if (empty) empty.hidden = found;
      if (found) {
        try { history.replaceState(null, "", "#" + key); } catch (e) {}
        if (scroll) document.getElementById(key).scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
    opens.forEach(function (b) {
      b.dataset.bound = "1";
      b.addEventListener("click", function () { show(b.getAttribute("data-key"), true); });
    });
    if (location.hash) show(decodeURIComponent(location.hash.slice(1)), true);
  }

  function init() {
    setupGenerations();
    setupPickCompare();
    setupSortableTables();
    setupCompare();
    setupNoticeFilter();
    addReportLink();
  }
  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
