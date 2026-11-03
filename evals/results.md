# LLM eval / observability 리포트

- mode: **offline**  (offline = LLM 꺼짐, 폴백 문구를 채점)

## 1. 폴백 문구 감사 (결정론 안전층)

| 상황 | 길이 | 무숫자 | 충실 | 반말 | 문구 |
|---|:--:|:--:|:--:|:--:|---|
| active_normal | ✅ | ✅ | ✅ | ✅ | 자립 쪽에 아직 남은 다음 칸이 있어. 어렵다면 더 작은 걸로 낮춰도 돼. |
| active_fallback_first | ✅ | ✅ | ✅ | ✅ | 오늘은 가볍게 이 작은 칸부터 둘게. 이것도 한 걸음이야. |
| active_signature | ✅ | ✅ | ✅ | ✅ | 자립 길의 마지막 칸이야. 이 확인만 마치면 접점이 열려. |
| escape_hatch | ✅ | ✅ | ✅ | ✅ | 아주 작은 것 하나만 열어둘게. 안 해도 괜찮아. |
| gated_warmup | ✅ | ✅ | ✅ | ✅ | 오늘은 행동 미션보다 리듬만 붙잡아도 괜찮아. |
| gated_done | ✅ | ✅ | ✅ | ✅ | 자립 길을 끝까지 걸었어. 오늘은 리듬만 붙잡아도 충분해. |

## 2. 가드 메커니즘

| 케이스 | 기대 | 결과 | 통과 |
|---|:--:|:--:|:--:|
| 정상 짧은 문구 | True | True | ✅ |
| 길이 초과 | False | False | ✅ |
| 숫자 포함(짧은필드) | False | False | ✅ |
| 숫자 포함(서사필드) | True | True | ✅ |
| 빈 문자열 | False | False | ✅ |

## 3. Observability

- generations: 6 · used_llm: 0 · fallback: 6
- **fallback_rate**: 1.0 · **guard_trip_rate**: 0.0
- latency avg/p50/p95 (ms): None / None / None
- tokens_total: 0

> offline에선 LLM 미호출이라 fallback_rate=1.0, 지연/토큰은 비어 있다.
> live로 켜면(evals/README.md) 진짜 폴백률·가드 트립률·지연·토큰이 채워진다.
