"""Autonomy mission selection over the closed state math from Batch 4A."""
from app.catalog import loader
from app.core import (
    copy_selector,
    energy_controller,
    gap_calculator,
    state_space,
    waypoint_planner,
)
from app.core.gate import gate
from app.core.rhythm_estimator import estimate_v_rhythm
from app.schemas.mission import Mission, RecommendRequest, RecommendResponse
from app.schemas.state import ARIVector, MissionAxis


def _mission_from_template(template: dict, reason: str | None = None) -> Mission:
    mission_id = template["id"]
    return Mission(
        id=mission_id,
        mission_id=mission_id,
        axis=template["axis"],
        stage=template.get("stage"),
        waypoint=template["waypoint"],
        difficulty=template["difficulty"],
        delta=ARIVector(**template["delta"]),
        title=template["title"],
        description=template.get("description"),
        mission_type=template.get("mission_type", "CHECK"),
        required_count=int(template.get("required_count", 1)),
        is_signature=bool(template.get("is_signature", False)),
        is_fallback=bool(template.get("is_fallback", False)),
        fallback_mission_id=template.get("fallback_mission_id"),
        goal_tags=template.get("goal_tags", []),
        how_to=template.get("how_to", []),
        reason=reason or "지금 상태에서 가장 작은 다음 칸이야.",
    )


_CONNECTION_NUDGE_ID = "c_connection_nudge"


def _connection_nudge_mission() -> Mission:
    """B12c: not a catalog mission — same Mission shape for the frontend's
    uniform "today's mission" card, but completable=False and no
    waypoint/difficulty/delta (connection has none of those concepts; the real
    completion/delta happens later in /collection/capture, not here)."""
    return Mission(
        id=_CONNECTION_NUDGE_ID,
        mission_id=_CONNECTION_NUDGE_ID,
        axis="connection",
        title="두디를 잡으러 가보자",
        how_to=["지도를 열어봐", "가까운 핀으로 가봐", "두디를 탭해서 잡아봐"],
        reason=copy_selector.mission_reason("connection_priority"),
        completable=False,
    )


def _templates_for(axis: MissionAxis, include_fallback: bool = False) -> list[dict]:
    missions = [m for m in loader.missions() if m.get("axis") == axis]
    if not include_fallback:
        missions = [m for m in missions if not m.get("is_fallback", False)]
    return sorted(missions, key=lambda m: (int(m.get("stage", 0)), int(m.get("difficulty", 0))))


def _template_by_id(mission_id: str) -> dict | None:
    for template in loader.missions():
        if template.get("id") == mission_id:
            return template
    return None


def _fallback_template(template: dict) -> dict | None:
    fallback_id = template.get("fallback_mission_id")
    return _template_by_id(fallback_id) if fallback_id else None


def _fallback_for(template: dict) -> Mission | None:
    fallback = _fallback_template(template)
    return _mission_from_template(fallback) if fallback else None


def _sized_template(
    template: dict,
    gate_value: float,
    energy: int,
    config: dict,
) -> tuple[dict, Mission | None, bool]:
    """B9a: choose the normal card, or the smaller fallback card as primary.

    On a low-warmth (gate) or low-energy day the engine serves the smaller step
    *before* the user asks — the gate acts as a volume knob, not an on/off switch.
    The signature stage is excluded: its fallback is preparation and would not
    unlock the contact, so stage 10 always presents the normal signature.
    Returns (chosen_template, fallback_field, fallback_first). When fallback-first,
    fallback_field is None (there is nothing smaller) — the frontend must hide the
    downshift control in that case.
    """
    fallback_tmpl = _fallback_template(template)
    is_signature = template.get("is_signature", False)
    gate_below = float(config.get("fallback_first_gate_below", 0.5))
    energy_at_or_below = int(config.get("fallback_first_energy_at_or_below", 2))
    fallback_first = (
        not is_signature
        and fallback_tmpl is not None
        and (gate_value < gate_below or energy <= energy_at_or_below)
    )
    if fallback_first:
        return fallback_tmpl, None, True
    return template, _fallback_for(template), False


def _days_without_mission(history: list) -> int:
    days = 0
    for item in reversed(history):
        if item.status == "completed":
            break
        days += 1
    return days


def _effective_drag(recovery_drag: ARIVector, gate_value: float) -> dict[str, float]:
    return {
        "autonomy": recovery_drag.autonomy * gate_value,
        "connection": recovery_drag.connection * gate_value,
    }


def _template_for_stage(stage: int) -> dict:
    for template in _templates_for("autonomy"):
        if int(template.get("stage", 0)) == stage:
            return template
    raise ValueError(f"no autonomy mission template for stage: {stage}")



def select_one(axis: MissionAxis, waypoint: str | None, difficulty_hint: int) -> Mission:
    """Pick one normal catalog mission matching axis and waypoint."""
    templates = _templates_for(axis)
    if not templates:
        raise ValueError(f"no mission templates for axis: {axis}")

    if waypoint is not None:
        matching = [m for m in templates if m.get("waypoint") == waypoint]
        if matching:
            templates = matching

    eligible = [m for m in templates if int(m.get("difficulty", 0)) <= difficulty_hint]
    if eligible:
        templates = eligible

    return _mission_from_template(templates[0])


def select_candidates(axis: MissionAxis, max_difficulty: int) -> list[Mission]:
    """Return fallback candidate when a mission has a configured fallback."""
    templates = [
        m for m in _templates_for(axis, include_fallback=True)
        if m.get("is_fallback", False) and int(m.get("difficulty", 0)) <= max_difficulty
    ]
    return [_mission_from_template(m) for m in templates[:1]]


def recommend(req: RecommendRequest) -> RecommendResponse:
    """Return active/gated/escape_hatch/connection_priority recommendation.

    Autonomy missions are this function's own domain; connection_priority (B12)
    only ever points the user at the separate /collection/capture channel — it
    never fabricates a connection mission here.
    """
    # B9b: seed the v_rhythm EMA from the onboarding rhythm answer (carried in
    # current_ari.rhythm), so the gate starts personalised instead of a fixed prior.
    v_rhythm = estimate_v_rhythm(req.rhythm_history, seed=req.current_ari.rhythm)
    days_without_mission = _days_without_mission(req.history)
    gate_value = gate(v_rhythm, days_without_mission)
    eta_value = energy_controller.eta(req.energy)

    gap_v = gap_calculator.gap(req.goal, req.current_ari)
    velocity_v = gap_calculator.velocity(req.recent_trajectory)
    recovery_drag_v = gap_calculator.recovery_drag(gap_v, velocity_v)
    effective = _effective_drag(recovery_drag_v, gate_value)
    bottleneck = gap_calculator.bottleneck_axis(recovery_drag_v)

    diagnostics = {
        "v_rhythm": v_rhythm,
        "gate": gate_value,
        "gap": gap_v.model_dump(),
        "velocity": velocity_v.model_dump(),
        "recovery_drag": {
            "autonomy": recovery_drag_v.autonomy,
            "connection": recovery_drag_v.connection,
        },
        "effective_drag": effective,
        "bottleneck_axis": bottleneck,
        "days_without_mission": days_without_mission,
        "eta": eta_value,
    }

    config = loader.gate_config()
    start_floor = state_space.start_stage_from_autonomy(req.current_ari.autonomy)
    diagnostics["start_stage"] = start_floor

    # Stuck for too long: surface the gentlest next step regardless of gate.
    # Escape hatch is the smallest possible nudge, so it serves the fallback card
    # (except the signature stage, whose fallback would not unlock the contact).
    if days_without_mission >= int(config["escape_days"]):
        # B12b: same bottleneck check as the normal-day branch below, so escape_hatch
        # doesn't stay autonomy-only while every other day already respects bottleneck.
        # "Stalled" here is measured from autonomy history only (history is autonomy
        # mission log, connection captures live in a separate channel/table) — if
        # connection is the bigger gap, the gentlest nudge is pointing there, not a
        # smaller autonomy step.
        if bottleneck == "connection":
            diagnostics["decision_trace"] = copy_selector.build_trace(
                "connection_priority", "connection_behind", None, None, False
            )
            return RecommendResponse(
                mission=_connection_nudge_mission(),
                fallback=None,
                mission_state="connection_priority",
                rest_message=None,
                unlocked_contacts=[],
                v_rhythm=v_rhythm,
                diagnostics=diagnostics,
            )
        stage = waypoint_planner.next_stage("autonomy", req.history, start_floor)
        template = _template_for_stage(stage or start_floor)
        fallback_tmpl = _fallback_template(template)
        if not template.get("is_signature", False) and fallback_tmpl is not None:
            chosen, fallback, fallback_first = fallback_tmpl, None, True
        else:
            chosen, fallback, fallback_first = template, _fallback_for(template), False
        diagnostics["fallback_first"] = fallback_first
        diagnostics["decision_trace"] = copy_selector.build_trace(
            "escape_hatch", "stalled", chosen.get("stage"), chosen.get("waypoint"), fallback_first
        )
        mission = _mission_from_template(chosen, copy_selector.mission_reason("escape_hatch"))
        return RecommendResponse(
            mission=mission,
            fallback=fallback,
            mission_state="escape_hatch",
            rest_message=None,
            unlocked_contacts=[],
            v_rhythm=v_rhythm,
            diagnostics=diagnostics,
        )

    # Rhythm foundation not warm enough: only the two daily rhythms today.
    if gate_value <= 0:
        diagnostics["decision_trace"] = copy_selector.build_trace(
            "gated_warmup", "low_rhythm", None, None, False
        )
        return RecommendResponse(
            mission=None,
            fallback=None,
            mission_state="gated",
            rest_message=copy_selector.rest_message("gated_warmup"),
            unlocked_contacts=[],
            v_rhythm=v_rhythm,
            diagnostics=diagnostics,
        )

    # B12: bottleneck decides which ONE axis gets today's single card — not an
    # add-on note next to the autonomy card, a swap of it. No threshold: recovery_drag
    # already shrinks on its own as an axis nears its goal (gap -> 0), so this
    # self-regulates near signature completion without a special case.
    if not waypoint_planner.signature_completed("autonomy", req.history) and bottleneck == "connection":
        diagnostics["decision_trace"] = copy_selector.build_trace(
            "connection_priority", "connection_behind", None, None, False
        )
        return RecommendResponse(
            mission=_connection_nudge_mission(),
            fallback=None,
            mission_state="connection_priority",
            rest_message=None,
            unlocked_contacts=[],
            v_rhythm=v_rhythm,
            diagnostics=diagnostics,
        )

    # Autonomy is a staged path. While the signature is unfinished, the next stage
    # drives the recommendation. The finish line is completing the normal signature
    # (stage 10), not reaching an ARI threshold — ARI/drag stay in diagnostics as a
    # thermometer, they no longer gate or route the autonomy mission.
    if not waypoint_planner.signature_completed("autonomy", req.history):
        stage = waypoint_planner.next_stage("autonomy", req.history, start_floor)
        template = _template_for_stage(stage or start_floor)
        # B9a: gate/energy decide whether the smaller card is served first.
        chosen, fallback, fallback_first = _sized_template(
            template, gate_value, req.energy, config
        )
        # B10: situation drives the copy (and the future LLM's input trace).
        if fallback_first:
            energy_at_or_below = int(config.get("fallback_first_energy_at_or_below", 2))
            situation = "active_fallback_first"
            primary = "low_energy" if req.energy <= energy_at_or_below else "low_rhythm"
        elif chosen.get("is_signature", False):
            situation, primary = "active_signature", "on_track"
        else:
            situation, primary = "active_normal", "on_track"
        diagnostics["fallback_first"] = fallback_first
        diagnostics["decision_trace"] = copy_selector.build_trace(
            situation, primary, chosen.get("stage"), chosen.get("waypoint"), fallback_first
        )
        mission = _mission_from_template(chosen, copy_selector.mission_reason(situation))
        return RecommendResponse(
            mission=mission,
            fallback=fallback,
            mission_state="active",
            rest_message=None,
            unlocked_contacts=[],
            v_rhythm=v_rhythm,
            diagnostics=diagnostics,
        )

    # Autonomy path complete (signature done): no active autonomy mission today.
    diagnostics["decision_trace"] = copy_selector.build_trace(
        "gated_done", "path_done", None, None, False
    )
    return RecommendResponse(
        mission=None,
        fallback=None,
        mission_state="gated",
        rest_message=copy_selector.rest_message("gated_done"),
        unlocked_contacts=[],
        v_rhythm=v_rhythm,
        diagnostics=diagnostics,
    )
