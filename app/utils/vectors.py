"""벡터 연산 / clamp / normalize. (3축 ARIVector 헬퍼)"""
from app.schemas.state import ARIVector

AXES = ("rhythm", "autonomy", "connection")


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def add(a: ARIVector, b: ARIVector, *, clamp: bool = True) -> ARIVector:
    vals = {ax: getattr(a, ax) + getattr(b, ax) for ax in AXES}
    if clamp:
        vals = {ax: clamp01(v) for ax, v in vals.items()}
    return ARIVector(**vals)


def sub(a: ARIVector, b: ARIVector) -> ARIVector:
    return ARIVector(**{ax: getattr(a, ax) - getattr(b, ax) for ax in AXES})


def scale(a: ARIVector, k: float) -> ARIVector:
    return ARIVector(**{ax: getattr(a, ax) * k for ax in AXES})
