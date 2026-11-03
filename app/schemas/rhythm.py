"""2리듬 입출력 — api_contract §2.11~2.12."""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.state import Dudy


class Reward(BaseModel):
    """사용자 행동에 대한 균일 보상."""

    hana_money: int = Field(ge=0)


class MorningRequest(BaseModel):
    user_id: str
    timestamp: str
    energy: int = Field(ge=1, le=5)


class MorningResponse(BaseModel):
    reward: Reward
    greeting: str
    collected_dudy: list[Dudy] = Field(default_factory=list)


class EveningRequest(BaseModel):
    user_id: str
    text: str


class EveningResponse(BaseModel):
    reward: Reward
    signals: Optional[dict[str, float]] = None
    reply: str
    collected_dudy: list[Dudy] = Field(default_factory=list)
