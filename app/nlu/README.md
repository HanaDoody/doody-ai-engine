# nlu — 임베딩 기반 신호 추출 설계 (Signal Extraction via Embeddings)

> **위치**: `app/nlu/README.md` — 이 모듈(`extractor.py`)의 설계 노트.
> **역할**: `extract_signal(text) → {rhythm, autonomy, connection}` seam의 설계.
> MVP는 prototype similarity로 시작하고, 데이터가 쌓이면 지도 probe로 승급한다.
> 인터페이스(`extract_signal`)는 고정, 내부 구현만 교체한다.
>
> 관련 문서: [`api_contract.md`](../../docs/api_contract.md)(§2.7 chat)

---

## 0. 정의

> 짧은 한국어 발화를 임베딩 공간의 점으로 보내고,
> **리듬·자립·연결 세 축 방향으로의 사영(projection)** 을 신호로 읽는다.

이 모듈이 답하려는 연구 질문(RQ):
**"짧은 발화 임베딩이 리듬·자립·연결 회복 축 신호를 담고 있는가?"**

---

## 1. MVP에서 가능한 방식

probing에는 두 종류가 있고, MVP가 쓸 수 있는 건 후자다.

| 방식 | 필요한 것 | MVP |
|------|----------|-----|
| **지도 probe** (linear probe 학습) | (발화, 축 라벨) 쌍 수백 개 | 불가 (라벨 데이터 없음) |
| **prototype similarity** (앵커 기반) | 축마다 씨앗 문장 3~5개 | 가능 (라벨 없이 시작) |

MVP는 prototype similarity를 사용한다. 이는 probing의 경량 버전으로(§3 참고), 라벨 없이 RQ를 확인할 수 있다.
데이터가 쌓이면 같은 seam 뒤에서 지도 probe로 교체한다.

---

## 2. 설계 — prototype similarity

```python
# app/nlu/prototype_extractor.py  (개념 스케치)
from app.utils.vector import normalize, cosine, softmax

# ① 축마다 씨앗 문장(앵커) — 라벨 대신 이것이 축의 '정의'
ANCHORS = {
    "rhythm":     ["자꾸 미루게 돼요", "아침에 못 일어나겠어요", "하루가 엉켜요"],
    "autonomy":   ["돈 보는 게 무서워요", "통장을 못 열겠어요", "소비가 불안해요"],
    "connection": ["상담받기 무서워요", "기관에 연락 못 하겠어요", "혼자인 것 같아요"],
}

# ② 앵커를 임베딩해 축마다 prototype(평균 벡터) 1개 — 서버 기동 시 1회
#    proto[axis] = normalize(mean(embed(seed) for seed in seeds))
proto = {
    axis: normalize(mean([embed(s) for s in seeds]))
    for axis, seeds in ANCHORS.items()
}

# ③ 새 발화 → 임베딩 → 각 prototype과 코사인 → 신호
def extract_signal(text: str) -> dict:
    e = normalize(embed(text))
    sims = {axis: cosine(e, p) for axis, p in proto.items()}
    return softmax(sims)   # 예: {"rhythm":0.1, "autonomy":0.7, "connection":0.2}
```

- **임베딩 모델**: 한국어 짧은 발화이므로 **Ko-SBERT**(`jhgan/ko-sroberta-multitask` 등)
  추천 — 로컬·무료·한국어 튜닝. OpenAIEmbeddings도 가능하나 비용·언어 면에서 Ko-SBERT가 MVP에 적합.
- **출력**: 계약서 `signals` 필드와 동일한 `{rhythm, autonomy, connection}` (0~1).
  softmax 대신 raw 코사인을 clamp([0,1])해도 됨 — 합이 1일 필요가 있는지에 따라 선택.
- **계약서 예시 재현**: `"돈 문제가 무섭다" → autonomy 0.7`을 그대로 만들 수 있다.

---

## 3. Probing 관점: 사영으로서의 신호

**prototype similarity = nearest-centroid 분류기 = 특정 형태의 linear probe.**

두 축 prototype `p_a, p_b` 사이 결정경계는 두 점에서 등거리인 초평면 → 임베딩 공간의 **선형 경계**.
코사인 유사도는

```
cos(e, p_a) = ê · p̂_a       # 발화 벡터를 축 방향 p̂_a 에 사영한 양
```

즉 **각 축 = 임베딩 공간의 한 방향이고, 신호 = 그 방향으로의 사영 크기.**
(회귀를 projection으로 보는 것과 같은 구조다.)

그래서 RQ가 측정 가능한 형태로 바뀐다:

> "세 축 prototype이 임베딩 공간에서 선형 분리되는가?
>  손으로 라벨한 20~30개 발화에서 코사인 랭킹이 맞게 나오는가?"

→ **라벨 20~30개짜리 미니 실험**으로 RQ 1차 검증 가능(accuracy / ranking / ROC).

---

## 4. 예상되는 실패 모드

짧은 발화 임베딩의 대표 실패 모드를 미리 잡아둔다.

- **anisotropy(쏠림)**: 임베딩이 한 방향으로 몰려 *모든 코사인이 0.7~0.8로 비슷*하게 나옴
  → 축 구분이 뭉개짐. **해결: whitening/centering**(전체 평균 빼고 공분산 정규화).
  → 통계적 전처리로 축 간 분리도를 개선할 수 있다.
- **짧은 텍스트 노이즈**: 한두 단어 발화는 임베딩이 불안정 → 신호 신뢰도 낮음.
  MVP에선 `signals`를 `null`로 두거나 신뢰도 임계 미만이면 미반영.
- **앵커 품질 의존**: 씨앗 문장이 축을 잘 대표해야 함. 앵커를 늘리거나 다듬는 게 곧 튜닝.

> 진단 원칙: nlu 품질을 **LLM/미션과 분리해서** 따로 측정한다.
> "미션이 이상하다"가 검색(신호 추출) 실패인지 로직(core) 문제인지 분리 가능해야 한다.

---

## 5. 발전 경로 (seam 뒤 구현 교체)

인터페이스 `extract_signal(text) → {rhythm, autonomy, connection}` 는 고정. 내부만 단계적으로 승급.

```
[MVP]            rule-based 키워드 사전        (가장 단순, 설명 쉬움)
   ↓
[MVP+]           prototype similarity          ← 이 문서. 라벨 0개, projection 구조
   ↓
[데이터 축적 후]  지도 linear probe            (logistic regression on embedding)
   ↓
[확장]           fine-tuned / metric learning  (도메인 정렬, W 학습)
```

- 각 단계는 같은 입출력 계약을 지키므로 `core/`(미션 선택 로직)는 안 바뀐다.
- `fusion/`이 이 신호를 선택지 ARI와 합쳐 v를 보정.

---

## 6. 연구로의 확장 (RQ 후속)

- **RQ1 (1차)**: 세 축이 임베딩 공간에서 선형 분리되는가? (prototype + 미니 라벨셋)
- **RQ2**: whitening이 분리도를 얼마나 올리는가? (anisotropy 정량화)
- **RQ3 (입력→표현→행동)**: nlu를 stub→임베딩으로 켰을 때 *미션 선택이 어떻게 달라지나*?
  → 표현 변화가 행동(미션)을 바꾸는 경로를 측정.
- **RQ4**: 축 방향 벡터(prototype 차이)가 해석 가능한 의미 축과 정렬되는가?

---

## 부록 A — 미니 실험 체크리스트 (MVP 검증)

1. Ko-SBERT 로드, `ANCHORS`로 축별 prototype 3개 생성.
2. 손으로 발화 20~30개 작성 + 정답 축 라벨링(직관으로).
3. 각 발화에 `extract_signal` 적용, argmax 축 vs 라벨 → accuracy.
4. (선택) 코사인 분포가 다 비슷하면 whitening 적용 후 재측정 → 개선폭 기록.
5. 결과를 표/혼동행렬로 → RQ1 1차 답.
