"""Stateless contact unlock helpers."""
from app.catalog import loader
from app.schemas.mission import Contact, MissionHistoryItem
from app.schemas.state import MissionAxis


def contacts_for_axis(axis: MissionAxis) -> list[Contact]:
    return [Contact(**item) for item in loader.contacts() if item.get("axis") == axis]


def unlocked_for_axis(axis: MissionAxis) -> list[Contact]:
    """Return contacts unlocked for an axis.

    The engine is stateless, so duplicate suppression belongs to the backend.
    """
    return contacts_for_axis(axis)


def _mission_template(mission_id: str) -> dict | None:
    for item in loader.missions():
        if item.get("id") == mission_id:
            return item
    return None


def unlocks_contact(mission_id: str) -> bool:
    """Only normal signature mission completion unlocks autonomy contact."""
    template = _mission_template(mission_id)
    return bool(
        template
        and template.get("axis") == "autonomy"
        and template.get("is_signature", False)
        and not template.get("is_fallback", False)
    )


def newly_unlocked(history: list[MissionHistoryItem]) -> list[Contact]:
    if not history:
        return []
    latest = history[-1]
    if latest.status == "completed" and unlocks_contact(latest.mission_id):
        return unlocked_for_axis("autonomy")
    return []
