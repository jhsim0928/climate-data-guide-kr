# 기후데이터 길잡이 (Korean Climate Data Guide)

대기·해양·해빙·극지·원격탐사 연구자를 위해 **원자료의 출처, 받는 방법, 제공 기간, 논문용 레퍼런스, 제공 중단·변경 공지**를 한곳에 정리하는 한국어 사이트입니다. 자료 자체는 보관하지 않고 공식 출처로 연결합니다.

현재 수록: 30개 자료 — 대기 16(재분석 12, 장기·관측 제한 재분석 4), 해양 8, 해빙 8 (HadISST·OISST는 해양·해빙 교차 수록)

---

## 처음 한 번: GitHub에 올리고 사이트 열기

1. GitHub에서 새 **공개(Public)** 저장소를 만듭니다. 이름은 `climate-data-guide-kr`을 추천합니다.
2. 이 폴더의 파일을 전부 올립니다. (웹에서 "Add file → Upload files"로 끌어다 놓아도 됩니다.)
3. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 바꿉니다.
4. GitHub 아이디(`jhsim0928`)는 이미 들어가 있습니다. 아이디나 주소가 바뀌면 아래 파일에서 고치면 됩니다.
    - `mkdocs.yml` (site_url, repo_url, extra.site_citation)
    - `docs/about.md`
    - `CITATION.cff` (작성자 이름 `성`, `이름` 자리도 본인 이름으로 바꿔주세요)
5. 커밋하면 **Actions** 탭에서 "사이트 배포"가 돌고, 1~2분 뒤 `https://<아이디>.github.io/climate-data-guide-kr/`에서 사이트가 열립니다.

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
data/providers.yaml      ← 하단 "데이터 제공 기관" 회전 띠 목록 (기관 추가·순서 변경은 여기서)
scripts/validate.py      ← YAML 검사 도구 (사이트 빌드와 같은 규칙)
hooks/datasets.py        ← YAML을 읽어 페이지·메뉴·목록·공지 모음·전환 가이드·폼을 자동 생성 + 검증
docs/index.md            ← 홈 (분야별 요약과 최근 공지는 자동으로 채워짐)
docs/about.md, privacy.md, subscribe.md, suggest.md
docs/compare.md          ← 자료 비교 (표·변수 찾기는 자동 생성)
docs/stylesheets/, docs/javascripts/   ← site.js: 자료 비교·공지 필터·정보 오류 신고 링크
overrides/               ← 하단 제공 기관 띠와 면책 문구 템플릿
.github/workflows/       ← 배포(deploy.yml), PR 검사(check.yml)
CITATION.cff             ← GitHub "Cite this repository" 버튼
```

## 데이터셋 추가하기

1. 비슷한 자료의 YAML(예: `data/datasets/jra3q.yaml`)을 복사해 `data/datasets/<id>.yaml`로 저장합니다. 파일명과 `id`가 같아야 합니다.
2. `data/SCHEMA.md`의 규칙대로 내용을 채웁니다. 메뉴 위치는 `domain`(대기·해양·해빙), `group`(소분류), `order`(순서)로 정해지므로 `mkdocs.yml`은 고칠 필요가 없습니다.
3. 후속 자료가 있으면 이전 자료 파일에 `transitions:`를 적습니다. 후속 자료 페이지와 전환 가이드에 자동으로 연결됩니다.
4. `python scripts/validate.py data/datasets/<id>.yaml`로 검사합니다. 필수 항목이 빠지거나 형식이 틀리면 무엇이 잘못됐는지 알려줍니다.

## 알림 신청 · 데이터셋 제안 폼

- `docs/subscribe.md`(알림 신청)와 `docs/suggest.md`(데이터셋 제안)의 입력 양식은 `hooks/datasets.py`가 데이터셋 목록으로 자동 생성합니다. 데이터셋을 추가하면 체크박스도 자동으로 늘어납니다.
- 데이터셋 제안은 지금 바로 동작합니다. 입력한 내용이 채워진 GitHub 이슈가 새 창에서 열립니다.
- 메일 알림은 **아직 준비 중**입니다. 양식은 미리 볼 수 있지만 신청이 저장되지 않습니다.
- 메일 발송을 시작할 때는 신청을 받을 주소(예: Google Apps Script 웹앱)를 `mkdocs.yml`의 `extra.forms.subscribe_endpoint`에 넣으면 됩니다. 그 전에 `docs/privacy.md`(개인정보 처리방침 초안)의 빈칸을 채워주세요.

## 하단 제공 기관 띠와 로고

`data/providers.yaml`의 기관이 사이트 하단에서 천천히 돌아갑니다(마우스를 올리면 멈춤, 움직임 줄이기 설정을 켠 사용자에게는 정지 상태로 표시). 기본은 약자 배지이며, 기관에서 **로고 사용 허가를 받은 경우에만** `docs/assets/logos/`에 이미지를 넣고 해당 기관의 `logo:`에 경로를 적으세요. 정부·국제기구 로고는 대부분 사용 규정이 있고, 허가 없이 쓰면 공식 제휴처럼 보일 수 있습니다.

## 방문자 수 집계 (선택)

GoatCounter에 가입한 뒤 `docs/javascripts/notranslate.js`의 `GOATCOUNTER_CODE = ""` 따옴표 안에 정한 Code를 넣으면 집계가 시작됩니다.

## 정리 원칙

- DOI, 기간, URL은 **반드시 공식 페이지에서 직접 확인**한 뒤 적습니다. (AI가 만든 초안도 마찬가지)
- 공지에는 항상 원문 링크(`source`)를 붙입니다.
- 데이터셋 이름·변수명·DOI·코드는 번역하지 않습니다.

## 다음 단계 (예정)

- [ ] 공지 페이지 변경 감지 스크립트 + 주간 GitHub Actions → 변경 시 이슈 자동 생성
- [ ] 이슈를 받아 Claude가 YAML 수정 PR을 여는 워크플로 (사람이 검토 후 머지)
- [ ] Zenodo 연동으로 릴리스별 DOI 발급
- [ ] 메일 알림 발송 연결 (구글 폼·시트 + Apps Script)
- [ ] 데이터셋 확장 (ERA5-Land 등) 및 WRF·CESM2 모델 페이지

## 라이선스

콘텐츠 CC BY 4.0, 코드 MIT. 자세한 내용은 `LICENSE`를 참고하세요. 각 데이터의 이용 조건은 제공 기관의 약관을 따릅니다.
