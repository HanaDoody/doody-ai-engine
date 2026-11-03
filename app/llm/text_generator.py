"""동적 텍스트 — 미션 reason / rest_message / 완료 message.

패턴: 프롬프트 조립 → client.complete → prompts.valid 검증 → 실패 시 fallback.
LLM이 꺼졌거나(키·플래그) 실패·거절·규칙위반이면 항상 결정론 fallback을 돌려준다.
결정(무엇을 할지)은 core가 하고, 여기선 그 결정을 문장으로 옮기기만 한다.
"""
from app.llm import client, metrics, prompts

_MAX_REASON = 80
_MAX_REST = 60
_MAX_COMPLETE = 70
_MAX_CHAT = 120
_MAX_GREETING = 50
_MAX_EVENING = 100


def _outcome(text: str | None, ok: bool) -> str:
    """가드 통과=used_llm, LLM은 답했지만 가드 탈락=guard_trip, 그 외=fallback."""
    if ok:
        return "used_llm"
    return "guard_trip" if text else "fallback"


def _humanize(prompt: str, fallback: str, max_len: int) -> str:
    text = client.complete(prompt, system=prompts.SYSTEM_PROMPT)
    ok = prompts.valid(text, max_len)
    metrics.record_generation(outcome=_outcome(text, ok))
    return text if ok else fallback


def mission_reason(trace: dict, fallback: str) -> str:
    return _humanize(prompts.build_reason(trace), fallback, _MAX_REASON)


def rest_message(trace: dict, fallback: str) -> str:
    return _humanize(prompts.build_rest(trace), fallback, _MAX_REST)


def complete_message(situation: dict, fallback: str) -> str:
    return _humanize(prompts.build_complete(situation), fallback, _MAX_COMPLETE)


def chat_reply(message: str, action: str, fallback: str) -> str:
    """유저 원문을 받아 답을 생성. 위기 판정은 호출부(라우트)가 먼저 처리한 뒤 부른다."""
    text = client.complete(prompts.build_chat(message, action), system=prompts.SYSTEM_PROMPT)
    # 채팅은 대화라 숫자가 자연스러울 수 있어 길이만 검증한다.
    ok = prompts.valid(text, _MAX_CHAT, forbid_digits=False)
    metrics.record_generation(outcome=_outcome(text, ok))
    return text if ok else fallback


def greeting(energy: int, fallback: str) -> str:
    return _humanize(prompts.build_greeting(energy), fallback, _MAX_GREETING)


def evening_reply(text_line: str, fallback: str) -> str:
    """저녁 한 줄을 받아 답을 생성. 위기 판정은 호출부가 먼저 처리한 뒤 부른다."""
    text = client.complete(prompts.build_evening(text_line), system=prompts.SYSTEM_PROMPT)
    ok = prompts.valid(text, _MAX_EVENING, forbid_digits=False)
    metrics.record_generation(outcome=_outcome(text, ok))
    return text if ok else fallback
