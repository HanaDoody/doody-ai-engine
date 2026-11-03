"""L1: 두디 voice 프롬프트 + decision_trace → 유저 프롬프트 빌더 + 출력 검증.

말투·문구 규칙이 사는 단 한 곳. 팀이 톤을 다듬을 땐 여기만 고치면 된다.
LLM에는 구조화된 상태(trace)와 아래 gloss만 넣는다 — 사용자 원문·숫자는 넣지 않는다.
"""
import re

SYSTEM_PROMPT = (
    "너는 '두디'야. 세상이랑 거리를 둔 청년이 아주 작은 하루를 다시 시작하도록 "
    "곁에서 돕는 캐릭터야.\n\n"
    "말투\n"
    "- 한국어 반말. 따뜻하고 담담하게, 재촉하지 마.\n"
    "- 짧게. 지시된 문장 수(보통 한 문장)만. 인사말·따옴표·이모지·군더더기 없이 문장만 내.\n"
    "- 친근하지만 가볍지 않게. 툭 건네는 위로에 가깝게.\n\n"
    "절대 규칙 (어기면 실패)\n"
    "- 숫자·점수·퍼센트·단계 번호·'며칠째' 같은 평가 지표 절대 쓰지 마.\n"
    "- 잘한다/못한다 평가하거나 몰아붙이지 마. '그것도 괜찮아'의 태도.\n"
    "- 주어진 상태 밖의 사실을 지어내지 마. 상태를 사람 말로 옮기기만 해.\n\n"
    "너는 결정하지 않아. 뭘 할지는 이미 정해졌고, 너는 그 결정을 따뜻한 한 마디로 옮길 뿐이야."
)

# --- trace enum → LLM이 알아듣는 한국어 gloss (숫자는 넣지 않는다) ---
_SITUATION = {
    "active_normal": "순항 중, 자립 다음 칸을 권함",
    "active_fallback_first": "컨디션이 낮아 더 작은 칸을 먼저 권함",
    "active_signature": "자립 길의 마지막 칸(접점이 열리는 칸)",
    "gated_warmup": "리듬이 아직 안 데워져 오늘은 리듬만 붙잡는 날",
    "gated_done": "자립 길을 끝까지 걸어 오늘은 리듬만 붙잡는 날",
    "escape_hatch": "한동안 멈춰 있어 가장 작은 한 걸음을 슬쩍 권함",
    "connection_priority": "오늘은 자립보다 연결(바깥)이 더 뒤처져 있어, 자립 대신 두디를 잡으러 나가보길 권함",
}
_CONSTRAINT = {
    "low_rhythm": "리듬 토대가 아직 약함",
    "low_energy": "오늘 기운이 적음",
    "stalled": "한동안 멈춰 있음",
    "path_done": "자립 길을 끝냄",
    "on_track": "무리 없이 나아가는 중",
    "connection_behind": "연결이 자립보다 더 뒤처짐",
}
_WAYPOINT = {
    "feeling_face": "돈에 붙은 감정을 마주하기",
    "positive_memory": "최근 잘한 일 하나 떠올리기",
    "finance_touch": "금융 앱을 살짝 열어보기",
    "balance_observe": "잔액을 한 번 보기",
    "spend_observe": "소비 하나 살펴보기",
    "future_exploration": "관심 가는 미래를 둘러보기",
    "direction_confirm": "관심 방향 확인하기",
    "direction_choose": "먼저 볼 방향 고르기",
    "resource_plan": "필요한 자원 하나 확인하기",
    "signature": "다음 행동을 실제로 정하기",
}
_COMPLETION = {
    "normal": "오늘의 한 칸을 넘겼다",
    "fallback": "더 작은 칸으로 한 걸음 옮겼다",
    "signature_unlock": "자립 길의 마지막 칸을 완성했고 새로운 접점이 열렸다",
    "signature_prep": "마지막 준비 행동을 남겼다 (접점은 아직 열리지 않음)",
}
_AXIS = {"autonomy": "돈·자립", "connection": "바깥·연결", "rhythm": "리듬"}


def _gloss(table: dict, key, default: str = "") -> str:
    return table.get(key, default) if key is not None else default


def build_reason(trace: dict) -> str:
    situation = trace.get("situation")
    # B12c: connection_priority now ships as a populated Mission (not
    # mission=null), so routes_mission.py calls mission_reason here, not
    # build_rest — the "go capture instead" invitation lives in this prompt.
    if situation == "connection_priority":
        ask = "오늘은 자립 대신 두디를 잡으러 나가보자고 담담하게 권하는 1문장. 재촉하지 말고."
        return (
            "[상황]\n"
            f"- 국면: {_gloss(_SITUATION, situation)}\n"
            f"- 제약: {_gloss(_CONSTRAINT, trace.get('primary_constraint'))}\n"
            "[요청]\n"
            f"{ask} 30~80자, 반말. 문장만 출력."
        )
    return (
        "[상황]\n"
        f"- 국면: {_gloss(_SITUATION, situation)}\n"
        f"- 제약: {_gloss(_CONSTRAINT, trace.get('primary_constraint'))}\n"
        f"- 오늘 할 일의 의미: {_gloss(_WAYPOINT, trace.get('waypoint'), '작은 다음 한 걸음')}\n"
        "[요청]\n"
        "'왜 지금 이 작은 행동인지'를 담은 문장 1개. 30~80자, 반말. 문장만 출력."
    )


def build_rest(trace: dict) -> str:
    return (
        "[상황]\n"
        f"- 국면: {_gloss(_SITUATION, trace.get('situation'))}\n"
        f"- 제약: {_gloss(_CONSTRAINT, trace.get('primary_constraint'))}\n"
        "[요청]\n"
        "오늘은 행동 미션 대신 리듬만 붙잡아도 괜찮다는 담담한 위로 1문장. 25~60자, 반말. 문장만 출력."
    )


_DIR = {"up": "나아졌다", "flat": "유지했다", "down": "조금 물러났다"}
_GAP_KO = {
    "close": "목표에 거의 닿았음",
    "mid": "목표까지 중간쯤 남음",
    "far": "목표까지 아직 많이 남음",
}
_VEL_KO = {
    "stalled": "최근엔 거의 제자리",
    "slow": "천천히 나아가는 중",
    "fast": "빠르게 나아가는 중",
}


def build_summary(
    directions: dict,
    period_label: str,
    bottleneck_axis: str | None = None,
    best_axis: str | None = None,
    flow: dict | None = None,
) -> str:
    """B11: goal이 있으면(flow 채워짐) gap·velocity 버킷으로 세 축을 각각 짚는
    개인화 서사를 요청한다. goal이 없으면(구버전 백엔드) 기존 단순 방향 서사로
    내려간다 — 하위호환.
    """
    if flow:
        lines = "\n".join(
            f"- {_AXIS.get(axis, axis)}: {_GAP_KO.get(f['gap'], '')}, {_VEL_KO.get(f['velocity'], '')}"
            for axis, f in flow.items()
        )
        callouts = ""
        if bottleneck_axis:
            callouts += (
                f"\n[가장 신경 쓰면 좋은 축]\n{_AXIS.get(bottleneck_axis, bottleneck_axis)}"
                " — 목표 대비 아직 가장 남아있음"
            )
        if best_axis:
            callouts += (
                f"\n[가장 순항 중인 축]\n{_AXIS.get(best_axis, best_axis)}"
                " — 목표 대비 가장 여유 있음"
            )
        return (
            f"[{period_label}, 세 축의 흐름]\n{lines}\n{callouts}\n\n"
            "[요청]\n"
            "위 세 축을 각각 최소 한 마디씩, 서로 다르게 짚어줘 — 하나로 뭉뚱그리지 마. "
            "가장 순항 중인 축은 반드시 언급하고, 가장 신경 쓰면 좋은 축은 다그치지 말고 "
            "자연스럽게 다음으로 이어지게. '힘내'·'잘하고 있어' 같은 누구에게나 할 수 있는 "
            "격려 대신, 이번 기간의 흐름을 정확히 짚는 것 자체로 챙기는 느낌을 내. "
            "140~220자, 3~4문장, 반말. 숫자·퍼센트·순위 표현 없이 사람 말로만. 문장만 출력."
        )

    lines = "\n".join(
        f"- {_AXIS.get(axis, axis)}: {_DIR.get(d, '유지했다')}"
        for axis, d in directions.items()
    )
    return (
        f"[{period_label}의 흐름]\n{lines}\n"
        "[요청]\n"
        "위 흐름을 담담하게 이야기로 풀어줘. 60~140자, 반말. "
        "숫자·점수 쓰지 말고 방향만 사람 말로. 문장만 출력."
    )


def build_complete(situation: dict) -> str:
    return (
        "[상황]\n"
        f"- 방금 일어난 일: {_gloss(_COMPLETION, situation.get('kind'), '오늘의 한 칸을 넘겼다')}\n"
        f"- 움직인 영역: {_gloss(_AXIS, situation.get('axis'))}\n"
        "[요청]\n"
        "완료를 담담하게 인정해주는 문장 1개. 30~70자, 반말. 과장된 칭찬 금지. 문장만 출력."
    )


_ENERGY = {1: "기운이 거의 없는", 2: "기운이 적은", 3: "그럭저럭인", 4: "기운이 좀 있는", 5: "기운이 좋은"}


def build_greeting(energy: int) -> str:
    return (
        "[상황]\n"
        f"아침 리듬을 찍었고, 오늘은 {_ENERGY.get(energy, '그럭저럭인')} 날.\n"
        "[요청]\n"
        "아침 인사 한 문장. 20~50자, 반말. 부담 없이 담담하게. 문장만 출력."
    )


def build_evening(text: str) -> str:
    return (
        "[사용자의 저녁 한 줄]\n"
        f"{text}\n"
        "[역할]\n"
        "사용자의 저녁 한 줄을 읽고 진짜 친구처럼 답한다. 상담하거나 감정을 분석하지 말고, "
        "말을 제대로 들은 뒤 공감하거나 칭찬하고 오늘을 함께 마무리한다.\n"
        "[첫 번째 문장: 공감 또는 칭찬]\n"
        "- 사용자가 말한 가장 구체적인 상황을 자연스럽게 되짚는다.\n"
        "- 힘들거나 복잡한 이야기에는 형식적이지 않게 공감한다. 서로 어긋나는 마음은 둘 다 담는다.\n"
        "- 무언가 시도하거나 해낸 이야기에는 그 행동을 구체적으로, 아끼지 말고 칭찬한다.\n"
        "- 사용자가 말하지 않은 감정·행동·성과·생활 패턴은 추측하거나 과장하지 않는다.\n"
        "- '그랬구나', '힘들었겠다'만 붙이는 빈 공감이나 무조건적인 '잘했어'는 쓰지 않는다.\n"
        "[두 번째 문장: 친구다운 마무리]\n"
        "- 오늘을 편안하게 닫는 마무리·응원·동행 중 입력에 가장 어울리는 하나를 건넨다.\n"
        "- '고생 많았어', '편히 쉬자', '내가 옆에 있을게', '오늘은 마음 놓아도 돼' 같은 표현은 "
        "상황에 맞게 자연스럽게 쓴다.\n"
        "- 첫 문장을 반복하지 말고, 새로운 행동·내일 할 일·질문·조언·해결책·교훈·미션을 제시하지 않는다.\n"
        "[친구 같은 말투]\n"
        "- 따뜻하고 자연스러운 반말. 상담사처럼 해설하거나 진단하지 않는다.\n"
        "- '오', '그래도', '진짜', '잘했네'는 어울릴 때만 쓰고 같은 상투어를 반복하지 않는다.\n"
        "- '오늘도 잘 마무리했어', '이 기록이 내일의 기준이 될 거야'처럼 입력과 무관한 기록 완료 문구는 금지한다.\n"
        "[출력]\n"
        "정확히 두 문장, 줄바꿈 없이 한 칸 띄어 이어 쓴다. 전체 45~100자의 따뜻한 반말. 답변 문장만 출력."
    )


_CHAT_ACTION = {
    "offer_rest": "오늘은 쉬어가도 된다고 부담 없이 권하기",
    "offer_downshift": "더 작은 걸로 낮추자고 권하기",
    "none": "특별한 제안 없이 곁에서 들어주기",
}


def build_chat(message: str, action: str) -> str:
    return (
        "[사용자가 한 말]\n"
        f"{message}\n"
        "[두디의 방향]\n"
        f"{_CHAT_ACTION.get(action, '곁에서 들어주기')}\n"
        "[요청]\n"
        "반말로 2~3문장 안에서 따뜻하게 답해. 40~120자. 몰아붙이지 말고, 조언은 가볍게. 문장만 출력."
    )


def valid(text: str | None, max_len: int, *, forbid_digits: bool = True) -> bool:
    """빈 문자열·길이 초과면 실패 → 호출부가 결정론 폴백.

    forbid_digits=True(기본): 아라비아 숫자 포함도 실패(무평가). 짧은 한 줄 문구용.
    summary처럼 긴 서사는 forbid_digits=False로 길이만 검사(프롬프트로 숫자 억제).
    """
    if not text:
        return False
    if len(text) > max_len:
        return False
    if forbid_digits and re.search(r"\d", text):
        return False
    return True
