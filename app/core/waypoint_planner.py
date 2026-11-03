"""Autonomy stage progression from stateless mission history."""
from app.catalog import loader
from app.schemas.mission import MissionHistoryItem
from app.schemas.state import MissionAxis


def _templates(axis: MissionAxis, include_fallback: bool = False) -> list[dict]:
    missions = [m for m in loader.missions() if m.get("axis") == axis]
    if not include_fallback:
        missions = [m for m in missions if not m.get("is_fallback", False)]
    return sorted(missions, key=lambda m: (int(m.get("stage", 0)), int(m.get("difficulty", 0))))


def _by_id() -> dict[str, dict]:
    return {m["id"]: m for m in loader.missions()}


def completed_stages(axis: MissionAxis, history: list[MissionHistoryItem]) -> set[int]:
    """Return stages counted as completed for an axis.

    A smaller step is still a completed step: for stages 1-9 either the normal or the
    fallback completion advances the stage. The only exception is the signature stage —
    a signature fallback is preparation, so it does not complete stage 10 (only the
    normal signature does, which is what unlocks the contact).
    """
    catalog = _by_id()
    stages: set[int] = set()
    for item in history:
        if item.status != "completed":
            continue
        template = catalog.get(item.mission_id)
        if not template or template.get("axis") != axis:
            continue
        if template.get("is_signature", False) and template.get("is_fallback", False):
            continue
        stage = template.get("stage")
        if stage is not None:
            stages.add(int(stage))
    return stages


def signature_completed(axis: MissionAxis, history: list[MissionHistoryItem]) -> bool:
    catalog = _by_id()
    for item in history:
        if item.status != "completed":
            continue
        template = catalog.get(item.mission_id)
        if (
            template
            and template.get("axis") == axis
            and template.get("is_signature", False)
            and not template.get("is_fallback", False)
        ):
            return True
    return False


def next_stage(
    axis: MissionAxis,
    history: list[MissionHistoryItem],
    start_floor: int = 1,
) -> int | None:
    """Return the first unfinished stage at or above start_floor.

    start_floor lets onboarding set where a fresh user begins (see
    state_space.start_stage_from_autonomy). Stages below the floor are treated as
    granted and never recommended.
    """
    stages = [int(m["stage"]) for m in _templates(axis) if m.get("stage") is not None]
    completed = completed_stages(axis, history)
    for stage in stages:
        if stage < start_floor:
            continue
        if stage not in completed:
            return stage
    return stages[-1] if stages else None


def next_waypoint(axis: MissionAxis, history: list[MissionHistoryItem]) -> str | None:
    stage = next_stage(axis, history)
    if stage is None:
        return None
    for template in _templates(axis):
        if int(template.get("stage", 0)) == stage:
            return str(template["waypoint"])
    return None


def current_waypoint(axis: MissionAxis, history: list[MissionHistoryItem]) -> str | None:
    completed = completed_stages(axis, history)
    if not completed:
        return None
    latest = max(completed)
    for template in _templates(axis):
        if int(template.get("stage", 0)) == latest:
            return str(template["waypoint"])
    return None


def replan(axis: MissionAxis, current: str | None) -> str | None:
    """Keep the current waypoint for MVP downshift; frontend swaps to fallback locally."""
    if current is not None:
        return current
    templates = _templates(axis)
    return str(templates[0]["waypoint"]) if templates else None
