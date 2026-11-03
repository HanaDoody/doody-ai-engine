"""POST /mission/recommend, /complete, and /reject."""
from fastapi import APIRouter, HTTPException

from app.catalog import loader
from app.core import ari_updater, contact_unlocker, energy_controller, mission_selector
from app.llm import text_generator
from app.schemas.mission import (
    Mission,
    MissionCompleteRequest,
    MissionCompleteResponse,
    MissionHistoryItem,
    RecommendRequest,
    RecommendResponse,
    RejectRequest,
    RejectResponse,
)
from app.schemas.rhythm import Reward
from app.schemas.state import ARIVector, Dudy

router = APIRouter(prefix="/mission", tags=["mission"])


def _mission_template(mission_id: str) -> dict:
    for item in loader.missions():
        if item.get("id") == mission_id:
            return item
    raise HTTPException(status_code=404, detail="unknown mission_id")


def _dudy_by_id(dudy_id: str) -> Dudy:
    for item in loader.dudy_templates():
        if item.get("id") == dudy_id:
            return Dudy(**item)
    raise HTTPException(status_code=500, detail="missing dudy template")


def _mission_reward(template: dict) -> Reward:
    """Hana money for completing a mission, priced by difficulty (d1=20..d4=50).

    A downshift earns the same as the normal step it replaces, so fallback
    missions are priced by their parent normal's difficulty (their own is
    deflated to 1 for selection sizing).
    """
    reward_by_difficulty = loader.gate_config()["mission_reward_by_difficulty"]
    difficulty = template["difficulty"]
    if template.get("is_fallback"):
        for item in loader.missions():
            if item.get("fallback_mission_id") == template["id"]:
                difficulty = item["difficulty"]
                break
    return Reward(hana_money=int(reward_by_difficulty[str(difficulty)]))


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    resp = mission_selector.recommend(req)
    # L1: the engine already produced deterministic copy + a decision_trace.
    # Translate the trace into doody's voice; the deterministic copy is the fallback.
    trace = (resp.diagnostics or {}).get("decision_trace")
    if trace:
        if resp.mission is not None:
            resp.mission.reason = text_generator.mission_reason(trace, fallback=resp.mission.reason)
        if resp.rest_message is not None:
            resp.rest_message = text_generator.rest_message(trace, fallback=resp.rest_message)
    return resp


@router.post("/complete", response_model=MissionCompleteResponse)
def complete(req: MissionCompleteRequest) -> MissionCompleteResponse:
    template = _mission_template(req.mission_id)
    eta = energy_controller.eta(req.energy)
    updated_ari, applied_delta = ari_updater.apply(
        req.current_ari,
        ARIVector(**template["delta"]),
        eta,
    )

    history_item = MissionHistoryItem(
        mission_id=req.mission_id,
        status="completed",
        axis=template["axis"],
        waypoint=template["waypoint"],
        difficulty=template["difficulty"],
    )
    unlocked_contacts = contact_unlocker.newly_unlocked([history_item])
    is_signature = bool(template.get("is_signature", False))
    is_fallback = bool(template.get("is_fallback", False))
    signature_completed = is_signature and not is_fallback
    collected_dudy = [_dudy_by_id("d_autonomy_signature")] if unlocked_contacts else []

    if signature_completed and unlocked_contacts:
        completion_kind = "signature_unlock"
    elif is_signature and is_fallback:
        completion_kind = "signature_prep"
    elif is_fallback:
        completion_kind = "fallback"
    else:
        completion_kind = "normal"
    message = text_generator.complete_message(
        {"kind": completion_kind, "axis": template["axis"]},
        fallback="오늘의 한 칸을 조용히 넘겼어.",
    )

    return MissionCompleteResponse(
        updated_ari=updated_ari,
        applied_delta=applied_delta,
        eta=eta,
        reward=_mission_reward(template),
        signature_available=updated_ari.autonomy >= 0.0 and is_signature,
        signature_completed=signature_completed,
        contact_unlocked=bool(unlocked_contacts),
        collected_dudy=collected_dudy,
        unlocked_contacts=unlocked_contacts,
        message=message,
    )


@router.post("/reject", response_model=RejectResponse)
def reject(req: RejectRequest) -> RejectResponse:
    template = _mission_template(req.mission_id)
    candidates: list[Mission] = []
    fallback_id = template.get("fallback_mission_id")
    if fallback_id:
        fallback = _mission_template(fallback_id)
        candidates = [mission_selector._mission_from_template(fallback)]
    return RejectResponse(
        action="downshift" if candidates else "rest",
        message="괜찮아. 더 쉬운 칸으로 낮춰둘게." if candidates else "오늘은 조금 쉬어가도 괜찮아.",
        rest_option=True,
        candidates=candidates,
        diagnostics={"rejected_mission_id": req.mission_id},
    )
