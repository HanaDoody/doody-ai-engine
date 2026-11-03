"""회복 리포트 서술 — api_contract §2.9.

🚨 LLM은 숫자를 만들지 않는다. 축별 방향(up/flat/down, goal 있으면 gap·velocity
   버킷)만 받아 이야기로 푼다. 숫자 사실(카운트·포인트)은 라우트의 결정론
   highlights에만 있고 여기 안 온다.
   summary는 긴 서사라 길이만 검증한다(숫자 차단 X) — prompts.valid(forbid_digits=False).

B11: goal 있으면(flow 채워짐) 세 축을 각각 짚는 개인화 서사라 기존보다 길다 —
   _MAX_SUMMARY를 140→240으로, max_tokens도 이 콜에서만 늘렸다(기본 200으로는
   140~220자 한글 서사가 중간에 잘릴 수 있음).
"""
from app.llm import client, prompts

_MAX_SUMMARY = 240
_SUMMARY_MAX_TOKENS = 300


def summary(
    directions: dict,
    period_label: str,
    fallback: str,
    bottleneck_axis: str | None = None,
    best_axis: str | None = None,
    flow: dict | None = None,
) -> str:
    prompt = prompts.build_summary(directions, period_label, bottleneck_axis, best_axis, flow)
    text = client.complete(prompt, system=prompts.SYSTEM_PROMPT, max_tokens=_SUMMARY_MAX_TOKENS)
    return text if prompts.valid(text, _MAX_SUMMARY, forbid_digits=False) else fallback
