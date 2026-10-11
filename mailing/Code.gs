/**
 * 기후데이터 길잡이 — 변경 알림 메일 서버 (Google Apps Script)
 *
 * 하는 일
 *  1) 사이트의 "알림 신청" 양식을 받아 구독자 시트에 저장하고 확인 메일을 보냅니다(이중 확인).
 *  2) 메일 속 링크로 신청 확인·수신 거부를 처리합니다(수신 거부 시 정보 즉시 삭제).
 *  3) 하루 한 번 사이트의 공지 목록(assets/notices.json)을 확인해, 새 공지를
 *     해당 데이터셋·공지 구분을 고른 구독자에게만 묶어서 보냅니다.
 *  4) 사이트의 "데이터셋 제안" 양식을 받아 제안 시트에 저장하고 운영자에게 알립니다.
 *
 * 설치: README의 순서대로 setup()을 한 번 실행한 뒤 웹 앱으로 배포하세요.
 * 개인 Gmail 계정은 하루 발송 인원이 약 100명으로 제한됩니다.
 */

// ── 설정 ────────────────────────────────────────────────
var SITE_NAME = '기후데이터 길잡이';
var SITE_URL = 'https://data4researchers.kr/';
var NOTICES_URL = SITE_URL + 'assets/notices.json';
var SUBSCRIBE_PAGE = SITE_URL + 'subscribe/';
var SEND_HOUR = 9; // 매일 공지 확인 시각 (프로젝트 시간대 기준, Asia/Seoul 권장)

var SHEET_SUBS = '구독자';
var SHEET_SUGGEST = '데이터셋 제안';
var SHEET_SENT = '발송 기록';
var SUB_HEADERS = ['email', 'datasets', 'levels', 'status', 'token', 'requested_at', 'confirmed_at', 'updated_at'];
var LEVEL_LABEL = { critical: '중요', warning: '주의', info: '안내' };

// ── 최초 1회 실행: 시트 만들기 + 매일 확인 예약 ──────────
function setup() {
  var ss = SpreadsheetApp.getActive();
  ensureSheet_(ss, SHEET_SUBS, SUB_HEADERS);
  ensureSheet_(ss, SHEET_SUGGEST, ['received_at', 'name', 'category', 'url', 'reason', 'notes', 'contact']);
  ensureSheet_(ss, SHEET_SENT, ['notice_key', 'first_seen_at', 'recipients']);
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'checkNotices') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('checkNotices').timeBased().everyDays(1).atHour(SEND_HOUR).create();
  // 기존 공지는 '이미 보낸 것'으로 기록 — 설치 직후 옛 공지가 한꺼번에 나가지 않도록
  try { markAllAsSent_(); } catch (err) { Logger.log('공지 목록을 아직 읽을 수 없습니다: ' + err); }
  Logger.log('설치 완료. 이제 [배포 → 새 배포 → 웹 앱]으로 배포하세요.');
}

function ensureSheet_(ss, name, headers) {
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    sh.appendRow(headers);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, headers.length).setFontWeight('bold');
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
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS);
  var row = findRow_(sh, email);
  var now = new Date();
  if (row) {
    var status = sh.getRange(row, 4).getValue();
    sh.getRange(row, 2, 1, 2).setValues([[datasets, levels]]);
    sh.getRange(row, 8).setValue(now);
    var token = sh.getRange(row, 5).getValue();
    if (status === 'active') {
      sendMail_(email, '[' + SITE_NAME + '] 알림 설정이 바뀌었습니다',
        '<p>알림 받을 데이터셋과 공지 구분이 아래처럼 바뀌었습니다.</p>' + prefsHtml_(datasets, levels) + footer_(token));
      return text_('updated');
    }
    sendConfirm_(email, token, datasets, levels);
    return text_('pending');
  }
  var newToken = Utilities.getUuid().replace(/-/g, '');
  sh.appendRow([email, datasets, levels, 'pending', newToken, now, '', now]);
  sendConfirm_(email, newToken, datasets, levels);
  return text_('pending');
}

function handleSuggest_(p) {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SUGGEST);
  sh.appendRow([new Date(), cut_(p.name), cut_(p.category), cut_(p.url), cut_(p.reason, 2000), cut_(p.notes, 2000), cut_(p.contact)]);
  var owner = Session.getEffectiveUser().getEmail();
  if (owner) {
    MailApp.sendEmail({
      to: owner, name: SITE_NAME,
      subject: '[' + SITE_NAME + '] 새 데이터셋 제안: ' + cut_(p.name, 80),
      body: '데이터셋: ' + p.name + '\n종류: ' + p.category + '\n공식 페이지: ' + p.url +
        '\n용도: ' + (p.reason || '-') + '\n중단·변경 소식: ' + (p.notes || '-') + '\n제안자: ' + (p.contact || '-')
    });
  }
  return text_('ok');
}

// ── 메일 속 링크(확인·수신 거부) → 여기로 GET ────────────
function doGet(e) {
  var p = (e && e.parameter) || {};
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS);
  var row = p.token ? findRowByToken_(sh, p.token) : null;
  if (!row) return page_('링크가 만료되었거나 이미 처리되었습니다.', '알림을 다시 받으려면 사이트에서 새로 신청해 주세요.');
  if (p.action === 'confirm') {
    sh.getRange(row, 4).setValue('active');
    sh.getRange(row, 7).setValue(new Date());
    return page_('알림 신청이 완료되었습니다', '고르신 데이터셋에 새 공지가 올라오면 메일로 알려드릴게요.');
  }
  if (p.action === 'unsubscribe') {
    sh.deleteRow(row); // 개인정보 처리방침: 수신 거부 시 지체 없이 파기
    return page_('수신 거부가 완료되었습니다', '이메일 주소와 설정을 모두 삭제했습니다. 그동안 이용해 주셔서 감사합니다.');
  }
  return page_('알 수 없는 요청입니다', '');
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
  cleanupPending_();
  var notices = fetchNotices_();
  var sentSh = SpreadsheetApp.getActive().getSheetByName(SHEET_SENT);
  if (sentSh.getLastRow() <= 1) {
    // 처음 실행: 지금까지의 공지는 '이미 보낸 것'으로 기록만 하고 끝냄 (옛 공지 일괄 발송 방지)
    markAllAsSent_();
    return;
  }
  var sent = {};
  sentSh.getDataRange().getValues().slice(1).forEach(function (r) { sent[r[0]] = true; });
  var fresh = notices.filter(function (n) { return !sent[n.key]; });
  if (!fresh.length) return;

  var subs = SpreadsheetApp.getActive().getSheetByName(SHEET_SUBS).getDataRange().getValues().slice(1)
    .filter(function (r) { return r[3] === 'active'; });
  var plan = [];
  subs.forEach(function (r) {
    var ds = String(r[1]).split(','), lv = String(r[2]).split(',');
    var mine = fresh.filter(function (n) {
      return (ds.indexOf('all') !== -1 || ds.indexOf(n.dataset_id) !== -1) &&
        (lv.indexOf('all') !== -1 || lv.indexOf(n.level) !== -1);
    });
    if (mine.length) plan.push({ email: r[0], token: r[4], items: mine });
  });

  if (plan.length > MailApp.getRemainingDailyQuota()) {
    // 오늘 보낼 수 있는 인원을 넘으면 보내지 않고 운영자에게 알린 뒤 내일 다시 시도
    MailApp.sendEmail(Session.getEffectiveUser().getEmail(), '[' + SITE_NAME + '] 알림 발송 보류',
      '오늘 남은 발송 한도(' + MailApp.getRemainingDailyQuota() + '명)보다 받을 사람(' + plan.length +
      '명)이 많아 발송을 내일로 미뤘습니다. 구독자가 늘었다면 뉴스레터 서비스로 옮길 때가 되었습니다.');
    return;
  }
  plan.forEach(function (x) {
    var crit = x.items.some(function (n) { return n.level === 'critical'; });
    var subject = '[' + SITE_NAME + '] ' + (crit ? '중요 공지 포함 · ' : '') + '새 공지 ' + x.items.length + '건';
    sendMail_(x.email, subject, noticesHtml_(x.items) + footer_(x.token));
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
  fetchNotices_().forEach(function (n) { sentSh.appendRow([n.key, now, 0]); });
}

function fetchNotices_() {
  var res = UrlFetchApp.fetch(NOTICES_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('공지 목록 응답 ' + res.getResponseCode());
  return JSON.parse(res.getContentText()).notices || [];
}

// ── 메일 본문 ───────────────────────────────────────────
function sendConfirm_(email, token, datasets, levels) {
  var url = ScriptApp.getService().getUrl() + '?action=confirm&token=' + token;
  sendMail_(email, '[' + SITE_NAME + '] 알림 신청을 확인해 주세요',
    '<p>' + SITE_NAME + ' 변경 알림 신청을 받았습니다. 아래 버튼을 눌러야 신청이 완료됩니다.</p>' +
    '<p><a href="' + url + '" style="display:inline-block;padding:10px 18px;background:#00897b;color:#fff;border-radius:6px;text-decoration:none">신청 확인하기</a></p>' +
    prefsHtml_(datasets, levels) +
    '<p style="color:#777">본인이 신청하지 않았다면 이 메일을 무시하세요. 확인하지 않은 신청은 메일이 발송되지 않습니다.</p>' +
    footer_(token));
}

function prefsHtml_(datasets, levels) {
  var lv = levels === 'all' ? '전체' : levels.split(',').map(function (l) { return LEVEL_LABEL[l] || l; }).join(', ');
  return '<p style="background:#f5f7fa;padding:10px 14px;border-radius:6px">데이터셋: ' +
    esc_(datasets === 'all' ? '전체 (앞으로 추가되는 데이터셋 포함)' : datasets) + '<br>공지 구분: ' + esc_(lv) + '</p>';
}

function noticesHtml_(items) {
  var colors = { critical: '#c62828', warning: '#b26a00', info: '#546e7a' };
  return '<p>고르신 데이터셋에 새 공지가 올라왔습니다.</p>' + items.map(function (n) {
    return '<div style="border-left:4px solid ' + (colors[n.level] || '#999') + ';padding:8px 14px;margin:14px 0">' +
      '<div style="font-size:13px;color:' + (colors[n.level] || '#999') + ';font-weight:bold">' +
      (LEVEL_LABEL[n.level] || n.level) + ' · ' + esc_(n.dataset_name) + ' · ' + esc_(n.date) + '</div>' +
      '<div style="font-size:16px;font-weight:bold;margin:4px 0">' + esc_(n.title) + '</div>' +
      '<div style="font-size:14px;color:#333">' + esc_(n.body || '') + '</div>' +
      '<div style="font-size:13px;margin-top:6px"><a href="' + esc_(n.source) + '">원문 공지</a> · ' +
      '<a href="' + esc_(n.url) + '">' + esc_(n.dataset_name) + ' 페이지</a></div></div>';
  }).join('') +
  '<p style="color:#777;font-size:13px">공지는 운영자가 공식 출처를 확인한 내용이지만, 분석·논문에 반영하기 전에는 원문 공지를 꼭 다시 확인해 주세요.</p>';
}

function footer_(token) {
  var unsub = ScriptApp.getService().getUrl() + '?action=unsubscribe&token=' + token;
  return '<hr style="border:0;border-top:1px solid #ddd;margin:20px 0">' +
    '<p style="color:#888;font-size:12px">' + SITE_NAME + ' (<a href="' + SITE_URL + '">' + SITE_URL + '</a>)는 개인이 운영하는 비공식 프로젝트이며, ' +
    '소속 기관이나 자료 제공 기관의 공식 입장이 아닙니다.<br>' +
    '설정 변경: <a href="' + SUBSCRIBE_PAGE + '">알림 신청 페이지</a>에서 같은 이메일로 다시 신청 · ' +
    '<a href="' + unsub + '">수신 거부(정보 즉시 삭제)</a></p>';
}

function sendMail_(to, subject, html) {
  MailApp.sendEmail({ to: to, subject: subject, htmlBody: html, name: SITE_NAME,
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
function page_(title, msg) {
  return HtmlService.createHtmlOutput(
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<div style="font-family:sans-serif;max-width:520px;margin:60px auto;padding:0 20px;line-height:1.6">' +
    '<h2>' + esc_(title) + '</h2><p>' + esc_(msg) + '</p><p><a href="' + SITE_URL + '">' + SITE_NAME + '로 돌아가기</a></p></div>'
  ).setTitle(SITE_NAME);
}
