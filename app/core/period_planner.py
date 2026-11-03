"""Goal-based period recommendation for onboarding.

MVP uses a deterministic lookup from goal_templates.json. The optional
gap_axis/energy arguments are accepted as future seams but do not affect the
result yet.
"""
from app.catalog import loader
from app.schemas.onboarding import Period

_PERIOD_MESSAGE: dict[str, str] = {
    "today": "오늘 하루만 가볍게 시작해볼게요.",
    "1w": "1주 플랜을 추천해요. 작은 단계로 나눠볼게요.",
    "1m": "1개월을 추천해요. 작은 단계로 나눠볼게요.",
    "3m": "3개월 동안 천천히 보고 가볼게요.",
}

_DEFAULT_PERIOD: Period = "1w"


def recommend_period(
    goal_choice: str,
    gap_axis: str | None = None,
    energy: int | None = None,
) -> tuple[Period, str]:
    """Return (recommended_period, message)."""
    goal = loader.goals().get(goal_choice, {})
    period: Period = goal.get("recommended_period", _DEFAULT_PERIOD)
    message = _PERIOD_MESSAGE.get(period, _PERIOD_MESSAGE[_DEFAULT_PERIOD])
    return period, message
