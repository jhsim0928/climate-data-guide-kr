// 자료 비교 · 공지 필터 · 페이지별 "정보 오류 신고" 링크
(function () {
  // 영어판(/en/)이면 영어 문구를 씁니다
  var IS_EN = (document.documentElement.lang || "").toLowerCase().indexOf("en") === 0;
  function L(ko, en) { return IS_EN ? en : ko; }
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
    var results = document.getElementById("var-results");
    var basket = document.getElementById("var-basket");
    var VAR_MODE = !!document.querySelector(".var-mode");
    var stdEl = document.getElementById("std-data");
    var STD = stdEl ? JSON.parse(stdEl.textContent) : [];
    var stdById = {};
    STD.forEach(function (c) { stdById[c.id] = c; });

    var params = new URLSearchParams(location.search);
    (params.get("ids") || "").split(",").filter(Boolean).slice(0, 4).forEach(function (id, i) {
      if (byId[id]) selects[i].value = id;
    });
    if (params.get("v")) q.value = params.get("v");

    var ROWS = [
      [L("분류", "Section"), function (d) { return esc(d.domain + " › " + d.group); }],
      [L("상태", "Status"), function (d) { return d.status; }],
      [L("제공 기관", "Provider"), function (d) { return esc(d.provider); }],
      [L("기간", "Period"), function (d) { return esc(d.period); }],
      [L("공간 범위", "Coverage"), function (d) { return esc(d.coverage); }],
      [L("제공 해상도 (단순 비교)", "Provided resolution (simplified)"), function (d) { return esc(d.spatial) + ' <span class="hint">' + L("(km는 적도 기준 근사)", "(km approximate at the equator)") + '</span>'; }],
      [L("시간 간격 (단순 비교)", "Interval (simplified)"), function (d) { return esc(d.temporal_s); }],
      [L("수평 해상도 (공식)", "Horizontal resolution (official)"), function (d) { return esc(d.spatial_d); }],
      [L("연직 해상도", "Vertical resolution"), function (d) { return esc(d.vertical); }],
      [L("시간 해상도 (공식)", "Temporal resolution (official)"), function (d) { return esc(d.temporal); }],
      [L("갱신 주기", "Update frequency"), function (d) { return esc(d.update); }],
      [L("계정 필요", "Account required"), function (d) { return esc(d.account); }],
      [L("대표 DOI", "Key DOIs"), function (d) {
        return d.doi.map(function (x) { return '<a href="https://doi.org/' + esc(x) + '" target="_blank" rel="noopener">' + esc(x) + "</a>"; }).join("<br>") || "-";
      }],
      [L("후속 자료", "Successor"), function (d) { return esc(d.successor); }]
    ];

    // ── 변수 찾기: 입력 → 표준 변수(data/variables.yaml) → 그 변수가 있는 자료 ──
    function norm(s) { return String(s || "").toLowerCase().replace(/[\s·_\-]/g, ""); }
    function findConcepts(term) {
      var n = norm(term);
      if (!n) return [];
      // 1) 이름·별칭·실제 변수명과 정확히 같으면 그것만 (예: "강수" → 총강수, 가강수량은 아님)
      var exact = STD.filter(function (c) {
        return norm(c.n) === n || norm(c.ko) === n || norm(c.en) === n ||
          c.a.some(function (a) { return norm(a) === n; });
      });
      if (exact.length) return exact;
      if (n.length < 2) return [];
      // 2) 이름이나 별칭에 들어 있으면 (입력 중일 때)
      return STD.filter(function (c) {
        return norm(c.ko).indexOf(n) !== -1 || norm(c.en).indexOf(n) !== -1 ||
          c.a.some(function (a) { var x = norm(a); return x.length >= 3 && x.indexOf(n) !== -1; });
      });
    }
    function matches(d, term, concepts) {
      var out = [];
      var ids = (concepts || []).map(function (c) { return c.id; });
      var t = term.toLowerCase();
      d.groups.forEach(function (g) {
        g.i.forEach(function (it) {
          var hit = ids.length ? (it.s || []).some(function (x) { return ids.indexOf(x) !== -1; })
                               : it.t.toLowerCase().indexOf(t) !== -1;
          if (hit) out.push({ g: g.n, it: it });
        });
      });
      return out;
    }
    function selectedIds() {
      var ids = selects.map(function (s) { return s.value; }).filter(Boolean);
      return ids.filter(function (id, i) { return ids.indexOf(id) === i; });
    }
    function toggleSelect(id) {
      var cur = selects.filter(function (s) { return s.value === id; });
      if (cur.length) { cur.forEach(function (s) { s.value = ""; }); }
      else {
        var free = selects.filter(function (s) { return !s.value; })[0];
        if (!free) { alert(L("자료는 4개까지 비교할 수 있어요. 하나를 빼 주세요.", "You can compare up to four datasets. Remove one first.")); return; }
        free.value = id;
      }
      render();
    }
    function renderResults(term, concepts) {
      if (!results) return;
      if (!term) { results.hidden = true; results.innerHTML = ""; return; }
      var picked = selectedIds();
      var rows = all.map(function (d) { return { d: d, m: matches(d, term, concepts) }; })
        .filter(function (x) { return x.m.length; });
      var h = '<h2 class="var-results-title">' + L("변수 찾기 결과", "Datasets with this variable") + "</h2>";
      if (concepts.length) {
        h += '<div class="var-concepts">' + concepts.map(function (c) {
          return '<div class="var-concept"><strong>' + esc(c.n) + "</strong>" +
            (c.cf ? ' <span class="hint">CF: <code>' + esc(c.cf) + "</code></span>" : "") + "</div>";
        }).join("");
        var rel = [];
        concepts.forEach(function (c) { c.r.forEach(function (r) { if (stdById[r] && rel.indexOf(r) === -1 && !concepts.some(function (x) { return x.id === r; })) rel.push(r); }); });
        if (rel.length) h += '<div class="var-related"><span class="hint">' + L("관련 변수", "Related") + ':</span> ' +
          rel.map(function (r) { return '<button type="button" class="chip" data-q="' + esc(stdById[r].n) + '">' + esc(stdById[r].n) + "</button>"; }).join(" ") + "</div>";
        h += "</div>";
      } else {
        h += '<p class="hint">' + L("표준 변수 목록에 없는 말이라 변수 설명에서 글자 그대로 찾았습니다.", "Not in the standard variable list, so this is a plain text match on the variable descriptions.") + "</p>";
      }
      if (!rows.length) {
        results.innerHTML = h + '<p class="hint">' + L("이 변수가 정리된 자료가 없습니다.", "No dataset lists this variable.") + "</p>";
        results.hidden = false; return;
      }
      h += '<p class="hint">' + (VAR_MODE
        ? L("자료 " + rows.length + "개 · 시간 특성(순간값·평균·누적)과 단위가 자료마다 다르니 꼭 확인하세요. <b>비교에 넣기</b>로 2개 이상 담으면 아래에 <b>비교하기</b> 버튼이 나타납니다.",
            rows.length + " datasets · the time convention (instantaneous, mean, accumulated) and units differ between datasets. Add two or more with <b>Add to compare</b> and a <b>Compare</b> button appears below.")
        : L("자료 " + rows.length + "개 · 시간 특성(순간값·평균·누적)과 단위가 자료마다 다르니 꼭 확인하세요. <b>비교에 넣기</b>를 누르면 위 비교표에 들어갑니다.",
            rows.length + " datasets · the time convention (instantaneous, mean, accumulated) and units differ between datasets. Use <b>Add to compare</b> to put a dataset in the table above.")) + "</p>";
      h += '<div class="table-scroll var-table"><table><thead><tr><th>' + L("자료", "Dataset") + "</th><th>" + L("변수 (이 자료의 이름·단위)", "Variable (name and units in this dataset)") +
        "</th><th>" + L("시간 간격", "Interval") + "</th><th>" + L("기간", "Period") + "</th><th>" + L("상태", "Status") + "</th></tr></thead><tbody>";
      rows.forEach(function (x) {
        var d = x.d, on = picked.indexOf(d.id) !== -1;
        h += "<tr><td><a href=\"../datasets/" + d.id + '/"><span class="notranslate" translate="no">' + esc(d.name) + '</span></a><br><span class="hint">' + esc(d.group) + "</span>" +
          '<br><button type="button" class="md-button var-add' + (on ? " is-on" : "") + '" data-id="' + d.id + '">' +
          (on ? L("✓ 담음 (빼기)", "✓ Added (remove)") : L("+ 비교에 넣기", "+ Add to compare")) + "</button></td>" +
          '<td><ul class="cmp-vars">' + x.m.slice(0, 6).map(function (v) {
            return "<li>" + codeText(v.it.t) + " " + (v.it.b || "") + "</li>";
          }).join("") + (x.m.length > 6 ? '<li class="hint">' + L("외 " + (x.m.length - 6) + "개", "+ " + (x.m.length - 6) + " more") + "</li>" : "") + "</ul></td>" +
          '<td class="nowrap">' + esc(d.temporal_s) + "</td><td>" + esc(d.period) + "</td><td>" + d.status + "</td></tr>";
      });
      results.innerHTML = h + "</tbody></table></div>";
      results.hidden = false;
      results.querySelectorAll(".var-add").forEach(function (b) {
        b.addEventListener("click", function () { toggleSelect(b.getAttribute("data-id")); });
      });
      results.querySelectorAll(".var-related .chip").forEach(function (b) {
        b.addEventListener("click", function () { q.value = b.getAttribute("data-q"); render(); });
      });
    }

    function render() {
      var ids = selectedIds();
      var term = q.value.trim();
      var concepts = findConcepts(term);
      var p = new URLSearchParams();
      if (ids.length) p.set("ids", ids.join(","));
      if (term) p.set("v", term);
      try { history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : "")); } catch (e) {}

      renderResults(term, concepts);
      if (VAR_MODE) {
        // 변수로 찾기: 담은 자료를 자료 비교 페이지로 넘김
        table.hidden = true;
        empty.hidden = !!term;
        if (basket) {
          if (!ids.length) { basket.hidden = true; basket.innerHTML = ""; }
          else {
            var href = "../compare/?ids=" + ids.join(",") + (term ? "&v=" + encodeURIComponent(term) : "");
            basket.innerHTML = '<span>' + L("비교에 담은 자료", "Selected") + ': <b>' + ids.map(function (id) { return esc(byId[id].name); }).join(", ") + "</b></span> " +
              (ids.length >= 2 ? '<a class="md-button md-button--primary" href="' + href + '">' + L("선택한 " + ids.length + "개 비교하기 →", "Compare " + ids.length + " datasets →") + "</a>"
                               : '<span class="hint">' + L("하나 더 고르면 비교할 수 있어요", "Pick one more to compare") + "</span>");
            basket.hidden = false;
          }
        }
        return;
      }
      if (ids.length < 2) {
        table.hidden = true;
        empty.hidden = !!term;
        return;
      }
      empty.hidden = true;
      var ds = ids.map(function (id) { return byId[id]; });
      var h = "<thead><tr><th>" + L("항목", "Item") + "</th>" + ds.map(function (d) {
        return '<th><a href="../datasets/' + d.id + '/"><span class="notranslate" translate="no">' + esc(d.name) + "</span></a></th>";
      }).join("") + "</tr></thead><tbody>";
      ROWS.forEach(function (r) {
        h += "<tr><th scope=\"row\">" + r[0] + "</th>" + ds.map(function (d) { return "<td>" + r[1](d) + "</td>"; }).join("") + "</tr>";
      });
      if (term) {
        h += '<tr class="cmp-var-row"><th scope="row">' + L("변수 찾기", "Find a variable") + '<br><span class="hint">“' + esc(term) + "”</span></th>" + ds.map(function (d) {
          var m = matches(d, term, concepts);
          if (!m.length) return '<td><span class="hint">' + L("정리된 변수 중 없음", "No matching variable listed") + '</span></td>';
          return "<td><ul class=\"cmp-vars\">" + m.slice(0, 8).map(function (x) {
            return "<li>" + codeText(x.it.t) + " " + (x.it.b || "") + '<br><span class="hint">' + esc(x.g) + "</span></li>";
          }).join("") + (m.length > 8 ? '<li class="hint">' + L("외 " + (m.length - 8) + "개", "+ " + (m.length - 8) + " more") + "</li>" : "") + "</ul></td>";
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
      count.textContent = L(n + "건 표시 중", n + " shown");
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

  // ── 정보 오류 신고: 페이지 하단 버튼 + 신고 창 (운영자 메일로 전달) ──
  function meta(name) {
    var m = document.querySelector('meta[name="' + name + '"]');
    return m ? m.getAttribute("content") : "";
  }
  function pageTitle() {
    var h1 = document.querySelector(".md-content__inner h1");
    return (h1 ? h1.textContent : document.title).replace("¶", "").trim();
  }
  function reportDialog() {
    var dlg = document.getElementById("report-dialog");
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.id = "report-dialog";
    dlg.className = "report-dialog md-typeset";
    dlg.innerHTML =
      '<form method="dialog" class="cdg-form" novalidate>' +
      '<h2>' + L("정보 오류 신고", "Report an error") + '</h2>' +
      '<p class="hint">' + L("페이지", "Page") + ': <strong class="rp-title"></strong></p>' +
      '<label class="field">' + L("어떤 정보가 틀렸나요? <em>필수</em>", "What is wrong? <em>required</em>") +
      '<textarea name="wrong" rows="3" placeholder="' + L("예) 제공 기간 끝이 2023-12로 되어 있는데 실제로는 갱신이 계속되고 있어요", "e.g. The period ends 2023-12 here, but the dataset is still being updated") + '"></textarea></label>' +
      '<label class="field">' + L("올바른 정보 (선택)", "Correct information (optional)") + '<textarea name="correct" rows="2"></textarea></label>' +
      '<label class="field">' + L("근거가 되는 공식 출처 링크 (선택)", "Link to the official source (optional)") + '<input type="url" name="source" placeholder="https://"></label>' +
      '<label class="field">' + L("답변 받을 이메일 (선택)", "Your email for a reply (optional)") + '<input type="email" name="contact" placeholder="name@example.ac.kr" autocomplete="email"></label>' +
      '<div class="hp-field" aria-hidden="true"><label>' + L("웹사이트 (비워 두세요)", "Website (leave empty)") + '<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>' +
      '<div class="form-actions">' +
      '<button type="submit" value="send" class="md-button md-button--primary rp-send">' + L("보내기", "Send") + '</button>' +
      '<button type="button" class="md-button rp-close">' + L("닫기", "Close") + '</button></div>' +
      '<p class="form-message" role="status" aria-live="polite"></p>' +
      '<p class="hint rp-mail"></p>' +
      "</form>";
    document.body.appendChild(dlg);
    var form = dlg.querySelector("form");
    var msg = dlg.querySelector(".form-message");
    function say(t, k) { msg.textContent = t; msg.className = "form-message " + (k || ""); }
    dlg.querySelector(".rp-close").addEventListener("click", function () { dlg.close(); });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });  // 바깥 누르면 닫기
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var get = function (n) { return form.elements[n].value.trim(); };
      var endpoint = meta("cdg-report-endpoint");
      if (!get("wrong")) return say(L("어떤 정보가 틀렸는지 적어주세요.", "Please describe what is wrong."), "error");
      if (get("contact") && !form.elements.contact.checkValidity()) return say(L("이메일 주소를 확인해 주세요.", "Please check the email address."), "error");
      if (!endpoint) return say(L("지금은 아래 메일 주소로 보내주세요.", "For now, please email the address below."), "info");
      var btn = form.querySelector(".rp-send");
      btn.disabled = true;
      say(L("보내는 중…", "Sending…"), "info");
      fetch(endpoint, { method: "POST", mode: "no-cors", body: new URLSearchParams({
        type: "report", title: dlg.dataset.title, page: dlg.dataset.page,
        wrong: get("wrong"), correct: get("correct"), source: get("source"),
        contact: get("contact"), website: get("website"), lang: IS_EN ? "en" : "ko", requested_at: new Date().toISOString()
      }) }).then(function () {
        form.reset();
        say(L("신고를 보냈습니다. 고맙습니다! 공식 출처를 확인한 뒤 고치겠습니다.", "Thank you! Your report was sent. We will check the official source and fix it."), "success");
      }).catch(function () {
        say(L("보내지 못했습니다. 아래 메일 주소로 보내주세요.", "Sending failed. Please email the address below."), "error");
      }).then(function () { btn.disabled = false; });
    });
    return dlg;
  }
  function openReport(title) {
    var dlg = reportDialog();
    var page = location.href.split("#")[0];
    try { page = decodeURIComponent(page); } catch (e) {}
    dlg.dataset.title = title || pageTitle();
    dlg.dataset.page = page;
    dlg.querySelector(".rp-title").textContent = dlg.dataset.title;
    dlg.querySelector(".form-message").textContent = "";
    var mail = meta("cdg-contact");
    var box = dlg.querySelector(".rp-mail");
    box.innerHTML = "";
    if (mail) {
      var a = document.createElement("a");
      a.href = "mailto:" + mail + "?" + "subject=" + encodeURIComponent(L("[정보 오류] ", "[Error report] ") + dlg.dataset.title) +
        "&body=" + encodeURIComponent(L("페이지: " + page + "\n\n어떤 정보가 틀렸나요?\n\n올바른 정보\n\n근거 출처\n", "Page: " + page + "\n\nWhat is wrong?\n\nCorrect information\n\nOfficial source\n"));
      a.textContent = mail;
      box.append(L("메일로 직접 보내셔도 됩니다: ", "You can also email: "), a);
    }
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    var first = dlg.querySelector("textarea");
    if (first) first.focus();
  }
  function addReportLink() {
    var inner = document.querySelector(".md-content__inner");
    if (!inner) return;
    if (!inner.querySelector(".report-bar")) {
      var bar = document.createElement("div");
      bar.className = "report-bar";
      bar.innerHTML =
        '<span>' + L("이 페이지에서 틀린 정보나 바뀐 내용을 발견하셨나요?", "Found something wrong or outdated on this page?") + '</span> ' +
        '<a class="act act-report" href="#report">' + L("정보 오류 신고", "Report an error") + '</a>';
      inner.appendChild(bar);
    }
    inner.querySelectorAll(".act-report:not([data-bound])").forEach(function (a) {
      a.setAttribute("data-bound", "1");
      a.addEventListener("click", function (e) {
        e.preventDefault();
        openReport(a.getAttribute("data-report") || "");
      });
    });
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
      '<a class="pick-go" href="#">' + L("선택한 자료 비교하기", "Compare selected") + '</a>' +
      '<button type="button" class="pick-clear">' + L("선택 해제", "Clear") + '</button>';
    document.body.appendChild(bar);
    function update() {
      bar.hidden = picked.length === 0;
      bar.querySelector(".pick-count").textContent =
        L(picked.length + "개 선택" + (picked.length < 2 ? " — 1개 더 고르세요" : "") + " (최대 4개)", picked.length + " selected" + (picked.length < 2 ? " — pick one more" : "") + " (max 4)");
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
      th.innerHTML = '<span title="' + L("체크해서 비교", "Tick to compare") + '">' + L("비교", "Compare") + '</span>';
      table.tHead.rows[0].insertBefore(th, table.tHead.rows[0].firstChild);
      Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
        var td = document.createElement("td");
        td.className = "pick-col";
        td.innerHTML = '<input type="checkbox" class="pick-box" value="' + esc(tr.dataset.id) + '" aria-label="' + L("비교에 담기", "Add to comparison") + '">';
        tr.insertBefore(td, tr.firstChild);
      });
      w.addEventListener("change", function (e) {
        if (!e.target.classList.contains("pick-box")) return;
        var id = e.target.value, i = picked.indexOf(id);
        if (e.target.checked && i === -1) {
          if (picked.length >= 4) { e.target.checked = false; alert(L("한 번에 4개까지 비교할 수 있어요.", "You can compare up to four datasets at a time.")); return; }
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
      th.title = (th.title ? th.title + " — " : "") + L("눌러서 정렬", "Click to sort");
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

  // ── 언어 선택: 지금 보고 있는 페이지의 다른 언어판으로 바로 이동 (두 판의 주소 구조가 같음) ──
  function setupLangSwitch() {
    var path = location.pathname;
    var rel = path.indexOf("/en/") === 0 ? path.slice(3) : path;  // 한국어판 기준 경로
    document.querySelectorAll(".md-select__link[hreflang]").forEach(function (a) {
      var lang = a.getAttribute("hreflang");
      if (lang === "en") a.setAttribute("href", "/en" + rel + location.search);
      else if (lang === "ko") a.setAttribute("href", rel + location.search);
    });
  }

  // ── 홈: 최근 7일 안에 올라온 '중요' 공지를 팝업으로 (오늘 하루 보지 않기 지원) ──
  var POPUP_KEY = "kcdn-notice-popup-hide";   // 값: 숨긴 날짜(한국 시간 YYYY-MM-DD)
  function kstToday() {
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
    } catch (e) { return new Date().toISOString().slice(0, 10); }
  }
  function daysBetween(a, b) {  // a, b: YYYY-MM-DD → b - a (일)
    return Math.round((Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10)) -
                       Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10))) / 86400000);
  }
  function setupNoticePopup() {
    var root = document.getElementById("notice-popup-root");
    if (!root || document.querySelector(".notice-popup")) return;
    var today = kstToday();
    try { if (localStorage.getItem(POPUP_KEY) === today) return; } catch (e) {}
    try { if (sessionStorage.getItem(POPUP_KEY) === "closed") return; } catch (e) {}
    var en = IS_EN;
    fetch("assets/notices.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.notices) return;
      var items = data.notices.filter(function (n) {
        if (n.level !== "critical" || !/^\d{4}-\d{2}-\d{2}$/.test(n.date)) return false;
        var d = daysBetween(n.date, today);
        return d >= 0 && d <= 7;
      }).sort(function (a, b) { return a.date < b.date ? 1 : -1; });
      if (!items.length) return;
      var t = en ? {
        title: "Important notices from the past week", page: "Dataset page", src: "Original notice ↗",
        hide: "Don't show again today", close: "Close", all: "All provider notices →", lv: "Important"
      } : {
        title: "최근 1주일 중요 공지", page: "자료 페이지", src: "기관 원문 ↗",
        hide: "오늘 하루 보지 않기", close: "닫기", all: "기관 공지 전체 보기 →", lv: "중요"
      };
      var list = items.slice(0, 5).map(function (n) {
        return '<li><div class="np-meta"><span class="np-lv">' + esc(t.lv) + "</span> " + esc(n.date) + " · <b>" + esc(n.dataset_name) + "</b></div>" +
          '<div class="np-title">' + esc(n.title) + "</div>" +
          (n.body ? '<p class="np-body">' + esc(n.body) + "</p>" : "") +
          '<div class="np-links"><a href="' + esc(n.url) + '">' + esc(t.page) + "</a>" +
          (n.source ? ' · <a href="' + esc(n.source) + '" target="_blank" rel="noopener noreferrer">' + esc(t.src) + "</a>" : "") + "</div></li>";
      }).join("");
      var wrap = document.createElement("div");
      wrap.className = "notice-popup";
      wrap.innerHTML = '<div class="np-backdrop"></div><div class="np-box" role="dialog" aria-modal="true" aria-labelledby="np-h">' +
        '<div class="np-head"><h2 id="np-h">' + esc(t.title) + '</h2><button type="button" class="np-x" aria-label="' + esc(t.close) + '">×</button></div>' +
        '<ul class="np-list">' + list + "</ul>" +
        '<a class="np-all" href="notices/">' + esc(t.all) + "</a>" +
        '<div class="np-foot"><button type="button" class="np-hide">' + esc(t.hide) + '</button><button type="button" class="np-close">' + esc(t.close) + "</button></div></div>";
      document.body.appendChild(wrap);
      function close(hideToday) {
        try {
          if (hideToday) localStorage.setItem(POPUP_KEY, today);
          else sessionStorage.setItem(POPUP_KEY, "closed");  // 닫기: 이번 방문 동안만 다시 안 뜸
        } catch (e) {}
        document.removeEventListener("keydown", onKey);
        wrap.remove();
      }
      function onKey(e) { if (e.key === "Escape") close(false); }
      wrap.querySelector(".np-hide").addEventListener("click", function () { close(true); });
      wrap.querySelector(".np-close").addEventListener("click", function () { close(false); });
      wrap.querySelector(".np-x").addEventListener("click", function () { close(false); });
      wrap.querySelector(".np-backdrop").addEventListener("click", function () { close(false); });
      document.addEventListener("keydown", onKey);
      wrap.querySelector(".np-close").focus({ preventScroll: true });
    }).catch(function () {});
  }

  function init() {
    setupNoticePopup();
    setupLangSwitch();
    setupGenerations();
    setupPickCompare();
    setupSortableTables();
    setupCompare();
    setupNoticeFilter();
    addReportLink();
  }
  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);

  // ── 바깥 사이트 링크(기관 페이지·포털·DOI 등)는 새 탭으로, 사이트 안 링크는 같은 탭 ──
  // 클릭 순간에 판단하므로 검색 결과·비교표처럼 나중에 그려지는 링크에도 적용됨
  function markExternal(a) {
    if (!a || !a.href || a.hasAttribute("download")) return;
    var u;
    try { u = new URL(a.href, location.href); } catch (e) { return; }
    if ((u.protocol !== "http:" && u.protocol !== "https:") || u.host === location.host) return;
    a.target = "_blank";
    var rel = (a.getAttribute("rel") || "").split(/\s+/).filter(Boolean);
    ["noopener", "noreferrer"].forEach(function (r) { if (rel.indexOf(r) < 0) rel.push(r); });
    a.setAttribute("rel", rel.join(" "));
  }
  ["click", "auxclick", "keydown"].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      if (ev === "keydown" && e.key !== "Enter") return;
      markExternal(e.target && e.target.closest ? e.target.closest("a[href]") : null);
    }, true);
  });
})();
