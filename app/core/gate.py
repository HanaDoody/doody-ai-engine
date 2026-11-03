"""Mission gate math for api_contract section 2.4."""
from app.catalog import loader


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def gate(v_rhythm: float, days_without_mission: int) -> float:
    """Return the scalar gate applied to autonomy/connection recovery drag."""
    config = loader.gate_config()
    r_floor = float(config["r_floor"])
    r_open = float(config["r_open"])
    escape_days = int(config["escape_days"])
    floor_key = "gate_floor_escape" if days_without_mission >= escape_days else "gate_floor_normal"
    gate_floor = float(config[floor_key])

    if r_open <= r_floor:
        raise ValueError("gate_config.r_open must be greater than r_floor")

    raw_gate = (v_rhythm - r_floor) / (r_open - r_floor)
    return max(gate_floor, _clamp(raw_gate))
