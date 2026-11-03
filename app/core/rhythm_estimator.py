"""Rhythm existence EMA for api_contract section 2.4."""
from datetime import datetime

from app.catalog import loader
from app.schemas.state import RhythmHistory


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _date_key(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return timestamp[:10]


def estimate_v_rhythm(rhythm_history: RhythmHistory, seed: float | None = None) -> float:
    """Estimate v_rhythm from morning/evening existence only.

    seed is the EMA starting point (day-0 prior). It comes from the user's onboarding
    rhythm answer (carried in current_ari.rhythm) so the gate starts personalised;
    when None it falls back to the configured v0_rhythm. As real logs accumulate they
    dominate the seed.
    """
    config = loader.gate_config()
    v = float(seed) if seed is not None else float(config["v0_rhythm"])
    alpha_up = float(config["alpha_up"])
    alpha_down = float(config["alpha_down"])

    morning_dates = {
        _date_key(log.timestamp)
        for log in rhythm_history.morning
        if log.did_check_in
    }
    evening_dates = {_date_key(log.timestamp) for log in rhythm_history.evening}

    for day in sorted(morning_dates | evening_dates):
        a_t = ((1.0 if day in morning_dates else 0.0) + (1.0 if day in evening_dates else 0.0)) / 2.0
        alpha = alpha_up if a_t >= v else alpha_down
        v = v + alpha * (a_t - v)

    return _clamp(v)
