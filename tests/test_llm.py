"""L0/L1: the LLM chokepoint falls back safely and only ships valid copy."""
from fastapi.testclient import TestClient

from app.llm import client, prompts, report_writer, safety, text_generator
from app.main import app
from tests.test_v07_contract import recommend_payload

DIRECTIONS = {"rhythm": "flat", "autonomy": "up", "connection": "flat"}

REPORT_PAYLOAD = {
    "user_id": "u1",
    "period": "1m",
    "stats": {
        "total_records": 12,
        "active_days": 8,
        "points": 160,
        "axis_counts": {"rhythm": 6, "autonomy": 4, "connection": 2},
        "ari_start": {"rhythm": 0.2, "autonomy": 0.1, "connection": 0.4},
        "ari_now": {"rhythm": 0.5, "autonomy": 0.3, "connection": 0.42},
    },
}

http = TestClient(app)

TRACE = {
    "situation": "active_normal",
    "primary_constraint": "on_track",
    "stage": 1,
    "waypoint": "feeling_face",
    "fallback_first": False,
}


# --- L0: chokepoint safety ---
def test_complete_returns_none_when_disabled():
    assert client.complete("아무 프롬프트") is None


def test_generate_falls_back_when_disabled():
    assert client.generate("p", system="s", fallback="결정론 문구") == "결정론 문구"


# --- L1: guardrail (prompts.valid) ---
def test_valid_accepts_short_no_number():
    assert prompts.valid("짧고 숫자 없는 반말 문장이야", 80) is True


def test_valid_rejects_empty_number_and_too_long():
    assert prompts.valid("", 80) is False
    assert prompts.valid("여기 3개 남았어", 80) is False          # 아라비아 숫자 → 무평가 위반
    assert prompts.valid("가" * 100, 80) is False                # 길이 초과


# --- L1: text_generator (LLM mocked) ---
def test_reason_uses_valid_llm_text(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "오늘은 작은 칸부터 같이 가보자")
    assert text_generator.mission_reason(TRACE, fallback="폴백") == "오늘은 작은 칸부터 같이 가보자"


def test_reason_falls_back_on_number(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "3단계를 넘겼어")
    assert text_generator.mission_reason(TRACE, fallback="폴백") == "폴백"


def test_reason_falls_back_on_too_long(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "가" * 200)
    assert text_generator.mission_reason(TRACE, fallback="폴백") == "폴백"


def test_complete_message_falls_back_when_disabled():
    out = text_generator.complete_message({"kind": "normal", "axis": "autonomy"}, fallback="폴백")
    assert out == "폴백"


# --- L1: route wiring (LLM output flows into the response) ---
def test_route_recommend_humanizes_reason(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "오늘은 이 작은 칸부터 같이 가보자")
    res = http.post("/mission/recommend", json=recommend_payload())
    assert res.status_code == 200
    assert res.json()["mission"]["reason"] == "오늘은 이 작은 칸부터 같이 가보자"


# --- B12: connection_priority swaps today's one card, humanized like any rest_message ---
def test_route_recommend_humanizes_connection_priority(monkeypatch):
    captured = {}

    def _fake_complete(prompt, **kwargs):
        captured["prompt"] = prompt
        return "오늘은 자립 말고 두디 잡으러 나가볼까"

    monkeypatch.setattr(client, "complete", _fake_complete)
    res = http.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.5, "autonomy": 0.6, "connection": 0.1},
            goal={"rhythm": 0.5, "autonomy": 0.7, "connection": 0.7},
        ),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mission_state"] == "connection_priority"
    # B12c: mission이 populated이라 routes_mission.py가 mission_reason(build_reason)을
    # 부른다 — rest_message는 active와 마찬가지로 None.
    assert body["mission"]["axis"] == "connection"
    assert body["mission"]["completable"] is False
    assert body["mission"]["reason"] == "오늘은 자립 말고 두디 잡으러 나가볼까"
    assert body["rest_message"] is None
    # 톤 검증: "쉬어도 돼" 위로 요청이 아니라 초대 요청으로 분기됐는지.
    assert "두디를 잡으러 나가보자" in captured["prompt"]
    assert "위로" not in captured["prompt"]


def test_route_recommend_connection_priority_falls_back_when_disabled():
    res = http.post(
        "/mission/recommend",
        json=recommend_payload(
            current_ari={"rhythm": 0.5, "autonomy": 0.6, "connection": 0.1},
            goal={"rhythm": 0.5, "autonomy": 0.7, "connection": 0.7},
        ),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mission_state"] == "connection_priority"
    assert body["mission"]["reason"] == "오늘은 자립 대신 두디를 잡으러 나가보는 건 어때?"
    assert body["rest_message"] is None


def test_route_recommend_falls_back_to_deterministic_when_disabled():
    # _llm_disabled fixture is active → deterministic bucket copy (반말).
    res = http.post("/mission/recommend", json=recommend_payload())
    assert res.status_code == 200
    assert res.json()["mission"]["reason"].endswith("괜찮아.") or "칸" in res.json()["mission"]["reason"]


# --- L1c: crisis safety belt ---
def test_is_crisis_detects_signals():
    assert safety.is_crisis("요즘 자꾸 죽고 싶어") is True
    assert safety.is_crisis("자해하고 싶어") is True
    assert safety.is_crisis("다 사라지고 싶다") is True


def test_is_crisis_ignores_benign_and_empty():
    assert safety.is_crisis("오늘 좀 피곤했어") is False
    assert safety.is_crisis("") is False
    assert safety.is_crisis(None) is False


def test_safe_reply_present():
    assert len(safety.safe_reply()) > 0


def test_chat_crisis_bypasses_llm(monkeypatch):
    # Even if the LLM would answer, a crisis message never reaches it.
    monkeypatch.setattr(client, "complete", lambda *a, **k: "LLM이 생성한 답")
    res = http.post("/chat/message", json={"user_id": "u", "message": "요즘 자꾸 죽고 싶어"}).json()
    assert res["reply"] == safety.safe_reply()
    assert res["suggested_action"] == "none"


def test_chat_humanizes_reply(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "그랬구나, 오늘은 그냥 여기까지여도 괜찮아.")
    res = http.post("/chat/message", json={"user_id": "u", "message": "오늘 뭘 해야 할지 모르겠어"}).json()
    assert res["reply"] == "그랬구나, 오늘은 그냥 여기까지여도 괜찮아."


def test_chat_falls_back_and_keeps_rule_action():
    # disabled → deterministic reply; '힘들' → offer_rest (규칙기반 유지).
    res = http.post("/chat/message", json={"user_id": "u", "message": "너무 힘들어"}).json()
    assert res["suggested_action"] == "offer_rest"
    assert "쉬어가도" in res["reply"]


def test_evening_crisis_bypasses_llm(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "LLM이 생성한 답")
    res = http.post("/rhythm/evening", json={"user_id": "u", "text": "다 사라지고 싶어"}).json()
    assert res["reply"] == safety.safe_reply()
    assert res["reward"]["hana_money"] > 0  # 위기여도 보상은 지급


def test_evening_humanizes_reply(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "그런 하루였구나. 남겨줘서 고마워, 오늘은 여기까지면 돼.")
    res = http.post("/rhythm/evening", json={"user_id": "u", "text": "그냥 누워있었어"}).json()
    assert res["reply"] == "그런 하루였구나. 남겨줘서 고마워, 오늘은 여기까지면 돼."


def test_evening_prompt_requires_friendlike_empathy_or_praise_then_closure():
    prompt = prompts.build_evening("사람 만나는 게 싫어 외로워")

    assert "사람 만나는 게 싫어 외로워" in prompt
    assert "첫 번째 문장: 공감 또는 칭찬" in prompt
    assert "두 번째 문장: 친구다운 마무리" in prompt
    assert "서로 어긋나는 마음" in prompt
    assert "그 행동을 구체적으로, 아끼지 말고 칭찬" in prompt
    assert "사용자가 말하지 않은 감정·행동·성과·생활 패턴" in prompt
    assert "오늘도 잘 마무리했어" in prompt
    assert "이 기록이 내일의 기준이 될 거야" in prompt
    assert "정확히 두 문장, 줄바꿈 없이" in prompt


def test_morning_greeting_humanized(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "일어났구나, 천천히 시작하자.")
    res = http.post(
        "/rhythm/morning", json={"user_id": "u", "timestamp": "2026-07-04T08:00:00Z", "energy": 2}
    ).json()
    assert res["greeting"] == "일어났구나, 천천히 시작하자."


def test_morning_evening_fall_back_when_disabled():
    m = http.post(
        "/rhythm/morning", json={"user_id": "u", "timestamp": "2026-07-04T08:00:00Z", "energy": 3}
    ).json()
    e = http.post("/rhythm/evening", json={"user_id": "u", "text": "그냥 그런 하루"}).json()
    assert m["greeting"] == "안녕 좋은 아침이야!"
    assert e["reply"] == "오늘 하루도 수고 많았어. 이야기해줘서 고마워."


# --- L1b: report summary ---
def test_summary_uses_valid_llm_text(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "이번 달은 리듬을 꾸준히 붙잡았고 자립도 한 걸음 나아갔어")
    out = report_writer.summary(DIRECTIONS, "이번 달", fallback="폴백")
    assert out == "이번 달은 리듬을 꾸준히 붙잡았고 자립도 한 걸음 나아갔어"


def test_summary_allows_digits(monkeypatch):
    # summary는 긴 서사라 숫자 차단을 풀었다 — 있어도 폴백 안 됨(길이만 검사).
    monkeypatch.setattr(client, "complete", lambda *a, **k: "이번 달엔 3번쯤 마음이 흔들렸지만 다시 붙잡았어")
    out = report_writer.summary(DIRECTIONS, "이번 달", fallback="폴백")
    assert out == "이번 달엔 3번쯤 마음이 흔들렸지만 다시 붙잡았어"


def test_summary_falls_back_on_too_long(monkeypatch):
    # B11: _MAX_SUMMARY 140→240 (개인화 서사가 더 김) — 240 넘는 걸로 테스트.
    monkeypatch.setattr(client, "complete", lambda *a, **k: "가" * 250)
    assert report_writer.summary(DIRECTIONS, "이번 달", fallback="폴백") == "폴백"


def test_route_report_falls_back_and_has_no_ari_numbers():
    # disabled → deterministic summary; 무평가: ARI 소수·기간코드 없음.
    res = http.post("/report/summary", json=REPORT_PAYLOAD)
    assert res.status_code == 200
    summary = res.json()["summary"]
    assert "이번 달" in summary and "1m" not in summary
    for decimal in ("0.1", "0.2", "0.3", "0.42"):
        assert decimal not in summary


def test_route_report_humanizes_summary(monkeypatch):
    monkeypatch.setattr(client, "complete", lambda *a, **k: "이번 달은 천천히, 그래도 꾸준히 이어졌어")
    res = http.post("/report/summary", json=REPORT_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["summary"] == "이번 달은 천천히, 그래도 꾸준히 이어졌어"


# --- B11: report bottleneck axis (gap_calculator reused at report-period scale) ---
def test_report_without_goal_has_no_bottleneck_highlight():
    # 하위호환: goal 없는 구버전 백엔드 요청은 그대로 동작하고 병목 highlight도 없다.
    res = http.post("/report/summary", json=REPORT_PAYLOAD)
    assert res.status_code == 200
    assert not any("챙겨보면" in h for h in res.json()["highlights"])


def test_report_with_goal_adds_bottleneck_highlight():
    payload = {
        **REPORT_PAYLOAD,
        "stats": {
            **REPORT_PAYLOAD["stats"],
            # connection gap(0.4-0.42=-0.02)보다 autonomy gap(0.7-0.3=0.4)이 훨씬 커서
            # velocity 보정 후에도 autonomy가 병목이어야 한다.
            "goal": {"rhythm": 0.5, "autonomy": 0.7, "connection": 0.4},
        },
    }
    res = http.post("/report/summary", json=payload)
    assert res.status_code == 200
    highlights = res.json()["highlights"]
    assert any("자립 쪽도 살짝 챙겨보면 좋겠어" in h for h in highlights)
    # 숫자(gap 자체)는 어디에도 노출되지 않는다 (무평가).
    assert not any(any(ch.isdigit() for ch in h) for h in highlights if "챙겨보면" in h)


def test_summary_without_flow_uses_simple_direction_prompt(monkeypatch):
    # goal 없음(flow=None) → bottleneck_axis만 줘도 무시되고 기존 단순 방향 서사로.
    captured = {}

    def _fake_complete(prompt, **kwargs):
        captured["prompt"] = prompt
        return "이번 달은 리듬을 꾸준히 붙잡았어"

    monkeypatch.setattr(client, "complete", _fake_complete)
    out = report_writer.summary(DIRECTIONS, "이번 달", fallback="폴백", bottleneck_axis="autonomy")
    assert out == "이번 달은 리듬을 꾸준히 붙잡았어"
    assert "특히 신경 쓰면 좋은 축" not in captured["prompt"]
    assert "나아졌다" in captured["prompt"]  # DIRECTIONS의 autonomy=up → _DIR 문구


def test_summary_with_flow_builds_personalized_prompt(monkeypatch):
    captured = {}

    def _fake_complete(prompt, **kwargs):
        captured["prompt"] = prompt
        return "리듬은 거의 다 왔고, 연결은 여유 있고, 자립은 아직 갈 길이 남았지만 속도가 붙었어"

    monkeypatch.setattr(client, "complete", _fake_complete)
    flow = {
        "rhythm": {"gap": "close", "velocity": "fast"},
        "autonomy": {"gap": "far", "velocity": "fast"},
        "connection": {"gap": "close", "velocity": "stalled"},
    }
    out = report_writer.summary(
        DIRECTIONS,
        "이번 달",
        fallback="폴백",
        bottleneck_axis="autonomy",
        best_axis="connection",
        flow=flow,
    )
    assert out == "리듬은 거의 다 왔고, 연결은 여유 있고, 자립은 아직 갈 길이 남았지만 속도가 붙었어"
    prompt = captured["prompt"]
    assert "가장 신경 쓰면 좋은 축" in prompt and "돈·자립" in prompt
    assert "가장 순항 중인 축" in prompt and "바깥·연결" in prompt
    assert "목표까지 아직 많이 남음" in prompt  # autonomy gap=far
    assert "최근엔 거의 제자리" in prompt  # connection velocity=stalled
    # 무평가: gap·velocity 원본 실수값(ARI 소수 패턴 "0.")은 프롬프트에 안 들어간다.
    # (지시문의 "140~220자" 같은 길이 숫자는 LLM에게 주는 형식 지시일 뿐 상태 수치가 아니라 허용.)
    assert "0." not in prompt


def test_report_route_with_goal_passes_flow_end_to_end(monkeypatch):
    captured = {}

    def _fake_complete(prompt, **kwargs):
        captured["prompt"] = prompt
        return "리듬이랑 연결은 잘 굴러가고, 자립만 천천히 따라오는 중이야"

    monkeypatch.setattr(client, "complete", _fake_complete)
    payload = {
        **REPORT_PAYLOAD,
        "stats": {
            **REPORT_PAYLOAD["stats"],
            "goal": {"rhythm": 0.5, "autonomy": 0.7, "connection": 0.4},
        },
    }
    res = http.post("/report/summary", json=payload)
    assert res.status_code == 200
    assert res.json()["summary"] == "리듬이랑 연결은 잘 굴러가고, 자립만 천천히 따라오는 중이야"
    assert "가장 순항 중인 축" in captured["prompt"]
