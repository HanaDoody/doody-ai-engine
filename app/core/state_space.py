"""Initial ARI state from onboarding diagnosis."""
from app.catalog import loader
from app.schemas.onboarding import Diagnosis
from app.schemas.state import ARIVector


def _choice_value(raw_choice: int, values: dict) -> float:
    key = str(raw_choice)
    if key not in values:
        raise ValueError("diagnosis choices must be mapped in onboarding_templates.choice_values")
    return float(values[key])


def compute_initial_ari(diagnosis: Diagnosis) -> ARIVector:
    """Map diagnosis integers to v0.

    Rhythm is a warm-start seed: the onboarding rhythm answer sets where v_rhythm
    begins, so a user who reports good rhythm starts with the gate already open and
    one who reports poor rhythm warms up first. From then on v_rhythm is estimated
    from actual two-rhythm existence logs, which overwrite the seed within days
    (self-report -> measured). See rhythm_estimator.estimate_v_rhythm.
    """
    onboarding = loader.onboarding_questions()
    values = onboarding["choice_values"] if isinstance(onboarding, dict) else {}
    return ARIVector(
        rhythm=_choice_value(diagnosis.rhythm, values),
        autonomy=_choice_value(diagnosis.autonomy, values),
        connection=_choice_value(diagnosis.connection, values),
    )


def start_stage_from_autonomy(autonomy: float) -> int:
    """Map an autonomy readiness value to the autonomy path's starting stage.

    Onboarding diagnosis feeds initial_ari.autonomy, which returns to the engine
    as current_ari.autonomy. A fresh user begins their staged path here instead of
    always at stage 1 — the first place the state vector routes behaviour.
    Bounds are configured in gate_config.autonomy_start_stage_bounds (checked low→high).
    """
    bounds = loader.gate_config().get("autonomy_start_stage_bounds", [])
    for band in bounds:
        if autonomy <= float(band["max_autonomy"]):
            return int(band["stage"])
    return int(bounds[-1]["stage"]) if bounds else 1


def connection_unlock_count(connection: float) -> int:
    """Map onboarding connection readiness to how many Dudy unlock the contact.

    Mirror of start_stage_from_autonomy: onboarding personalises the journey length.
    More isolated (low connection) → longer journey (more Dudy); each capture stays
    gentle. Bounds in gate_config.connection_unlock_count_bounds (checked low→high).
    """
    bounds = loader.gate_config().get("connection_unlock_count_bounds", [])
    for band in bounds:
        if connection <= float(band["max_connection"]):
            return int(band["count"])
    return int(bounds[-1]["count"]) if bounds else 5
