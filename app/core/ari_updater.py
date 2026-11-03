"""ARI update math for api_contract section 2.5."""
from app.schemas.state import ARIVector


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def apply(current: ARIVector, delta: ARIVector, eta: float) -> tuple[ARIVector, ARIVector]:
    """Return (updated_ari, applied_delta), where applied_delta = eta * delta."""
    applied_delta = ARIVector(
        rhythm=eta * delta.rhythm,
        autonomy=eta * delta.autonomy,
        connection=eta * delta.connection,
    )
    updated = ARIVector(
        rhythm=_clamp(current.rhythm + applied_delta.rhythm),
        autonomy=_clamp(current.autonomy + applied_delta.autonomy),
        connection=_clamp(current.connection + applied_delta.connection),
    )
    return updated, applied_delta
