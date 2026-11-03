"""회복 리포트 입출력 — api_contract §2.9.

핵심: 수치는 백엔드가 stats로 주입, LLM은 서술만 (숫자 생성 X).
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.mission import Contact
from app.schemas.state import ARIVector, Dudy


class RecentMission(BaseModel):
    title: str
    axis: str
    date: str


class ReportStats(BaseModel):
    """백엔드가 집계해 주입하는 수치.

    goal이 있으면 gap_calculator로 병목축(bottleneck_axis)을 재계산해 리포트에
    반영한다(recommend가 매 콜 계산하는 것과 같은 수식, report period 스케일).
    goal이 없으면(구버전 백엔드) 조용히 건너뛴다 — 하위호환.
    """

    total_records: int
    active_days: int
    points: int
    axis_counts: dict[str, int]
    ari_start: ARIVector
    ari_now: ARIVector
    goal: Optional[ARIVector] = None
    collected_dudy: list[Dudy] = Field(default_factory=list)
    unlocked_contacts: list[Contact] = Field(default_factory=list)
    recent_missions: list[RecentMission] = Field(default_factory=list)


class ReportRequest(BaseModel):
    user_id: str
    period: str
    stats: ReportStats


class ReportResponse(BaseModel):
    summary: str
    highlights: list[str]
    generated_at: str
