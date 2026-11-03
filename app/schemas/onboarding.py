"""온보딩 입출력 — api_contract §2.2~2.3."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.state import ARIVector

GapAxis = Literal["rhythm", "autonomy", "connection", "composite", "unknown"]
Period = Literal["today", "1w", "1m", "3m"]


# --- /onboarding/intro (ARI 없음) ---
class IntroRequest(BaseModel):
    user_id: str
    gap_axis: GapAxis
    energy: int = Field(ge=1, le=5)


class IntroResponse(BaseModel):
    direction_promise: str
    message: str


# --- /onboarding/complete (v₀·g 생성) ---
class Diagnosis(BaseModel):
    """축별 4지선다 raw 답. 1=회복 높음, 4=낮음."""

    rhythm: int = Field(ge=1, le=4)
    autonomy: int = Field(ge=1, le=4)
    connection: int = Field(ge=1, le=4)


class MyDataInput(BaseModel):
    """마이데이터 연동 여부. MVP는 linked 여부만 사용한다."""

    linked: bool = False


class CompleteRequest(BaseModel):
    user_id: str
    goal_choice: str
    diagnosis: Diagnosis
    period: Optional[Period] = None
    gap_axis: Optional[GapAxis] = None
    mydata: Optional[MyDataInput] = None


class CompleteResponse(BaseModel):
    initial_ari: ARIVector
    goal: ARIVector
    period: Period
    start_axis: str
    plan_summary: str
    diagnostics: dict | None = None


# --- /onboarding/recommend-period (목표→기간 도출, MVP 추천=확정) ---
class RecommendPeriodRequest(BaseModel):
    user_id: str
    goal_choice: str
    # gap_axis·energy 는 상태 기반 보정용 seam — MVP(목표 하드코딩)에선 미반영.
    gap_axis: Optional[GapAxis] = None
    energy: Optional[int] = Field(default=None, ge=1, le=5)


class RecommendPeriodResponse(BaseModel):
    recommended_period: Period
    options: list[Period] = ["today", "1w", "1m", "3m"]
    message: str
