"""공통 상태 객체 — api_contract §1."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Axis = Literal["rhythm", "autonomy", "connection"]
MissionAxis = Literal["autonomy", "connection"]
DudyTier = Literal["common", "rare", "signature"]


class ARIVector(BaseModel):
    """현재 상태 v / 목표 g / 변화량 Δ 에 공통으로 쓰는 3축 벡터."""

    rhythm: float = Field(ge=0.0, le=1.0)
    autonomy: float = Field(ge=0.0, le=1.0)
    connection: float = Field(ge=0.0, le=1.0)


class ARISnapshot(BaseModel):
    """궤적(velocity 계산용)의 원소."""

    ari: ARIVector
    timestamp: str  # ISO 8601


class Dudy(BaseModel):
    """도감 캐릭터. signature 두디만 하나금융 해금 열쇠가 된다."""

    id: str
    tier: DudyTier
    axis: Optional[MissionAxis] = None
    earned_reason: str


class RhythmMorningLog(BaseModel):
    """아침 리듬 이력 원소."""

    timestamp: str
    did_check_in: bool = True


class RhythmEveningLog(BaseModel):
    """저녁 리듬 이력 원소."""

    text: str
    timestamp: str


class RhythmHistory(BaseModel):
    """2리듬 이력. v_rhythm 존재-EMA의 입력."""

    morning: list[RhythmMorningLog] = Field(default_factory=list)
    evening: list[RhythmEveningLog] = Field(default_factory=list)
