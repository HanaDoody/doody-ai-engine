"""Gap, velocity, recovery drag, and bottleneck axis math."""
from app.schemas.state import ARISnapshot, ARIVector, MissionAxis


def _internal_vector(rhythm: float, autonomy: float, connection: float) -> ARIVector:
    """Build an internal vector that may contain signed intermediate values."""
    return ARIVector.model_construct(
        rhythm=rhythm,
        autonomy=autonomy,
        connection=connection,
    )


def gap(goal: ARIVector, current: ARIVector) -> ARIVector:
    """gap = g - v."""
    return _internal_vector(
        rhythm=goal.rhythm - current.rhythm,
        autonomy=goal.autonomy - current.autonomy,
        connection=goal.connection - current.connection,
    )


def velocity(trajectory: list[ARISnapshot]) -> ARIVector:
    """velocity = v_last - v_previous. Return zero if history is too short."""
    if len(trajectory) < 2:
        return ARIVector(rhythm=0.0, autonomy=0.0, connection=0.0)

    previous = trajectory[-2].ari
    current = trajectory[-1].ari
    return _internal_vector(
        rhythm=current.rhythm - previous.rhythm,
        autonomy=current.autonomy - previous.autonomy,
        connection=current.connection - previous.connection,
    )


def recovery_drag(gap_v: ARIVector, velocity_v: ARIVector) -> ARIVector:
    """recovery_drag = gap - velocity."""
    return _internal_vector(
        rhythm=gap_v.rhythm - velocity_v.rhythm,
        autonomy=gap_v.autonomy - velocity_v.autonomy,
        connection=gap_v.connection - velocity_v.connection,
    )


def bottleneck_axis(recovery_drag_v: ARIVector) -> MissionAxis:
    """Return the larger actionable drag axis; rhythm is not a mission axis."""
    if recovery_drag_v.connection > recovery_drag_v.autonomy:
        return "connection"
    return "autonomy"
