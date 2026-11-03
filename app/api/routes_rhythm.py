"""POST /rhythm/morning and /rhythm/evening (doody-voice copy over deterministic core)."""
from fastapi import APIRouter

from app.core import rhythm_handler
from app.llm import safety, text_generator
from app.schemas.rhythm import EveningRequest, EveningResponse, MorningRequest, MorningResponse

router = APIRouter(prefix="/rhythm", tags=["rhythm"])


@router.post("/morning", response_model=MorningResponse)
def morning(req: MorningRequest) -> MorningResponse:
    resp = rhythm_handler.morning()
    resp.greeting = text_generator.greeting(req.energy, fallback=resp.greeting)
    return resp


@router.post("/evening", response_model=EveningResponse)
def evening(req: EveningRequest) -> EveningResponse:
    resp = rhythm_handler.evening(req.text)
    # Crisis belt: a crisis line never reaches the copy LLM. Reward stays (no penalty).
    if safety.is_crisis(req.text):
        resp.reply = safety.safe_reply()
    else:
        resp.reply = text_generator.evening_reply(req.text, fallback=resp.reply)
    return resp
