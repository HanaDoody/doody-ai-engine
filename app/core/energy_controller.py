"""Energy to eta (step size), backed by gate_config.json."""
from app.catalog import loader


def eta(energy: int) -> float:
    """Convert today's energy level (1..5) to an ARI update multiplier."""
    table = loader.gate_config()["eta_by_energy"]
    key = str(energy)
    if key not in table:
        raise ValueError("energy must be between 1 and 5")
    return float(table[key])
