"""Morning/evening rhythm response helpers."""
from app.catalog import loader
from app.schemas.rhythm import EveningResponse, MorningResponse, Reward
from app.schemas.state import Dudy


def _dudy_by_id(dudy_id: str) -> Dudy | None:
    for item in loader.dudy_templates():
        if item.get("id") == dudy_id:
            return Dudy(**item)
    return None


def morning() -> MorningResponse:
    """Return the MVP morning rhythm response."""
    reward = Reward(hana_money=int(loader.gate_config()["morning_reward_hana_money"]))
    return MorningResponse(
        reward=reward,
        greeting="안녕 좋은 아침이야!",
        collected_dudy=[],
    )


def evening(text: str) -> EveningResponse:
    """Return the MVP evening rhythm response with signals deferred."""
    reward = Reward(hana_money=int(loader.gate_config()["evening_reward_hana_money"]))
    first_night = _dudy_by_id("d_first_night")
    return EveningResponse(
        reward=reward,
        signals=None,
        reply="오늘 하루도 수고 많았어. 이야기해줘서 고마워.",
        collected_dudy=[first_night] if first_night is not None else [],
    )
