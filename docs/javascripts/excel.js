// 표를 엑셀(.xlsx) 파일로 저장 — 외부 라이브러리 없이 브라우저에서 바로 만듭니다.
// 화면에 보이는 그대로(정렬 순서, 필터로 숨긴 행 제외, 비교표는 고른 자료만) 저장합니다.
(function () {
  // 영어판(/en/)이면 영어 문구를 씁니다
  var IS_EN = (document.documentElement.lang || "").toLowerCase().indexOf("en") === 0;
  function L(ko, en) { return IS_EN ? en : ko; }
  // ── ZIP(무압축) 만들기 ─────────────────────────────────
  var CRC_TABLE = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(bytes) {
    var c = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  function u16(v) { return [v & 0xff, (v >>> 8) & 0xff]; }
  function u32(v) { return [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]; }
  function zip(files) {
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    files.forEach(function (f) {
      var name = enc.encode(f.name), data = enc.encode(f.data), crc = crc32(data);
      var local = [].concat([0x50, 0x4b, 0x03, 0x04], u16(20), u16(0x0800), u16(0), u16(0), u16(0x21),
        u32(crc), u32(data.length), u32(data.length), u16(name.length), u16(0));
      parts.push(new Uint8Array(local), name, data);
      central.push([].concat([0x50, 0x4b, 0x01, 0x02], u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21),
        u32(crc), u32(data.length), u32(data.length), u16(name.length), u16(0), u16(0), u16(0), u16(0), u32(0),
        u32(offset)), name);
      offset += local.length + name.length + data.length;
    });
    var cdSize = 0;
    central.forEach(function (c, i) {
      if (i % 2 === 0) { parts.push(new Uint8Array(c)); cdSize += c.length; }
      else { parts.push(c); cdSize += c.length; }
    });
    parts.push(new Uint8Array([].concat([0x50, 0x4b, 0x05, 0x06], u16(0), u16(0), u16(files.length),
      u16(files.length), u32(cdSize), u32(offset), u16(0))));
    return new Blob(parts, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  }

  // ── XLSX 구성 ──────────────────────────────────────────
  function xmlEsc(s) {
    return String(s).replace(/[<>&"]/g, function (c) {
      return { "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c];
    }).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
  }
  function colName(i) {
    var s = "";
    for (i++; i > 0; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + ((i - 1) % 26)) + s;
    return s;
  }
  function buildXlsx(rows, sheetName, footer) {
    var widths = [];
    var n = rows.length;
    var foot = (footer || []).map(function (text, i) {
      var r = n + 2 + i;  // 표와 한 줄 띄움
      return '<row r="' + r + '"><c r="A' + r + '" s="' + (i === 0 ? 3 : 4) + '" t="inlineStr"><is><t xml:space="preserve">' + xmlEsc(text) + "</t></is></c></row>";
    }).join("");
    var body = rows.map(function (row, r) {
      return '<row r="' + (r + 1) + '">' + row.map(function (v, c) {
        var ref = colName(c) + (r + 1), style = r === 0 ? ' s="1"' : ' s="2"';
        widths[c] = Math.max(widths[c] || 8, Math.min(60, String(v).length * 1.6 + 2));
        if (r > 0 && /^-?\d+(\.\d+)?$/.test(v) && v.length < 15) return '<c r="' + ref + '"' + style + "><v>" + v + "</v></c>";
        return '<c r="' + ref + '"' + style + ' t="inlineStr"><is><t xml:space="preserve">' + xmlEsc(v) + "</t></is></c>";
      }).join("") + "</row>";
    }).join("") + foot;
    var cols = "<cols>" + widths.map(function (w, i) {
      return '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + w.toFixed(1) + '" customWidth="1"/>';
    }).join("") + "</cols>";
    var NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"';
    var REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    return zip([
      { name: "[Content_Types].xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>' },
      { name: "_rels/.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="' + REL + '/officeDocument" Target="xl/workbook.xml"/></Relationships>' },
      { name: "xl/workbook.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook ' + NS + ' xmlns:r="' + REL + '"><sheets><sheet name="' + xmlEsc(sheetName) + '" sheetId="1" r:id="rId1"/></sheets></workbook>' },
      { name: "xl/_rels/workbook.xml.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="' + REL + '/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="' + REL + '/styles" Target="styles.xml"/></Relationships>' },
      { name: "xl/styles.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet ' + NS + '><fonts count="4"><font><sz val="11"/><name val="Malgun Gothic"/></font><font><b/><sz val="11"/><name val="Malgun Gothic"/></font><font><b/><sz val="10"/><color rgb="FF00695C"/><name val="Malgun Gothic"/></font><font><sz val="10"/><color rgb="FF555555"/><name val="Malgun Gothic"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8EEFC"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>' },
      { name: "xl/worksheets/sheet1.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet ' + NS + '><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' + cols + "<sheetData>" + body + "</sheetData></worksheet>" }
    ]);
  }

  // ── 화면의 표 → 행 목록 ────────────────────────────────
  function cellText(cell) {
    var c = cell.cloneNode(true);
    c.querySelectorAll("input, .hint, script").forEach(function (e) { e.remove(); });
    c.querySelectorAll("br, li").forEach(function (e) { e.insertAdjacentText("beforebegin", "\n"); });
    return c.textContent.replace(/[ \t]+/g, " ").replace(/\n\s*/g, "\n").replace(/↕|▲|▼|¶/g, "").trim();
  }
  function tableRows(table) {
    var skip = [];
    var rows = [];
    Array.prototype.forEach.call(table.rows, function (tr) {
      if (tr.hidden || tr.style.display === "none") return;
      var row = [];
      Array.prototype.forEach.call(tr.cells, function (cell, i) {
        if (cell.classList.contains("pick-col")) { skip[i] = true; return; }
        row.push(cellText(cell));
      });
      rows.push(row);
    });
    return rows;
  }
  function headText(h) {
    var c = h.cloneNode(true);
    c.querySelectorAll(".domain-count, .headerlink, .h2-tools").forEach(function (e) { e.remove(); });
    return c.textContent.replace("¶", "").trim();
  }
  function tableTitle(table) {
    var page = ((document.querySelector(".md-content__inner h1") || {}).textContent || document.title).replace("¶", "").trim();
    if (table.id === "cmp-table") return page;
    // 표 바로 위의 소제목(h2·h3)을 찾아 파일 이름에 붙임
    var found = {}, node = table, stop = document.querySelector(".md-content__inner");
    while (node && node !== stop && !(found.H2)) {
      if (node.previousElementSibling) {
        node = node.previousElementSibling;
        if (/^H[23]$/.test(node.tagName) && !found[node.tagName]) found[node.tagName] = headText(node);
      } else {
        node = node.parentElement;
      }
    }
    var parts = [found.H2, found.H3].filter(Boolean);
    return parts.length ? page + " - " + parts.join(" ") : page;
  }
  // 엑셀 맨 아래에 붙는 출처·인용 안내 (인용 문구는 mkdocs.yml 의 extra.site_citation)
  function meta(name) {
    var m = document.querySelector('meta[name="' + name + '"]');
    return m ? m.getAttribute("content") : "";
  }
  function pageUrl() {
    var u = location.href.split("#")[0];
    try { return decodeURIComponent(u); } catch (e) { return u; }
  }
  function citeFooter() {
    var lines = [L("이 자료가 도움이 되셨다면 논문·보고서에 기후데이터 길잡이를 인용해 주세요.", "If this table helped, please acknowledge the Korean Climate Data Navigator (KCDN) in your paper or report.")];
    if (meta("cdg-ack")) lines.push("Acknowledgements: " + meta("cdg-ack"));
    lines.push(L("출처 페이지: ", "Source page: ") + pageUrl());
    lines.push(L("이 표는 요약입니다. 분석·논문에 쓰기 전에는 각 자료의 공식 출처에서 반드시 다시 확인하세요.", "This table is a summary. Always re-check each dataset's official source before using it in an analysis or paper."));
    return lines;
  }

  function download(table) {
    var rows = tableRows(table);
    if (rows.length < 2) { alert(L("저장할 내용이 없습니다.", "Nothing to save.")); return; }
    var title = tableTitle(table);
    if (table.id === "cmp-table") title = L("자료 비교 - ", "Dataset comparison - ") + rows[0].slice(1).join(" vs ");
    var safe = title.replace(/[\\/:*?"<>|\[\]]/g, "").slice(0, 80);
    var blob = buildXlsx(rows, safe.replace(/[^0-9A-Za-z가-힣 _-]/g, "").slice(0, 31) || "Sheet1", citeFooter());
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = safe + ".xlsx";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  // ── 모든 표에 "엑셀로 저장" 버튼 ──────────────────────
  function addButtons() {
    document.querySelectorAll(".md-typeset table").forEach(function (table) {
      if (table.dataset.xlsx) return;
      table.dataset.xlsx = "1";
      var anchor = table.closest(".md-typeset__scrollwrap") || table.closest(".table-scroll") || table;
      var bar = document.createElement("div");
      bar.className = "table-tools";
      bar.innerHTML = '<button type="button" class="xlsx-btn" title="' + L("화면에 보이는 그대로 엑셀 파일로 저장", "Save the table as shown to an Excel file") + '">' + L("엑셀로 저장", "Save as Excel") + '</button>';
      bar.querySelector("button").addEventListener("click", function () { download(table); });
      anchor.parentNode.insertBefore(bar, anchor);
      // 변수 표: 표 위 안내 문구(영어 이름 보기)를 버튼 왼쪽에 함께 표시
      var box = table.closest(".var-tbl"), note = box && box.querySelector(":scope > .var-en-hint");
      if (note) { bar.insertBefore(note, bar.firstChild); bar.classList.add("has-note"); }
      if (table.id === "cmp-table") bar.classList.add("cmp-tools");
    });
  }

  // ── 자료 페이지: "활용 가능한 변수" 제목 옆에 전체 변수 한 번에 저장 ──
  function prevHeading(el, tags) {
    var n = el;
    while (n) {
      if (n.previousElementSibling) {
        n = n.previousElementSibling;
        if (tags.indexOf(n.tagName) >= 0) return n;
      } else n = n.parentElement;
      if (n && n.classList && n.classList.contains("md-content__inner")) return null;
    }
    return null;
  }
  function downloadAllVars(boxes) {
    var rows = [], head = null;
    boxes.forEach(function (box) {
      var table = box.querySelector("table");
      if (!table) return;
      var r = tableRows(table), h3 = prevHeading(box, ["H3", "H2"]);
      var group = h3 && h3.tagName === "H3" ? headText(h3) : "";
      if (!head) { head = [L("구분", "Group")].concat(r[0]); rows.push(head); }
      r.slice(1).forEach(function (row) { rows.push([group].concat(row)); });
    });
    if (rows.length < 2) { alert(L("저장할 내용이 없습니다.", "Nothing to save.")); return; }
    var page = ((document.querySelector(".md-content__inner h1") || {}).textContent || document.title).replace("¶", "").trim();
    var title = page + L(" - 전체 변수", " - all variables");
    var safe = title.replace(/[\\/:*?"<>|\[\]]/g, "").slice(0, 80);
    var blob = buildXlsx(rows, L("전체 변수", "All variables"), citeFooter());
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = safe + ".xlsx";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function addAllVarsButton() {
    var boxes = Array.prototype.slice.call(document.querySelectorAll(".var-tbl"));
    if (!boxes.length) return;
    var h2 = prevHeading(boxes[0], ["H2"]);
    if (!h2 || h2.querySelector(".h2-tools")) return;
    var span = document.createElement("span");
    span.className = "h2-tools";
    span.innerHTML = '<button type="button" class="xlsx-btn" title="' + L("이 자료의 모든 변수 표를 한 시트로 저장", "Save every variable table of this dataset to one sheet") + '">' + L("전체 변수 엑셀로 저장", "Save all variables as Excel") + "</button>";
    span.querySelector("button").addEventListener("click", function () { downloadAllVars(boxes); });
    h2.appendChild(span);
  }

  function init() { setTimeout(function () { addButtons(); addAllVarsButton(); }, 0); }  // 다른 스크립트가 표를 정리한 뒤 실행
  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
