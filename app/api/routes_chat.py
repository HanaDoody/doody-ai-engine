"""Chat endpoint: crisis guard → doody-voice reply (deterministic fallback)."""
from fastapi import APIRouter

from app.llm import safety, text_generator
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

_REST_KEYWORDS = (
    "tired",
    "exhausted",
    "burnout",
    "rest",
    "stop",
    "\uc9c0\uccd0",      # 지쳐
    "\ud798\ub4e4",      # 힘들
    "\uc26c\uace0",      # 쉬고
    "\uc26c\uc5b4",      # 쉬어
    "\ubabb \ud558\uaca0",  # 못 하겠
    "\ubabb\ud558\uaca0",   # 못하겠
)
_DOWNSHIFT_KEYWORDS = (
    "hard",
    "difficult",
    "too much",
    "smaller",
    "\uc5b4\ub824",      # 어려
    "\ubb34\ub9ac",      # 무리
    "\ubd80\ub2f4",      # 부담
    "\uc791\uac8c",      # 작게
    "\ub354 \uc26c\uc6b4",  # 더 쉬운
)

_REPLIES = {
    "offer_rest": "\uc624\ub298\uc740 \uc870\uae08 \uc26c\uc5b4\uac00\ub3c4 \uad1c\ucc2e\uc544. \ub9ac\ub4ec\ub9cc \ubd99\uc7a1\uc544\ub3c4 \ucda9\ubd84\ud574.",
    "offer_downshift": "\uad1c\ucc2e\uc544. \uc9c0\uae08\uc740 \ub354 \uc26c\uc6b4 \uce78\uc73c\ub85c \ub0ae\ucdb0\uc11c \uac00\ubcf4\uc790.",
    "none": "\ub9d0\ud574\uc918\uc11c \uace0\ub9c8\uc6cc. \uc9c0\uae08 \ud560 \uc218 \uc788\ub294 \ub9cc\ud07c\ub9cc \ucc9c\ucc9c\ud788 \uac00\ubcf4\uc790.",
}


def _suggested_action(req: ChatRequest) -> str:
    text = req.message.lower()
    if any(keyword in text for keyword in _REST_KEYWORDS):
        return "offer_rest"
    if req.context and req.context.current_mission_id:
        if any(keyword in text for keyword in _DOWNSHIFT_KEYWORDS):
            return "offer_downshift"
    return "none"


@router.post("/message", response_model=ChatResponse)
def message(req: ChatRequest) -> ChatResponse:
    # Crisis belt: never send a crisis disclosure to the copy LLM. Fixed safe reply,
    # no mission/downshift nudge. Frontend crisis button handles real resources.
    if safety.is_crisis(req.message):
        return ChatResponse(reply=safety.safe_reply(), signals=None, suggested_action="none")

    action = _suggested_action(req)
    reply = text_generator.chat_reply(req.message, action, fallback=_REPLIES[action])
    return ChatResponse(reply=reply, signals=None, suggested_action=action)
