"""Mission/contact DTOs for api_contract sections 1 and 2.4-2.6."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.rhythm import Reward
from app.schemas.state import ARISnapshot, ARIVector, Dudy, MissionAxis, RhythmHistory

# B12: connection_priority — mission=null이지만 gated와 다르다(게이트는 열려있음).
# bottleneck_axis가 connection을 가리키면 오늘의 유일한 카드를 자립 미션 대신
# 연결(지도/포획) 화면으로 전환하라는 신호. frontend는 이 상태를 받으면 자립 카드
# 대신 연결 탭을 오늘의 액션으로 보여준다(문구 하나 덧붙이는 게 아니라 카드 자체 전환).
MissionState = Literal["active", "gated", "escape_hatch", "connection_priority"]
MissionStatus = Literal["recommended", "completed", "rejected"]
MissionType = Literal["CHECK", "IMAGE", "LINK"]


class Mission(BaseModel):
    """Static catalog mission plus display fields.

    `id` preserves the existing v0.7 contract. `mission_id` is surfaced for the
    frontend/downshift flow where completion sends the actual completed id.

    B12c: axis="connection" uses this SAME shape for the frontend's "today's
    mission" card (one response model, one render path) even though it isn't a
    catalog mission. `completable=False` marks that — waypoint/difficulty/delta
    don't mean anything for it (no catalog waypoint graph, no completion via
    /mission/complete, no delta from this call) so they stay None rather than
    faking autonomy-shaped values. Storage stays separate: autonomy missions go
    to mission_logs via /mission/complete; connection is /collection/capture +
    collection_captures, unaffected by this DTO sharing.
    """

    id: str
    mission_id: str
    axis: MissionAxis
    stage: Optional[int] = None
    waypoint: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    delta: Optional[ARIVector] = None
    title: str
    description: Optional[str] = None
    mission_type: MissionType = "CHECK"
    required_count: int = Field(default=1, ge=1)
    is_signature: bool = False
    is_fallback: bool = False
    fallback_mission_id: Optional[str] = None
    goal_tags: list[str] = Field(default_factory=list)
    how_to: list[str] = Field(min_length=3, max_length=3)
    reason: str
    completable: bool = True


class Contact(BaseModel):
    """Hana contact unlocked by an axis-specific signature completion."""

    id: str
    title: str
    axis: MissionAxis


class MissionHistoryItem(BaseModel):
    mission_id: str
    status: MissionStatus
    axis: Optional[MissionAxis] = None
    waypoint: Optional[str] = None
    difficulty: Optional[int] = None
    timestamp: Optional[str] = None


class RecommendRequest(BaseModel):
    user_id: str
    current_ari: ARIVector
    goal: ARIVector
    recent_trajectory: list[ARISnapshot] = Field(default_factory=list)
    energy: int = Field(ge=1, le=5)
    rhythm_history: RhythmHistory
    history: list[MissionHistoryItem] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    mission: Optional[Mission] = None
    fallback: Optional[Mission] = None
    mission_state: MissionState
    rest_message: Optional[str] = None
    unlocked_contacts: list[Contact] = Field(default_factory=list)
    v_rhythm: float = Field(ge=0.0, le=1.0)
    diagnostics: dict | None = None


class MissionCompleteRequest(BaseModel):
    user_id: str
    mission_id: str
    current_ari: ARIVector
    energy: int = Field(ge=1, le=5)


class MissionCompleteResponse(BaseModel):
    updated_ari: ARIVector
    applied_delta: ARIVector
    eta: float
    reward: Reward
    completed: bool = True
    signature_available: bool = False
    signature_completed: bool = False
    contact_unlocked: bool = False
    collected_dudy: list[Dudy] = Field(default_factory=list)
    unlocked_contacts: list[Contact] = Field(default_factory=list)
    message: str


class RejectRequest(BaseModel):
    user_id: str
    mission_id: str
    reason_text: Optional[str] = None


class RejectResponse(BaseModel):
    action: Literal["downshift", "same_waypoint", "different_axis", "rest"]
    message: str
    rest_option: bool
    candidates: list[Mission] = Field(default_factory=list)
    diagnostics: dict | None = None
