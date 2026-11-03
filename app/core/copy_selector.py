"""B10: turn the engine's state-based decision into a decision_trace and pick
the matching user-facing copy.

The engine decides (situation), the copy follows — never the other way round. The
same selector output is the input a later LLM step (L1) will translate; the
deterministic strings here are its fallback. Copy lives in
app/data/copy_templates.json so tone can change without touching logic.
"""
from app.catalog import loader

# Situations the recommend flow can produce.
SITUATIONS = {
    "active_normal",
    "active_fallback_first",
    "active_signature",
    "gated_warmup",
    "gated_done",
    "escape_hatch",
}


def build_trace(
    situation: str,
    primary_constraint: str,
    stage: int | None,
    waypoint: str | None,
    fallback_first: bool,
) -> dict:
    """Structured 'why' for diagnostics + future LLM input."""
    return {
        "situation": situation,
        "primary_constraint": primary_constraint,
        "stage": stage,
        "waypoint": waypoint,
        "fallback_first": fallback_first,
    }


def mission_reason(situation: str) -> str:
    reasons = loader.copy_templates().get("mission_reason", {})
    return reasons.get(situation, reasons.get("active_normal", ""))


def rest_message(situation: str) -> str:
    messages = loader.copy_templates().get("rest_message", {})
    return messages.get(situation, messages.get("gated_warmup", ""))


def direction(before: float, after: float, eps: float = 0.03) -> str:
    """축 시작→현재의 방향: up / flat / down. (LLM summary 입력용)"""
    delta = after - before
    if delta > eps:
        return "up"
    if delta < -eps:
        return "down"
    return "flat"


_direction = direction  # 내부 호환 별칭


def gap_bucket(gap: float) -> str:
    """목표까지 남은 거리(|gap|)를 close/mid/far로. (B11: report 병렬 서사용)"""
    g = abs(gap)
    if g <= 0.1:
        return "close"
    if g <= 0.3:
        return "mid"
    return "far"


def velocity_bucket(velocity: float) -> str:
    """report period 동안의 움직임 크기를 stalled/slow/fast로. (B11)"""
    v = abs(velocity)
    if v <= 0.03:
        return "stalled"
    if v <= 0.15:
        return "slow"
    return "fast"


def axis_narrative(axis: str, before: float, after: float) -> str:
    """Turn an axis's start->now movement into a direction sentence (no numbers)."""
    table = loader.copy_templates().get("report_axis_direction", {}).get(axis, {})
    return table.get(_direction(before, after), "")
