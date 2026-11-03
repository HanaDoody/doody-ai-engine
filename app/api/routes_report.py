"""Report summary endpoint with deterministic MVP fallback text."""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core import copy_selector, gap_calculator
from app.llm import report_writer
from app.schemas.report import ReportRequest, ReportResponse
from app.schemas.state import ARISnapshot

router = APIRouter(prefix="/report", tags=["report"])

_PERIOD_LABEL = {"today": "오늘", "1w": "이번 주", "1m": "이번 달", "3m": "지난 세 달"}


def _axis_label(axis: str) -> str:
    return {
        "rhythm": "리듬",
        "autonomy": "자립",
        "connection": "연결",
    }.get(axis, axis)


def _top_axis(axis_counts: dict[str, int]) -> str | None:
    if not axis_counts:
        return None
    axis, count = max(axis_counts.items(), key=lambda item: item[1])
    if count <= 0:
        return None
    return axis


@router.post("/summary", response_model=ReportResponse)
def summary(req: ReportRequest) -> ReportResponse:
    stats = req.stats
    top_axis = _top_axis(stats.axis_counts)

    highlights: list[str] = [
        f"{stats.active_days}일 동안 두디와 기록을 남겼어.",
        f"하나머니 {stats.points}이 쌓였어.",
    ]
    if top_axis:
        highlights.append(f"이번에는 {_axis_label(top_axis)} 쪽 기록이 가장 많이 쌓였어.")
    if stats.unlocked_contacts:
        highlights.append(f"새로운 접점 {len(stats.unlocked_contacts)}개가 열렸어.")
    if stats.collected_dudy:
        highlights.append(f"두디 {len(stats.collected_dudy)}개를 만났어.")

    start = stats.ari_start
    now = stats.ari_now

    # B11: goal이 오면 recommend와 같은 gap→velocity→recovery_drag 수식을 report
    # period 스케일로 재사용해 병목축·순항축·축별 흐름(flow)을 구한다. goal 없는
    # 구버전 백엔드는 조용히 건너뛴다(하위호환) — 숫자(gap 자체)는 절대 노출 안
    # 하고, 축 이름과 gap/velocity 버킷(카테고리)만 LLM 서사 재료로 넘어간다.
    bottleneck: str | None = None
    best_axis: str | None = None
    flow: dict | None = None
    if stats.goal is not None:
        trajectory = [
            ARISnapshot(ari=start, timestamp="start"),
            ARISnapshot(ari=now, timestamp="now"),
        ]
        gap_v = gap_calculator.gap(stats.goal, now)
        velocity_v = gap_calculator.velocity(trajectory)
        drag_v = gap_calculator.recovery_drag(gap_v, velocity_v)
        bottleneck = gap_calculator.bottleneck_axis(drag_v)
        best_axis = min(
            ("autonomy", "connection"), key=lambda axis: getattr(drag_v, axis)
        )
        flow = {
            axis: {
                "gap": copy_selector.gap_bucket(getattr(gap_v, axis)),
                "velocity": copy_selector.velocity_bucket(getattr(velocity_v, axis)),
            }
            for axis in ("rhythm", "autonomy", "connection")
        }
        highlights.append(f"다음엔 {_axis_label(bottleneck)} 쪽도 살짝 챙겨보면 좋겠어.")

    period_label = _PERIOD_LABEL.get(req.period, "그동안")
    # Read each axis's direction and tell it as a story — no scores, no ARI numbers,
    # and no counts (무평가). Counts live only in highlights above.
    axis_sentences = " ".join(
        s for s in (
            copy_selector.axis_narrative("rhythm", start.rhythm, now.rhythm),
            copy_selector.axis_narrative("autonomy", start.autonomy, now.autonomy),
            copy_selector.axis_narrative("connection", start.connection, now.connection),
        ) if s
    )
    fallback_summary = (
        f"{period_label} 동안 두디와 함께한 기록이 쌓였어. "
        f"{axis_sentences} "
        "숫자보다 중요한 건 네가 다시 한 칸씩 남겼다는 거야."
    ).strip()
    # L1b: humanize via Sonnet 5 from the raw directions; deterministic story is the fallback.
    directions = {
        "rhythm": copy_selector.direction(start.rhythm, now.rhythm),
        "autonomy": copy_selector.direction(start.autonomy, now.autonomy),
        "connection": copy_selector.direction(start.connection, now.connection),
    }
    summary_text = report_writer.summary(
        directions,
        period_label,
        fallback=fallback_summary,
        bottleneck_axis=bottleneck,
        best_axis=best_axis,
        flow=flow,
    )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return ReportResponse(
        summary=summary_text,
        highlights=highlights,
        generated_at=generated_at,
    )
