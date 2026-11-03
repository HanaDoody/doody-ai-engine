"""llm/metrics.py — 인프로세스 LLM 관측 카운터 (observability).

단일 길목 client.complete()와 text_generator의 가드에서 이벤트를 기록해
폴백률·가드 트립률·지연·토큰을 집계한다. 프로세스 로컬 카운터(경량, MVP).
snapshot()으로 JSON 덤프하거나 evals 하네스가 읽는다.

여기서 재는 것 (D0 "결정론 코어 + LLM 표면"이 실제로 어떻게 도는가):
  - fallback_rate   : 생성 중 결정론 폴백으로 강등된 비율
  - guard_trip_rate : LLM이 답했지만 가드(길이/숫자)에 걸려 버려진 비율
  - latency / tokens: 실제 LLM 호출 비용 (라이브에서만 채워짐)
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class _Acc:
    calls: int = 0           # complete() 진입 횟수
    disabled: int = 0        # LLM 꺼져서 즉시 None (기본 배포)
    api_ok: int = 0          # API가 텍스트 반환
    api_fail: int = 0        # API 예외/거절/빈응답 → None
    generations: int = 0     # text_generator 필드 생성 횟수
    used_llm: int = 0        # LLM 텍스트가 최종 채택됨
    fallback: int = 0        # 결정론 폴백으로 강등 (guard_trip 포함)
    guard_trips: int = 0     # LLM 텍스트가 valid() 실패로 버려짐
    latency_ms: list = field(default_factory=list)
    tokens: list = field(default_factory=list)


_lock = threading.Lock()
_acc = _Acc()


def record_call(*, enabled: bool, ok: bool, latency_ms: float | None = None,
                tokens: int | None = None) -> None:
    """단일 길목 client.complete() 1회의 전송 결과."""
    with _lock:
        _acc.calls += 1
        if not enabled:
            _acc.disabled += 1
        elif ok:
            _acc.api_ok += 1
        else:
            _acc.api_fail += 1
        if latency_ms is not None:
            _acc.latency_ms.append(latency_ms)
        if tokens is not None:
            _acc.tokens.append(tokens)


def record_generation(*, outcome: str) -> None:
    """text_generator 필드 1개의 최종 결과. outcome ∈ {used_llm, guard_trip, fallback}."""
    with _lock:
        _acc.generations += 1
        if outcome == "used_llm":
            _acc.used_llm += 1
        elif outcome == "guard_trip":
            _acc.guard_trips += 1
            _acc.fallback += 1
        else:
            _acc.fallback += 1


def reset() -> None:
    global _acc
    with _lock:
        _acc = _Acc()


def _pct(values: list[float], p: int) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return round(s[k], 1)


def snapshot() -> dict:
    """집계 스냅샷. 비율은 생성 수 기준."""
    with _lock:
        n = _acc.generations or 1
        lat = list(_acc.latency_ms)
        return {
            "calls": _acc.calls,
            "disabled": _acc.disabled,
            "api_ok": _acc.api_ok,
            "api_fail": _acc.api_fail,
            "generations": _acc.generations,
            "used_llm": _acc.used_llm,
            "fallback": _acc.fallback,
            "guard_trips": _acc.guard_trips,
            "fallback_rate": round(_acc.fallback / n, 3),
            "guard_trip_rate": round(_acc.guard_trips / n, 3),
            "latency_ms_avg": round(sum(lat) / len(lat), 1) if lat else None,
            "latency_ms_p50": _pct(lat, 50),
            "latency_ms_p95": _pct(lat, 95),
            "tokens_total": sum(_acc.tokens) if _acc.tokens else 0,
        }
