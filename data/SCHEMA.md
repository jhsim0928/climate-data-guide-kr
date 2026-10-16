# 데이터셋 YAML 작성 규칙

`data/datasets/<id>.yaml` 파일 하나가 데이터셋 페이지, 메뉴, 목록, 공지 모음, 알림 신청 체크박스를 모두 만듭니다.
작성 후 `python scripts/validate.py data/datasets/<id>.yaml`로 검사하세요.
영어판은 같은 구조의 `data/datasets_en/<id>.yaml`이 필요합니다(공식 영어 출처를 보고 작성, `id`·`domain`·`group`·`domains`·`status`·`level`·`kind`·`temporal_short`·날짜·URL·DOI는 한국어 파일과 같은 값).

## 필수 항목

| 키 | 설명 |
|---|---|
| `id` | 파일명과 같은 영문 소문자 식별자 (예: `merra2`) |
| `name` | 표시 이름 (예: `MERRA-2`) |
| `full_name` | (선택) 정식 명칭과 한국어 설명 |
| `category` | `reanalysis` 재분석 / `analysis` 관측 기반 분석장 / `satellite` 위성자료 / `forcing` 모델 강제력 / `in_situ` / `model_output` / `model_source` |
| `domain` | 메뉴 탭: `atmosphere` 대기 / `ocean` 해양 / `seaice` 해빙 / `land` 지면 / `satellite` 위성 / `model` 기후모델 |
| `group` | 탭 안 소분류 (아래 표) |
| `order` | 소분류 안 표시 순서 (작을수록 위) |
| `also_in` | (선택) 다른 탭에도 실을 때: `[{domain, group, label}]` |
| `domains` | 다루는 영역 태그 목록 (예: `[대기, 육지]`) |
| `provider` | 제공 기관 |
| `status` | `active` 정상 / `delayed` 지연 / `deprecated` 대체 예정 / `ended` 갱신 종료 / `upcoming` 공개 예정(아직 공개 전 — `variables`·`time_convention`은 비워도 됨) |
| `status_note` | 현재 상태 설명 (한국어 2~3문장) |
| `successor` | `ended`이면 필수: `{name, url, note}` (후속이 없으면 `name: 없음`) |
| `period` | `{start: "YYYY-MM", end: present 또는 "YYYY-MM", note}` |
| `resolution` | `{spatial_short, temporal_short, spatial, vertical, temporal}` — `spatial_short`은 목록·비교용 대표 값 `"31 km (0.28°)"` 형식(기후모델 자료처럼 모델마다 격자가 다르면 `"모델마다 다름"`), `temporal_short`는 가장 짧은 제공 간격 `1시간 미만`/`10분`/`30분`/`1시간`/`3시간`/`6시간`/`1일`/`5일`/`7일`/`8일`/`10일`/`15일`/`16일`/`1개월`/`1년` 중 하나. `spatial`·`vertical`·`temporal`은 데이터셋 상세 페이지 '한눈에 보기'에 그대로 나가므로 **공식 문서의 격자 정보를 정확히**(모델 원본 격자 + 제공 격자, 격자 이름·크기) 적고, 직접 계산한 km·° 환산값은 넣지 않습니다. `spatial_short`·`temporal_short`는 목록·비교표에서만 쓰입니다 |
| `coverage` | 공간 범위 `{short, note}` — `short`는 목록·비교표 '범위' 열 값으로 `전지구`/`준전지구`/`양극`/`북극`/`북극·북대서양`/`북극 일부`/`남극`/`아시아`/`북미`/`대륙별 영역`(CORDEX처럼 여러 지역 영역으로 나뉜 자료) 중 하나(영어판도 같은 한국어 값, 화면에서 번역). 큰 영역이 빠지면(예: 북극해 없음) `전지구` 대신 `준전지구`. `note`(선택)는 빠진 곳·위경도 범위·육지만 여부 등 — 표 칸에 마우스를 올리면 보이고 상세 페이지 '한눈에 보기'에 나옴. 영어판 `note`는 영어로 |
| `update` | 갱신 주기 |
| `license` | 라이선스·이용 조건 요약 |
| `account_required` | `true` / `false` |
| `summary` | 한국어 개요 2~4문장 |
| `variables` | 아래 형식 |
| `access` | 받는 곳 목록 `[{name, url, method, note, login}]` — 로그인·계정 없이 바로 받을 수 있는 곳은 `login: false`(페이지에 '로그인 없이 받기' 표시). 안내 페이지·확인 못 한 곳은 적지 않음 |
| `example` | (선택) `{lang, note, code}` |
| `tips` | (선택) 실전 팁 목록 |
| `citations` | `{dataset: [...], papers: [...], acknowledgement}` 각 항목 `{label, text, doi, bibtex}` |
| `notices` | 공지 목록 `[{date, level, title, body, source, key_date}]` — `level`: `critical` / `warning` / `info`, `source`는 필수. `date`는 `YYYY-MM-DD`(원문에 달까지만 있으면 `YYYY-MM` → '(일자 미공개)'로 표시). 제목이 `(예정)`으로 시작하거나 날짜가 미래면 중요 공지 페이지의 '예정된 변경'에 따로 표시. 이미 메일로 나간 공지의 날짜를 고칠 때는 `key_date`에 원래 날짜를 남겨 다시 발송되지 않게 함 |
| `links` | 참고 링크 `[{name, url}]` |
| `watch_urls` | 자동 감시할 공지 페이지 |
| `last_verified` | 공식 페이지에서 확인한 날짜 `"YYYY-MM-DD"` |

## 분야별 소분류 (`group` 허용값)

| domain | group |
|---|---|
| `atmosphere` | `재분석`, `지역 재분석`, `위성 관측 미동화 재분석`, `육상 재분석`, `강수 자료`, `기온 자료`, `복사 자료` |
| `ocean` | `재분석`(상태 추정 포함), `해수면온도 분석장`, `수온·염분 분석장`, `위성 관측 자료`, `모델 강제력` |
| `seaice` | `재분석`, `관측 기반 분석장`(SST 자료의 해빙 농도 교차 수록), `위성 관측 자료`, `해빙 이동`, `해빙 지수` |
| `land` | `육상 재분석·자료동화`, `토양수분`, `증발산`, `식생`, `토지피복`, `지표면온도·알베도`, `적설`, `육수저장량`, `산불` |
| `model` | `전지구 모델 실험`(CMIP), `지역 다운스케일링`(CORDEX), `통계 다운스케일링·편이보정`, `국가 기후변화 시나리오` — 기후모델 시뮬레이션 자료 |
| `satellite` | `강수`, `구름·복사`, `기온·수증기`, `에어로졸·대기 성분`, `해수면온도`, `해상풍`, `해색`, `해면 염분`, `해면고도·파랑`, `해빙`, `빙하·빙상`, `지면` — 위성 자료를 관측 대상별로 모은 탭. 다른 탭의 위성 자료는 `also_in`으로 교차 수록 |

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

## 변수의 시간 특성 (필수)

3시간 간격 자료라도 그 값이 **그 시각의 순간값**인지, **3시간 평균**인지, **3시간 누적**인지에 따라 해석이 완전히 달라집니다.
그래서 모든 변수에 시간 특성(`kind`)을 적고, 자료 전체의 시간 표기 규칙(`time_convention`)을 요약합니다.

`kind` 허용값: `instant` 순간값 / `mean` 평균 / `accum` 누적 / `max` 최대 / `min` 최소 / `static` 고정값(지형·해륙 마스크 등)

`period`: 평균·누적·최대·최소의 구간 (예: `"1시간"`, `"3시간"`, `"6시간"`, `"일"`, `"월"`, `"예보 시작 이후"`)

그룹 단위로 기본값을 주고, 다른 변수만 항목에서 따로 적을 수 있습니다.

```yaml
time_convention:
  summary: >-
    분석 변수는 표시 시각의 순간값이고, 강수·복사·플럭스는 표시 시각까지 직전 1시간 동안 누적한 값입니다.
  points:
    - "누적 변수는 표시 시각이 누적 구간의 '끝'입니다 (예: 01 UTC 값 = 00~01 UTC 누적)"
    - "단위가 m(강수), J m-2(복사)처럼 누적량이므로 W m-2로 바꾸려면 3600으로 나눕니다"
  source: https://공식-문서-주소
  source_name: ERA5 documentation

variables:
  groups:
    - name: 지표·단일면
      kind: instant              # 이 그룹의 기본값
      items:
        - "2m 기온 — `2t` (K)"
        - text: "총강수량 — `tp` (m)"
          kind: accum
          period: 1시간
          note: 표시 시각 직전 1시간
```

## 표준 변수 (변수 찾기)

자료 비교 페이지의 **변수 찾기**는 `data/variables.yaml`의 표준 변수 목록(CF 표준 이름 기준)으로 자료마다 다른 변수 이름을 묶습니다.

- 각 변수 항목은 한국어 설명을 정규식 규칙(`include`/`exclude`)으로 읽어 자동으로 표준 변수에 묶입니다. 영어 파일은 같은 자리의 한국어 항목을 따릅니다.
- 자동 판정이 틀리면 변수 항목을 `{text: "...", std: [precip]}`처럼 직접 지정하고, 어디에도 묶지 않으려면 `std: []`를 씁니다.
- 기후모델(`domain: model`) 자료는 대기·해양·해빙·지면 변수를 모두 다루므로 표준 변수의 `domains` 제한을 받지 않습니다.
- 새 자료를 추가한 뒤 `python scripts/var_report.py`로 묶인 결과와 안 묶인 변수를 확인하세요.

## 정리 원칙

- DOI, 기간, URL, 상태는 **반드시 공식 페이지에서 확인**합니다.
- 공지에는 원문 링크(`source`)를 붙입니다.
- 데이터셋 이름·변수명·DOI·코드·BibTeX는 원문 그대로 둡니다.
