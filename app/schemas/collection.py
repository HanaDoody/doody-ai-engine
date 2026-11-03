"""두디 포획 입출력 — api_contract §2.7."""
from pydantic import BaseModel, Field

from app.schemas.mission import Contact
from app.schemas.rhythm import Reward
from app.schemas.state import ARIVector, Dudy


class Location(BaseModel):
    lat: float
    lng: float


class CaptureRequest(BaseModel):
    user_id: str
    pin_id: str
    location: Location
    current_ari: ARIVector
    goal: ARIVector
    energy: int = Field(ge=1, le=5)
    # 이번 포획 '전까지' 모은 두디 수. 엔진이 이 포획(+1)을 더해 N과 비교한다.
    current_collection_count: int = Field(default=0, ge=0)


class CaptureResponse(BaseModel):
    dudy: Dudy
    reward: Reward
    updated_ari: ARIVector
    applied_delta: ARIVector
    collected_dudy: list[Dudy] = Field(default_factory=list)
    unlocked_contacts: list[Contact] = Field(default_factory=list)
