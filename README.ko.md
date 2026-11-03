# 두디(Doody): 일상 리듬과 금융 자립 회복을 위한 해석 가능한 상태공간 엔진

[English](./README.md) | 한국어

두디는 일·학업·사회 활동에서 멀어진 청년의 일상 리듬과 금융 자립 회복을 돕는 서비스이고, 이 레포는 그중 AI 엔진이다. 4개월 과정의 하나금융인재 프로그램(2026.03–2026.07)에서 개발했으며, 220개 팀 중 13개 팀에 선발되었다. 팀장이자 AI 엔진 담당으로 참여했다.

엔진은 사용자 상태를 리듬·자립·연결 3개 축의 벡터로 표현하고, 이를 바탕으로 오늘의 작은 행동 하나를 고른다. 결정은 명시적인 수식으로 내리고, LLM은 그 결정을 설명하는 문장만 작성한다.

프론트엔드와 백엔드는 별도 레포에 있다: [doody-frontend](https://github.com/HanaDoody/doody-frontend), [doody-backend](https://github.com/HanaDoody/doody-backend).

## 세 축과 메커니즘

세 축은 하나의 좌표계를 공유하지만 움직이는 방식은 서로 다르다.

| 축 | 메커니즘 | 해금 |
|---|---|---|
| 리듬 | 아침·저녁 체크인. 미션 축이 아니라 항상 열려 있으며 미션 게이트의 시작값이 된다 | 없음 |
| 자립 | 10단계 미션 경로. 온보딩으로 시작 단계를 정하고, fallback 미션도 단계를 진행한다 | 10단계 정상 signature 미션 완료 |
| 연결 | 두디 캐릭터 수집. 온보딩으로 필요 개수 N을 정한다 | 수집 개수 ≥ N |

## 결정 과정

매 호출은 상태 읽기, 다음 행동 고르기, 문장 작성의 세 단계로 이루어진다.

### 1. 상태 읽기

| 값 | 식 | 의미 |
|---|---|---|
| 리듬 존재도 | `v ← v + α(aₜ − v)`, `aₜ = (아침 + 저녁) / 2` | 체크인 존재 여부의 EMA. `α_up > α_down`이므로 회복을 하락보다 빠르게 반영한다 |
| 간격 | `gap = g − v` | 목표까지 남은 방향 |
| 속도 | `velocity = vₜ − vₜ₋₁` | 최근 변화 방향 |
| 회복 저항 | `recovery_drag = gap − velocity` | 남은 간격에서 최근 진전을 뺀 잔차. 값이 가장 큰 축이 병목이다 |

### 2. 다음 행동 고르기

| 값 | 규칙 | 의미 |
|---|---|---|
| 게이트 | `gate = clamp((v_rhythm − r_floor) / (r_open − r_floor))` | 리듬을 [0, 1]로 변환한다. 0이면 리듬 체크인만 남는다. 오래 정체되면 escape hatch가 하한을 올린다 |
| Fallback 우선 | `gate < 0.5` 또는 `energy ≤ 2` | 더 작은 미션을 먼저 제시한다 |
| 스텝 크기 | `vₜ₊₁ = vₜ + η(energy)Δ`, η는 0.4~1.0 | 에너지가 낮은 날에는 같은 미션의 상태 변화가 작다 |
| 축 우선순위 | `bottleneck_axis(recovery_drag)` | 연결이 더 뒤처지면 자립 미션을 연결 유도로 교체한다 |

### 3. 문장 작성

모든 결정은 `decision_trace = {situation, primary_constraint, stage, waypoint, fallback_first}`로 기록된다. LLM은 이 기록을 받아 문장으로 작성하며, 결정을 바꿀 수 없다.

## 실패 모드

실패 조건마다 처리 경로를 정해 두었다.

| 조건 | 트리거 | 처리 |
|---|---|---|
| 리듬 하한 | `gate = 0` | 자립·연결을 잠그고 리듬 체크인만 유지 |
| 낮은 컨디션 | `gate < 0.5` 또는 `energy ≤ 2` | 더 작은 미션을 먼저 제시 |
| 장기 정체 | `days_without ≥ escape_days` | 게이트 하한 상향 |
| 사용자 원문의 위기 신호 | 위기 키워드 감지 | LLM을 우회하고 고정 안전 문구 반환 |
| LLM 실패 또는 가드 위반 | 예외, 길이·숫자 위반 | 고정 문구로 대체하며 예외를 전파하지 않음 |

30회 호출 실측: 지연 시간 중앙값 약 3.5초, p95 약 10초, fallback 0회(timeout 20초, retry 1회). 측정 도구는 [`evals/`](./evals)에 있다.

## 상태 추정의 한계

이 서비스는 회피나 실패를 기록하지 않으므로 로그 대부분이 긍정 이벤트다. 문항반응이론처럼 engagement를 잠재 상태의 noisy readout으로 모델링하면, innovation의 양의 성분만 반영되어 추정값이 상승 방향으로 치우치고 그 편향은 상태가 낮은 사용자에게서 더 크다. 하방 동역학은 이 로그만으로 식별할 수 없다.

복귀 간격과 발화 probe를 쓰면 사용자에게 불이익을 주지 않고 빠진 신호를 일부 복원할 수 있다. 이 내용은 모델 구조 분석이며 실제 사용자 데이터로 측정한 결과는 아니다. 자세한 내용은 [`docs/research_track.md`](./docs/research_track.md)에 있다.

## 현재 범위

- 구현: 위 상태공간 수식, FastAPI 엔드포인트 12개, LLM 문장 생성과 fallback, 위기 가드, 테스트
- 상태공간은 데이터로 학습한 것이 아니라 직접 설계한 것이다. 로그 기반 학습과 probing 검증으로 확장 가능하다.
- 자연어 신호 추출(`app/nlu/`)은 MVP에서 stub이다. 설계는 [`app/nlu/README.md`](./app/nlu/README.md)에 있다.

## 레포 구조

```
app/
├── api/       FastAPI 라우트
├── schemas/   요청·응답 모델
├── core/      상태공간 수식, 게이트, 미션 선택, 해금
├── llm/       문장 생성, fallback, 위기 가드
├── data/      카탈로그와 설정
├── nlu/       신호 추출 (stub)
└── fusion/    신호 결합 (stub)
evals/         LLM 평가 도구
tests/         계약 테스트와 단위 테스트
```

| 문서 | 내용 |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | 설계 결정 |
| [`docs/research_track.md`](./docs/research_track.md) | 상태 추정의 한계와 연구 확장 |
| [`docs/api_contract.md`](./docs/api_contract.md) | API 계약 |

## 실행

```bash
pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload
```

LLM은 기본적으로 꺼져 있어 API 키 없이 고정 문구로 동작한다. 켜려면 `ANTHROPIC_API_KEY`와 `LLM_ENABLED=true`를 설정한다.

이 레포는 AI 엔진의 정리본이다. 개발 기록은 팀의 비공개 레포에 있다.
