# 기후데이터 길잡이 (Korean Climate Data Guide)

대기·해양·해빙·극지·원격탐사 연구자를 위해 **원자료의 출처, 받는 방법, 제공 기간, 논문용 레퍼런스, 제공 중단·변경 공지**를 한곳에 정리하는 한국어 사이트입니다. 자료 자체는 보관하지 않고 공식 출처로 연결합니다.

현재 수록: 30개 자료 — 대기 16(재분석 12, 위성 관측 미동화 재분석 4), 해양 8, 해빙 8 (HadISST·OISST는 해양·해빙 교차 수록)

---

## 처음 한 번: GitHub에 올리고 사이트 열기

1. GitHub에서 새 **공개(Public)** 저장소를 만듭니다. 이름은 `climate-data-guide-kr`을 추천합니다.
2. 이 폴더의 파일을 전부 올립니다. (웹에서 "Add file → Upload files"로 끌어다 놓아도 됩니다.)
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

## 내 컴퓨터에서 미리 보기

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
mkdocs serve
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
2. `data/SCHEMA.md`의 규칙대로 내용을 채웁니다. 메뉴 위치는 `domain`(대기·해양·해빙), `group`(소분류), `order`(순서)로 정해지므로 `mkdocs.yml`은 고칠 필요가 없습니다.
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
3. Apps Script가 매일 오전 9시쯤 이 파일을 읽어, 처음 보는 공지만 골라 구독자별(데이터셋·공지 구분)로 한 통씩 묶어 보냅니다. 보낸 공지는 `발송 기록` 시트에 남습니다.
4. 수신 거부 링크를 누르면 시트에서 해당 행이 바로 지워집니다. 30일 넘게 확인하지 않은 신청도 자동 삭제됩니다.

즉, **YAML에 공지를 추가하고 커밋하면 다음 날 아침 메일이 자동으로 나갑니다.** 이미 올린 공지의 날짜나 제목을 고치면 새 공지로 보고 다시 발송되니, 오타 수정은 본문(`body`)에서 하세요.

- Gmail 무료 계정은 하루 약 100명에게 보낼 수 있습니다. 넘으면 남은 사람은 다음 날 보냅니다.
- Gmail 새 계정에서 보낸 메일은 처음에 스팸함으로 갈 수 있습니다. 신청 페이지와 확인 메일에 '스팸 아님' 표시 안내를 넣어 두었습니다.
- `mailing/Code.gs`를 고쳤다면 Apps Script 편집기에 붙여넣고 저장합니다. 매일 실행(checkNotices)은 저장만 하면 반영되고, 신청 접수(doPost/doGet)를 고쳤다면 **배포 → 배포 관리 → 수정 → 새 버전**으로 다시 배포해야 합니다(주소는 그대로).

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

- [ ] 공지 페이지 변경 감지 스크립트 + 주간 GitHub Actions → 변경 시 이슈 자동 생성
- [ ] 이슈를 받아 Claude가 YAML 수정 PR을 여는 워크플로 (사람이 검토 후 머지)
- [ ] 데이터셋 확장 (ERA5-Land 등) 및 WRF·CESM2 모델 페이지

## 라이선스

콘텐츠 CC BY 4.0, 코드 MIT. 자세한 내용은 `LICENSE`를 참고하세요. 각 데이터의 이용 조건은 제공 기관의 약관을 따릅니다.
