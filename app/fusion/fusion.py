"""선택지 ARI + 자연어 신호 → 보정 ARI (MVP: passthrough).

신호가 없으면(보류) 선택지 ARI를 그대로 돌려준다.
"""
from app.schemas.state import ARIVector


def fuse(choice_ari: ARIVector, signal: ARIVector | None) -> ARIVector:
    if signal is None:
        return choice_ari
    raise NotImplementedError  # TODO: 가중 결합
