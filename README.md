# 기후데이터 길잡이 (Korean Climate Data Guide)

대기·해양·해빙·극지·원격탐사 연구자를 위해 **원자료의 출처, 받는 방법, 제공 기간, 논문용 레퍼런스, 제공 중단·변경 공지**를 한곳에 정리하는 한국어 사이트입니다. 자료 자체는 보관하지 않고 공식 출처로 연결합니다.

현재 수록: ERA5, JRA-55

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
hooks/datasets.py        ← YAML을 읽어 페이지·목록·공지 모음을 자동 생성 + 검증
docs/index.md            ← 홈 (상태 표와 최근 공지는 자동으로 채워짐)
docs/about.md            ← 소개·인용·기여 방법
docs/stylesheets/        ← 상태 배지 등 스타일
docs/javascripts/        ← 크롬 번역이 코드·인용문·데이터셋 이름을 바꾸지 않게 보호
.github/workflows/       ← 배포(deploy.yml), PR 검사(check.yml)
CITATION.cff             ← GitHub "Cite this repository" 버튼
```

## 데이터셋 추가하기

1. `data/datasets/era5.yaml`을 복사해 `data/datasets/<id>.yaml`로 저장합니다. 파일명과 `id`가 같아야 합니다.
2. 내용을 채웁니다. 핵심 항목은 아래와 같습니다.

| 항목 | 설명 |
|---|---|
| `status` | `active`(정상) / `delayed`(지연) / `deprecated`(대체 예정) / `ended`(종료) |
| `successor` | `ended`이면 필수. 후속 자료 이름·링크·차이점 |
| `period` | `start: "YYYY-MM"`, `end: present` 또는 `"YYYY-MM"` |
| `access` | 받는 곳 목록 (`name`, `url`, `method`, `note`) |
| `citations` | `dataset`(데이터 DOI), `papers`(기술 논문), `acknowledgement` |
| `notices` | 공지 목록. `date`, `level`(critical/warning/info), `title`, `body`, **`source`(원문 링크, 필수)** |
| `watch_urls` | 다음 단계 자동 감시에 쓸 공지 페이지 |
| `last_verified` | 공식 페이지에서 마지막으로 확인한 날짜 `YYYY-MM-DD` |

3. `mkdocs.yml`의 `nav`에 한 줄 추가합니다. 예: `- MERRA-2: datasets/merra2.md`
4. 필수 항목이 빠지거나 형식이 틀리면 빌드가 실패하면서 무엇이 잘못됐는지 알려줍니다.

## 정리 원칙

- DOI, 기간, URL은 **반드시 공식 페이지에서 직접 확인**한 뒤 적습니다. (AI가 만든 초안도 마찬가지)
- 공지에는 항상 원문 링크(`source`)를 붙입니다.
- 데이터셋 이름·변수명·DOI·코드는 번역하지 않습니다.

## 다음 단계 (예정)

- [ ] 공지 페이지 변경 감지 스크립트 + 주간 GitHub Actions → 변경 시 이슈 자동 생성
- [ ] 이슈를 받아 Claude가 YAML 수정 PR을 여는 워크플로 (사람이 검토 후 머지)
- [ ] Zenodo 연동으로 릴리스별 DOI 발급
- [ ] 데이터셋 확장 (MERRA-2, JRA-3Q, 해빙 농도, SST …) 및 WRF·CESM2 모델 페이지

## 라이선스

콘텐츠 CC BY 4.0, 코드 MIT. 자세한 내용은 `LICENSE`를 참고하세요. 각 데이터의 이용 조건은 제공 기관의 약관을 따릅니다.
