# 두디 AI 엔진 — API 계약서 (API Contract) `draft v0.7`

> **Contract patch v0.7.2 (2026-06-27)**: 자립 미션 MVP가 **10단계 catalog + fallback/downshift + signature mission + contact unlock** 구조로 확정되었다. 이 섹션은 아래 기존 `Mission`, `/mission/recommend`, `/mission/complete`, `/mission/reject`, `unlocked_contacts` 설명 중 자립 미션과 충돌하는 부분을 우선한다. 연결 축은 기존대로 `collection/capture` 점수 누적 모델을 유지한다.

## 0-A. 자립 미션 MVP 계약 — 10단계, Fallback, Signature

### 0-A.1 적용 범위

이번 MVP에서 AI 엔진이 실제로 처리하는 범위:

- 자립(`autonomy`) 10단계 mission catalog 관리
- 각 normal mission에 fallback mission 1개 연결
- `/mission/recommend` 응답에 `mission`과 `fallback` 동시 제공
- 프론트의 "어려워요" 클릭은 서버 호출 없이 로컬에서 `fallback` 카드로 교체
- `/mission/complete`는 실제 완료한 `mission_id` 하나만 전송
- 엔진은 `mission_id`로 normal/fallback/signature 여부와 delta를 판정
- normal signature mission 완료 시에만 자립 contact unlock
- signature fallback은 준비 행동이며 contact를 unlock하지 않음

이번 MVP에서 하지 않는 것:

- 별도 downshift API 생성
- downshift 클릭 이력 저장
- 이미지 업로드/서버 저장
- OCR/VLM 분석
- FutureProfile DB/엔티티 생성
- 자유로운 관심 분야 생성
- LLM 기반 mission 생성

### 0-A.2 Mission DTO 확장

`Mission`은 기존 필드를 유지하되, 자립 10단계/fallback/signature 흐름을 위해 아래 필드를 추가한다.

| 필드 | 타입 | 필수 | 의미 |
|---|---|---:|---|
| `id` | string | O | 기존 호환용 mission id. `mission_id`와 같은 값 |
| `mission_id` | string | O | 실제 완료 요청에 다시 보내는 catalog id |
| `axis` | enum | O | `autonomy` 또는 `connection`. 자립 catalog는 `autonomy` |
| `stage` | int \| null | O | 자립 단계. normal/fallback 모두 같은 stage를 공유 |
| `waypoint` | string \| null | O | 단계 의미를 나타내는 내부 label. **B12c**: `completable=false`(연결 유도)일 땐 `null` |
| `difficulty` | int \| null | O | 1~5. **B12c**: `completable=false`일 땐 `null`(가짜 난이도 금지) |
| `delta` | `ARIVector` \| null | O | 완료 시 적용할 delta. rhythm은 0. **B12c**: `completable=false`일 땐 `null`(실제 delta는 `/collection/capture`가 적용) |
| `title` | string | O | 카드 제목 |
| `description` | string \| null | O | 카드 설명 |
| `mission_type` | enum | O | `CHECK` \| `IMAGE` \| `LINK` |
| `required_count` | int | O | IMAGE 등에서 필요한 로컬 선택 개수 |
| `is_signature` | bool | O | signature 단계/미션 여부 |
| `is_fallback` | bool | O | fallback/downshift 미션 여부 |
| `fallback_mission_id` | string \| null | O | normal mission에서 연결된 fallback id. fallback은 null |
| `goal_tags` | string[] | O | 미래 설계/관심 태그용. MVP에서는 catalog 값 |
| `how_to` | string[] | O | 수행 안내 |
| `reason` | string | O | 추천 이유. MVP는 deterministic 문구 가능 |
| `completable` | bool | O | **B12c 신규, 기본 `true`.** `false`면 `/mission/complete`·`/mission/reject` 대상 아님(카탈로그에 없는 id라 호출해도 404). 지금은 `connection_priority`의 연결 유도 카드(`id="c_connection_nudge"`)만 `false` |

예시:

```json
{
  "id": "a06_future_capture_3",
  "mission_id": "a06_future_capture_3",
  "axis": "autonomy",
  "stage": 6,
  "waypoint": "future_exploration",
  "difficulty": 2,
  "delta": { "rhythm": 0.0, "autonomy": 0.06, "connection": 0.0 },
  "title": "마음이 가는 화면 3개 남기기",
  "description": "진로, 취업, 학업 정보를 둘러보고 마음이 머무는 화면을 3개 골라요.",
  "mission_type": "IMAGE",
  "required_count": 3,
  "is_signature": false,
  "is_fallback": false,
  "fallback_mission_id": "a06_future_capture_1",
  "goal_tags": ["employment", "study", "career"],
  "how_to": ["이미지는 서버에 올리지 않아요", "기기 안에서 고르기만 해요"],
  "reason": "자립 쪽에 아직 남은 다음 칸이 있어요."
}
```

Fallback 예시:

```json
{
  "id": "a06_future_capture_1",
  "mission_id": "a06_future_capture_1",
  "axis": "autonomy",
  "stage": 6,
  "waypoint": "future_exploration",
  "difficulty": 1,
  "delta": { "rhythm": 0.0, "autonomy": 0.03, "connection": 0.0 },
  "title": "마음이 가는 화면 하나만 남기기",
  "description": "오늘은 하나만 골라도 충분해요.",
  "mission_type": "IMAGE",
  "required_count": 1,
  "is_signature": false,
  "is_fallback": true,
  "fallback_mission_id": null,
  "goal_tags": ["employment", "study", "career"],
  "how_to": ["preview만 보여줘도 돼요"],
  "reason": "지금 상태에서 가장 작은 다음 칸이에요."
}
```

### 0-A.3 자립 10단계 catalog 규칙

자립 catalog는 AI 엔진의 `app/data/mission_templates.json`이 source of truth다. DB에는 mission definition table을 만들지 않는다.

| Stage | 의미 | Normal | Fallback | 비고 |
|---:|---|---|---|---|
| 1 | 감정 마주하기 | 돈 생각 감정 하나 고르기 | 더 쉬운 감정 단어 하나 고르기 | CHECK |
| 2 | 긍정 경험 찾기 | 최근 잘한 일 하나 떠올리기 | 덜 무거운 종류 하나 고르기 | CHECK |
| 3 | 금융 접촉 | 금융 앱 열고 닫기 | 앱 아이콘만 찾아보기 | LINK/CHECK |
| 4 | 잔액 관찰 | 잔액 한 번 보기 | 로그인 화면까지만 가기 | LINK |
| 5 | 소비 관찰 | 최근 소비 하나 확인 | 소비 종류 하나 고르기 | CHECK |
| 6 | 미래 탐색 | 화면 3개 남기기 | 화면 1개 남기기 | IMAGE, 서버 업로드 없음 |
| 7 | 관심 확인 | 두디가 정리한 방향 확인 | 가까운 태그 하나 고르기 | CHECK |
| 8 | 방향 선택 | 먼저 볼 방향 하나 고르기 | 일단 보관하기 | CHECK |
| 9 | 자원 계획 | 필요한 시간/비용/지원 하나 확인 | 가장 부담되는 것 하나 고르기 | LINK/CHECK |
| 10 | Signature | 다음 행동/날짜/자원 확정 | 다음 행동만 고르고 날짜는 나중에 | normal만 unlock |

Fallback 완료는 실패가 아니다. 다만 normal stage 완료로 간주하지 않고, 낮은 delta만 적용한다. 따라서 다음 normal stage advance 여부는 backend/engine이 실제 완료 `mission_id`를 기준으로 판정한다.

### 0-A.4 `/mission/recommend` 응답 확장

`RecommendResponse`는 기존 필드에 `fallback`을 추가한다.

```json
{
  "mission": { "...": "Mission | null" },
  "fallback": { "...": "Mission | null" },
  "mission_state": "active",
  "rest_message": null,
  "unlocked_contacts": [],
  "v_rhythm": 0.62,
  "diagnostics": {}
}
```

규칙:

- `mission_state="gated"`이면 `mission=null`, `fallback=null`.
- `mission_state="active"`이고 자립 normal mission이 있으면 가능한 경우 `fallback`도 함께 제공한다.
- 사용자가 "어려워요"를 누르면 프론트는 서버 호출 없이 `fallback` 카드로 교체한다.
- fallback 완료 시 `/mission/complete`에는 fallback의 실제 `mission_id`를 보낸다.
- 별도 `is_downshifted`, `completion_mode`, downshift API는 없다.
- **B12 (2026-07-11)**: `bottleneck_axis`가 connection이면(리듬 게이트 열림 + 자립 signature 미완료 조건 하에서) `mission_state="connection_priority"`. 자립 카드에 문구를 덧붙이는 게 아니라 **오늘의 카드 자체를 연결로 교체**한다 — "오늘의 카드는 하나" 원칙. 연결 자체의 진행·해금은 여전히 `/collection/capture` 채널이 전담(아래 Mission은 그쪽으로 안내만 할 뿐 자체적으로 뭘 바꾸지 않음).
- **B12c (2026-07-11, 백엔드 피드백 반영)**: 프론트가 자립·연결을 "오늘의 미션" **같은 응답 모델**로 렌더링해야 해서 `mission=null` 대신 **자립과 같은 `Mission` 형태**로 내려준다. 단 `completable=false`(이 미션은 `/mission/complete` 대상이 아님, 실제 진행은 `/collection/capture`가 함), `waypoint`·`difficulty`·`delta`는 연결에 없는 개념이라 **가짜 값 대신 `null`**로 둔다(자립 값처럼 저장하면 자립/연결 분리 원칙 위반). `id`/`mission_id`는 카탈로그에 없는 고정 문자열 `"c_connection_nudge"` — `/mission/complete`·`/mission/reject`에 이 id로 호출하면 카탈로그 조회 실패로 404(의도된 안전장치, 프론트는 `completable=false`로 애초에 완료 버튼을 안 띄워야 함). `mission_logs` 저장 여부는 백엔드 재량(자립처럼 저장 안 해도 됨 — 이 DTO 공유는 저장 대상 공유를 의미하지 않음).

```json
{
  "mission": {
    "id": "c_connection_nudge",
    "mission_id": "c_connection_nudge",
    "axis": "connection",
    "stage": null,
    "waypoint": null,
    "difficulty": null,
    "delta": null,
    "title": "두디를 잡으러 가보자",
    "description": null,
    "mission_type": "CHECK",
    "how_to": ["지도를 열어봐", "가까운 핀으로 가봐", "두디를 탭해서 잡아봐"],
    "reason": "오늘은 자립 대신 두디를 잡으러 나가보는 건 어때?",
    "completable": false
  },
  "fallback": null,
  "mission_state": "connection_priority",
  "rest_message": null
}
```
- 자립 ARI가 목표에 도달했고 normal signature가 아직 완료되지 않았으면 signature mission을 추천한다.

Active 예시:

```json
{
  "mission_state": "active",
  "mission": {
    "mission_id": "a06_future_capture_3",
    "axis": "autonomy",
    "stage": 6,
    "waypoint": "future_exploration",
    "title": "마음이 가는 화면 3개 남기기",
    "description": "진로, 취업, 학업 정보를 둘러보고 마음이 머무는 화면을 3개 골라요.",
    "mission_type": "IMAGE",
    "required_count": 3,
    "is_signature": false,
    "is_fallback": false
  },
  "fallback": {
    "mission_id": "a06_future_capture_1",
    "title": "마음이 가는 화면 하나만 남기기",
    "description": "오늘은 하나만 골라도 충분해요.",
    "mission_type": "IMAGE",
    "required_count": 1,
    "is_fallback": true
  },
  "rest_message": null,
  "unlocked_contacts": [],
  "v_rhythm": 0.62,
  "diagnostics": {
    "gate": 0.95,
    "bottleneck_axis": "autonomy"
  }
}
```

### 0-A.5 `/mission/complete` 처리 확장

Request는 기존처럼 실제 완료한 mission id만 보낸다.

```json
{
  "user_id": "u_a1b2c3",
  "mission_id": "a06_future_capture_1",
  "current_ari": { "rhythm": 0.42, "autonomy": 0.30, "connection": 0.55 },
  "energy": 3
}
```

엔진 처리:

```text
mission_id -> catalog lookup
normal/fallback/signature 판정
eta = eta_by_energy[energy]
updated_ari = current_ari + eta * mission.delta
```

Response 확장:

| 필드 | 타입 | 의미 |
|---|---|---|
| `updated_ari` | `ARIVector` | 적용 후 ARI |
| `applied_delta` | `ARIVector` | eta가 곱해진 실제 delta |
| `eta` | float | energy 기반 step size |
| `completed` | bool | 완료 처리 여부 |
| `signature_available` | bool | 이 완료가 signature 계열인지 |
| `signature_completed` | bool | normal signature 완료 여부 |
| `contact_unlocked` | bool | 이번 완료로 contact가 열렸는지 |
| `collected_dudy` | `Dudy[]` | signature 등 획득 두디 |
| `unlocked_contacts` | `Contact[]` | 이번 완료로 열린 접점 |
| `message` | string | 사용자용 문구 |

Normal 완료 예시:

```json
{
  "updated_ari": { "rhythm": 0.42, "autonomy": 0.336, "connection": 0.55 },
  "applied_delta": { "rhythm": 0.0, "autonomy": 0.036, "connection": 0.0 },
  "eta": 0.6,
  "completed": true,
  "signature_available": false,
  "signature_completed": false,
  "contact_unlocked": false,
  "collected_dudy": [],
  "unlocked_contacts": [],
  "message": "오늘의 한 칸을 조용히 넘겼어요."
}
```

Fallback 완료 예시:

```json
{
  "updated_ari": { "rhythm": 0.42, "autonomy": 0.318, "connection": 0.55 },
  "applied_delta": { "rhythm": 0.0, "autonomy": 0.018, "connection": 0.0 },
  "eta": 0.6,
  "completed": true,
  "signature_available": false,
  "signature_completed": false,
  "contact_unlocked": false,
  "collected_dudy": [],
  "unlocked_contacts": [],
  "message": "오늘의 한 칸을 조용히 넘겼어요."
}
```

Normal signature 완료 예시:

```json
{
  "updated_ari": { "rhythm": 0.42, "autonomy": 0.77, "connection": 0.55 },
  "applied_delta": { "rhythm": 0.0, "autonomy": 0.05, "connection": 0.0 },
  "eta": 1.0,
  "completed": true,
  "signature_available": true,
  "signature_completed": true,
  "contact_unlocked": true,
  "collected_dudy": [
    { "id": "d_autonomy_signature", "tier": "signature", "axis": "autonomy", "earned_reason": "돈을 마주하는 마지막 한 칸에 닿았어요" }
  ],
  "unlocked_contacts": [
    { "id": "hana_youth_edu", "title": "하나 청년 금융교육 바로가기", "axis": "autonomy" }
  ],
  "message": "오늘의 한 칸을 조용히 넘겼어요."
}
```

Signature fallback 완료 예시:

```json
{
  "completed": true,
  "signature_available": true,
  "signature_completed": false,
  "contact_unlocked": false,
  "collected_dudy": [],
  "unlocked_contacts": []
}
```

### 0-A.6 `/mission/reject`와 downshift 구분

- `reject`는 사용자가 미션을 하지 않겠다고 거절/rest 흐름으로 나갈 때 사용한다.
- "어려워요" downshift는 reject가 아니다.
- downshift fallback은 `/mission/recommend` 응답의 `fallback`을 프론트가 로컬 state로 교체한다.
- fallback completion은 `/mission/complete`에 fallback `mission_id`를 보내는 것으로 충분하다.

### 0-A.7 Contact unlock 규칙 갱신

자립:

```text
autonomy ARI >= goal.autonomy
-> normal signature mission appears
-> normal signature mission completed
-> autonomy signature dudy
-> autonomy contact unlock
```

자립 signature fallback:

```text
signature fallback completed
-> preparation recorded
-> signature_completed=false
-> contact_unlocked=false
-> normal signature can be retried later
```

연결:

```text
connection ARI >= goal.connection
-> signature pin can be surfaced by frontend
-> signature pin captured through /collection/capture
-> connection signature dudy
-> connection contact unlock
```

자립과 연결 unlock은 독립이다. 두 축을 동시에 완료해야 하는 global unlock 구조가 아니다.

### 0-A.8 Backend / Frontend responsibility

Backend:

- 추천 응답의 `mission`과 `fallback`을 프론트에 전달한다.
- 완료 요청에는 실제 완료된 `mission_id`를 엔진에 보낸다.
- 엔진 응답의 `updated_ari`, `applied_delta`, `collected_dudy`, `unlocked_contacts`, signature 상태를 저장한다.
- MVP에서 FutureProfile, MissionEvidence, downshift history, image file storage table을 새로 만들지 않는다.

Frontend:

- `mission_type`에 따라 generic mission screen을 렌더링한다.
  - `CHECK`: 완료 버튼
  - `IMAGE`: 로컬 이미지 선택/preview, 서버 업로드 없음
  - `LINK`: 외부 링크/확인 버튼
- "어려워요" 클릭 시 서버 호출 없이 `fallback` 카드로 교체한다.
- fallback 완료 시 fallback `mission_id`를 `/mission/complete`에 보낸다.
- required_count 충족 여부는 로컬 UI에서 처리한다.


> **이 문서의 역할**: 백엔드·프론트엔드가 AI 엔진과 통신할 때 지키는 **계약(contract)**.
> "이렇게 물어보면 → 이렇게 답한다"의 약속이며, AI 엔진 내부 수학은 몰라도 이 문서만으로 연동할 수 있다.
> - 추정 반쪽의 한계·연구 질문: [`research_track.ko.md`](./research_track.ko.md)

- **상태**: 초안 (draft). 팀 리뷰 후 확정.
- **갱신**: 2026-06-21 — 새 기획 통합본 v3.1(게이트형 모델)에 맞춰 대개편.
- **통신 방식**: HTTP + JSON. 모든 요청·응답 본문은 `application/json`.
- **Base URL (예시)**: `https://ai.doody.internal` (배포 환경에서 확정)
- **인증**: 백엔드 ↔ AI 엔진 내부 호출. 사용자 인증은 백엔드가 처리하고, AI 엔진엔 `user_id`만 전달한다.

---

## 0. 엔진 모델 한눈에 — "리듬은 토대, 미션은 자립·연결" (v3.1)

```
리듬(토대)  = 하루를 여닫는 2개 리듬(미션 아님). 인증데이터로 v_rhythm 추정 → 게이트 입력
자립·연결   = 능동 미션이 나오는 2축. effective_drag = recovery_drag × gate(v_rhythm)
게이트      = 리듬 토대가 데워졌을 때만 능동 미션을 내보냄 (닫히면 2리듬만 도는 날)
```

- 능동 미션 후보는 **`{autonomy, connection}` 2축뿐.** 리듬은 미션 축이 아니다.
- 게이트가 닫히면 `/mission/recommend`는 **미션 없이**(`mission: null`) 응답한다 — "토대 데우기" 날.
- 5일 이상 정체 시 **escape hatch**(게이트 바닥값)가 가장 쉬운 칸 하나를 띄운다.
- 사용자에겐 점수·단계·진행률·게이트값이 **전부 비노출**(무평가). 캐릭터·흔적으로만.

### 통신 구조 — AI 엔진은 "무상태 계산기"

```
[앱 화면]          [백엔드]                         [AI 엔진 = 이 문서]
 프론트  ──요청──▶  인증·DB 저장·중계  ──요청──▶  ARI·v_rhythm 계산 / 게이트 / 미션 선택 / 응답 생성
        ◀─응답──                     ◀─응답──   (DB 없음. 받은 데이터로 계산만)
                       │
                    ┌──▼──┐
                    │ DB  │  ← 사용자·미션·ARI·2리듬·도감 이력 저장 (백엔드 책임)
                    └─────┘
```

**핵심**: AI 엔진은 **DB를 가지지 않는다(stateless)**. 매 호출마다 백엔드가 필요한 상태(현재 ARI, 궤적, 미션 이력, **2리듬 이력**, 도감 등)를 함께 보내주고, AI 엔진은 계산 결과만 돌려준다. → [§3 백엔드 저장 데이터](#3-백엔드로-넘어가는-데이터-db-스키마-입력) 참고.

---

## 1. 공통 데이터 객체 (Schemas / DTO)

### `ARIVector` — 현재 상태 v / 목표 g / 변화량 Δ 에 공통으로 쓰는 3축 벡터
| 필드 | 타입 | 범위 | 의미 |
|---|---|---|---|
| `rhythm` | float | 0.0 ~ 1.0 | 리듬 회복도 (= v_rhythm. **2리듬으로 추정**, 미션으로 안 바뀜) |
| `autonomy` | float | 0.0 ~ 1.0 | 자립 준비도 (미션으로 갱신) |
| `connection` | float | 0.0 ~ 1.0 | 연결 회복도 (미션으로 갱신) |

```json
{ "rhythm": 0.3, "autonomy": 0.2, "connection": 0.4 }
```
> `rhythm` 축은 ARI 벡터엔 그대로 있지만 **미션이 움직이는 축이 아니다.** 게이트 입력으로만 쓰이고, 값은 2리듬 인증데이터에서 추정한다(§2.4 diagnostics).

### `Mission` — 추천되는 미션 한 건
정적(카탈로그) + 동적(LLM 생성). **미션 축은 `autonomy`·`connection`만.**

| 필드 | 타입 | 정적/동적 | 의미 |
|---|---|---|---|
| `id` | string | 정적 | 미션 고유 id (카탈로그 키) |
| `axis` | enum | 정적 | 움직이는 축: `autonomy` \| `connection` |
| `waypoint` | string | 정적 | 경로 단계. 자립·연결 공통 `마주`/`관찰`/`선택`/`접점` |
| `difficulty` | int | 정적 | 난이도 `1~5` |
| `delta` | ARIVector | 정적 | 완료 시 적용될 기본 변화량 Δ (rhythm은 0) |
| `title` | string | 정적 | 미션 문구 |
| `how_to` | string[] | 정적 | 하는 방법 단계 |
| `reason` | string | **동적** | "왜 지금 너에게" — recommend 시 **LLM이 1회 생성**(다리 놓기 포함) |

```json
{
  "id": "m_balance_glance",
  "axis": "autonomy",
  "waypoint": "관찰",
  "difficulty": 2,
  "delta": { "rhythm": 0.0, "autonomy": 0.04, "connection": 0.0 },
  "title": "통장 잔액 한 번 보고 닫기",
  "how_to": [ "오늘 통장 앱을 한 번 열어요", "잔액을 딱 한 번만 보고 닫아요", "분석도 평가도 하지 않아요" ],
  "reason": "돈을 마주하는 첫 걸음을 가장 가볍게 시작해요"
}
```
> **"구경만/더 작게"는 별도 플래그가 아니라 *더 낮은 waypoint 미션*이다.** 연결의 "집에서 구경만"·자립의 "그냥 닫기"는 `관찰` waypoint 미션을 완료한 것으로 기록한다. (출구는 **완료 / 거절** 2개. 자립·연결 동일)
>
> **B12c (2026-07-11) 추가 필드**: `completable`(bool, 기본 `true`). `mission_state="connection_priority"`일 때만 `axis="connection"`·`completable=false`인 Mission이 오고, 이때 `waypoint`·`difficulty`·`delta`는 `null`(카탈로그 미션이 아니라 지도/포획으로 안내하는 문구일 뿐 — 완료·ARI 변화는 `/collection/capture`가 담당). `completable=false`인 Mission은 `/mission/complete`·`/mission/reject` 대상이 아니다.

### `Dudy` — 도감 캐릭터 (수집·해금 산출물)
| 필드 | 타입 | 의미 |
|---|---|---|
| `id` | string | 두디 id (`app/data/dudy_templates.json` 키) |
| `tier` | enum | `common` \| `rare` \| `signature` |
| `axis` | enum \| null | 어느 축의 두디인지 (해당 시) |
| `earned_reason` | string | "어떻게 만났나" (의미 있는 순간 문구, 진행률 아님) |

```json
{ "id": "d_happy", "tier": "common", "axis": null, "earned_reason": "오늘 처음 저녁 한 줄을 남겼어요" }
```
> **`signature` 두디 = 그 축의 최종 미션(`접점` waypoint) 완료 = 하나금융 해금 트리거.** 흔한/레어는 리텐션 도감(별도). 해금 열쇠는 `signature`만. (§2.8)

### `Contact` — 하나금융 접점 (해금 대상)
| 필드 | 타입 | 의미 |
|---|---|---|
| `id` | string | 접점 id (`app/data/contact_templates.json` 키) |
| `title` | string | 사용자에게 보이는 문구 |
| `axis` | enum | 어느 축의 접점인지 (`autonomy`/`connection`) |

```json
{ "id": "hana_youth_edu", "title": "하나 청년 금융교육 바로가기", "axis": "autonomy" }
```

### `ARISnapshot` — 궤적(velocity 계산용)의 원소
```json
{ "ari": { "rhythm": 0.34, "autonomy": 0.21, "connection": 0.36 }, "timestamp": "2026-06-01T09:00:00Z" }
```

### `RhythmHistory` — 2리듬 이력 (v_rhythm·게이트 계산 입력)
무상태 엔진이 v_rhythm을 계산하려면 백엔드가 2리듬 로그를 실어 보낸다.
```json
{
  "morning": [ { "timestamp": "2026-06-04T11:00:00Z", "did_check_in": true } ],
  "evening": [ { "text": "그냥 누워있었음", "timestamp": "2026-06-04T23:10:00Z" } ]
}
```
> v_rhythm은 **"리듬이 꾸준히 떴나(존재)"** 로 추정한다(존재-EMA). **리듬이 뜬 *시각·규칙성*은 v_rhythm에 안 쓴다 — 존재 여부만.** 계수는 `app/data/gate_config.json`.

### `EnergyLevel`
정수 `1~5`. **아침 리듬에서 받는 "오늘 기분"** 이 곧 오늘 step size η를 정한다. 축이 아니라 **조건**. (v_rhythm엔 반영 안 함 — η 전용)

### enum 정리
| 이름 | 가능한 값 |
|---|---|
| ARI 축 | `rhythm`, `autonomy`, `connection` |
| **미션 축** `axis` | `autonomy`, `connection` (리듬 제외) |
| 공백 선택 `gap_axis` | `rhythm`, `autonomy`, `connection`, `composite`, `unknown` |
| 기간 `period` | `today`, `1w`, `1m`, `3m` |
| 미션 상태 `status` | `recommended`, `completed`, `rejected` |
| **미션 응답 상태** `mission_state` | `active`, `gated`, `escape_hatch`, `connection_priority`(B12) |
| 재설계 행동 `action` | `downshift`, `same_waypoint`, `different_axis`, `rest` |
| 채팅 액션 힌트 `suggested_action` | `none`, `offer_downshift`, `offer_rest` |
| waypoint | `마주`, `관찰`, `선택`, `접점` (자립·연결 공통) |
| 두디 등급 `tier` | `common`, `rare`, `signature` |

---

## 2. 엔드포인트 명세

| Method & Path | 역할 | 비고 |
|---|---|---|
| `GET /health` | 서버 상태 확인 | — |
| `POST /onboarding/intro` | 최초 진입 → **방향 약속**(미션 안 줌) | §2.2 |
| `POST /onboarding/recommend-period` | 목표 → 기간 도출 (MVP: 추천=확정, goal_choice 룩업) | §2.10 |
| `POST /onboarding/complete` | 후행 온보딩 → v₀·g·기간 (미션 안 줌) | §2.3 |
| `POST /rhythm/morning` | 아침 리듬 (출석 + 기분) | §2.11 |
| `POST /rhythm/evening` | 저녁 휘갈기기 리듬 (텍스트 + 자연어 신호) | §2.12 |
| `POST /mission/recommend` | 현재 상태 → 게이트 통과 시 미션 (or 미션 없음) | §2.4 |
| `POST /mission/complete` | 미션 완료 → ARI 갱신 + 해금/도감 | §2.5 |
| `POST /mission/reject` | 거절 → 더 작은 후보 (쉬어가기 포함) | §2.6 |
| `POST /collection/capture` | 밖에서 두디 포획 (GPS, 채널 B=연결 미션) → 연결 점수↑·해금 | §2.7 |
| `POST /chat/message` | 두디 응답 + 자연어 보조 신호 (2역할) | §2.8 |
| `POST /report/summary` | 회복 패스포트 자연어 리포트 | §2.9 |

> **하나금융 접점 해금**은 별도 엔드포인트가 아니라 mission/complete 응답의 `unlocked_contacts`로 실린다. (§2.13)

---

### 2.1 `GET /health`
```json
{ "status": "ok", "version": "0.7.0" }
```

---

### 2.2 `POST /onboarding/intro` — 최초 진입 (방향 약속, 미션 없음)
"가장 막힌 공백"과 오늘 에너지를 받는다. **첫날엔 미션도 경로도 주지 않는다** — 목표를 받았다는 응답 + "그쪽으로 같이 갈게" 방향 약속 + "내일 기다릴게" 재방문 후크만. (경로를 펼치면 완벽주의 회피 발동 → §4 회피 차단)

**Request**
```json
{ "user_id": "u_a1b2c3", "gap_axis": "rhythm", "energy": 2 }
```
| 필드 | 의미 |
|---|---|
| `gap_axis` | "요즘 어디가 제일 막혀요?" (리듬/자립/연결/복합/모름) — 저장 + 후행 온보딩 시작축 동점판정 |
| `energy` | "오늘 움직일 힘은?" 1~5 |

> **자연어 입력(free_text) 없음.** 온보딩 자연어 화면은 제거됐다 — 자연어 신호 채널은 **저녁 리듬 한 곳**으로 단일화(§2.12). Day-0 방향 약속 개인화는 `goal_choice`+`gap_axis` 구조화 입력으로 조립한다.

**Response**
```json
{
  "direction_promise": "돈 얘기 천천히 가고 싶다는 거, 다 들었어. 그쪽으로 같이 갈 거야. 오늘은 일단 쉬고, 내일 아침에 내가 첫 한 걸음 들고 기다릴게.",
  "message": "만나서 반가워. 천천히 가자."
}
```

---

### 2.3 `POST /onboarding/complete` — 후행 온보딩 (ARI·목표·기간)
목표·진단 답·기간·**마이데이터(선택)** 를 받아 **초기 상태 v₀**, **목표 g**, **기간**, **방향 약속**을 만든다. **여기서도 미션은 주지 않는다** — 첫 능동 미션은 게이트가 열린 뒤(보통 토대 데우기 5일 후)에 나온다.

**Request**
```json
{
  "user_id": "u_a1b2c3",
  "goal_choice": "face_money",
  "diagnosis": { "rhythm": 2, "autonomy": 3, "connection": 1 },
  "gap_axis": "autonomy",
  "mydata": { "linked": true }
}
```
| 필드 | 의미 |
|---|---|
| `goal_choice` | 목표 선택지 id → 목표 벡터 `g` |
| `diagnosis` | **축별 4지선다 답** `{rhythm, autonomy, connection}`, 각 정수 `1~4`(1=회복 높음 … 4=낮음). 엔진이 `onboarding_templates.json`의 `choice→value` 매핑으로 v₀ 계산. **MVP=축당 1문항 고정형.** 향후 복합·다문항은 JSONB 배열로 마이그레이션(seam) |
| `period` | **optional (MVP 미사용 입력).** MVP에선 사용자가 고르지 않고 **엔진이 `goal_choice`로 결정론적 도출**(§2.10). 보내도 무시되고 엔진이 `goal_templates.json` 룩업으로 덮어쓴다. v₀·g엔 영향 없음. **화면엔 진행률로 안 뜸**(무평가) |
| `gap_axis` | 최초 진입에서 고른 공백. 저장 + 첫 미션 시작축 동점판정 |
| `mydata` | optional. 마이데이터 연동 여부 → **자립 gap 초기화**. 거절 시 돈 질문 2개로 대체. **MVP=목업, 잔고 비노출.** 변환식 미정(seam) |

**Response**
```json
{
  "initial_ari": { "rhythm": 0.2, "autonomy": 0.35, "connection": 0.9 },
  "goal": { "rhythm": 0.5, "autonomy": 0.7, "connection": 0.4 },
  "period": "1w",
  "start_axis": "autonomy",
  "plan_summary": "목표는 '돈과 소비를 편안하게 마주하기'예요. 지금은 자립이 가장 비어 있고, 리듬이 받쳐주면 더 수월해요. 아침에 일어나 인사하는 것부터 같이 잡아봐요.",
  "diagnostics": {
    "axis_scores": { "rhythm": 0.2, "autonomy": 0.35, "connection": 0.9 },
    "start_axis": "autonomy",
    "start_axis_reason": "gap_axis_tiebreak"
  }
}
```
> **`initial_ari.rhythm`은 워밍업 시작값(예 0.2)** — 2리듬 데이터가 없어 아직 *측정*이 아니다. 이후 아침·저녁 리듬이 쌓이며 존재-EMA로 올라간다(§2.4 diagnostics).
> **`first_mission` 없음.** v0.6과 달리 온보딩은 미션을 만들지 않는다. 첫 행동은 *아침·저녁 리듬 찍기*이고, 능동 미션은 게이트가 열린 뒤 `/mission/recommend`로.

---

### 2.11 `POST /rhythm/morning` — 아침 리듬
"일어나 인사" 접속을 받는다. **출석(존재) + 오늘 기분(1~5)** 을 받아 보상을 주고, v_rhythm 신호원이 된다.

**Request**
```json
{ "user_id": "u_a1b2c3", "timestamp": "2026-06-04T11:00:00Z", "energy": 3 }
```

**Response**
```json
{
  "reward": { "hana_money": 20 },
  "greeting": "일어났네, 좋아. 오늘도 천천히 가자.",
  "collected_dudy": []
}
```
> **보상**: 아침 리듬 **출석만으로 균일 지급**(`hana_money`). **기상 *시각*은 보지 않고, 늦어도 벌 없음.** 하루 1회 상한(어뷰징 방어). (MVP: 약속시간·비대칭 보너스 없음)
> `energy`는 백엔드가 저장해 두었다가 그날 `/mission/recommend`·`/mission/complete`의 `energy`(η) 입력으로 공급한다. **기분은 η 전용 — v_rhythm엔 안 들어간다.**
> `collected_dudy`: 이 리듬으로 "처음 아침 인사" 같은 의미 있는 순간이 달성되면 흔한 두디가 실릴 수 있다.

---

### 2.12 `POST /rhythm/evening` — 저녁 휘갈기기 리듬
"오늘 한 줄"을 받는다. **텍스트 존재 자체로 완료·보상**, 그리고 그 텍스트가 **유일한 자연어 신호 채널**이다.

**Request**
```json
{ "user_id": "u_a1b2c3", "text": "그냥 누워있었음" }
```

**Response**
```json
{
  "reward": { "hana_money": 20 },
  "signals": null,
  "reply": "오늘 하루도 고생했어. 한 줄 남겨줘서 고마워.",
  "collected_dudy": [ { "id": "d_first_night", "tier": "common", "axis": null, "earned_reason": "처음으로 저녁 한 줄을 남겼어요" } ]
}
```
> **텍스트 존재 = 완료.** 글자수 하한은 안 두거나 아주 낮게(타깃 이탈 방지). 어뷰징은 *하루 1회 보상 상한*으로 막고, 반복 동일 입력은 내부 신호 가중치만 낮춘다(화면 무표시).
> **`signals`** 는 발화에서 뽑은 축별 신호(0~1) — `extract_signal(text)`. **MVP에선 미정(stub) → `null` 허용.** 채워지면 v_rhythm 정서 보정 + 자립/연결 보조 신호로 fusion. (온보딩 free_text를 없애고 자연어 신호를 여기로 단일화)

---

### 2.4 `POST /mission/recommend` — 게이트 통과 시 미션
현재 상태·목표·궤적·에너지·**2리듬 이력**·미션 이력을 받아 게이트를 계산하고, 열렸으면 **오늘의 미션 한 건**을, 닫혔으면 **미션 없음**을 돌려준다.

**Request**
```json
{
  "user_id": "u_a1b2c3",
  "current_ari": { "rhythm": 0.42, "autonomy": 0.22, "connection": 0.40 },
  "goal": { "rhythm": 0.6, "autonomy": 0.7, "connection": 0.5 },
  "recent_trajectory": [
    { "ari": { "rhythm": 0.34, "autonomy": 0.21, "connection": 0.36 }, "timestamp": "2026-06-01T09:00:00Z" },
    { "ari": { "rhythm": 0.42, "autonomy": 0.22, "connection": 0.40 }, "timestamp": "2026-06-04T09:00:00Z" }
  ],
  "energy": 3,
  "rhythm_history": {
    "morning": [ { "timestamp": "2026-06-04T11:00:00Z", "did_check_in": true } ],
    "evening": [ { "text": "그냥 누워있었음", "timestamp": "2026-06-04T23:10:00Z" } ]
  },
  "history": [ { "mission_id": "m_balance_glance", "status": "completed" } ]
}
```
| 필드 | 쓰임 |
|---|---|
| `current_ari` | 현재 위치 vₜ |
| `goal` | 목표 g (gap 계산) |
| `recent_trajectory` | velocity = vₜ − vₜ₋₁ (없으면 0) |
| `energy` | 오늘 step size η (아침 리듬에서 옴) |
| `rhythm_history` | **v_rhythm 계산 입력**(존재-EMA) → 게이트 |
| `history` | 최근 미션 결과. 축·waypoint·`days_without_mission`·해금 판정의 원천 |

**Response (게이트 열림 — `active`)**
```json
{
  "mission": {
    "id": "m_spend_log", "axis": "autonomy", "waypoint": "관찰", "difficulty": 3,
    "delta": { "rhythm": 0.0, "autonomy": 0.04, "connection": 0.0 },
    "title": "오늘 소비 하나 기록하기",
    "how_to": [ "오늘 쓴 돈이 있으면 하나만 떠올려요", "금액과 항목을 한 줄로 적어요", "없으면 '0원 소비'로 남겨요" ],
    "reason": "자립 축이 목표 대비 가장 막혀 있어, 오늘은 여기를 조금 더 채워요"
  },
  "mission_state": "active",
  "rest_message": null,
  "unlocked_contacts": [],
  "v_rhythm": 0.62,
  "diagnostics": {
    "v_rhythm": 0.62,
    "gate": 0.95,
    "gap": { "rhythm": 0.18, "autonomy": 0.48, "connection": 0.10 },
    "velocity": { "rhythm": 0.08, "autonomy": 0.01, "connection": 0.04 },
    "recovery_drag": { "autonomy": 0.47, "connection": 0.06 },
    "effective_drag": { "autonomy": 0.447, "connection": 0.057 },
    "bottleneck_axis": "autonomy",
    "days_without_mission": 0,
    "eta": 0.6
  }
}
```

**Response (게이트 닫힘 — `gated`, 토대 데우기 날)**
```json
{
  "mission": null,
  "mission_state": "gated",
  "rest_message": "오늘은 푹 쉬어. 저녁에 한 줄만 남겨줘.",
  "unlocked_contacts": [],
  "v_rhythm": 0.24,
  "diagnostics": { "v_rhythm": 0.24, "gate": 0.0, "days_without_mission": 2,
    "recovery_drag": { "autonomy": 0.47, "connection": 0.06 },
    "effective_drag": { "autonomy": 0.0, "connection": 0.0 }, "bottleneck_axis": null, "eta": 0.5 }
}
```

**Response (정체 5일↑)**: **B12b (2026-07-11)로 갱신** — `bottleneck_axis`가 connection이면 `mission_state="connection_priority"`(§2.4 B12/B12c 규칙 참고 — `mission`은 `completable=false`인 연결 Mission)로 대신 응답한다. autonomy가 bottleneck이면 예전 그대로 `mission_state="escape_hatch"`, `mission`에 **정체 축(자립)의 최저 난이도 칸**이 채워진다. (gate_floor=0.05가 받친 결과 — "해금"이 아니라 연속 보정)

> **게이트 계산** (내부; 사용자 비노출):
> ```
> effective_drag[a] = recovery_drag[a] × gate(v_rhythm)         a ∈ {autonomy, connection}
> gate(r) = max( gate_floor(days_without_mission), clamp((r − r_floor)/(r_open − r_floor), 0, 1) )
> r_floor=0.3, r_open=0.6, gate_floor= 0 (d<5) / 0.05 (d≥5)    ← app/data/gate_config.json, 미검증·보정대상
> bottleneck = argmax(effective_drag);  모두 ≈0 이고 d<5 → mission=null (gated)
> ```
> **`v_rhythm`(표면 필드)**: 이번 호출에서 `rhythm_history`로 재계산한 **현재 리듬값.** diagnostics에도 같은 값이 있으나, 이 표면 필드는 **백엔드가 떳떳이 쓰는 정식 출력**(리포트 `ari_now.rhythm` 산출·내부 상태 갱신용). **단 사용자 화면엔 숫자로 띄우지 않는다** — 리포트에선 LLM이 문장으로만 풀고, 진행률/점수로 노출 금지(비노출 불변식). **v_rhythm은 `rhythm_logs`의 파생값이라 매 호출 재계산되며, `ari_snapshots.rhythm`에 저장된 값이 아니라 이 값이 권위 출처다.** (autonomy/connection은 ari_snapshots 증분 누적이 권위, rhythm만 재계산 — 둘의 성질이 다름)
> **`v_rhythm` 추정식 = 존재-EMA**: `a_t=(아침 들어옴 + 저녁 썼나)/2`, `v_t=v_{t-1}+α(a_t−v_{t-1})`, 비대칭 EMA(오를 때 α_up≫내릴 때 α_down). 5일·0.3·0.6은 α(≈0.13) 하나의 결과 — 하드코딩 임계가 아님. (리듬이 뜬 *시각·규칙성*은 안 씀, 존재만)
> **`mission.reason`** 은 LLM이 1회 생성(다리 놓기 포함: 오늘 축이 목표 축과 다르면 이유를 한 줄로 이음). 백엔드는 미션 객체를 `mission_logs`에 스냅샷 저장.
> **`diagnostics`** 는 설명가능성·디버깅·research용. recovery_drag·effective_drag는 자립·연결만(리듬 제외). 프로덕션서 무시 가능하나 **사용자 화면엔 절대 노출 금지.**

---

### 2.5 `POST /mission/complete`
미션 완료를 받아 **ARI를 갱신**하고, 해금·도감을 판정한다. `vₜ₊₁ = vₜ + η·Δ`.

**Request**
```json
{ "user_id": "u_a1b2c3", "mission_id": "m_spend_log", "current_ari": { "rhythm": 0.42, "autonomy": 0.22, "connection": 0.40 }, "energy": 3 }
```

**Response**
```json
{
  "updated_ari": { "rhythm": 0.42, "autonomy": 0.244, "connection": 0.40 },
  "applied_delta": { "rhythm": 0.0, "autonomy": 0.024, "connection": 0.0 },
  "eta": 0.6,
  "collected_dudy": [],
  "unlocked_contacts": [],
  "message": "오늘 소비를 기록했어요. 돈을 마주하는 힘이 조금씩 쌓이고 있어요."
}
```
> 계산: Δautonomy=0.04, η=0.6 → applied=0.024 → 0.22+0.024=0.244. (0~1 clamp)
> **리듬은 미션으로 안 바뀐다** — `updated_ari.rhythm`은 그대로. v_rhythm은 2리듬으로만 갱신.
> **`collected_dudy`**: 이 완료가 의미 있는 순간(첫 미션 등)이면 두디가 실린다. **그 축의 `접점` waypoint를 완료했다면 `signature` 두디**가 실리고, 동시에 `unlocked_contacts`가 채워진다(§2.13).
> 백엔드는 `updated_ari`를 새 `ari_snapshot`으로 저장 → 다음 recommend의 궤적.
> **"구경만/더 작게"** 로 들어온 완료는 더 낮은 waypoint(`관찰`) 미션의 `mission_id`로 온다 — 별도 처리 없이 그 미션의 Δ가 적용되고, `접점`을 advance하지 않아 정체 신호가 유지된다(거절 아님, 보상 있음).

---

### 2.6 `POST /mission/reject`
거절을 **"경로가 너무 앞섰다"는 신호**로 보고 **더 작은 후보 목록**을 돌려준다. ARI 하락·벌점 없음. (홈/미션상세 어디서 눌러도 같은 이벤트. 상태에 안 먹임 — 정밀 회피반영은 research_track.)

**Request**
```json
{ "user_id": "u_a1b2c3", "mission_id": "m_consult_apply_check", "reason_text": "상담 신청은 아직 너무 부담돼요" }
```

**Response**
```json
{
  "action": "downshift",
  "message": "괜찮아요. 지금 가능한 만큼만 해도 충분해요.",
  "rest_option": true,
  "candidates": [
    { "id": "m_center_page_open", "axis": "connection", "waypoint": "마주", "difficulty": 1,
      "delta": { "rhythm": 0.0, "autonomy": 0.0, "connection": 0.03 },
      "title": "청년센터 페이지 한 번 열어보기",
      "how_to": [ "청년센터 홈페이지를 한 번 열어요", "둘러보기만 하고 닫아도 괜찮아요" ],
      "reason": "방향은 그대로, 더 작은 한 걸음으로 바꿨어요" }
  ],
  "diagnostics": { "previous_waypoint": "실행", "new_waypoint": "마주", "signal": "waypoint_too_far" }
}
```
> `action` = `downshift`/`same_waypoint`/`different_axis`/`rest`. `rest_option=true`면 "오늘은 쉬어가기"도 띄운다.
> **"집에서 구경만"** 은 이 후보 목록의 `관찰`/`마주` 미션으로 제공된다(인라인 3번째 버튼 아님). 후보를 골라 완료하면 그 낮은 미션의 Δ 적용.

---

### 2.7 `POST /collection/capture` — 밖에서 두디 포획 (GPS, 채널 B = 연결 미션)
연결온 지도에서 핀에 도달해 포획한다. **자립 미션(채널 A, waypoint 길)과 분리된 통로** — 도감을 채우고, **연결 축 점수를 올리며**, 시그니처면 하나금융으로 잇는다.

> **연결 = 점수 채우기 모델 (자립과 다름).** 자립은 마주→관찰→선택→접점 *waypoint 길*이지만, **연결은 밖에서 랜덤 두디(흔한/레어)를 잡을 때마다 연결 점수가 조금씩 누적**된다. 연결 점수가 **목표치 `goal.connection`에 닿으면** 시그니처 두디가 등장(= 연결의 *마지막 미션*), 그걸 포획하면 하나금융 연결 해금. 즉 포획은 **연결의 미션 완료 = ARI를 움직이는 채널**이다(도감만 채우는 게 아님). → `mission_logs`/waypoint 안 씀.

**Request**
```json
{
  "user_id": "u_a1b2c3",
  "pin_id": "pin_conv_seed01",
  "location": { "lat": 37.50, "lng": 127.03 },
  "current_ari": { "rhythm": 0.42, "autonomy": 0.30, "connection": 0.55 },
  "goal": { "rhythm": 0.6, "autonomy": 0.7, "connection": 0.6 },
  "energy": 3
}
```
| 필드 | 쓰임 |
|---|---|
| `pin_id` | 포획 핀(카탈로그 키) → 두디·tier·Δ 룩업 |
| `current_ari` | 현재 vₜ — 연결 Δ 적용(`vₜ₊₁=vₜ+η·Δ`)·시그니처 등장 판정 입력 |
| `goal` | 목표 g — `connection`이 goal에 닿았는지(시그니처 eligibility) 판정 |
| `energy` | η (아침 리듬에서). 없으면 기본 η |

**Response**
```json
{
  "dudy": { "id": "d_happy", "tier": "common", "axis": "connection", "earned_reason": "집 앞 편의점까지 나가 두디를 만났어요" },
  "reward": { "hana_money": 30 },
  "updated_ari": { "rhythm": 0.42, "autonomy": 0.30, "connection": 0.58 },
  "applied_delta": { "rhythm": 0.0, "autonomy": 0.0, "connection": 0.03 },
  "collected_dudy": [ { "id": "d_happy", "tier": "common", "axis": "connection", "earned_reason": "집 앞 편의점까지 나가 두디를 만났어요" } ],
  "unlocked_contacts": []
}
```
> **포획은 연결 ARI를 움직인다**: 핀→두디 카탈로그에 각 두디의 `delta_connection`(흔한=작게)이 있고, `vₜ₊₁ = vₜ + η·Δ`로 연결 점수가 오른다. 백엔드는 `updated_ari`를 **새 `ari_snapshot`(`source_type='capture'`, `source_id=capture_id`)** 으로 적재 → 다음 recommend의 궤적·velocity에 반영. (자립의 `/mission/complete`와 같은 적재 방식)
> **어떤 두디가 나올지는 핀 카탈로그 고정값**(`app/data/pin_templates.json`: `{pin_id, location, dudy_id, tier, delta_connection}`) — 사용자도 랜덤도 결정 안 함(확정 획득). tier는 장소 종류로(편의점·공원=흔한, 도서관·청년센터 건물=레어, 기관=시그니처).
> **시그니처 등장·해금**: `current_ari.connection`이 `goal.connection`에 닿은 뒤 포획한 핀이 `tier=signature`(기관)면 시그니처 두디 + `unlocked_contacts`가 채워진다. **시그니처 핀 *surfacing*(언제 띄울지)** 은 MVP에선 프론트 정적(점수 도달 시 노출) — 엔진은 포획된 핀의 tier로 해금만 판정(post-MVP seam).
> **MVP**: 흔한 핀은 시드지역 1~2곳 실제 시연, GPS 느슨, 기관·시그니처는 하드코딩 흐름만.

---

### 2.8 `POST /chat/message`
두디 대화 응답을 생성한다. **판단이 아니라 설명·완충.** 무상태 단일 턴. MVP 역할 **2가지**(데일리 체크인은 *아침 리듬*으로 이동해 빠짐):
- **A. 미션 완충** — 부담 표현 감지 → "미션 더 작게?" (`suggested_action`)
- **B. 짧은 공감/사담** — 응원 한마디

**Request**
```json
{
  "user_id": "u_a1b2c3",
  "message": "상담은 받고 싶은데 돈 문제부터 너무 무서워요",
  "context": { "current_ari": { "rhythm": 0.42, "autonomy": 0.22, "connection": 0.40 }, "current_mission_id": "m_center_page_open", "energy": 2 }
}
```

**Response**
```json
{
  "reply": "괜찮아요. 상담을 떠올린 것만으로도 한 걸음이에요. 돈이 무겁게 느껴지면, 오늘은 가볍게 보는 것부터 같이 해봐요.",
  "signals": { "rhythm": 0.0, "autonomy": 0.7, "connection": 0.3 },
  "suggested_action": "offer_downshift"
}
```
> **`suggested_action`**: `none`/`offer_downshift`/`offer_rest`. 채팅은 **제안만**, 실제 미션 변경은 미션 엔드포인트가.
> **`signals`**: 발화 축별 신호(0~1) — 저녁 리듬과 같은 `extract_signal` seam. **MVP 미정 → `null` 허용.** `reply`는 Claude API 1회 호출(짧은 공감 + 액션 판단), 세션·메모리 없음.

---

### 2.9 `POST /report/summary` — 회복 패스포트 자연어 리포트
서술형 요약을 생성한다. **집계 수치는 백엔드가 `stats`로 주입**, LLM은 **서술만**. (골격은 v0.6과 동일)

> 🚨 **LLM은 숫자를 만들지 않는다.** 수치는 반드시 `stats`로 받아 문장으로만 푼다.

**Request**
```json
{
  "user_id": "u_a1b2c3", "period": "1m",
  "stats": {
    "total_records": 28, "active_days": 18, "points": 1400,
    "axis_counts": { "rhythm": 4, "autonomy": 3, "connection": 2 },
    "ari_start": { "rhythm": 0.2, "autonomy": 0.18, "connection": 0.4 },
    "ari_now": { "rhythm": 0.55, "autonomy": 0.42, "connection": 0.5 },
    "goal": { "rhythm": 0.5, "autonomy": 0.7, "connection": 0.4 },
    "collected_dudy": [ { "id": "d_happy", "tier": "common", "axis": "connection", "earned_reason": "집 앞까지 나갔어요" } ],
    "unlocked_contacts": [ { "id": "hana_youth_edu", "title": "하나 청년 금융교육 시작", "axis": "autonomy" } ],
    "recent_missions": [ { "title": "0원 소비 기록 남기기", "axis": "autonomy", "date": "2026-06-01" } ]
  }
}
```
> **`axis_counts.rhythm`** 은 이제 미션이 아니라 **2리듬 기록(기상·휘갈기기) 집계**다. **`collected_dudy`** 추가(도감 그리드).
> **`goal`(신규, optional) — B11.** 있으면 `mission/recommend`와 같은 `gap→velocity→recovery_drag` 수식을 report period 스케일로 재계산해 축마다 **gap 버킷**(close/mid/far)·**velocity 버킷**(stalled/slow/fast)을 구하고, **병목축**·**순항축**(가장 여유 있는 축)을 뽑는다. `highlights`엔 병목축 한 줄("다음엔 OO 쪽도 살짝 챙겨보면 좋겠어")을 더하고, LLM `summary`는 세 축을 각각 개별적으로(뭉뚱그리지 않고) 짚으면서 병목축·순항축을 반드시 언급하는 더 긴 개인화 서사(140~220자)로 나간다. **숫자(gap 자체)는 절대 노출 안 함**(무평가), 버킷 카테고리·축 이름만 나간다. `goal`을 안 보내면(구버전 백엔드) 조용히 건너뛴다 — 하위호환, 에러 없음.

**Response**
```json
{
  "summary": "이번 달, 당신은 하루를 여닫는 리듬을 가장 꾸준히 채웠어요. 자립 기록도 처음으로 쌓이기 시작했고, 하나 청년 금융교육까지 한 걸음 닿았네요. 아무것도 안 한 것 같아도, 18일이나 두디와 함께였어요.",
  "highlights": [ "아침·저녁 리듬을 가장 꾸준히 했어요", "자립 기록이 처음으로 쌓였어요", "하나 청년 금융교육을 시작했어요" ],
  "generated_at": "2026-06-21T09:00:00Z"
}
```
> **캐시 필수**(주/월 1회 생성 → `report_summaries` 저장 → 열 때 읽기). **톤**: 무평가·무자책, "쌓였다" 프레이밍. **화면 주의**: 진행률 %·미수행(빈 요일) 노출 금지, 도감은 "초대장" 톤(수집 카운트 금지) — §8-3·§10 비노출 불변식.

---

### 2.10 `POST /onboarding/recommend-period` — 기간(호흡) 추천
목표에 맞는 미션 호흡(기간)을 골라 준다. **MVP에선 추천 = 확정** — 사용자가 칩으로 바꾸지 않고, 화면엔 "두디가 이 호흡을 골라줬어요"로 표시(선택 부담 제거). period의 **단일 출처 = `goal_choice`**(아래).

**Request**
```json
{ "user_id": "u_a1b2c3", "goal_choice": "face_money", "gap_axis": "autonomy", "energy": 2 }
```
**Response**
```json
{ "recommended_period": "1w", "options": ["today", "1w", "1m", "3m"], "message": "이 호흡을 추천해요. 작은 단계로 나눠볼게요." }
```
> **MVP=목표 기반 하드코딩**(`goal_templates.json`의 `recommended_period` 룩업), `gap_axis`·`energy`는 받아두되 미반영(seam). `message`는 정적 템플릿(LLM 아님). `options`는 후속 버전(칩 오버라이드)을 위한 자리이며 **MVP 화면엔 안 띄운다**(추천=확정).
> **period의 단일 출처**: `goal_choice` → `goal_templates.json` 룩업. **사용자 입력 아님.** `/onboarding/complete`가 `period`를 받아도 엔진이 이 룩업값으로 덮어쓴다(출처 둘 방지). DB `onboarding_responses.period`는 *도출값 스냅샷*. period는 엔진 *수학*엔 안 들어감(미션 페이싱 seam, MVP no-op). 이후 "N일차/진행률"은 화면에 안 뜬다(§6-1 무평가).

---

### 2.13 하나금융 접점 해금 (`unlocked_contacts`)
별도 엔드포인트가 아니라 `/mission/complete`·`/collection/capture` **응답에 실리는** `Contact[]`.

**해금 규칙 (MVP, 축별 독립)**: 그 축의 **`signature` 두디를 획득**하면 **그 축의** 하나금융 접점이 열린다. 자립·연결은 **독립**(동시 충족 아님) → 자립 해금창 / 연결 해금창 따로. **단 축마다 시그니처에 닿는 길이 다르다:**

```
자립(waypoint 길):  마주 → 관찰 → 선택 → [접점 미션 완료]  → 자립 signature 두디 + 자립 해금   (/mission/complete)
연결(점수 채우기):   포획·포획·포획… → connection 점수 ≥ goal → [시그니처 두디 포획] → 연결 signature + 연결 해금  (/collection/capture)
```
- **자립 현재 waypoint는 저장값이 아니라 파생값** — 엔진이 `mission_logs` history로 카탈로그 조회해 계산. **연결은 waypoint를 안 쓰고** `connection` 점수가 `goal.connection`에 닿았는지로 시그니처 등장을 판정.
- 해금이 *처음* 일어난 호출에서만 채워진다(이미 열린 건 재전송 안 함).
- 흔한/레어 두디는 **연결 점수를 올리는 과정**이자 리텐션 도감 — 다만 **해금 열쇠는 `signature` 두디 하나뿐.**
- **동의 게이트 UX**: 하나 접점 진입 직전, *긍정 활동만* 공유 동의를 받는다(§10). 거절해도 보상만 보류.

```json
{ "unlocked_contacts": [ { "id": "hana_youth_edu", "title": "하나 청년 금융교육 바로가기", "axis": "autonomy" } ] }
```

---

## 3. 백엔드로 넘어가는 데이터 (DB 스키마 입력)

| 테이블(권고) | 핵심 컬럼 | 왜 필요한가 |
|---|---|---|
| `users` | `user_id`, `created_at` | 모든 호출의 주체 |
| `onboarding_responses` | `user_id`, `gap_axis`, `goal_choice`, `recommended_period`, `rhythm_choice`/`autonomy_choice`/`connection_choice`(int 1~4), `mydata`, `timestamp` | 온보딩 원본. **free_text 컬럼 제거**. 진단=**축별 4지선다 정수**(MVP 고정형, 엔진이 value 매핑). **`recommended_period`=`goal_choice` 도출 스냅샷**(사용자 선택 아님) |
| `goals` | `user_id`, `rhythm`, `autonomy`, `connection`, `period`, `created_at` | recommend의 `goal` |
| `ari_snapshots` | `user_id`, `timestamp`, `rhythm`, `autonomy`, `connection`, `source_type`, `source_id?` | 궤적/velocity. complete의 `updated_ari` 적재. **`autonomy`·`connection`=증분 누적(권위)**, **`rhythm`=비권위 캐시**(권위 출처는 recommend의 `v_rhythm` 표면필드, rhythm_logs 재계산). `source_type`(onboarding/mission_complete/**capture**)으로 적재 출처 구분. capture=연결 포획이 connection 점수 갱신. "미션이 rhythm 비갱신"도 source_type으로 감사 |
| `rhythm_logs` *(신규)* | `user_id`, `type`(morning/evening), `timestamp`, `did_check_in`, `text?`, `reward` | **2리듬 이력 → recommend의 `rhythm_history`(v_rhythm 입력)** + 보상·자연어 신호 원천 |
| `mission_logs` *(=autonomy_logs)* | `user_id`, `mission_id`, `axis`, `waypoint`, `difficulty`, `delta_autonomy`, `reason`, `status`, `reject_reason_text?`, `timestamp` | **자립 미션**(waypoint 길) 결과. `history`·자립 해금·`days_without_mission` 원천. **연결은 여기 안 옴 → `collection_captures`** |
| `collection_captures` *(신규, 연결 채널)* | `user_id`, `pin_id`, `lat?`, `lng?`, `dudy_id`, `reward`, `captured_at` | **연결 포획 = 연결 미션 완료.** 응답 `updated_ari`(connection +Δ)는 `ari_snapshots`(source=capture)로, signature면 `contact_unlocks`로 |
| `contact_unlocks` *(신규)* | `user_id`, `contact_id`, `axis`, `source`(mission/capture), `source_id?`, `unlocked_at` | 하나금융 해금 기록. **`UNIQUE(user_id, contact_id)`** 로 재해금 멱등(엔진 무상태라 중복 반환 가능) |
| `energy_logs` | `user_id`, `energy_date`, `energy`, `source_rhythm_log_id?`, `timestamp` | **아침 리듬에서 수집한 기분(η).** recommend/complete에 그날 값 공급 |
| `dudy_collection` *(신규)* | `user_id`, `dudy_id`, `tier`, `axis?`, `earned_reason`, `source`(mission/capture/rhythm), `timestamp` | 도감. signature=해금 판정, 패스포트 그리드 |
| `chat_logs` *(optional)* | `user_id`, `timestamp`, `message`, `reply`, `signals_*` | 대화 + 자연어 신호 |
| `user_axis_progress` *(optional 캐시)* | `user_id`, `axis`, `current_waypoint` | 현재 단계 캐시. 원천은 `mission_logs.waypoint` 집계 |
| `passport_summary` *(파생)* | `user_id`, 축별 완료 수, 적립 등 | `mission_logs`+`rhythm_logs`+`dudy_collection` 집계. `/report/summary` `stats` 입력원 |
| `report_summaries` *(optional 캐시)* | `user_id`, `period`, `summary`, `highlights`(json), `generated_at` | 리포트 캐시(주/월 1회) |

> **`missions`(미션 정의) 테이블 불필요** — 카탈로그는 AI 엔진 소유. 마찬가지로 **`dudy_templates`·`pin_templates`·`contact_templates`·`goal_templates`·`gate_config`** 도 엔진 설정파일(`app/data/`).
> **위기 "도움 요청" 버튼**은 엔진 비관여 — 프론트 상시 버튼 + 외부기관 링크. **escape hatch(§2.4)와 절대 안 섞는다.**

---

## 4. 용어집 (Glossary)

| 용어 | 한 줄 정의 |
|---|---|
| **ARI** | 리듬·자립·연결 3축 현재 상태 벡터 v |
| **v_rhythm** | 리듬 축 값. **2리듬 존재로 추정(존재-EMA)**, 미션으로 안 바뀜. 게이트 입력 |
| **2리듬** | 아침 리듬 + 저녁 휘갈기기 리듬. 미션 아닌 상시 골격 |
| **게이트** | `gate(v_rhythm)` — 자립·연결 미션이 *언제 의미 있는지* 결정 |
| **effective_drag** | `recovery_drag × gate(v_rhythm)`. argmax가 오늘의 한 칸 |
| **recovery_drag** | `gap − velocity`. 목표 대비 막힌 정도 (자립·연결만) |
| **escape hatch** | 정체 5일↑ 시 gate_floor가 가장 쉬운 칸 1개를 띄움(연속 보정, "해금" 아님) |
| **mission_state** | `active`/`gated`/`escape_hatch`/`connection_priority`(B12) — 오늘 미션 유무·종류 |
| **η (eta)** | 아침 기분으로 정해지는 이동 크기 배율 (step size) |
| **waypoint** | 미션 경로 단계 (마주→관찰→선택→접점) |
| **Dudy / 도감** | 수집 캐릭터. signature=축 최종 미션=하나금융 해금 열쇠 |
| **unlocked_contacts** | 시그니처 도달 시 열리는 하나금융 접점(`Contact[]`), 축별 독립 |
| **채널 A/B** | A=미션 완료(흔적·η) / B=GPS 두디 포획(도감) — 분리된 통로 |

