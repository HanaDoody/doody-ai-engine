"""Onboarding endpoints for the v0.7 stateless engine contract."""
from fastapi import APIRouter, HTTPException

from app.core import goal_space, period_planner, state_space
from app.schemas.onboarding import (
    CompleteRequest,
    CompleteResponse,
    IntroRequest,
    IntroResponse,
    RecommendPeriodRequest,
    RecommendPeriodResponse,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

def _start_axis(req: CompleteRequest, initial, goal) -> str:
    if req.gap_axis in {"autonomy", "connection"}:
        return req.gap_axis
    gaps = {
        "autonomy": goal.autonomy - initial.autonomy,
        "connection": goal.connection - initial.connection,
    }
    return max(gaps, key=gaps.get)


@router.post("/intro", response_model=IntroResponse)
def intro(req: IntroRequest) -> IntroResponse:
    return IntroResponse(
        direction_promise="최근 잘 썼다고 느낀 돈 하나 떠올리기",
        message="만나서 반가워! 나는 두디야. 오늘부터 나랑 매일 한 칸씩 나아가보자. 준비됐지?",
    )


@router.post("/complete", response_model=CompleteResponse)
def complete(req: CompleteRequest) -> CompleteResponse:
    try:
        initial_ari = state_space.compute_initial_ari(req.diagnosis)
        goal = goal_space.goal_vector(req.goal_choice)
        period, _ = period_planner.recommend_period(req.goal_choice)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    start_axis = _start_axis(req, initial_ari, goal)
    mydata_linked = bool(req.mydata and req.mydata.linked)
    return CompleteResponse(
        initial_ari=initial_ari,
        goal=goal,
        period=period,
        start_axis=start_axis,
        plan_summary="계획 요약 (plan summary)",
        diagnostics={
            "goal_choice": req.goal_choice,
            "requested_period": req.period,
            "period_source": "goal_choice",
            "gap_axis": req.gap_axis,
            "mydata_linked": mydata_linked,
            "mission_created": False,
        },
    )


@router.post("/recommend-period", response_model=RecommendPeriodResponse)
def recommend_period(req: RecommendPeriodRequest) -> RecommendPeriodResponse:
    period, message = period_planner.recommend_period(
        req.goal_choice, gap_axis=req.gap_axis, energy=req.energy
    )
    return RecommendPeriodResponse(recommended_period=period, message=message)
