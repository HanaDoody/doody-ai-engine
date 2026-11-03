# doody-ai-engine

[English](./README.md) | 한국어

두디(Doody) **AI 엔진** 레포지토리.

공백 청년의 상태를 **리듬·자립·연결 3차원 회복 공간**의 벡터로 모델링하고,
현재 상태(ARI)와 목표 사이의 간격을 **작은 미션(이동 벡터)** 으로 줄여가는 AI 엔진이다.
LLM에게 판단을 맡기지 않고, 해석 가능한 상태 공간 안에서 *오늘 가능한 한 걸음*의 **위치·크기·난이도·말투·해금**을 계산한다.

> 두디 서비스는 **[front](https://github.com/HanaDoody/doody-frontend) / [back](https://github.com/HanaDoody/doody-backend) / AI 각각 별도 레포**로 나뉘며, 이 레포는 그중 **AI 엔진**을 담당한다.
> 세 레포는 HTTP API + JSON 계약으로만 연동된다.

### [설계 결정 → `DESIGN.md`](./DESIGN.md)
왜 이렇게 지었는가(ADR). **결정론 코어 + LLM 언어 표면**(D0)을 중심으로, **stateless 엔진**(D1)·**위기 안전가드**(D2)·**비용 게이팅**(D3)의 맥락·대안·tradeoff를 기록했다.

## 세 축, 서로 다른 메커니즘

3축은 하나의 ARI 좌표계를 공유하지만, 축마다 다른 방식으로 움직인다. (대칭적인 기능 3개가 아니다.)

| 축 | 메커니즘 | 해금 |
|---|---|---|
| **리듬(rhythm)** | 매일의 기본 리듬 (아침/저녁 체크인). 미션 축이 아니라 항상 열려 있는 바닥 레이어이자 미션 게이트 seed | 없음 |
| **자립(autonomy)** | 10단계 미션 경로 (stage 1→10). 온보딩 진단으로 시작 stage 개인화, fallback도 stage 진행 | stage 10 정상 signature 완료 → 접점 |
| **연결(connection)** | 두디 수집 경로. 온보딩 연결 진단으로 필요 개수 N 개인화(고립 심할수록 큰 N) | 모은 두디 수 ≥ N → 접점 |

> 엔진 = *다음 한 걸음을 고르는 상태공간 컨트롤러*. 결정은 core(수학)가 하고, 말은 LLM이 입힌다.

## 아키텍처 — 무상태 계산기

AI 엔진은 **DB를 갖지 않는다(stateless).** 매 호출마다 백엔드가 필요한 상태(현재 ARI·궤적·이력·수집 개수 등)를 실어 보내고, 엔진은 계산 결과만 돌려준다. 따라서 *"엔진이 입력으로 요구하는 것" = "백엔드가 저장해야 하는 것"* 이다.

```
[앱 화면] ──▶ [백엔드: 인증·DB·중계] ──▶ [AI 엔진(이 레포): 계산만]
                    │
                  [ DB ]  ← 저장·누적(하나머니 등)은 백엔드 책임
```

- **AI 엔진**: ARI 계산 · 미션 선택 · waypoint 재설계 · 보상 산정 · 접점 해금 판정 · 동적 문장 생성
- **백엔드**: 인증 · 상태/이력/보상 저장 · 엔진 호출 중계

## AI 엔진이 정확히 하는 일

두디 AI는 **판단하는 블랙박스도, 데이터로 학습한 생성 모델도 아니다.** 사용자의 행동 로그를 **해석 가능한 3차원 표현 공간(리듬·자립·연결)의 상태 벡터**로 읽고, 그 표현 위에서 *오늘의 한 걸음*을 고르는 **결정론적 컨트롤러**다. 즉 `입력(행동) → 내부 표현(상태 벡터) → 행동(다음 미션)` 경로 전체가 학습된 가중치가 아니라 **직접 설계한 수식으로 드러나 있고**, 말(문장)만 LLM이 입힌다. 매 호출은 세 단계다:

```
① 읽기(상태 추정)  →  ② 고르기(결정)  →  ③ 말하기(문장)
   상태공간 수학          게이트·stage          Sonnet 5 + 폴백
```

### ① 읽기 — 상태를 벡터로 추정
| 계산 | 식 | 의미 |
|---|---|---|
| 리듬 존재도 | `v ← v + α·(aₜ − v)`, `aₜ=(아침+저녁)/2` | 체크인의 **존재**만으로 EMA. `α_up>α_down` 비대칭 → **회복은 관대하게, 붕괴는 보수적으로** 반영하는 히스테리시스. 시작값 = 온보딩 리듬 답 |
| 간격 | `gap = g − v` | 목표까지 남은 방향 벡터 |
| 속도 | `velocity = vₜ − vₜ₋₁` | 최근 회복 방향 |
| 회복 저항 | `recovery_drag = gap − velocity` | 남은 거리에서 **자기 힘으로 좁히는 만큼을 뺀 잔차(residual)** — 개입이 필요한 부분만 남는다. 큰 축 = 병목 |

### ② 고르기 — 게이트·stage로 다음 칸 결정
| 계산 | 식 | 의미 |
|---|---|---|
| 게이트 | `gate = clamp((v_rhythm − r_floor)/(r_open − r_floor))` | 리듬 축을 [0,1]로 변환한 값 — 리듬이 바닥이면 `gate=0`으로 자립/연결 축을 **잠근다**(리듬 카드만). 며칠 방치 시 floor↑(escape hatch) |
| fallback-first | `gate<0.5` 또는 `energy≤2` | 컨디션 낮으면 **더 작은 칸 먼저** |
| 자립 경로 | `next_stage(history)` | 종료 조건 = stage 10 정상 signature. ARI는 라우팅에 쓰지 않고 diagnostics에만 남음 |
| 스텝 크기 | `v_{t+1} = v_t + η·Δ`, `η(energy)` 0.4~1.0 | 같은 미션도 컨디션 따라 반영 크기가 다름 |
| 축 우선순위 | `bottleneck_axis(recovery_drag)` | 연결이 자립보다 더 뒤처지면 오늘의 카드를 자립 미션 대신 연결 유도로 교체(`mission_state="connection_priority"`) — 오늘의 카드는 하나라 덧붙이지 않고 통째로 바꾼다 |
| 접점 해금 | 자립: signature 완료 / 연결: 모은 두디 ≥ N | 규칙 기반, N은 온보딩으로 개인화 |

### ③ 말하기 — 결정과 언어의 분리
- 엔진은 매 결정을 **`decision_trace = {situation, primary_constraint, stage, waypoint, fallback_first}`** 로 남긴다 — 왜 이 미션이 나왔는지에 대한 해석 가능한 근거.
- 이 trace가 **LLM 입력**이다. **판정은 해석 가능한 수학이 소유하고, 생성 모델은 그 trace에 grounding된 표면 문장만 만든다** — LLM(Sonnet 5)은 말투를 입힐 뿐 **결정을 오버라이드할 수 없다.** 실패·위기 시 결정론 문구로 폴백한다.

### 실패 모드를 설계로 다룬다
정상 경로보다 **"언제·왜 깨지는가"를 먼저 정의**하고, 각 붕괴 지점에 안전 경로를 뒀다.

| 붕괴 조건 | 트리거 | 안전 처리 |
|---|---|---|
| 리듬 바닥 — 미션 동력 없음 | `gate = 0` | 자립/연결 잠금, 리듬 바닥 레이어만 남김 |
| 낮은 컨디션 | `gate<0.5` 또는 `energy≤2` | fallback-first — 더 작은 칸 먼저 |
| 오래 정체 | `days_without ≥ escape_days` | escape hatch — 게이트 floor↑로 우회 |
| 위기 신호 (사용자 원문) | crisis 키워드 감지 | LLM 우회 + 고정 안전문구 (보상은 지급) |
| LLM 실패·가드 위반 | 호출 예외·길이/숫자 위반 | 결정론 문구로 폴백 (엔진은 절대 예외 전파 X) |

### 현재 범위 — 구현된 것 / 아직 아닌 것
- **구현된 것**: 위 상태공간 수학 전부(존재 EMA·게이트·recovery_drag·η·해금), 12 엔드포인트, LLM 문장 생성 + 폴백 + 위기가드, 테스트. LLM 라이브 실측(30콜·Sonnet 5): 지연 **median ~3.5s / p95 ~10s**, 폴백 0 (timeout 20s·retry 1). 계측·eval 하네스는 [`evals/`](./evals).
- **아직 아닌 것**: 현재 표현 공간은 데이터로 **학습한 게 아니라 설계된 것**이다 — 로그에서 표현을 학습하거나 상태 추정을 probing으로 검증하는 확장 자리는 열려 있지만(roadmap seam), 지금은 규칙/수식 기반이다. 자연어 이해(`nlu/`)는 MVP 보류(stub). 연결 두디 거리/난이도 그레이딩은 개념만. 프롬프트 캐싱 미적용.

## API 한눈에 (12 엔드포인트)

| Method & Path | 역할 |
|---|---|
| `GET  /health` | 서버 상태 확인 |
| `POST /onboarding/intro` | 최초 진입 → 가벼운 첫 미션 (**ARI 없음**) |
| `POST /onboarding/recommend-period` | 목표(+상태) → 추천 기간 (추천≠최종) |
| `POST /onboarding/complete` | 후행 온보딩 → 초기 ARI v₀ · 목표 g · 시작 stage · 리듬 seed |
| `POST /mission/recommend` | 현재 상태 → 추천 미션 (게이트 · fallback-first · decision_trace) |
| `POST /mission/complete` | 미션 완료 → ARI 갱신(vₜ₊₁ = vₜ + η·Δ) · **보상(hana_money)** · 접점 해금 |
| `POST /mission/reject` | 거절 → 더 작은 후보 / 경로 재설계 |
| `POST /collection/capture` | 두디 포획 → 연결 ARI 갱신 · 보상 · **count 기반 접점 해금** |
| `POST /rhythm/morning` | 아침 리듬 체크인 → 인사 · 보상 |
| `POST /rhythm/evening` | 저녁 리듬 기록 → 답장 · 보상 (위기가드) |
| `POST /chat/message` | 두디 응답 + 자연어 보조 신호 (무상태 단일 턴, 위기가드) |
| `POST /report/summary` | 회복 리포트 (수치 주입 → LLM 방향 서술) |

> 엔드포인트별 요청/응답 JSON·필드 상세 → [`docs/api_contract.md`](./docs/api_contract.md)

## LLM — 말만, 판단은 안 함

- 동적 문구(`reason` · `rest_message` · `message` · `reply` · `greeting` · `summary`)는 **Claude Sonnet 5**가 생성한다.
- `is_enabled()`(API 키 AND 설정 토글)가 아니거나 호출 실패 시 **결정론 폴백**으로 안전하게 떨어진다. 레포 기본은 `enabled:false`(과금·지연은 프로덕션에서 의도적으로 켠다).
- **위기가드**: `chat`·`evening` 원문에 위기 신호가 감지되면 LLM을 우회하고 **고정 안전문구**를 반환한다(보상은 정상 지급).
- 정적 문구(`title` · `description` · `how_to`)는 카탈로그 고정값 → 그대로 노출.

## 기술 스택
- **Python + FastAPI** (uvicorn, pydantic)
- **Claude API** (`claude-sonnet-5`) — 동적 텍스트에만 사용, 판단 X
- 테스트: `python -m pytest -q`

## 문서
| 문서 | 내용 |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | **설계 결정(ADR)** — 결정론 코어 + LLM 표면 · stateless · 위기 안전가드 · 비용 게이팅 |
| [`docs/research_track.md`](./docs/research_track.md) | 상태 추정의 한계와 확장 가능한 연구 질문 |
| [`docs/api_contract.md`](./docs/api_contract.md) | API 계약 — 요청/응답 JSON·공통 객체·백엔드 저장 데이터·용어집 |
| [`app/nlu/README.md`](./app/nlu/README.md) | 임베딩 기반 신호 추출 설계 |
| [`evals/README.md`](./evals/README.md) | LLM eval / observability 하네스 |

## 레포 구조
`app/`은 폴더마다 한 가지 일만 한다:

```
app/
├── api/       요청 수신 (엔드포인트 → 라우터, 위 12개와 1:1)
├── schemas/   DTO (pydantic)
├── core/      회복 공간 수학 (게이트·미션 선택·ARI 갱신·해금·보상)
├── llm/       동적 문장 (Sonnet 5 단일 길목 + 결정론 폴백 + 위기가드)
├── data/      카탈로그·설정 (미션·두디·핀·목표·게이트 config)
├── nlu/       자연어 보조 (MVP 보류)
└── fusion/    신호 결합 (MVP 보류)
```

## 현재 상태
- [x] 기획·설계 정리
- [x] API 계약 문서 (`docs/`)
- [x] **AI 엔진 구현** — FastAPI 12 엔드포인트, 테스트
- [x] **v3.2 컨트롤러** — 진단→시작 stage · 리듬 seed 게이트 · fallback-first · 연결 count 해금 · 미션 보상
- [x] **LLM 통합** — Sonnet 5 단일 길목 + 결정론 폴백 + 위기가드

## 프로젝트 배경
하나금융인재 프로젝트 (ESG + 미래금융). 4개월 과정(2026.03–2026.07), 220개 팀 중 13개 팀 선발. 팀장 겸 AI 엔진 담당.

이 레포는 AI 엔진의 정리본이며, 개발 기록은 팀의 비공개 레포에 있다.
