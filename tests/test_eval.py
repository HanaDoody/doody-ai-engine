"""evals 하네스 + llm/metrics 검증."""
from app.llm import metrics
from evals import run_eval


def test_metrics_snapshot_rates():
    metrics.reset()
    metrics.record_call(enabled=False, ok=False)                 # disabled
    metrics.record_call(enabled=True, ok=True, latency_ms=100, tokens=30)
    metrics.record_call(enabled=True, ok=True, latency_ms=300, tokens=50)
    metrics.record_generation(outcome="used_llm")
    metrics.record_generation(outcome="guard_trip")             # fallback + guard
    metrics.record_generation(outcome="fallback")
    snap = metrics.snapshot()

    assert snap["calls"] == 3
    assert snap["disabled"] == 1
    assert snap["api_ok"] == 2
    assert snap["generations"] == 3
    assert snap["used_llm"] == 1
    assert snap["fallback"] == 2          # guard_trip counts as fallback
    assert snap["guard_trips"] == 1
    assert snap["fallback_rate"] == round(2 / 3, 3)
    assert snap["guard_trip_rate"] == round(1 / 3, 3)
    assert snap["latency_ms_avg"] == 200.0
    assert snap["tokens_total"] == 80


def test_faithfulness_rule_catches_contradiction():
    # fallback_first인데 "크게 가자"는 국면과 모순 → 실패
    assert run_eval.score_faithfulness("active_fallback_first", "오늘은 크게 가보자") is False
    # 상황에 맞는 문구 → 통과
    assert run_eval.score_faithfulness("active_fallback_first", "가볍게 작은 칸부터 둘게") is True


def test_tone_heuristic():
    assert run_eval.score_tone("작은 걸음이야.") is True
    assert run_eval.score_tone("작은 걸음이에요") is False
    assert run_eval.score_tone("여기까지 왔습니다.") is False


def test_fallback_copy_is_self_consistent():
    """카탈로그 회귀 가드: 모든 상황의 폴백 문구가 감사를 통과해야 한다."""
    for row in run_eval.audit_fallback_copy():
        assert row["len_ok"], row["situation"]
        assert row["no_digit"], row["situation"]
        assert row["faithful"], row["situation"]
        assert row["tone_ok"], row["situation"]


def test_guard_mechanism_all_pass():
    for row in run_eval.check_guard_mechanism():
        assert row["pass"], row["case"]


def test_llm_enabled_env_override():
    """레포 config.enabled=false여도 LLM_ENABLED env로 켤 수 있다 (키가 있을 때만)."""
    from app.llm import client

    class _S:
        anthropic_api_key = "sk-test"
        llm_enabled = True

    assert client._enabled({"enabled": False}, _S()) is True    # env on + key
    _S.llm_enabled = False
    assert client._enabled({"enabled": False}, _S()) is False    # config off + env off
    assert client._enabled({"enabled": True}, _S()) is True       # config on + key
    _S.llm_enabled = True
    _S.anthropic_api_key = ""
    assert client._enabled({"enabled": False}, _S()) is False     # 켰어도 키 없으면 꺼짐


def test_run_eval_populates_observability():
    result = run_eval.run_eval()
    assert result["mode"] in {"offline", "live"}
    obs = result["observability"]
    assert obs["generations"] >= len(run_eval._FAITHFULNESS)
