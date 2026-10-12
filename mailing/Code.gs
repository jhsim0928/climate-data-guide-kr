/**
 * 기후데이터 길잡이 — 중요 공지 알림 메일 서버 (Google Apps Script)
 *
 * 하는 일
 *  1) 사이트의 "알림 신청" 양식을 받아 구독자 시트에 저장하고 확인 메일을 보냅니다(이중 확인).
 *  2) 메일 속 링크로 신청 확인·수신 거부를 처리합니다(수신 거부 시 정보 즉시 삭제).
 *  3) 하루 한 번 사이트의 공지 목록(assets/notices.json, 영어판 en/assets/notices.json)을 확인해,
 *     새 공지를 해당 데이터셋·공지 구분을 고른 구독자에게만 묶어서 보냅니다.
 *  4) 사이트의 "데이터셋 제안" 양식을 받아 제안 시트에 저장하고 운영자에게 알립니다.
 *  5) 각 페이지의 "정보 오류 신고"를 받아 오류 신고 시트에 저장하고 운영자에게 알립니다.
 *  6) 사이트의 "의견 보내기" 양식을 받아 의견 시트에 저장하고 운영자에게 알립니다.
 *  7) 영어판(/en/)에서 신청한 사람에게는 확인 메일·알림 메일을 영어로 보냅니다(구독자 시트 lang 열).
 *  8) 매일 오전 9시, 자동 공지 점검 결과(watch/digest.json)를 운영자에게 요약 메일로 보냅니다.
 *     새 공지 후보는 GitHub PR로 올라오며, 운영자가 머지(승인)하면 사이트에 반영되고
 *     한 시간 안에(오전 8시~오후 9시 사이) 구독자에게 알림 메일이 나갑니다.
 *
 * 설치: MAINTAINING.md 순서대로 setup()을 한 번 실행한 뒤 웹 앱으로 배포하세요.
 * 개인 Gmail 계정은 하루 발송 인원이 약 100명으로 제한됩니다.
 */

// ── 설정 ────────────────────────────────────────────────
var SITE_URL = 'https://data4researchers.kr/';
var NOTICES_URL = SITE_URL + 'assets/notices.json';
var NOTICES_URL_EN = SITE_URL + 'en/assets/notices.json';
var OWNER_EMAIL = 'data4researchers@gmail.com'; // 제안·오류 신고 알림을 받을 주소
var SEND_OLD = false; // testSend 실행 때만 true (오래된 공지도 보냄)
var OLD_DAYS = 30;  // 공지 날짜가 이보다 오래된 새 공지는 메일로 보내지 않음 (새 데이터셋 추가 시 과거 공지 일괄 발송 방지)
var SEND_FROM = 8, SEND_UNTIL = 21; // 구독자 알림은 이 시간대(프로젝트 시간대, Asia/Seoul)에만 발송 — 밤에 승인해도 아침에 나감
var DIGEST_HOUR = 9; // 운영자 요약 메일 시각
var DIGEST_URL = 'https://raw.githubusercontent.com/jhsim0928/climate-data-guide-kr/main/watch/digest.json';
// 요약 메일을 함께 받을 주소는 코드(공개 저장소)에 적지 않고 [프로젝트 설정 → 스크립트 속성]에
// 속성 DIGEST_TO, 값 'a@example.com,b@example.com' 형태로 넣습니다. OWNER_EMAIL에는 항상 갑니다.

var SHEET_SUBS = '구독자';
var SHEET_SUGGEST = '데이터셋 제안';
var SHEET_SENT = '발송 기록';
var SHEET_REPORT = '오류 신고';
var SHEET_FEEDBACK = '의견';
var FEEDBACK_HEADERS = ['received_at', 'kind', 'message', 'contact', 'lang', 'status'];
var REPORT_HEADERS = ['received_at', 'page_title', 'page_url', 'wrong', 'correct', 'source', 'contact', 'status', 'lang'];
var SUB_HEADERS = ['email', 'datasets', 'levels', 'status', 'token', 'requested_at', 'confirmed_at', 'updated_at', 'lang',
                   'org_type', 'role', 'fields'];
var COL_LANG = 9; // 구독자 시트의 lang 열 (비어 있으면 한국어)
var COL_PROFILE = 10; // 이용자 정보(선택, 통계용): org_type · role · fields — 사이트의 코드값 그대로 저장

// ── 메일·안내 문구 (한국어 / 영어) ─────────────────────────
var TXT = {
  ko: {
    site: '기후데이터 길잡이', home: SITE_URL, subscribePage: SITE_URL + 'subscribe/',
    level: { critical: '중요', warning: '주의', info: '안내' },
    confirmSubject: '중요 공지 알림 신청을 확인해 주세요',
    confirmIntro: ' 중요 공지 알림 신청을 받았습니다. 아래 버튼을 눌러야 신청이 완료됩니다.',
    confirmButton: '신청 확인하기',
    spamTip: '이 메일이 <b>스팸함</b>에 있었다면 <b>스팸 아님</b>으로 표시해 주세요. 그래야 앞으로 오는 알림이 받은편지함으로 들어옵니다. {OWNER} 주소를 연락처에 추가해 두셔도 좋습니다.',
    notMe: '본인이 신청하지 않았다면 이 메일을 무시하세요. 확인하지 않은 신청은 메일이 발송되지 않습니다.',
    changedSubject: '알림 설정이 바뀌었습니다',
    changedIntro: '알림 받을 데이터셋과 공지 구분이 아래처럼 바뀌었습니다.',
    prefsDatasets: '데이터셋', prefsLevels: '공지 구분', all: '전체', allDatasets: '전체 (앞으로 추가되는 데이터셋 포함)',
    digestSubject: function (n, crit) { return (crit ? '중요 공지 포함 · ' : '') + '새 공지 ' + n + '건'; },
    digestIntro: '고르신 데이터셋에 새 공지가 올라왔습니다.',
    original: '원문 공지', page: ' 페이지',
    digestNote: '공지는 운영자가 공식 출처를 확인한 내용이지만, 분석·논문에 반영하기 전에는 원문 공지를 꼭 다시 확인해 주세요.',
    footer: function (unsub, subPage) {
      return '기후데이터 길잡이 (<a href="' + SITE_URL + '">' + SITE_URL + '</a>)는 개인이 운영하는 비공식 프로젝트이며, ' +
        '소속 기관이나 자료 제공 기관의 공식 입장이 아닙니다.<br>' +
        '설정 변경: <a href="' + subPage + '">중요 공지 알림 신청 페이지</a>에서 같은 이메일로 다시 신청 · ' +
        '<a href="' + unsub + '">수신 거부(정보 즉시 삭제)</a>';
    },
    expiredTitle: '링크가 만료되었거나 이미 처리되었습니다.', expiredMsg: '알림을 다시 받으려면 사이트에서 새로 신청해 주세요.',
    doneTitle: '알림 신청이 완료되었습니다',
    doneMsg: '고르신 데이터셋에 새 공지가 올라오면 메일로 알려드릴게요. 알림이 스팸함으로 가지 않도록 {OWNER} 주소를 연락처에 추가하거나, 확인 메일을 \'스팸 아님\'으로 표시해 주세요.',
    unsubTitle: '수신 거부가 완료되었습니다', unsubMsg: '이메일 주소와 설정을 모두 삭제했습니다. 그동안 이용해 주셔서 감사합니다.',
    unknown: '알 수 없는 요청입니다', back: '로 돌아가기'
  },
  en: {
    site: 'Korean Climate Data Navigator', home: SITE_URL + 'en/', subscribePage: SITE_URL + 'en/subscribe/',
    level: { critical: 'Critical', warning: 'Warning', info: 'Info' },
    confirmSubject: 'Please confirm your notice alert subscription',
    confirmIntro: ' received your request for notice alerts. Please click the button below to confirm it.',
    confirmButton: 'Confirm subscription',
    spamTip: 'If this email was in your <b>spam folder</b>, please mark it as <b>Not spam</b> so that future alerts reach your inbox. Adding {OWNER} to your contacts also helps.',
    notMe: 'If you did not sign up, just ignore this email. Unconfirmed sign-ups never receive alerts.',
    changedSubject: 'Your alert settings have changed',
    changedIntro: 'Your datasets and notice levels are now set as follows.',
    prefsDatasets: 'Datasets', prefsLevels: 'Notice levels', all: 'All', allDatasets: 'All (including datasets added later)',
    digestSubject: function (n, crit) { return (crit ? 'Includes critical notice · ' : '') + n + ' new notice' + (n > 1 ? 's' : ''); },
    digestIntro: 'New notices have been posted for the datasets you follow.',
    original: 'Original notice', page: ' page',
    digestNote: 'Notices are checked against official sources by the maintainer, but please re-read the original announcement before acting on it in an analysis or paper.',
    footer: function (unsub, subPage) {
      return 'The Korean Climate Data Navigator (<a href="' + SITE_URL + 'en/">' + SITE_URL + 'en/</a>) is an unofficial project run by an individual ' +
        'and does not represent any employer or data provider.<br>' +
        'Change settings: sign up again with the same email on the <a href="' + subPage + '">notice alerts page</a> · ' +
        '<a href="' + unsub + '">Unsubscribe (deletes your data immediately)</a>';
    },
    expiredTitle: 'This link has expired or was already used.', expiredMsg: 'To receive alerts again, please sign up on the website.',
    doneTitle: 'Your subscription is confirmed',
    doneMsg: 'We will email you when new notices are posted for the datasets you chose. To keep alerts out of spam, add {OWNER} to your contacts or mark the confirmation email as \'Not spam\'.',
    unsubTitle: 'You have been unsubscribed', unsubMsg: 'Your email address and settings have been deleted. Thank you for using the Navigator.',
    unknown: 'Unknown request', back: 'Back to '
  }
};
function T_(lang) { return TXT[lang === 'en' ? 'en' : 'ko']; }
function langOf_(v) { return String(v || '').toLowerCase() === 'en' ? 'en' : 'ko'; }

// ── 최초 1회 실행: 시트 만들기 + 매일 확인 예약 ──────────
function setup() {
  var ss = SpreadsheetApp.getActive();
  ensureSheet_(ss, SHEET_SUBS, SUB_HEADERS);
  ensureSheet_(ss, SHEET_SUGGEST, ['received_at', 'name', 'category', 'url', 'reason', 'notes', 'contact', 'lang']);
  ensureSheet_(ss, SHEET_SENT, ['notice_key', 'first_seen_at', 'recipients']);
  ensureSheet_(ss, SHEET_REPORT, REPORT_HEADERS);
  ensureSheet_(ss, SHEET_FEEDBACK, FEEDBACK_HEADERS);
  setupTriggers();
  // 기존 공지는 '이미 보낸 것'으로 기록 — 설치 직후 옛 공지가 한꺼번에 나가지 않도록
  try { markAllAsSent_(); } catch (err) { Logger.log('공지 목록을 아직 읽을 수 없습니다: ' + err); }
  Logger.log('설치 완료. 이제 [배포 → 새 배포 → 웹 앱]으로 배포하세요.');
}

// ── 실행 예약: 구독자 알림 확인(매시간) + 운영자 요약 메일(매일 9시) ──
// 예약을 바꾼 뒤 한 번만 실행하면 됩니다. 이미 보낸 기록은 건드리지 않습니다.
function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'checkNotices' || f === 'dailyDigest') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('checkNotices').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('dailyDigest').timeBased().everyDays(1).atHour(DIGEST_HOUR).nearMinute(0).create();
  Logger.log('예약 완료: 공지 확인 매시간, 운영자 요약 매일 ' + DIGEST_HOUR + '시. 요약 받을 주소: ' + digestRecipients_().join(', '));
}

function ensureSheet_(ss, name, headers) {
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    sh.appendRow(headers);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  } else if (sh.getLastColumn() < headers.length) {
    // 예전에 만든 시트에 새 열(예: lang)의 제목이 없으면 채워 넣음
    sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  }
  return sh;
}

// ── 사이트 양식 → 여기로 POST ───────────────────────────
function doPost(e) {
  var p = (e && e.parameter) || {};
  if (p.website) return text_('ok'); // 스팸 방지용 숨은 칸이 채워져 있으면 무시
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    if (p.type === 'subscribe') return handleSubscribe_(p);
    if (p.type === 'suggest') return handleSuggest_(p);
    if (p.type === 'report') return handleReport_(p);
    if (p.type === 'feedback') return handleFeedback_(p);
    return text_('unknown');
  } finally {
    lock.releaseLock();
  }
}

function handleSubscribe_(p) {
  var email = String(p.email || '').trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || p.consent !== 'yes') return text_('invalid');
  var datasets = clean_(p.datasets) || 'all';
  var levels = clean_(p.levels) || 'all';
  var lang = langOf_(p.lang);
  var profile = [clean_(p.org_type).slice(0, 40), clean_(p.role).slice(0, 40), clean_(String(p.fields || '').replace(/_/g, '-')).replace(/-/g, '_').slice(0, 200)];
  var sh = ensureSheet_(SpreadsheetApp.getActive(), SHEET_SUBS, SUB_HEADERS);
  var row = findRow_(sh, email);
  var now = new Date();
  if (row) {
    var status = sh.getRange(row, 4).getValue();
    sh.getRange(row, 2, 1, 2).setValues([[datasets, levels]]);
    sh.getRange(row, 8).setValue(now);
    sh.getRange(row, COL_LANG).setValue(lang);
    if (profile.join('')) sh.getRange(row, COL_PROFILE, 1, 3).setValues([profile]);  // 다시 신청하며 답했을 때만 갱신
    var token = sh.getRange(row, 5).getValue();
    if (status === 'active') {
      var t = T_(lang);
      sendMail_(email, '[' + t.site + '] ' + t.changedSubject,
        '<p>' + t.changedIntro + '</p>' + prefsHtml_(datasets, levels, lang) + footer_(token, lang), lang);
      return text_('updated');
    }
    sendConfirm_(email, token, datasets, levels, lang);
    return text_('pending');
  }
  var newToken = Utilities.getUuid().replace(/-/g, '');
  sh.appendRow([email, datasets, levels, 'pending', newToken, now, '', now, lang].concat(profile));
  sendConfirm_(email, newToken, datasets, levels, lang);
  return text_('pending');
}

function handleSuggest_(p) {
  var sh = ensureSheet_(SpreadsheetApp.getActive(), SHEET_SUGGEST,
    ['received_at', 'name', 'category', 'url', 'reason', 'notes', 'contact', 'lang']);
  sh.appendRow([new Date(), cut_(p.name), cut_(p.category), cut_(p.url), cut_(p.reason, 2000), cut_(p.notes, 2000), cut_(p.contact), langOf_(p.lang)]);
  var owner = OWNER_EMAIL || Session.getEffectiveUser().getEmail();
  if (owner) {
    MailApp.sendEmail({
      to: owner, name: TXT.ko.site,
      subject: '[' + TXT.ko.site + '] 새 데이터셋 제안' + (langOf_(p.lang) === 'en' ? ' (영어판)' : '') + ': ' + cut_(p.name, 80),
      body: '데이터셋: ' + p.name + '\n종류: ' + p.category + '\n공식 페이지: ' + p.url +
        '\n용도: ' + (p.reason || '-') + '\n중단·변경 소식: ' + (p.notes || '-') + '\n제안자: ' + (p.contact || '-')
    });
  }
  return text_('ok');
}

function handleReport_(p) {
  if (!String(p.wrong || '').trim()) return text_('invalid');
  var sh = ensureSheet_(SpreadsheetApp.getActive(), SHEET_REPORT, REPORT_HEADERS);
  sh.appendRow([new Date(), cut_(p.title, 200), cut_(p.page, 500), cut_(p.wrong, 3000), cut_(p.correct, 3000),
    cut_(p.source, 1000), cut_(p.contact, 200), '접수', langOf_(p.lang)]);
  var owner = OWNER_EMAIL || Session.getEffectiveUser().getEmail();
  if (owner) {
    var mail = { to: owner, name: TXT.ko.site,
      subject: '[' + TXT.ko.site + '] 정보 오류 신고' + (langOf_(p.lang) === 'en' ? ' (영어판)' : '') + ': ' + cut_(p.title, 80),
      body: '페이지: ' + (p.title || '-') + '\n' + (p.page || '-') +
        '\n\n어떤 정보가 틀렸나요?\n' + (p.wrong || '-') +
        '\n\n올바른 정보\n' + (p.correct || '-') +
        '\n\n근거 출처\n' + (p.source || '-') +
        '\n\n신고자 연락처: ' + (p.contact || '-') };
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(p.contact || '').trim())) mail.replyTo = String(p.contact).trim();
    MailApp.sendEmail(mail);
  }
  return text_('ok');
}

var FEEDBACK_KIND = { idea: '기능 제안', improve: '사이트 개선', thanks: '칭찬·응원', other: '기타' };
function handleFeedback_(p) {
  if (!String(p.message || '').trim()) return text_('invalid');
  var kind = FEEDBACK_KIND[p.kind] || '기타';
  var lang = langOf_(p.lang);
  var sh = ensureSheet_(SpreadsheetApp.getActive(), SHEET_FEEDBACK, FEEDBACK_HEADERS);
  sh.appendRow([new Date(), kind, cut_(p.message, 5000), cut_(p.contact, 200), lang, '접수']);
  var owner = OWNER_EMAIL || Session.getEffectiveUser().getEmail();
  if (owner) {
    var mail = { to: owner, name: TXT.ko.site,
      subject: '[' + TXT.ko.site + '] 새 의견 (' + kind + (lang === 'en' ? ', 영어판' : '') + ')',
      body: '종류: ' + kind + '\n\n' + (p.message || '-') + '\n\n답변 받을 이메일: ' + (p.contact || '-') };
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(p.contact || '').trim())) mail.replyTo = String(p.contact).trim();
    MailApp.sendEmail(mail);
  }
  return text_('ok');
}

// ── 발송 테스트: 이미 보낸 공지 하나를 '안 보낸 것'으로 되돌리고 바로 발송 ──
// Apps Script 편집기 위쪽 함수 목록에서 testSend 를 고르고 [실행]을 누르세요.
// 구독자 시트에서 status 가 active 이고, 이 데이터셋(또는 all)과 공지 구분(또는 all)을 고른 사람에게만 갑니다.
var TEST_KEY = 'oisst|2026-10-02|NCEI 클라우드 이전으로 자료 접근 지연 (2026-10-30까지 예정)';
function testSend() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SENT);
  if (sh.getLastRow() <= 1) markAllAsSent_();  // 발송 기록이 비어 있으면 먼저 채움 (옛 공지 일괄 발송 방지)
  var rows = sh.getDataRange().getValues();
  var removed = 0;
  for (var i = rows.length - 1; i >= 1; i--) {
    if (rows[i][0] === TEST_KEY) { sh.deleteRow(i + 1); removed++; }
  }
  Logger.log('발송 기록에서 지운 행: ' + removed + '개 → 지금 발송합니다');
  SEND_OLD = true;
  checkNotices();
  Logger.log('완료. 구독자 메일함(스팸함 포함)을 확인하세요.');
}

// ── 메일 속 링크(확인·수신 거부) → 여기로 GET ────────────
function doGet(e) {
  var p = (e && e.parameter) || {};
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS);
  var row = p.token ? findRowByToken_(sh, p.token) : null;
  var t = T_(p.lang);
  if (!row) return page_(t.expiredTitle, t.expiredMsg, p.lang);
  var lang = langOf_(sh.getLastColumn() >= COL_LANG ? sh.getRange(row, COL_LANG).getValue() : p.lang);
  t = T_(lang);
  if (p.action === 'confirm') {
    sh.getRange(row, 4).setValue('active');
    sh.getRange(row, 7).setValue(new Date());
    return page_(t.doneTitle, t.doneMsg.replace('{OWNER}', OWNER_EMAIL), lang);
  }
  if (p.action === 'unsubscribe') {
    sh.deleteRow(row); // 개인정보 처리방침: 수신 거부 시 지체 없이 파기
    return page_(t.unsubTitle, t.unsubMsg, lang);
  }
  return page_(t.unknown, '', lang);
}

// ── 매일 실행: 새 공지를 구독자에게 ───────────────────────
// 확인 링크를 30일 넘게 누르지 않은 신청은 삭제 (개인정보 처리방침 2항)
function cleanupPending_() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS);
  var rows = sh.getDataRange().getValues();
  var limit = Date.now() - 30 * 24 * 3600 * 1000;
  for (var i = rows.length - 1; i >= 1; i--) {
    var t = new Date(rows[i][5]).getTime();
    if (rows[i][3] === 'pending' && t && t < limit) sh.deleteRow(i + 1);
  }
}

function checkNotices() {
  var hour = Number(Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'H'));
  if (!SEND_OLD && (hour < SEND_FROM || hour >= SEND_UNTIL)) return;  // 밤에는 보내지 않음
  cleanupPending_();
  var file = fetchNoticeFile_(NOTICES_URL);
  var notices = file.notices || [];
  // 영어판 공지(같은 key) — 영어 구독자에게는 영어 제목·본문으로 보냄. 못 읽으면 한국어로 대신 보냄
  var enByKey = {};
  try { fetchNotices_(NOTICES_URL_EN).forEach(function (n) { enByKey[n.key] = n; }); }
  catch (err) { Logger.log('영어판 공지 목록을 읽지 못했습니다: ' + err); }

  var sentSh = SpreadsheetApp.getActive().getSheetByName(SHEET_SENT);
  if (sentSh.getLastRow() <= 1) {
    // 처음 실행: 지금까지의 공지는 '이미 보낸 것'으로 기록만 하고 끝냄 (옛 공지 일괄 발송 방지)
    markAllAsSent_();
    return;
  }
  var sent = {};
  sentSh.getDataRange().getValues().slice(1).forEach(function (r) { sent[r[0]] = true; });
  var fresh = notices.filter(function (n) { return !sent[n.key]; });

  // 사이트에 새로 추가된 자료의 기존 공지는 '새 소식'이 아니므로 보내지 않고 기록만 함
  // (발송 기록 시트의 'dataset|<id>' 행 = 이미 알고 있는 자료. 처음 실행 때는 지금 자료 전부를 기록만 함)
  if (file.datasets && file.datasets.length) {
    var known = {}, hasMarkers = false;
    Object.keys(sent).forEach(function (k) { if (k.indexOf('dataset|') === 0) { known[k.slice(8)] = true; hasMarkers = true; } });
    var added = file.datasets.filter(function (id) { return !known[id]; });
    if (added.length) {
      var at = new Date();
      added.forEach(function (id) { sentSh.appendRow(['dataset|' + id, at, 0]); });
      if (hasMarkers) {
        var backfill = fresh.filter(function (n) { return added.indexOf(n.dataset_id) !== -1; });
        backfill.forEach(function (n) { sentSh.appendRow([n.key, at, 0]); });
        if (backfill.length) Logger.log('새로 추가된 자료(' + added.join(', ') + ')의 기존 공지 ' + backfill.length + '건은 발송하지 않고 기록만 했습니다');
        fresh = fresh.filter(function (n) { return backfill.indexOf(n) === -1; });
      }
    }
  }
  if (!fresh.length) return;

  // 오래된 공지(공지 날짜가 OLD_DAYS일보다 이전)는 메일로 보내지 않고 '보낸 것'으로만 기록
  // — 새 데이터셋을 추가하면서 과거 공지가 한꺼번에 들어와도 구독자에게 옛 소식이 몰려가지 않게 함
  var limit = Date.now() - OLD_DAYS * 24 * 3600 * 1000;
  var old = fresh.filter(function (n) { var t = new Date(n.date).getTime(); return t && t < limit; });
  if (old.length && !SEND_OLD) {
    var stamp = new Date();
    old.forEach(function (n) { sentSh.appendRow([n.key, stamp, 0]); });
    Logger.log('오래된 공지 ' + old.length + '건은 발송하지 않고 기록만 했습니다');
    fresh = fresh.filter(function (n) { return old.indexOf(n) === -1; });
    if (!fresh.length) return;
  }

  var subs = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS).getDataRange().getValues().slice(1)
    .filter(function (r) { return r[3] === 'active'; });
  var plan = [];
  subs.forEach(function (r) {
    var ds = String(r[1]).split(','), lv = String(r[2]).split(',');
    var mine = fresh.filter(function (n) {
      return (ds.indexOf('all') !== -1 || ds.indexOf(n.dataset_id) !== -1) &&
        (lv.indexOf('all') !== -1 || lv.indexOf(n.level) !== -1);
    });
    if (mine.length) plan.push({ email: r[0], token: r[4], items: mine, lang: langOf_(r[COL_LANG - 1]) });
  });

  if (plan.length > MailApp.getRemainingDailyQuota()) {
    // 오늘 보낼 수 있는 인원을 넘으면 보내지 않고 운영자에게 알린 뒤 내일 다시 시도
    MailApp.sendEmail(OWNER_EMAIL || Session.getEffectiveUser().getEmail(), '[' + TXT.ko.site + '] 알림 발송 보류',
      '오늘 남은 발송 한도(' + MailApp.getRemainingDailyQuota() + '명)보다 받을 사람(' + plan.length +
      '명)이 많아 발송을 내일로 미뤘습니다. 구독자가 늘었다면 뉴스레터 서비스로 옮길 때가 되었습니다.');
    return;
  }
  Logger.log('새 공지 ' + fresh.length + '건 → 받을 사람 ' + plan.length + '명');
  plan.forEach(function (x) {
    var items = x.lang === 'en' ? x.items.map(function (n) { return enByKey[n.key] || n; }) : x.items;
    var crit = items.some(function (n) { return n.level === 'critical'; });
    var t = T_(x.lang);
    sendMail_(x.email, '[' + t.site + '] ' + t.digestSubject(items.length, crit),
      noticesHtml_(items, x.lang) + footer_(x.token, x.lang), x.lang);
  });
  var now = new Date();
  fresh.forEach(function (n) {
    var count = plan.filter(function (x) { return x.items.indexOf(n) !== -1; }).length;
    sentSh.appendRow([n.key, now, count]);
  });
}

function markAllAsSent_() {
  var sentSh = SpreadsheetApp.getActive().getSheetByName(SHEET_SENT);
  var now = new Date();
  var file = fetchNoticeFile_(NOTICES_URL);
  (file.notices || []).forEach(function (n) { sentSh.appendRow([n.key, now, 0]); });
  (file.datasets || []).forEach(function (id) { sentSh.appendRow(['dataset|' + id, now, 0]); });
}

function fetchNotices_(url) { return fetchNoticeFile_(url).notices || []; }
function fetchNoticeFile_(url) {
  var res = UrlFetchApp.fetch((url || NOTICES_URL) + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('공지 목록 응답 ' + res.getResponseCode());
  return JSON.parse(res.getContentText());
}

// ── 매일 9시: 운영자에게 자동 공지 점검 요약 ─────────────────
// 06시 GitHub Actions가 공지 페이지 변경을 찾고(watch/changes.json), 08시쯤 Claude 점검이 진짜 공지를 골라
// 공지 후보 PR과 watch/digest.json을 만듭니다. 이 함수는 그 결과를 메일로 정리해 보냅니다.
function digestRecipients_() {
  var extra = PropertiesService.getScriptProperties().getProperty('DIGEST_TO') || '';
  var list = [OWNER_EMAIL || Session.getEffectiveUser().getEmail()];
  extra.split(/[,;\s]+/).forEach(function (a) { if (a && list.indexOf(a) === -1) list.push(a); });
  return list;
}

function dailyDigest() {
  var tz = Session.getScriptTimeZone();
  var today = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  var d = null, err = '';
  try {
    var res = UrlFetchApp.fetch(DIGEST_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (res.getResponseCode() === 200) d = JSON.parse(res.getContentText());
    else err = '점검 결과 파일 응답 ' + res.getResponseCode();
  } catch (e) { err = String(e); }

  var colors = { critical: '#c62828', warning: '#b26a00', info: '#546e7a' };
  var lvName = TXT.ko.level;
  var box = function (bg, html) { return '<div style="background:' + bg + ';padding:12px 16px;border-radius:8px;margin:14px 0">' + html + '</div>'; };
  var btn = function (url, label) {
    return '<a href="' + esc_(url) + '" style="display:inline-block;padding:10px 18px;background:#1f6f8b;color:#fff;border-radius:6px;text-decoration:none;font-weight:bold">' + label + '</a>';
  };
  var html = '', subject;
  var fresh = d && d.date === today;
  var cands = (fresh && d.candidates) || [];
  var pending = (d && d.pending) || [];

  if (!fresh) {
    subject = '[운영] ' + today + ' 공지 점검 결과 없음 — 확인 필요';
    html += box('#fdecea', '<b>오늘 자동 점검 결과가 올라오지 않았습니다.</b><br>' +
      (d ? '마지막 점검: ' + esc_(d.date) : esc_(err || '결과 파일을 읽지 못했습니다')) +
      '<br>GitHub Actions의 "공지 페이지 점검"이나 Claude의 예약 작업이 실패했을 수 있습니다. Claude에게 "오늘 공지 점검이 안 됐어"라고 알려 주세요.');
  } else {
    subject = '[운영] ' + today + ' 공지 점검 — ' + (cands.length ? '새 공지 후보 ' + cands.length + '건, 승인 필요' : '새 공지 없음');
    if (d.summary) html += '<p style="font-size:15px">' + esc_(d.summary) + '</p>';
  }

  if (cands.length) {
    html += '<h3 style="margin:22px 0 6px">새 공지 후보</h3>' + cands.map(function (n) {
      var c = colors[n.level] || '#999';
      return '<div style="border-left:4px solid ' + c + ';padding:8px 14px;margin:12px 0">' +
        '<div style="font-size:13px;color:' + c + ';font-weight:bold">' + (lvName[n.level] || esc_(n.level)) + ' · ' + esc_(n.dataset || n.dataset_id) + ' · ' + esc_(n.date || '') + '</div>' +
        '<div style="font-size:16px;font-weight:bold;margin:4px 0">' + esc_(n.title) + '</div>' +
        (n.why ? '<div style="font-size:14px;color:#333">' + esc_(n.why) + '</div>' : '') +
        '<div style="font-size:13px;margin-top:6px"><a href="' + esc_(n.source) + '">원문 공지</a></div></div>';
    }).join('');
    if (d.pr && d.pr.url) {
      html += box('#e8f4f8', '<b>승인 방법</b><br>아래 버튼 → GitHub 페이지 맨 아래 <b>Merge pull request</b> → <b>Confirm merge</b>.<br>' +
        '승인하면 몇 분 뒤 사이트에 올라가고, 한 시간 안에(오전 8시~오후 9시) 해당 자료를 구독한 사람에게 알림 메일이 나갑니다.<br>' +
        '내용을 고치고 싶으면 Claude에게 PR 링크와 함께 말해 주세요. 공지가 아니면 <b>Close pull request</b>를 누르면 됩니다.' +
        '<p style="margin:12px 0 0">' + btn(d.pr.url, '검토하고 승인하기') + '</p>');
    }
  }

  var older = pending.filter(function (p) { return !(d && d.pr && p.url === d.pr.url); });
  if (older.length) {
    html += '<h3 style="margin:22px 0 6px">아직 승인하지 않은 공지 후보</h3><ul>' + older.map(function (p) {
      return '<li><a href="' + esc_(p.url) + '">' + esc_(p.title) + '</a>' + (p.opened ? ' (' + esc_(p.opened) + ')' : '') + '</li>';
    }).join('') + '</ul>';
  }

  if (fresh && d.notes && d.notes.length) {
    html += '<h3 style="margin:22px 0 6px">참고</h3><ul>' + d.notes.map(function (x) { return '<li>' + esc_(x) + '</li>'; }).join('') + '</ul>';
  }
  if (fresh && d.ignored && d.ignored.length) {
    html += '<h3 style="margin:22px 0 6px;color:#555">바뀌었지만 공지가 아니라고 본 페이지 ' + d.ignored.length + '곳</h3><ul style="color:#555;font-size:13px">' +
      d.ignored.map(function (x) {
        return '<li>' + esc_((x.datasets || []).join(', ')) + ' — ' + esc_(x.reason || '') + ' (<a href="' + esc_(x.url) + '">페이지</a>)</li>';
      }).join('') + '</ul>';
  }
  if (fresh && d.errors && d.errors.length) {
    html += '<h3 style="margin:22px 0 6px;color:#555">며칠째 열리지 않는 페이지 ' + d.errors.length + '곳</h3><ul style="color:#555;font-size:13px">' +
      d.errors.map(function (x) {
        return '<li>' + esc_((x.datasets || []).join(', ')) + ' — ' + esc_(x.error || '') + ', ' + (x.fails || '?') + '일째 (<a href="' + esc_(x.url) + '">페이지</a>)</li>';
      }).join('') + '</ul><p style="color:#777;font-size:13px">주소가 바뀌었을 수 있습니다. Claude에게 확인을 부탁하세요.</p>';
  }
  if (fresh && d.watch) {
    html += '<p style="color:#888;font-size:12px;margin-top:24px">점검한 공지 페이지 ' + (d.watch.checked || 0) + '곳 · 열림 ' + (d.watch.ok || 0) +
      ' · 바뀐 곳 ' + (d.watch.changed || 0) + ' · 점검 ' + esc_(d.watch.date || '') + '</p>';
  }
  html += '<p style="color:#888;font-size:12px">이 메일은 운영자에게만 가는 요약입니다. 구독자 메일은 승인한 공지만 나갑니다.</p>';

  MailApp.sendEmail({ to: digestRecipients_().join(','), subject: '[' + TXT.ko.site + '] ' + subject, htmlBody: html, name: TXT.ko.site + ' 점검',
    body: html.replace(/<br>|<\/(p|div|li|h3)>/g, '\n').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&') });
}

// ── 메일 본문 ───────────────────────────────────────────
function sendConfirm_(email, token, datasets, levels, lang) {
  var t = T_(lang);
  var url = ScriptApp.getService().getUrl() + '?action=confirm&token=' + token + '&lang=' + langOf_(lang);
  sendMail_(email, '[' + t.site + '] ' + t.confirmSubject,
    '<p>' + t.site + t.confirmIntro + '</p>' +
    '<p><a href="' + url + '" style="display:inline-block;padding:10px 18px;background:#00897b;color:#fff;border-radius:6px;text-decoration:none">' + t.confirmButton + '</a></p>' +
    prefsHtml_(datasets, levels, lang) +
    '<p style="background:#fff8e1;padding:10px 14px;border-radius:6px;color:#5d4037">' + t.spamTip.replace('{OWNER}', OWNER_EMAIL) + '</p>' +
    '<p style="color:#777">' + t.notMe + '</p>' +
    footer_(token, lang), lang);
}

function prefsHtml_(datasets, levels, lang) {
  var t = T_(lang);
  var lv = levels === 'all' ? t.all : levels.split(',').map(function (l) { return t.level[l] || l; }).join(', ');
  return '<p style="background:#f5f7fa;padding:10px 14px;border-radius:6px">' + t.prefsDatasets + ': ' +
    esc_(datasets === 'all' ? t.allDatasets : datasets) + '<br>' + t.prefsLevels + ': ' + esc_(lv) + '</p>';
}

function noticesHtml_(items, lang) {
  var t = T_(lang);
  var colors = { critical: '#c62828', warning: '#b26a00', info: '#546e7a' };
  return '<p>' + t.digestIntro + '</p>' + items.map(function (n) {
    return '<div style="border-left:4px solid ' + (colors[n.level] || '#999') + ';padding:8px 14px;margin:14px 0">' +
      '<div style="font-size:13px;color:' + (colors[n.level] || '#999') + ';font-weight:bold">' +
      (t.level[n.level] || n.level) + ' · ' + esc_(n.dataset_name) + ' · ' + esc_(n.date) + '</div>' +
      '<div style="font-size:16px;font-weight:bold;margin:4px 0">' + esc_(n.title) + '</div>' +
      '<div style="font-size:14px;color:#333">' + esc_(n.body || '') + '</div>' +
      '<div style="font-size:13px;margin-top:6px"><a href="' + esc_(n.source) + '">' + t.original + '</a> · ' +
      '<a href="' + esc_(n.url) + '">' + esc_(n.dataset_name) + t.page + '</a></div></div>';
  }).join('') +
  '<p style="color:#777;font-size:13px">' + t.digestNote + '</p>';
}

function footer_(token, lang) {
  var t = T_(lang);
  var unsub = ScriptApp.getService().getUrl() + '?action=unsubscribe&token=' + token + '&lang=' + langOf_(lang);
  return '<hr style="border:0;border-top:1px solid #ddd;margin:20px 0">' +
    '<p style="color:#888;font-size:12px">' + t.footer(unsub, t.subscribePage) + '</p>';
}

function sendMail_(to, subject, html, lang) {
  MailApp.sendEmail({ to: to, subject: subject, htmlBody: html, name: T_(lang).site,
    body: html.replace(/<br>/g, '\n').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&') });
}

// ── 도우미 ──────────────────────────────────────────────
function findRow_(sh, email) {
  var col = sh.getRange(2, 1, Math.max(sh.getLastRow() - 1, 1), 1).getValues();
  for (var i = 0; i < col.length; i++) if (String(col[i][0]).toLowerCase() === email) return i + 2;
  return null;
}
function findRowByToken_(sh, token) {
  var col = sh.getRange(2, 5, Math.max(sh.getLastRow() - 1, 1), 1).getValues();
  for (var i = 0; i < col.length; i++) if (col[i][0] && col[i][0] === token) return i + 2;
  return null;
}
function clean_(v) { return String(v || '').replace(/[^a-z0-9,\-]/gi, '').slice(0, 500); }
function cut_(v, n) { return String(v || '').slice(0, n || 300); }
function esc_(s) {
  return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
}
function text_(s) { return ContentService.createTextOutput(s); }
function page_(title, msg, lang) {
  var t = T_(lang);
  var back = langOf_(lang) === 'en' ? t.back + t.site : t.site + t.back;
  return HtmlService.createHtmlOutput(
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<div style="font-family:sans-serif;max-width:520px;margin:60px auto;padding:0 20px;line-height:1.6">' +
    '<h2>' + esc_(title) + '</h2><p>' + esc_(msg) + '</p><p><a href="' + t.home + '">' + esc_(back) + '</a></p></div>'
  ).setTitle(t.site);
}
