"""Focused v0.7 contract tests for rhythm, missions, and collection."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.catalog import loader
from app.schemas.mission import MissionHistoryItem
from app.core import waypoint_planner

client = TestClient(app)


ARI = {"rhythm": 0.42, "autonomy": 0.30, "connection": 0.55}
GOAL = {"rhythm": 0.50, "autonomy": 0.70, "connection": 0.60}
AUTONOMY_GOAL = {"rhythm": 0.50, "autonomy": 0.70, "connection": 0.30}
HIGH_RHYTHM_HISTORY = {
    "morning": [
        {"timestamp": f"2026-06-2{day}T08:00:00Z", "did_check_in": True}
        for day in range(1, 7)
    ],
    "evening": [
        {"timestamp": f"2026-06-2{day}T22:00:00Z", "text": "ok"}
        for day in range(1, 7)
    ],
}
EMPTY_RHYTHM_HISTORY = {"morning": [], "evening": []}


LOW_AUTONOMY_ARI = {"rhythm": 0.42, "autonomy": 0.15, "connection": 0.55}
AUTONOMY_PATH_1_TO_9 = [
    {"mission_id": mid, "status": "completed"}
    for mid in (
        "a01_feeling_word",
        "a02_positive_memory",
        "a03_finance_touch",
        "a04_balance_glance",
        "a05_spend_observe",
        "a06_future_capture_3",
        "a07_direction_confirm",
        "a08_direction_choose",
        "a09_check_certificate_fee",
    )
]


def recommend_payload(**overrides):
    payload = {
        "user_id": "u1",
        "current_ari": LOW_AUTONOMY_ARI,
        "goal": AUTONOMY_GOAL,
        "recent_trajectory": [],
        "energy": 3,
        "rhythm_history": HIGH_RHYTHM_HISTORY,
        "history": [],
    }
    payload.update(overrides)
    return payload


def test_health_version_is_v07():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0.7.0"}


def test_rhythm_endpoints_shape_has_no_removed_fields():
    morning = client.post(
        "/rhythm/morning",
        json={"user_id": "u1", "timestamp": "2026-06-28T08:00:00Z", "energy": 3},
    )
    evening = client.post(
        "/rhythm/evening",
        json={"user_id": "u1", "text": "one line"},
    )

    assert morning.status_code == 200
    assert evening.status_code == 200
    morning_body = morning.json()
    evening_body = evening.json()

    assert set(morning_body) == {"reward", "greeting", "collected_dudy"}
    assert set(evening_body) == {"reward", "signals", "reply", "collected_dudy"}
    assert evening_body["signals"] is None

    serialized = str(morning_body) + str(evening_body)
    for removed in ("is_bonus", "wake_timestamp", "promised_time", "morning_promise_time"):
        assert removed not in serialized


def test_recommend_active_includes_mission_and_fallback():
    res = client.post("/mission/recommend", json=recommend_payload())
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "active"
    assert body["mission"]["mission_id"] == "a01_feeling_word"
    assert body["fallback"]["mission_id"] == "a01_feeling_word_down"
    assert body["v_rhythm"] > 0
    assert body["diagnostics"]["bottleneck_axis"] == "autonomy"


def test_recommend_gated_when_low_rhythm_seed_and_no_logs():
    """B9b: a low rhythm self-report with no logs keeps the gate closed (warm up first)."""
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.1, "autonomy": 0.15, "connection": 0.55},
            rhythm_history=EMPTY_RHYTHM_HISTORY,
        ),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "gated"
    assert body["mission"] is None
    assert body["fallback"] is None
    assert body["diagnostics"]["gate"] == 0


def test_high_rhythm_seed_opens_gate_without_logs():
    """B9b: a good rhythm self-report opens the gate on day 0 (no logs needed)."""
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.7, "autonomy": 0.15, "connection": 0.55},
            rhythm_history=EMPTY_RHYTHM_HISTORY,
            energy=3,
        ),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "active"
    assert body["mission"] is not None


def test_low_energy_serves_fallback_first():
    """B9a: a low-energy day serves the smaller card first, with no downshift left."""
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.42, "autonomy": 0.1, "connection": 0.55},
            energy=1,
        ),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "active"
    assert body["mission"]["is_fallback"] is True
    assert body["fallback"] is None
    assert body["diagnostics"]["fallback_first"] is True


def test_recommend_escape_hatch_serves_smallest_step():
    history = [
        {"mission_id": "a01_feeling_word", "status": "rejected"}
        for _ in range(5)
    ]
    res = client.post("/mission/recommend", json=recommend_payload(history=history))
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "escape_hatch"
    assert body["mission"]["mission_id"] == "a01_feeling_word_down"
    assert body["fallback"] is None
    assert body["diagnostics"]["days_without_mission"] == 5


def test_escape_hatch_defers_to_connection_when_it_is_the_bottleneck():
    """B12b: stalled 5+ days AND connection is the bigger gap -> point at connection,
    not the smallest autonomy fallback. Consistency with the normal-day B12 branch."""
    history = [
        {"mission_id": "a01_feeling_word", "status": "rejected"}
        for _ in range(5)
    ]
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.5, "autonomy": 0.6, "connection": 0.1},
            goal={"rhythm": 0.5, "autonomy": 0.7, "connection": 0.7},
            history=history,
        ),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "connection_priority"
    # B12c: same Mission shape as autonomy for the frontend's uniform card,
    # but completable=False and no waypoint/difficulty/delta (fabricated
    # autonomy-only fields — real connection delta happens in /collection/capture).
    assert body["mission"]["axis"] == "connection"
    assert body["mission"]["completable"] is False
    assert body["mission"]["waypoint"] is None
    assert body["mission"]["difficulty"] is None
    assert body["mission"]["delta"] is None
    assert body["rest_message"] is None
    assert body["diagnostics"]["days_without_mission"] == 5
    assert body["diagnostics"]["bottleneck_axis"] == "connection"


def test_recommend_switches_to_connection_when_it_is_the_bottleneck():
    """B12: bottleneck decides today's ONE card — connection behind autonomy swaps
    the autonomy card out entirely (not an add-on note next to it)."""
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.5, "autonomy": 0.6, "connection": 0.1},
            goal={"rhythm": 0.5, "autonomy": 0.7, "connection": 0.7},
        ),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "connection_priority"
    assert body["mission"]["axis"] == "connection"
    assert body["mission"]["completable"] is False
    assert body["mission"]["reason"] == "오늘은 자립 대신 두디를 잡으러 나가보는 건 어때?"
    assert body["fallback"] is None
    assert body["rest_message"] is None
    assert body["diagnostics"]["bottleneck_axis"] == "connection"
    assert body["diagnostics"]["decision_trace"]["situation"] == "connection_priority"


def test_recommend_stays_active_when_autonomy_is_the_bottleneck():
    """Sanity check: the default fixture (autonomy far behind) is untouched by B12."""
    res = client.post("/mission/recommend", json=recommend_payload())
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "active"
    assert body["mission"] is not None
    assert body["diagnostics"]["bottleneck_axis"] == "autonomy"


def test_fallback_completion_advances_stage():
    """B8b: a smaller step still counts — stage 1-9 fallback advances the stage."""
    history = [
        MissionHistoryItem(mission_id="a01_feeling_word_down", status="completed")
    ]
    assert waypoint_planner.completed_stages("autonomy", history) == {1}
    assert waypoint_planner.next_stage("autonomy", history) == 2


def test_signature_fallback_does_not_advance_stage_ten():
    """Signature fallback is preparation: it does not complete stage 10."""
    history = [
        MissionHistoryItem(mission_id=mid, status="completed")
        for mid in (
            "a01_feeling_word", "a02_positive_memory", "a03_finance_touch",
            "a04_balance_glance", "a05_spend_observe", "a06_future_capture_3",
            "a07_direction_confirm", "a08_direction_choose", "a09_check_certificate_fee",
            "a10_signature_plan_down",
        )
    ]
    assert 10 not in waypoint_planner.completed_stages("autonomy", history)
    assert waypoint_planner.next_stage("autonomy", history) == 10


def test_start_stage_reflects_onboarding_autonomy():
    """B8a: a fresh user begins where their onboarding autonomy places them."""
    low = client.post(
        "/mission/recommend",
        json=recommend_payload(current_ari={"rhythm": 0.42, "autonomy": 0.1, "connection": 0.55}),
    ).json()
    high = client.post(
        "/mission/recommend",
        json=recommend_payload(current_ari={"rhythm": 0.42, "autonomy": 0.7, "connection": 0.55}),
    ).json()

    assert low["mission"]["stage"] == 1
    assert high["mission"]["stage"] == 4
    assert low["mission"]["mission_id"] != high["mission"]["mission_id"]
    assert low["diagnostics"]["start_stage"] == 1
    assert high["diagnostics"]["start_stage"] == 4


def test_completing_path_recommends_signature():
    """B8c: the finish line is the completed path (stage 10), not an ARI threshold."""
    res = client.post(
        "/mission/recommend",
        json=recommend_payload(history=AUTONOMY_PATH_1_TO_9),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["mission_state"] == "active"
    assert body["mission"]["mission_id"] == "a10_signature_plan"
    assert body["mission"]["is_signature"] is True
    assert body["fallback"]["mission_id"] == "a10_signature_plan_down"


@pytest.mark.parametrize(
    ("mission_id", "expected_delta"),
    [
        ("a01_feeling_word", 0.018),
        ("a01_feeling_word_down", 0.018),
    ],
)
def test_mission_complete_applies_normal_and_fallback_delta(mission_id, expected_delta):
    res = client.post(
        "/mission/complete",
        json={"user_id": "u1", "mission_id": mission_id, "current_ari": ARI, "energy": 3},
    )
    assert res.status_code == 200
    body = res.json()

    assert body["completed"] is True
    assert body["applied_delta"]["rhythm"] == 0
    assert body["applied_delta"]["connection"] == 0
    assert body["applied_delta"]["autonomy"] == pytest.approx(expected_delta)


@pytest.mark.parametrize(
    ("mission_id", "expected_hana_money"),
    [
        ("a01_feeling_word", 20),       # normal d1
        ("a03_finance_touch", 30),      # normal d2
        ("a09_check_certificate_fee", 40),  # normal d3
        ("a10_signature_plan", 50),     # normal d4 signature
        ("a01_feeling_word_down", 20),  # fallback of d1 -> 20
        ("a03_finance_touch_down", 30),  # fallback priced by parent d2, not own d1
        ("a10_signature_plan_down", 50),  # signature fallback priced by parent d4
    ],
)
def test_mission_complete_reward_by_difficulty(mission_id, expected_hana_money):
    res = client.post(
        "/mission/complete",
        json={"user_id": "u1", "mission_id": mission_id, "current_ari": ARI, "energy": 3},
    )
    assert res.status_code == 200
    assert res.json()["reward"]["hana_money"] == expected_hana_money


def test_every_mission_has_exactly_three_how_to_steps():
    """how_to is a uniform 3-step guideline across the whole catalog."""
    missions = loader.missions()
    assert missions
    for m in missions:
        steps = m.get("how_to")
        assert isinstance(steps, list), m["id"]
        assert len(steps) == 3, f"{m['id']} has {len(steps)} steps"
        assert all(isinstance(s, str) and s.strip() for s in steps), m["id"]


def test_signature_fallback_does_not_unlock_but_normal_signature_does():
    fallback = client.post(
        "/mission/complete",
        json={
            "user_id": "u1",
            "mission_id": "a10_signature_plan_down",
            "current_ari": ARI,
            "energy": 5,
        },
    ).json()
    normal = client.post(
        "/mission/complete",
        json={
            "user_id": "u1",
            "mission_id": "a10_signature_plan",
            "current_ari": ARI,
            "energy": 5,
        },
    ).json()

    assert fallback["signature_available"] is True
    assert fallback["signature_completed"] is False
    assert fallback["contact_unlocked"] is False
    assert fallback["unlocked_contacts"] == []

    assert normal["signature_available"] is True
    assert normal["signature_completed"] is True
    assert normal["contact_unlocked"] is True
    assert normal["unlocked_contacts"][0]["axis"] == "autonomy"


def _signature_capture(count: int):
    return client.post(
        "/collection/capture",
        json={
            "user_id": "u1",
            "pin_id": "pin_hana_signature_seed01",
            "location": {"lat": 37.502, "lng": 127.032},
            "current_ari": {"rhythm": 0.42, "autonomy": 0.30, "connection": 0.56},
            "goal": GOAL,
            "energy": 5,
            "current_collection_count": count,
        },
    ).json()


def test_collection_capture_applies_connection_delta():
    common = client.post(
        "/collection/capture",
        json={
            "user_id": "u1",
            "pin_id": "pin_conv_seed01",
            "location": {"lat": 37.5, "lng": 127.03},
            "current_ari": ARI,
            "goal": GOAL,
            "energy": 3,
            "current_collection_count": 0,
        },
    ).json()
    assert common["applied_delta"]["connection"] == pytest.approx(0.018)
    assert common["updated_ari"]["connection"] == pytest.approx(0.568)
    assert common["unlocked_contacts"] == []


def test_connection_unlock_is_count_based_and_personalised():
    # connection 0.56 → N=3 (state_space.connection_unlock_count); unlock at count+1 >= 3.
    from app.core import state_space

    assert state_space.connection_unlock_count(0.1) == 5
    assert state_space.connection_unlock_count(0.56) == 3
    assert state_space.connection_unlock_count(0.7) == 2

    too_few = _signature_capture(1)   # 1+1=2 < 3 → no unlock
    enough = _signature_capture(4)    # 4+1=5 >= 3 → unlock
    assert too_few["dudy"]["tier"] == "signature"
    assert too_few["unlocked_contacts"] == []
    assert enough["updated_ari"]["connection"] == pytest.approx(0.64)
    assert enough["unlocked_contacts"][0]["axis"] == "connection"


def test_recommend_carries_decision_trace():
    """B10: every recommendation records why (situation) for copy + future LLM."""
    normal = client.post("/mission/recommend", json=recommend_payload()).json()
    low_energy = client.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.42, "autonomy": 0.1, "connection": 0.55}, energy=1
        ),
    ).json()

    assert normal["diagnostics"]["decision_trace"]["situation"] == "active_normal"
    assert low_energy["diagnostics"]["decision_trace"]["situation"] == "active_fallback_first"
    assert low_energy["diagnostics"]["decision_trace"]["primary_constraint"] == "low_energy"


def test_report_summary_is_narrative_without_ari_numbers():
    """B10: report tells direction as a story — no ARI decimals, no raw period code."""
    res = client.post(
        "/report/summary",
        json={
            "user_id": "u1",
            "period": "1m",
            "stats": {
                "total_records": 12,
                "active_days": 8,
                "points": 160,
                "axis_counts": {"rhythm": 6, "autonomy": 4, "connection": 2},
                "ari_start": {"rhythm": 0.2, "autonomy": 0.1, "connection": 0.4},
                "ari_now": {"rhythm": 0.5, "autonomy": 0.3, "connection": 0.42},
            },
        },
    )
    assert res.status_code == 200
    summary = res.json()["summary"]

    assert "이번 달" in summary
    assert "1m" not in summary
    for decimal in ("0.1", "0.2", "0.3", "0.5", "0.42"):
        assert decimal not in summary


def test_forbidden_markers_do_not_reappear_in_app_contract_scope():
    root = Path(__file__).resolve().parents[1]
    scopes = ["app/core", "app/schemas", "app/api", "app/catalog", "app/data"]
    forbidden = [
        "free_text",
        "first_mission",
        "completion_mode",
        "is_bonus",
        "wake_timestamp",
        "morning_promise_time",
    ]
    text_suffixes = {".py", ".json", ".md"}
    haystack = "\n".join(
        path.read_text(encoding="utf-8")
        for scope in scopes
        for path in (root / scope).rglob("*")
        if path.is_file() and path.suffix in text_suffixes
    )

    for marker in forbidden:
        assert marker not in haystack
