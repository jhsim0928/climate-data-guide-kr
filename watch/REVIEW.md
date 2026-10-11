# 매일 아침 공지 점검 — Claude 작업 지침

매일 08시쯤(한국 시간) 예약 작업으로 실행되는 Claude가 이 문서를 그대로 따릅니다.
운영자가 읽어도 흐름을 알 수 있도록 한국어로 적었습니다.

## 전체 흐름

1. **06시 — GitHub Actions `공지 페이지 점검`** (`.github/workflows/watch.yml`, `scripts/watch.py`)
   각 데이터셋 YAML의 `watch_urls`를 열어 지난번과 달라진 줄을 `watch/changes.json`에 남깁니다.
2. **08시 — Claude (이 문서)**
   바뀐 부분이 진짜 새 공지인지 판단하고, 공지라면 한국어·영어 YAML에 공지를 써서 **PR(공지 후보)** 을 엽니다.
   결과를 `watch/digest.json`에 남깁니다.
3. **09시 — Apps Script `dailyDigest`**
   `watch/digest.json`을 읽어 운영자에게 요약 메일을 보냅니다(승인 버튼 = PR 링크).
4. **운영자가 PR을 머지(승인)** → 사이트 배포 → Apps Script `checkNotices`(매시간, 08~21시)가 구독자에게 알림 메일.

Claude는 **main에 공지를 직접 올리지 않습니다.** main에 직접 올리는 것은 `watch/digest.json` 하나뿐입니다.

## 단계

> GitHub 명령은 **REST API(`gh api`)만** 씁니다. 이 환경에서는 GraphQL이 막혀 있어 `gh pr create`, `gh pr list`, `gh workflow run`, `gh run list`는 실패합니다.
> 아래에서 `R=repos/jhsim0928/climate-data-guide-kr` 로 둡니다.

오늘 날짜는 한국 시간 기준(`TZ=Asia/Seoul date +%F`)으로 씁니다.

### 1. 준비

```bash
cd <저장소>
git config user.name "Claude" && git config user.email "noreply@anthropic.com"
git fetch origin main && git checkout -B main origin/main
pip install --break-system-packages -q -r requirements.txt
```

### 2. 감지 결과 확인

- `watch/changes.json`의 `date_kst`가 오늘이 아니면 감지 작업이 늦었거나 실패한 것입니다.
  `gh api -X POST $R/actions/workflows/watch.yml/dispatches -f ref=main` 로 직접 실행하고,
  `gh api "$R/actions/workflows/watch.yml/runs?per_page=1" --jq '.workflow_runs[0]|[.status,.conclusion]'` 가 `completed`가 될 때까지(최대 15분) 기다린 뒤 `git pull origin main`.
  그래도 오늘 결과가 없으면 `digest.json`의 `notes`에 그 사실을 적고 6단계로 갑니다.
- `baseline: true`이면 첫 점검이라 비교 대상이 없습니다. 후보 없이 `summary`에 "첫 점검: 기준 페이지를 저장했습니다"라고 적고 6단계로.

### 3. 바뀐 페이지마다 판단

`changes[]`의 각 항목(`url`, `datasets`, `added` = 새로 생긴 줄)에 대해:

1. `added`를 읽고, 필요하면 WebFetch로 그 페이지와 거기서 링크된 **개별 공지 원문**을 엽니다.
2. 다음에 해당하면 **새 공지**입니다 — 해당 자료를 쓰는 연구자가 알아야 하는 변화:
   생산·갱신 중단/종료, 갱신 지연, 서비스·다운로드 경로 이전/중단, 자료 오류·품질 문제·재처리, 새 버전 공개/버전 교체,
   기간 연장·축소, 변수·격자·형식 변경, 계정·라이선스·인용 방식 변경, 계획된 점검으로 인한 접근 중단.
3. 다음은 **공지가 아닙니다** — `ignored`에 한 줄 이유와 함께 적습니다:
   메뉴·배너·디자인·날짜 표시 변화, 행사·교육·채용·뉴스레터·논문 소개, 다른 자료에 관한 글, 이미 사이트에 있는 공지
   (`data/datasets/<id>.yaml`의 `notices`에 같은 사건이 있으면), 아주 오래된 글(공지 날짜가 60일 넘게 지난 것)이 다시 보이는 경우.
4. 한 공지가 `datasets`의 여러 자료에 해당할 수 있습니다(예: ECMWF 공지 → ERA5, ERA5-Land, ORAS5). **실제로 영향받는 자료에만** 넣습니다.
5. 애매하면 넣지 말고 `notes`에 "운영자 확인 필요: …(링크)"로 적습니다. 잘못된 알림이 구독자에게 가는 것보다 하루 늦는 게 낫습니다.

### 4. 공지 쓰기 (새 공지가 있을 때만)

`data/SCHEMA.md` 규칙을 따릅니다.

- **한국어** `data/datasets/<id>.yaml`의 `notices:` **맨 위**에 추가:
  ```yaml
    - date: "YYYY-MM-DD"        # 원문 공지 날짜 (없으면 원문에서 확인한 날짜)
      level: warning            # critical 중요 / warning 주의 / info 안내
      title: 짧고 구체적인 한국어 제목 (예정 기간이 있으면 괄호로)
      body: >-
        무슨 일인지, 연구자가 무엇을 해야 하는지 1~3문장. 원문에 없는 추측은 쓰지 않음.
      source: https://개별-공지-원문-주소
  ```
  - `critical`: 생산 종료, 자료 오류·철회처럼 분석 결과를 바꿀 수 있는 것
  - `warning`: 지연, 접근 장애, 일부 기간·변수 문제, 곧 있을 서비스 이전
  - `info`: 새 버전 공개, 일반 변경 안내
- **영어** `data/datasets_en/<id>.yaml`의 `notices:` **같은 위치(맨 위)** 에 같은 `date`·`level`·`source`로 추가.
  제목·본문은 한국어를 번역하지 말고 **원문 영어 공지의 표현**으로 씁니다.
- 공지 때문에 자료 상태가 바뀌면(예: 생산 종료 → `ended`, 장기 지연 → `delayed`) 두 파일의 `status`·`status_note`(·`successor`)도 고치고 PR 본문에 따로 적습니다.
- 두 파일의 `last_verified`를 오늘 날짜로 바꿉니다.
- 이미 열려 있는 공지 후보 PR에 같은 사건이 있으면 새로 만들지 않습니다.
  열린 PR 목록: `gh api "$R/pulls?state=open&per_page=50" --jq '.[]|select(.head.ref|startswith("notice/"))|[.number,.title,.html_url,.head.ref]|@tsv'`,
  변경 파일 내용: `gh api $R/pulls/<번호>/files --jq '.[].patch'`

검사 — 모두 통과해야 합니다:

```bash
python scripts/validate.py
mkdocs build --strict -q && mkdocs build --strict -q -f mkdocs.en.yml
python scripts/check_en.py     # 영어판에 한국어가 남았는지
```

### 5. 공지 후보 PR 열기

```bash
git checkout -b notice/$(TZ=Asia/Seoul date +%F)
git add data && git commit -m "공지 후보 $(TZ=Asia/Seoul date +%F): <자료> <요약>"
git push -u origin HEAD
gh api -X POST $R/pulls -f base=main -f head=notice/YYYY-MM-DD \
  -f title="공지 후보 YYYY-MM-DD: ERA5 외 N건" -F body=@<본문 파일> --jq '.html_url,.number'
```

PR 본문(한국어): 후보마다 `구분 · 자료 · 날짜 · 제목`, 왜 공지로 봤는지 한두 문장, 원문 링크.
맨 아래에 "승인하려면 Merge pull request → Confirm merge. 공지가 아니면 Close pull request." 를 적습니다.
같은 날 두 번째 실행이라 브랜치가 이미 있으면 그 브랜치에 커밋을 더하고 기존 PR을 씁니다.

### 6. `watch/digest.json` 쓰기 (매일, 후보가 없어도)

main으로 돌아와(`git checkout main && git pull --rebase origin main`) 아래 형식으로 씁니다. 사람이 읽는 글은 모두 한국어.

```json
{
  "date": "YYYY-MM-DD",
  "reviewed_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "summary": "공지 페이지 135곳 중 4곳이 바뀌었고, 그중 1건을 새 공지 후보로 올렸습니다.",
  "watch": {"date": "changes.json의 date_kst", "checked": 135, "ok": 131, "changed": 4},
  "candidates": [
    {"dataset": "ERA5", "dataset_id": "era5", "level": "warning", "date": "YYYY-MM-DD",
     "title": "한국어 공지 제목", "source": "https://...", "why": "왜 공지인지 / 연구자 영향 한 문장"}
  ],
  "pr": {"url": "https://github.com/jhsim0928/climate-data-guide-kr/pull/N", "number": N},
  "pending": [{"url": "...", "title": "...", "opened": "YYYY-MM-DD"}],
  "ignored": [{"datasets": ["gpcp"], "url": "https://...", "reason": "메뉴 문구만 바뀜"}],
  "errors": [{"datasets": ["aphrodite"], "url": "https://...", "error": "HTTP 503", "fails": 3}],
  "notes": []
}
```

- 후보가 없으면 `candidates: []`, `pr: null`.
- `pending`: 오늘 것을 포함해 아직 열려 있는 공지 후보 PR 전부 (위 열린 PR 목록 명령, `opened`는 `created_at`의 날짜).
- `errors`: `changes.json`의 `errors` 그대로. 7일 넘게 실패한 주소는 새 공식 주소를 찾아보고, 찾았으면 `notes`에 "watch_urls 교체 제안: 옛 주소 → 새 주소"로 적습니다(직접 고치지 않음).

```bash
git add watch/digest.json
git commit -m "watch: 점검 요약 $(TZ=Asia/Seoul date +%F) [skip ci]"
git push origin main     # 실패하면 git pull --rebase origin main 후 다시
```

커밋 메시지의 `[skip ci]`는 사이트 재배포를 막습니다. 08:55 전에 끝내야 9시 메일에 실립니다.

## 하지 말 것

- main에 공지·자료 YAML을 직접 올리기 (반드시 PR)
- PR을 직접 머지하기 — 승인은 운영자만 합니다
- `mailing/`, 구독자 정보, Apps Script 건드리기 / 메일 보내기
- 개인 이메일 주소를 저장소 파일·PR·digest에 쓰기 (공개 연락처는 data4researchers@gmail.com 뿐)
- 원문에 없는 내용을 추측해서 공지에 쓰기
