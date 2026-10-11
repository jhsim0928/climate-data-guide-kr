# 데이터셋 YAML 작성 규칙

`data/datasets/<id>.yaml` 파일 하나가 데이터셋 페이지, 메뉴, 목록, 공지 모음, 알림 신청 체크박스를 모두 만듭니다.
작성 후 `python scripts/validate.py data/datasets/<id>.yaml`로 검사하세요.

## 필수 항목

| 키 | 설명 |
|---|---|
| `id` | 파일명과 같은 영문 소문자 식별자 (예: `merra2`) |
| `name` | 표시 이름 (예: `MERRA-2`) |
| `full_name` | (선택) 정식 명칭과 한국어 설명 |
| `category` | `reanalysis` 재분석 / `analysis` 관측 기반 분석장 / `satellite` 위성자료 / `forcing` 모델 강제력 / `in_situ` / `model_output` / `model_source` |
| `domain` | 메뉴 탭: `atmosphere` 대기 / `ocean` 해양 / `seaice` 해빙 |
| `group` | 탭 안 소분류 (아래 표) |
| `order` | 소분류 안 표시 순서 (작을수록 위) |
| `also_in` | (선택) 다른 탭에도 실을 때: `[{domain, group, label}]` |
| `domains` | 다루는 영역 태그 목록 (예: `[대기, 육지]`) |
| `provider` | 제공 기관 |
| `status` | `active` 정상 / `delayed` 지연 / `deprecated` 대체 예정 / `ended` 갱신 종료 |
| `status_note` | 현재 상태 설명 (한국어 2~3문장) |
| `successor` | `ended`이면 필수: `{name, url, note}` (후속이 없으면 `name: 없음`) |
| `period` | `{start: "YYYY-MM", end: present 또는 "YYYY-MM", note}` |
| `resolution` | `{spatial, vertical, temporal}` |
| `update` | 갱신 주기 |
| `license` | 라이선스·이용 조건 요약 |
| `account_required` | `true` / `false` |
| `summary` | 한국어 개요 2~4문장 |
| `variables` | 아래 형식 |
| `access` | 받는 곳 목록 `[{name, url, method, note}]` |
| `example` | (선택) `{lang, note, code}` |
| `tips` | (선택) 실전 팁 목록 |
| `citations` | `{dataset: [...], papers: [...], acknowledgement}` 각 항목 `{label, text, doi, bibtex}` |
| `notices` | 공지 목록 `[{date, level, title, body, source}]` — `level`: `critical` / `warning` / `info`, `source`는 필수 |
| `links` | 참고 링크 `[{name, url}]` |
| `watch_urls` | 자동 감시할 공지 페이지 |
| `last_verified` | 공식 페이지에서 확인한 날짜 `"YYYY-MM-DD"` |

## 분야별 소분류 (`group` 허용값)

| domain | group |
|---|---|
| `atmosphere` | `재분석`, `장기(20세기)·관측 제한 재분석` |
| `ocean` | `재분석`, `관측 기반 분석장`, `모델 강제력` |
| `seaice` | `재분석`, `관측 기반 분석장`, `위성 관측 자료` |

## 변수 목록 형식

```yaml
variables:
  note: 공식 문서 기준 주요 변수입니다. 변수명은 파일 안의 이름(short name)입니다.
  full_list: https://공식-변수표-주소
  groups:
    - name: 지표·단일면
      items:
        - "2m 기온 — `2t` (K)"
        - "평균 해면기압 — `msl` (Pa)"
    - name: 기압면
      items:
        - "기온 — `t` (K)"
```

- 각 항목은 `"한국어 이름 — `파일 속 변수명` (단위)"` 형식을 권장합니다. 변수명을 백틱으로 감싸면 번역되지 않습니다.
- 공식 문서에서 확인한 이름만 적습니다. 확인하지 못한 변수명은 적지 않습니다.

## 후속 자료·새 버전과의 차이 (`transitions`)

**이전 자료의 파일**에 적습니다. (예: JRA-55 → JRA-3Q 비교는 `jra55.yaml`에)
같은 페이지 안에서 버전만 바뀐 경우(예: NSIDC CDR v5 → v6)는 그 자료 파일에 적고 `to_id`는 생략합니다.
후속 자료 페이지에는 "이전 자료와 무엇이 달라졌나" 링크가 자동으로 생기고, 모든 전환은 "전환 가이드" 페이지에 모입니다.

```yaml
transitions:
  - from: JRA-55
    to: JRA-3Q
    to_id: jra3q             # (선택) 후속 자료가 이 사이트에 있으면 그 id
    status: completed        # completed 완료 / planned 예정
    date: "2024-01"          # (선택) 전환 시점
    summary: 한 줄 요약 (한국어)
    changes:                 # 비교표 — 항목별 이전/이후
      - aspect: 기간
        before: 1958–2024-01
        after: 1947-09–현재
      - aspect: 수평 해상도
        before: TL319 (약 55 km)
        after: TL479 (약 40 km)
    impacts:                 # 바꿔 쓸 때 주의할 점 (분석에 미치는 영향)
      - 두 자료를 한 시계열로 이어 붙이지 말 것
    sources:                 # 근거 — 공식 문서·논문
      - name: Kosaka et al. (2024)
        url: https://doi.org/10.2151/jmsj.2024-004
```

비교 항목 예: 기간, 수평·연직 해상도, 자료동화 방식, 주요 관측 입력, 모델 개선, 알려진 문제 개선, 변수 이름·단위 변화, 파일 형식, 라이선스, 제공처.

## 정리 원칙

- DOI, 기간, URL, 상태는 **반드시 공식 페이지에서 확인**합니다.
- 공지에는 원문 링크(`source`)를 붙입니다.
- 데이터셋 이름·변수명·DOI·코드·BibTeX는 원문 그대로 둡니다.
