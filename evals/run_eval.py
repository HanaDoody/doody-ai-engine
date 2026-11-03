"""evals/run_eval.py — LLM 출력 eval + observability 하네스 (오프라인 기본).

무엇을 재나
  1. 폴백 문구 감사 (fallback copy audit)
     각 상황(situation)의 결정론 폴백 문구가 그 상황에 **충실(faithful)**하고,
     길이 가드 안이며, 반말 톤인지 룰 기반으로 채점. → 결정론 안전층 검증.
  2. 가드 메커니즘 점검 (guard mechanism)
     길이 초과·숫자 포함·빈 문자열이 prompts.valid()에 의해 실제로 걸러지는지.
  3. Observability 스냅샷
     하네스가 text_generator를 상황별로 돌리며 폴백률·가드 트립률·지연·토큰을 집계.

모드
  - offline (기본): LLM 꺼짐 → 폴백 문구를 채점. 키·과금 불필요. 나 혼자 검증 가능.
  - live: ANTHROPIC_API_KEY + llm_config.enabled=true → 진짜 LLM 출력·지연·토큰까지.
    실행법은 evals/README.md 참고.

실행:  python -m evals.run_eval   (repo 루트에서)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# repo 루트를 path에 (직접 `python evals/run_eval.py` 실행도 되도록)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import copy_selector  # noqa: E402
from app.llm import client, metrics, prompts, text_generator  # noqa: E402

# 필드별 길이 상한 (text_generator와 일치)
_MAX_REASON = text_generator._MAX_REASON
_MAX_REST = text_generator._MAX_REST

# 상황 → (문구 종류, 반드시 담아야 할 표현 중 하나, 담으면 안 되는 표현)
# 폴백 문구가 그 국면과 모순되지 않는지 룰로 검증한다.
_FAITHFULNESS = {
    "active_normal":         ("reason", ["다음 칸", "남은", "낮춰"], ["접점", "마지막 칸"]),
    "active_fallback_first": ("reason", ["작은", "가볍게"],          ["크게", "더 많이"]),
    "active_signature":      ("reason", ["마지막", "접점"],          []),
    "escape_hatch":          ("reason", ["작은", "괜찮"],            []),
    "gated_warmup":          ("rest",   ["리듬"],                    ["미션을 해"]),
    "gated_done":            ("rest",   ["리듬", "끝"],              []),
}


def score_faithfulness(situation: str, text: str) -> bool:
    """폴백 문구가 상황과 모순되지 않나: 필수 표현 중 하나 포함 AND 금지 표현 없음."""
    spec = _FAITHFULNESS.get(situation)
    if spec is None:
        return False
    _, must_any, must_not = spec
    if any(bad in text for bad in must_not):
        return False
    return any(good in text for good in must_any)


def score_tone(text: str) -> bool:
    """반말 휴리스틱: 해요체/합쇼체 어미가 아니면 통과."""
    stripped = text.rstrip(" .!?~…")
    if stripped.endswith("요"):
        return False
    return "습니다" not in text and "입니다" not in text


def _copy_for(situation: str) -> tuple[str, int]:
    kind = _FAITHFULNESS[situation][0]
    if kind == "reason":
        return copy_selector.mission_reason(situation), _MAX_REASON
    return copy_selector.rest_message(situation), _MAX_REST


def audit_fallback_copy() -> list[dict]:
    """결정론 폴백 문구 감사 (모드 무관, 항상 결정론)."""
    rows = []
    for situation in _FAITHFULNESS:
        text, max_len = _copy_for(situation)
        rows.append({
            "situation": situation,
            "text": text,
            "len_ok": len(text) <= max_len,
            "no_digit": not any(ch.isdigit() for ch in text),
            "faithful": score_faithfulness(situation, text),
            "tone_ok": score_tone(text),
        })
    return rows


def check_guard_mechanism() -> list[dict]:
    """prompts.valid()가 설계대로 거르는지 확인."""
    cases = [
        # (이름, 텍스트, max_len, forbid_digits, 기대값)
        ("정상 짧은 문구",       "작은 한 걸음이야.",   _MAX_REASON, True,  True),
        ("길이 초과",           "가" * 200,           _MAX_REASON, True,  False),
        ("숫자 포함(짧은필드)",  "3일째 잘하고 있어.",  _MAX_REASON, True,  False),
        ("숫자 포함(서사필드)",  "3일째 잘 지냈어.",    120,         False, True),
        ("빈 문자열",           "",                   _MAX_REASON, True,  False),
    ]
    rows = []
    for name, text, max_len, forbid, expected in cases:
        got = prompts.valid(text, max_len, forbid_digits=forbid)
        rows.append({"case": name, "expected": expected, "got": got, "pass": got == expected})
    return rows


def _drive_generation() -> None:
    """상황별로 text_generator를 실제로 돌려 observability 카운터를 채운다.
    offline이면 폴백으로 강등되며, 그 강등 자체가 관측 대상이다."""
    for situation, (kind, *_rest) in _FAITHFULNESS.items():
        trace = {
            "situation": situation,
            "primary_constraint": "on_track",
            "stage": 3,
            "waypoint": "finance_touch",
            "fallback_first": situation == "active_fallback_first",
        }
        if kind == "reason":
            text_generator.mission_reason(trace, fallback=copy_selector.mission_reason(situation))
        else:
            text_generator.rest_message(trace, fallback=copy_selector.rest_message(situation))


def run_eval() -> dict:
    """전체 eval 1회. metrics는 호출 전에 reset하는 게 깔끔하다."""
    metrics.reset()
    _drive_generation()
    return {
        "mode": "live" if client.is_enabled() else "offline",
        "fallback_copy_audit": audit_fallback_copy(),
        "guard_mechanism": check_guard_mechanism(),
        "observability": metrics.snapshot(),
    }


def _check(v: bool) -> str:
    return "✅" if v else "❌"


def format_markdown(result: dict) -> str:
    o = result["observability"]
    lines = [
        "# LLM eval / observability 리포트",
        "",
        f"- mode: **{result['mode']}**  (offline = LLM 꺼짐, 폴백 문구를 채점)",
        "",
        "## 1. 폴백 문구 감사 (결정론 안전층)",
        "",
        "| 상황 | 길이 | 무숫자 | 충실 | 반말 | 문구 |",
        "|---|:--:|:--:|:--:|:--:|---|",
    ]
    for r in result["fallback_copy_audit"]:
        lines.append(
            f"| {r['situation']} | {_check(r['len_ok'])} | {_check(r['no_digit'])} "
            f"| {_check(r['faithful'])} | {_check(r['tone_ok'])} | {r['text']} |"
        )
    lines += ["", "## 2. 가드 메커니즘", "", "| 케이스 | 기대 | 결과 | 통과 |", "|---|:--:|:--:|:--:|"]
    for r in result["guard_mechanism"]:
        lines.append(f"| {r['case']} | {r['expected']} | {r['got']} | {_check(r['pass'])} |")
    lines += [
        "",
        "## 3. Observability",
        "",
        f"- generations: {o['generations']} · used_llm: {o['used_llm']} · fallback: {o['fallback']}",
        f"- **fallback_rate**: {o['fallback_rate']} · **guard_trip_rate**: {o['guard_trip_rate']}",
        f"- latency avg/p50/p95 (ms): {o['latency_ms_avg']} / {o['latency_ms_p50']} / {o['latency_ms_p95']}",
        f"- tokens_total: {o['tokens_total']}",
        "",
        "> offline에선 LLM 미호출이라 fallback_rate=1.0, 지연/토큰은 비어 있다.",
        "> live로 켜면(evals/README.md) 진짜 폴백률·가드 트립률·지연·토큰이 채워진다.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    # Windows 콘솔(cp949)에서도 이모지 출력이 깨지지 않도록.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    result = run_eval()
    md = format_markdown(result)
    print(md)
    out = Path(__file__).resolve().parent / "results.md"
    out.write_text(md, encoding="utf-8")
    (out.with_name("results.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[written] {out}  &  results.json")


if __name__ == "__main__":
    main()
