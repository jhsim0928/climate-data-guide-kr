# 운영자 안내 (MAINTAINING)

> 사이트 소개는 [README.md](README.md)를 보세요. 이 문서는 사이트를 고치고 배포하는 방법(운영자용)입니다.

## 기후데이터 길잡이 (Korean Climate Data Navigator, KCDN)

대기·해양·해빙·극지·원격탐사 연구자를 위해 **원자료의 출처, 받는 방법, 제공 기간, 논문용 레퍼런스, 제공 중단·변경 공지**를 한곳에 정리하는 한국어 사이트입니다. 자료 자체는 보관하지 않고 공식 출처로 연결합니다.

현재 수록: 92개 자료 — 대기 29, 해양 21, 해빙 16, 지면 30 (교차 수록 포함). 한국어판(https://data4researchers.kr/)과 영어판(https://data4researchers.kr/en/)이 있습니다.

---

## 처음 한 번: GitHub에 올리고 사이트 열기

1. GitHub에서 새 **공개(Public)** 저장소를 만듭니다. 이름은 `climate-data-guide-kr`을 추천합니다.
2. 이 폴더의 파일을 전부 올립니다. (웹에서 "Add file → Upload files"로 끌어다 놓아도 됩니다.)
   - 웹 업로드는 **한 번에 100개 파일까지**입니다. `data/datasets`, `data/datasets_en`은 `data` 폴더 안에서(https://github.com/jhsim0928/climate-data-guide-kr/upload/main/data) 따로 올리세요.
   - 이름이 점으로 시작하는 `.github` 폴더는 끌어다 놓을 때 빠지기 쉬우니, 바뀌었다면 웹에서 파일을 직접 고치세요.
3. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 바꿉니다.
4. GitHub 아이디(`jhsim0928`)는 이미 들어가 있습니다. 아이디나 주소가 바뀌면 아래 파일에서 고치면 됩니다.
    - `mkdocs.yml` (site_url, extra.site_citation)
    - `docs/about.md`
    - `CITATION.cff`
5. 커밋하면 **Actions** 탭에서 "사이트 배포"가 돌고, 1~2분 뒤 `https://<아이디>.github.io/climate-data-guide-kr/`에서 사이트가 열립니다.

## 개인 도메인 (data4researchers.kr)

사이트 주소는 `https://data4researchers.kr/`입니다. 설정은 다음과 같습니다.

- 도메인 업체(아이티이지) DNS: `@` A 레코드 4개(185.199.108.153 / 109.153 / 110.153 / 111.153), `www` CNAME → `jhsim0928.github.io`, GitHub 도메인 인증용 TXT 레코드
- GitHub 저장소 Settings → Pages → Custom domain: `data4researchers.kr`, Enforce HTTPS 켜기
- GitHub Actions로 배포하므로 `CNAME` 파일은 필요 없습니다.
- 도메인을 바꾸면 `mkdocs.yml`의 `site_url`, `extra.site_citation`, `docs/about.md`, `CITATION.cff`의 주소도 함께 바꿉니다.

## 영어판 (English edition)

- 주소: `https://data4researchers.kr/en/` — 오른쪽 위 언어 선택 메뉴(한국어 / English)로 오가며, 보고 있던 페이지의 다른 언어판으로 바로 이동합니다.
- 설정: `mkdocs.en.yml` (나머지 설정은 `mkdocs.yml`을 물려받음). 빌드 결과는 `site/en/`.
- 자료 내용: `data/datasets_en/<id>.yaml` — 한국어 파일을 번역한 것이 아니라, 같은 공식 영어 출처를 다시 보고 쓴 영어판입니다. 구조(키, 공지·변수 개수와 순서)와 `id`·`group`·`status`·날짜·DOI 등은 한국어 파일과 같아야 합니다.
- 화면 문구(메뉴, 표 머리, 안내 상자 등): `hooks/i18n_en.py`. 사이트 고정 페이지(홈·소개·비교·알림 신청·제안·개인정보 처리방침): `docs_en/`.
- 그림·스크립트·스타일은 한국어판 `docs/`의 것을 그대로 함께 씁니다(따로 복사하지 않음).
- **자료를 고치거나 추가할 때는 한국어·영어 YAML을 함께 고치세요.** `python scripts/validate.py`가 영어 파일 누락, 공지 개수·날짜 불일치를 잡아냅니다. 영어판에 한국어가 남았는지는 `mkdocs build -f mkdocs.en.yml && python scripts/check_en.py`로 확인합니다.
- 메일 알림: 영어판에서 신청한 사람은 확인 메일·알림 메일을 영어로 받습니다(공지 key는 두 언어가 같아 발송 기록이 하나로 관리됨).

## 검색 노출 (SEO)

자동으로 들어가는 것
- 페이지마다 검색 결과용 제목·설명 (데이터셋 페이지: "ERA5 — 받는 방법·변수·인용·공지 정리"), 고정 페이지는 각 `.md` 맨 위 `title`·`description`
- 한국어·영어판이 서로 같은 페이지임을 알리는 `hreflang` 링크, 대표 주소(canonical)
- 링크 공유 미리보기(카카오톡·슬랙 등): `docs/assets/og-ko.png`, `og-en.png`
- 구조화 데이터(JSON-LD): 홈은 WebSite, 데이터셋 페이지는 해당 자료(Dataset: 이름·DOI·제공 기관·기간·공식 페이지)를 다루는 TechArticle
- `sitemap.xml`(한국어)·`en/sitemap.xml`(영어), `robots.txt`, 공지 RSS `feed.xml`·`en/feed.xml`

직접 한 번 해야 하는 것 (검색엔진에 사이트 등록)
1. **Google Search Console** (search.google.com/search-console) → 속성 추가 → URL 접두어 `https://data4researchers.kr/` → 'HTML 태그' 확인 방법의 `content="…"` 값을 `mkdocs.yml`의 `extra.seo.google_site_verification`에 넣고 배포 → [확인] → Sitemaps 메뉴에 `sitemap.xml`과 `en/sitemap.xml` 제출
2. **네이버 서치어드바이저** (searchadvisor.naver.com) → 웹마스터 도구 → 사이트 등록 `https://data4researchers.kr` → 'HTML 태그' 값을 `extra.seo.naver_site_verification`에 넣고 배포 → [소유확인] → 요청 → 사이트맵 제출(`https://data4researchers.kr/sitemap.xml`), RSS 제출(`https://data4researchers.kr/feed.xml`)
3. (선택) **Bing 웹마스터 도구**: Google Search Console에서 가져오기로 바로 등록. 직접 확인하려면 `extra.seo.bing_site_verification`

## 내 컴퓨터에서 미리 보기

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
mkdocs serve                      # 한국어판
mkdocs serve -f mkdocs.en.yml -a 127.0.0.1:8001   # 영어판 (따로 띄움)
```

브라우저에서 http://127.0.0.1:8000 을 열면 됩니다. YAML을 고치고 저장하면 바로 반영됩니다.

> `requirements.txt`에서 MkDocs를 1.6.1로 고정해 두었습니다. MkDocs 2.0은 플러그인·훅 구조가 바뀌어 이 사이트의 자동 페이지 생성이 동작하지 않으니, 버전을 올리지 마세요.

## 구조

```
data/datasets/*.yaml     ← 데이터셋 정보 (여기만 고치면 됩니다)
data/SCHEMA.md           ← YAML 작성 규칙 (변수 목록·시간 특성, 전환 분석 형식 포함)
scripts/validate.py      ← YAML 검사 도구 (사이트 빌드와 같은 규칙)
hooks/datasets.py        ← YAML을 읽어 페이지·메뉴·목록·중요 공지·세대별 비교·폼을 자동 생성 + 검증
docs/index.md            ← 홈 (최근 공지는 자동으로 채워짐)
docs/assets/             ← 로고·파비콘, 빌드 때 notices.json(메일 알림용 공지 목록) 자동 생성
mailing/Code.gs          ← 메일 알림·제안 접수용 Google Apps Script (사이트에는 올라가지 않음)
docs/about.md, privacy.md, subscribe.md, suggest.md
docs/compare.md          ← 자료 비교 (표·변수 찾기는 자동 생성)
docs/stylesheets/, docs/javascripts/   ← site.js: 자료 비교·공지 필터·정보 오류 신고 링크
overrides/               ← 하단 면책 문구 템플릿
.github/workflows/       ← 배포(deploy.yml), PR 검사(check.yml)
CITATION.cff             ← GitHub "Cite this repository" 버튼
```

## 데이터셋 추가하기

1. 비슷한 자료의 YAML(예: `data/datasets/jra3q.yaml`)을 복사해 `data/datasets/<id>.yaml`로 저장합니다. 파일명과 `id`가 같아야 합니다.
2. `data/SCHEMA.md`의 규칙대로 내용을 채웁니다. 메뉴 위치는 `domain`(대기·해양·해빙·지면), `group`(소분류), `order`(순서)로 정해지므로 `mkdocs.yml`은 고칠 필요가 없습니다.
3. 후속 자료가 있으면 이전 자료 파일에 `transitions:`를 적습니다. 후속 자료 페이지와 세대별 비교 페이지에 자동으로 연결됩니다.
4. `python scripts/validate.py data/datasets/<id>.yaml`로 검사합니다. 필수 항목이 빠지거나 형식이 틀리면 무엇이 잘못됐는지 알려줍니다.

## 알림 신청 · 데이터셋 제안 폼

- `docs/subscribe.md`(알림 신청)와 `docs/suggest.md`(데이터셋 제안)의 입력 양식은 `hooks/datasets.py`가 데이터셋 목록으로 자동 생성합니다. 데이터셋을 추가하면 체크박스도 자동으로 늘어납니다.
- 양식은 `mkdocs.yml`의 `extra.forms`에 적힌 Google Apps Script 웹앱 주소로 보내집니다. 신청 정보는 **운영자 Google 스프레드시트**에만 저장되고, 공개 저장소에는 남지 않습니다.
- 데이터셋 제안과 **정보 오류 신고**(모든 페이지 하단·데이터셋 페이지 제목 아래 버튼 → 신고 창)는 운영자 시트(`데이터셋 제안`, `오류 신고`)에 저장되고 `OWNER_EMAIL`(data4researchers@gmail.com)로 알림 메일이 옵니다.
- 방문자가 이 GitHub 저장소로 오지 않도록 `repo_url`·`edit_uri`(연필 버튼)를 넣지 않았고, 사이트 어디에도 저장소 링크가 없습니다.

### 메일 알림 동작

1. 신청 → 시트에 `pending`으로 저장되고 확인 메일 발송 → 메일 속 **신청 확인하기**를 누르면 `active`.
2. 사이트를 빌드할 때 모든 YAML의 `notices`가 `https://data4researchers.kr/assets/notices.json`으로 만들어집니다.
3. Apps Script가 매시간(오전 8시~오후 9시) 이 파일을 읽어, 처음 보는 공지만 골라 구독자별(데이터셋·공지 구분)로 한 통씩 묶어 보냅니다. 보낸 공지는 `발송 기록` 시트에 남습니다.
4. 수신 거부 링크를 누르면 시트에서 해당 행이 바로 지워집니다. 30일 넘게 확인하지 않은 신청도 자동 삭제됩니다.

즉, **YAML에 공지를 추가하고 main에 반영되면 한 시간 안에 메일이 자동으로 나갑니다**(밤이면 다음 날 아침 8시).

**새 자료를 추가할 때** 그 자료 YAML에 이미 들어 있는 공지는 새 소식이 아니므로 메일로 보내지 않고 `발송 기록`에 기록만 합니다(`notices.json`의 `datasets` 목록과 시트의 `dataset|<id>` 행으로 판단). 그 뒤에 그 자료에 추가되는 공지부터 발송됩니다. 이미 올린 공지의 날짜나 제목을 고치면 새 공지로 보고 다시 발송되니, 오타 수정은 본문(`body`)에서 하세요.

- Gmail 무료 계정은 하루 약 100명에게 보낼 수 있습니다. 넘으면 남은 사람은 다음 날 보냅니다.
- Gmail 새 계정에서 보낸 메일은 처음에 스팸함으로 갈 수 있습니다. 신청 페이지와 확인 메일에 '스팸 아님' 표시 안내를 넣어 두었습니다.
- `mailing/Code.gs`를 고쳤다면 Apps Script 편집기에 붙여넣고 저장합니다. 매일 실행(checkNotices)은 저장만 하면 반영되고, 신청 접수(doPost/doGet)를 고쳤다면 **배포 → 배포 관리 → 수정 → 새 버전**으로 다시 배포해야 합니다(주소는 그대로).

## 새 공지 자동 점검 (매일)

| 시각(한국) | 누가 | 하는 일 |
|---|---|---|
| 05:40쯤 | Apps Script `startWatch` → GitHub Actions `공지 페이지 점검` (`.github/workflows/watch.yml` → `scripts/watch.py`) | 각 YAML의 `watch_urls`(공지 페이지 약 135곳)를 열어 지난번과 달라진 줄을 `watch/changes.json`에 저장 |
| 08시 | Claude 예약 작업 (지침: `watch/REVIEW.md`) | 바뀐 부분이 진짜 공지인지 판단 → 공지면 한국어·영어 YAML에 써서 **공지 후보 PR** 생성 → `watch/digest.json` 작성 |
| 09시 | Apps Script `dailyDigest` | `digest.json`을 읽어 운영자에게 요약 메일 (새 공지 후보, 승인 버튼, 공지가 아니라고 본 변경, 열리지 않는 페이지) |
| 승인 후 | 운영자 → Apps Script `checkNotices` | PR에서 **Merge pull request → Confirm merge** → 사이트 배포 → 한 시간 안에 구독자 알림 메일 |

- **공지 추가·수정은 사람이든 Claude든 항상 PR로** 합니다. main에 직접 올린 공지는 승인 없이 한 시간 안에 구독자에게 발송됩니다.
- 공지가 아니면 PR에서 **Close pull request**. 고칠 점이 있으면 Claude에게 PR 링크와 함께 말하면 됩니다.
- 요약 메일 받는 사람: `OWNER_EMAIL` + Apps Script **프로젝트 설정 → 스크립트 속성 `DIGEST_TO`**(쉼표로 여러 주소). 개인 주소는 공개 저장소에 적지 않기 위해 이렇게 둡니다.
- **새벽 점검 시작 설정 (한 번만)** — GitHub 예약 실행(06:07)은 몇 시간씩 늦거나 빠지는 일이 잦아서, Apps Script가 05:40쯤 직접 시작시킵니다. 예약 실행은 예비로 남아 있고, 그날 점검이 이미 있으면 건너뜁니다.
  1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens → Generate new token**
     - Repository access: **Only select repositories** → `climate-data-guide-kr`
     - Permissions → Repository permissions → **Actions: Read and write** (다른 권한은 주지 않음)
     - 만료일은 길게 두고, 만료 전에 새로 만들어 바꿉니다. 만료되면 새벽에 운영자 주소로 "점검을 시작하지 못했습니다" 메일이 옵니다.
  2. Apps Script **프로젝트 설정 → 스크립트 속성**에 `GITHUB_TOKEN` = 토큰 값을 추가합니다(코드에 적지 않음).
  3. 바뀐 `mailing/Code.gs`를 붙여넣고 저장한 뒤 `setupTriggers`를 한 번 실행합니다. `startWatch`를 직접 한 번 실행해 Actions 탭에 `공지 페이지 점검`이 새로 도는지 확인합니다.
- 9시 메일에 "점검 결과 없음"이 오면 새벽 Actions나 08시 Claude 작업이 실패한 것입니다. GitHub **Actions** 탭에서 `공지 페이지 점검`을 열어 **Run workflow**로 다시 돌리거나 Claude에게 알려 주세요.
- 감시 주소를 바꾸려면 YAML의 `watch_urls`만 고치면 됩니다. 저장된 페이지 사본은 `watch/state/`, 지난 30일 감지 기록은 `watch/history/`에 있습니다.
- Actions와 Claude가 main에 올리는 점검 기록 커밋에는 `[skip ci]`가 붙어 사이트를 다시 배포하지 않습니다.

## 방문자 수 집계

GoatCounter(쿠키 없음)를 씁니다. Code는 `docs/javascripts/notranslate.js`의 `GOATCOUNTER_CODE`에 있고, 통계는 https://data4researchers.goatcounter.com 에서 봅니다.

## 인용 정보 (DOI)

- Zenodo DOI: https://doi.org/10.5281/zenodo.23300923 ("모든 버전" DOI — 새 버전을 올려도 그대로 씁니다)
- 인용 문구(영문·국문·BibTeX)는 `mkdocs.yml`의 `extra.site_citation` 한 곳에서 고치면 소개 페이지, 각 데이터셋 페이지 하단, 엑셀 저장 파일에 모두 반영됩니다.
- `CITATION.cff`도 같은 내용으로 맞춰 두세요.

## 정리 원칙

- DOI, 기간, URL은 **반드시 공식 페이지에서 직접 확인**한 뒤 적습니다. (AI가 만든 초안도 마찬가지)
- 공지에는 항상 원문 링크(`source`)를 붙입니다.
- 데이터셋 이름·변수명·DOI·코드는 번역하지 않습니다.

## 다음 단계 (예정)

- [x] 공지 페이지 변경 감지 + Claude 공지 후보 PR + 운영자 승인 (위 '새 공지 자동 점검')
- [ ] 데이터셋 확장 (ERA5-Land 등) 및 WRF·CESM2 모델 페이지

## 라이선스

콘텐츠 CC BY 4.0, 코드 MIT. 자세한 내용은 `LICENSE`를 참고하세요. 각 데이터의 이용 조건은 제공 기관의 약관을 따릅니다.
