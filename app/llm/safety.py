"""위기 안전벨트 — 유저 자유텍스트(chat·evening)가 카피 LLM에 가기 전 앞단.

명백한 위기 신호가 있으면 LLM을 아예 부르지 않고 고정 안전문구를 돌려준다.
엔진은 '악화 안 시키고 넘김'까지만 — 실제 위기대응(상담번호·기관)은 프론트 위기버튼·
외부기관 몫(역할분리). 키워드 방식은 오탐·누락이 있는 최소 바닥선이지, 완전한 탐지가 아니다.
"""
from app.catalog import loader


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()


def is_crisis(text: str | None) -> bool:
    """텍스트에 위기 키워드가 하나라도 있으면 True."""
    if not text:
        return False
    haystack = _normalize(text)
    for term in loader.crisis_terms().get("keywords", []):
        if _normalize(term) in haystack:
            return True
    return False


def safe_reply() -> str:
    """위기 감지 시 돌려줄 고정 문구 (즉흥·조언 금지)."""
    return loader.crisis_terms().get("safe_reply", "지금 많이 힘든 것 같아. 혼자 감당하지 않아도 돼.")
