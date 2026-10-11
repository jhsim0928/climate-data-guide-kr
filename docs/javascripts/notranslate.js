// 브라우저 자동 번역(크롬 등)이 코드, 인용문, 데이터셋 이름을 바꾸지 않도록 보호합니다.
// 설명 문장은 그대로 번역되므로 외국 연구자도 크롬 번역으로 읽을 수 있습니다.
function protectFromTranslation() {
  document
    .querySelectorAll("pre, code, kbd, .citation-text, .notranslate")
    .forEach(function (el) {
      el.setAttribute("translate", "no");
      el.classList.add("notranslate");
    });
}

if (typeof document$ !== "undefined") {
  // Material 테마의 페이지 전환 이벤트
  document$.subscribe(protectFromTranslation);
} else {
  document.addEventListener("DOMContentLoaded", protectFromTranslation);
}
