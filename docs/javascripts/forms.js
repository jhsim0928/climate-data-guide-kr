// 알림 신청 · 데이터셋 제안 폼
// 발송 주소(endpoint)는 mkdocs.yml 의 extra.forms 에서 정합니다. 비어 있으면 "준비 중"으로 동작합니다.
(function () {
  // 영어판(/en/)이면 영어 문구를 씁니다
  var IS_EN = (document.documentElement.lang || "").toLowerCase().indexOf("en") === 0;
  function L(ko, en) { return IS_EN ? en : ko; }
  var LEVEL_LABEL = IS_EN ? { critical: "Critical", warning: "Warning", info: "Info" } : { critical: "중요", warning: "주의", info: "안내" };

  function show(form, text, kind) {
    var box = form.querySelector(".form-message");
    if (!box) return;
    box.textContent = text;
    box.className = "form-message " + (kind || "");
  }

  function values(form, name) {
    return Array.prototype.map.call(
      form.querySelectorAll('input[name="' + name + '"]:checked'),
      function (el) { return el.value; }
    );
  }

  // "전체" 체크박스와 개별 체크박스 연동
  function bindSelectAll(form) {
    form.querySelectorAll("[data-all]").forEach(function (all) {
      var name = all.getAttribute("data-all");
      var items = form.querySelectorAll('input[name="' + name + '"]');
      function sync() {
        var n = form.querySelectorAll('input[name="' + name + '"]:checked').length;
        all.checked = n === items.length && n > 0;
        all.indeterminate = n > 0 && n < items.length;
      }
      all.addEventListener("change", function () {
        items.forEach(function (el) { el.checked = all.checked; });
        all.indeterminate = false;
      });
      items.forEach(function (el) { el.addEventListener("change", sync); });
      sync();
    });
  }

  function post(endpoint, data) {
    // Google Apps Script 웹앱 등으로 보낼 때를 위한 형식 (응답은 읽지 않음)
    return fetch(endpoint, { method: "POST", mode: "no-cors", body: new URLSearchParams(data) });
  }

  function setupSubscribe(form) {
    bindSelectAll(form);

    // 데이터셋 페이지의 "알림 받기" 링크로 들어오면 해당 데이터셋을 미리 체크
    var pre = new URLSearchParams(location.search).get("dataset");
    if (pre) {
      var box = form.querySelector('input[name="datasets"][value="' + pre + '"]');
      if (box) { box.checked = true; box.dispatchEvent(new Event("change")); }
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var allDatasets = form.querySelector('[data-all="datasets"]').checked;
      var datasets = values(form, "datasets");
      var levels = values(form, "levels");
      var email = form.querySelector('input[name="email"]');
      var consent = form.querySelector('input[name="consent"]');

      if (!datasets.length) return show(form, L("알림 받을 데이터셋을 하나 이상 골라주세요.", "Please choose at least one dataset."), "error");
      if (!levels.length) return show(form, L("받을 공지 구분을 하나 이상 골라주세요.", "Please choose at least one notice level."), "error");
      if (!email.value || !email.checkValidity()) return show(form, L("이메일 주소를 확인해 주세요.", "Please check your email address."), "error");
      if (!consent.checked) return show(form, L("개인정보 수집·이용에 동의해 주세요.", "Please agree to the collection and use of your personal information."), "error");

      var endpoint = form.getAttribute("data-endpoint");
      var hp = form.querySelector('input[name="website"]');
      var summary =
        L((allDatasets ? "전체 데이터셋" : datasets.length + "개 데이터셋") + " · " +
        levels.map(function (l) { return LEVEL_LABEL[l]; }).join(", ") + " 공지",
        (allDatasets ? "All datasets" : datasets.length + " dataset(s)") + " · " +
        levels.map(function (l) { return LEVEL_LABEL[l]; }).join(", ") + " notices");

      if (!endpoint) {
        return show(form, summary + L("를 선택하셨어요. 메일 알림은 아직 준비 중이라 신청이 저장되지 않았습니다. 오픈하면 다시 신청해 주세요.", ": email alerts are not available yet, so nothing was saved. Please sign up again once they open."), "info");
      }
      show(form, L("신청하는 중…", "Subscribing…"), "info");
      post(endpoint, {
        type: "subscribe",
        email: email.value.trim(),
        datasets: allDatasets ? "all" : datasets.join(","),
        levels: levels.length === 3 ? "all" : levels.join(","),
        consent: "yes",
        lang: IS_EN ? "en" : "ko",
        // 이용자 정보(선택) — 통계용
        org_type: (form.querySelector('select[name="org_type"]') || {}).value || "",
        role: (form.querySelector('select[name="role"]') || {}).value || "",
        fields: values(form, "fields").join(","),
        website: hp ? hp.value : "",
        requested_at: new Date().toISOString()
      }).then(function () {
        form.reset();
        show(form, summary + L(" 알림 신청을 받았습니다. 확인 메일을 보냈습니다. 메일함에서 '신청 확인하기'를 눌러야 완료됩니다. 받은편지함에 없으면 꼭 스팸함을 확인하고 '스팸 아님'으로 표시해 주세요.", " — request received. We have sent a confirmation email; click 'Confirm subscription' in it to finish. If it is not in your inbox, check your spam folder and mark it as 'Not spam'."), "success");
      }).catch(function () {
        show(form, L("신청을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.", "Sending failed. Please try again later."), "error");
      });
    });
  }

  function setupSuggest(form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var get = function (n) { var el = form.elements[n]; return el ? el.value.trim() : ""; };
      var urlField = form.elements.url;
      var endpoint = form.getAttribute("data-endpoint");

      if (!get("name")) return show(form, L("데이터셋 이름을 적어주세요.", "Please enter the dataset name."), "error");
      if (!get("url") || !urlField.checkValidity() || !/^https?:\/\//.test(get("url")))
        return show(form, L("공식 페이지 주소를 https:// 로 시작하는 형식으로 적어주세요.", "Please enter the official page URL starting with https://"), "error");
      if (!endpoint) return show(form, L("제안 접수는 준비 중입니다. data4researchers@gmail.com 으로 메일을 보내주세요.", "Suggestions are not open yet. Please email data4researchers@gmail.com."), "info");

      var btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      show(form, L("보내는 중…", "Sending…"), "info");
      post(endpoint, {
        type: "suggest", name: get("name"), category: get("category"), url: get("url"),
        reason: get("reason"), notes: get("notes"), contact: get("contact"), website: get("website"), lang: IS_EN ? "en" : "ko",
        requested_at: new Date().toISOString()
      }).then(function () {
        form.reset();
        show(form, L("제안을 보냈습니다. 감사합니다! 확인 후 사이트에 정리해 올리겠습니다.", "Thank you! Your suggestion was sent. We will check it and add a page."), "success");
      }).catch(function () {
        show(form, L("보내지 못했습니다. 잠시 후 다시 시도하거나 data4researchers@gmail.com 으로 메일을 보내주세요.", "Sending failed. Please try again later or email data4researchers@gmail.com."), "error");
      }).then(function () { btn.disabled = false; });
    });
  }

  function setupFeedback(form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var get = function (n) { var el = form.elements[n]; return el ? el.value.trim() : ""; };
      var endpoint = form.getAttribute("data-endpoint");
      if (!get("message")) return show(form, L("의견 내용을 적어주세요.", "Please write your feedback."), "error");
      if (get("contact") && !form.elements.contact.checkValidity()) return show(form, L("이메일 주소를 확인해 주세요.", "Please check your email address."), "error");
      if (!endpoint) return show(form, L("지금은 data4researchers@gmail.com 으로 메일을 보내주세요.", "For now, please email data4researchers@gmail.com."), "info");
      var btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      show(form, L("보내는 중…", "Sending…"), "info");
      post(endpoint, {
        type: "feedback", kind: get("kind"), message: get("message"), contact: get("contact"),
        website: get("website"), lang: IS_EN ? "en" : "ko", requested_at: new Date().toISOString()
      }).then(function () {
        form.reset();
        show(form, L("의견을 보냈습니다. 고맙습니다! 사이트를 더 낫게 만드는 데 쓰겠습니다.", "Thank you! Your feedback was sent and will help improve the site."), "success");
      }).catch(function () {
        show(form, L("보내지 못했습니다. 잠시 후 다시 시도하거나 data4researchers@gmail.com 으로 메일을 보내주세요.", "Sending failed. Please try again later or email data4researchers@gmail.com."), "error");
      }).then(function () { btn.disabled = false; });
    });
  }

  function init() {
    document.querySelectorAll("#feedback-form:not([data-bound])").forEach(function (f) {
      f.setAttribute("data-bound", "1"); setupFeedback(f);
    });
    document.querySelectorAll("#subscribe-form:not([data-bound])").forEach(function (f) {
      f.setAttribute("data-bound", "1"); setupSubscribe(f);
    });
    document.querySelectorAll("#suggest-form:not([data-bound])").forEach(function (f) {
      f.setAttribute("data-bound", "1"); setupSuggest(f);
    });
  }

  if (typeof document$ !== "undefined") document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
