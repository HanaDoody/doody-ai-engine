# evals — LLM eval / observability 하네스

두디 엔진의 [D0 결정(결정론 코어 + LLM 표면)](../DESIGN.md)이 **실제로 어떻게 도는지** 측정한다.
결정론 안전층은 항상 검증하고, LLM을 켜면 실제 운영 수치(폴백률·가드 트립률·지연·토큰)까지 잡는다.

## 무엇을 재나
1. **폴백 문구 감사** — 각 상황의 결정론 폴백 문구가 그 국면에 충실(faithful)하고, 길이 가드 안이며, 반말 톤인지.
2. **가드 메커니즘** — 길이 초과·숫자 포함·빈 문자열이 `prompts.valid()`에 실제로 걸러지는지.
3. **Observability** — `text_generator`를 상황별로 돌리며 `llm/metrics.py` 카운터 집계.

## 실행 (offline — 기본, 키·과금 불필요)
```bash
python -m evals.run_eval
```
→ 콘솔 리포트 + `evals/results.md` · `evals/results.json` 생성.
offline에선 LLM 미호출이라 `fallback_rate=1.0`, 지연/토큰은 비어 있다. 감사·가드는 완전히 검증된다.

## live로 켜기 (실제 LLM 수치, 과금 발생)
```bash
export ANTHROPIC_API_KEY=sk-...           # (Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-...")
export LLM_ENABLED=true                    # 또는 app/data/llm_config.json 의 enabled -> true
python -m evals.run_eval
```
→ `mode: live`로 돌며 실제 지연·토큰·폴백률·가드 트립률이 채워진다.
호출량이 작아(상황 ~6건) 비용은 몇십 원 수준. 끝나면 `enabled`를 다시 false로.

## 파일
- `run_eval.py` — 하네스 (스코어 함수 + 실행/리포트)
- `results.md` / `results.json` — 마지막 실행 결과 (offline 샘플이 커밋돼 있음)
- 계측 소스: [`app/llm/metrics.py`](../app/llm/metrics.py)
