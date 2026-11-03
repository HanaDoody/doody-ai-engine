"""자연어 → 축 신호 (MVP: 보류/stub). seam 인터페이스만 고정.

구현(키워드/임베딩/LLM)은 나중에. 저녁 리듬 텍스트·chat message에 공통.
설계 노트: app/nlu/README.md (prototype similarity → 지도 probe 승급 경로).
"""
from app.schemas.state import ARIVector


def extract_signal(text: str) -> ARIVector | None:
    """text → {rhythm, autonomy, connection}. MVP에선 None(보류)."""
    return None
