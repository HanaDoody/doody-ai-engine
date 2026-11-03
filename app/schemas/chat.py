"""채팅 입출력 — api_contract §2.7 (무상태 단일 턴)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.state import ARIVector


class ChatContext(BaseModel):
    """무상태라 매 호출에 백엔드가 실어주는 맥락."""

    current_ari: Optional[ARIVector] = None
    current_mission_id: Optional[str] = None
    energy: Optional[int] = Field(default=None, ge=1, le=5)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    context: Optional[ChatContext] = None


class ChatResponse(BaseModel):
    reply: str
    signals: Optional[dict[str, float]] = None  # MVP: extract_signal stub, null 가능
    suggested_action: Literal["none", "offer_downshift", "offer_rest"] = "none"
