"""
llm/client.py — LLM 생성 API 호출의 단일 길목 (chokepoint)

역할
  text_generator.py · report_writer.py 가 직접 provider를 부르지 않고,
  전부 이 파일을 거친다. 즉 "어느 모델을 어떻게 부르나"는 여기서만 결정한다.
  (호출 주체는 동적 텍스트가 필요한 엔드포인트뿐: onboarding/mission/chat/report.
   core/ 의 도메인 수학은 LLM을 부르지 않는다 — 결정/서술 분리.)

여기 한 곳에 가두는 것
  - API 키 / provider 선택            (config.py · .env)
  - 모델 라우팅 · 파라미터            (llm_config.json)
  - 에러 · 타임아웃 · 거절
  - 폴백: LLM 이상 시 결정론 문구로 강등 (서비스 안 죽게)

L0 (배선) 원칙 — 이 파일은 절대 예외를 밖으로 던지지 않는다.
  disabled / 키 없음 / SDK 없음 / API 오류 / 타임아웃 / 거절 / 빈 응답
  → 전부 None 반환 → 호출부가 결정론 문구로 폴백.
  켜기: (1) ANTHROPIC_API_KEY 설정  (2) llm_config.enabled=true. 둘 다 필요.
"""
import time

from app.catalog import loader
from app.config import get_settings
from app.llm import metrics


def _config() -> dict:
    return loader.llm_config()


def _enabled(cfg: dict, settings) -> bool:
    """순수 판정: (config.enabled 또는 LLM_ENABLED env) AND API 키."""
    enabled = bool(cfg.get("enabled", False)) or bool(getattr(settings, "llm_enabled", False))
    return enabled and bool(settings.anthropic_api_key)


def is_enabled() -> bool:
    """LLM은 (config.enabled 또는 LLM_ENABLED env) AND API 키가 모두 있을 때만 사용된다.

    레포 기본 llm_config.enabled=false. 프로덕션은 소스를 안 건드리고 env로만 켠다:
    LLM_ENABLED=true + ANTHROPIC_API_KEY. (키가 없으면 무엇을 켜도 꺼짐 — 안전장치.)
    """
    return _enabled(_config(), get_settings())


def complete(prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str | None:
    """프롬프트 1회 호출 → 텍스트, 또는 실패 시 None. (호출부는 폴백을 가져야 한다.)"""
    if not is_enabled():
        metrics.record_call(enabled=False, ok=False)
        return None

    cfg = _config()
    try:
        import anthropic  # SDK를 하드 의존성으로 만들지 않도록 지연 임포트
    except ImportError:
        metrics.record_call(enabled=True, ok=False)
        return None

    start = time.perf_counter()
    try:
        # 재시도 정책 명시: 넉넉한 timeout(중앙값 ~3s 대비 큰 헤드룸)으로 정상 콜의
        # 헛-타임아웃→재시도 스톰을 없애고, max_retries를 낮게 캡해 최악 지연 tail을 묶는다.
        # 그래도 실패하면 호출부가 결정론 폴백으로 받는다 (D0).
        client = anthropic.Anthropic(
            api_key=get_settings().anthropic_api_key or None,
            timeout=float(cfg.get("timeout_seconds", 20)),
            max_retries=int(cfg.get("max_retries", 1)),
        )
        kwargs: dict = {
            "model": cfg.get("model", "claude-sonnet-5"),
            "max_tokens": int(max_tokens or cfg.get("max_tokens", 200)),
            "thinking": {"type": "disabled"},  # 한두 문장 — 사고 오버헤드 불필요
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
    except Exception:
        metrics.record_call(enabled=True, ok=False,
                            latency_ms=(time.perf_counter() - start) * 1000)
        return None

    latency_ms = (time.perf_counter() - start) * 1000
    if getattr(response, "stop_reason", None) == "refusal":
        metrics.record_call(enabled=True, ok=False, latency_ms=latency_ms)
        return None

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    usage = getattr(response, "usage", None)
    tokens = None
    if usage is not None:
        tokens = int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "output_tokens", 0) or 0)
    metrics.record_call(enabled=True, ok=bool(text), latency_ms=latency_ms, tokens=tokens)
    return text or None


def generate(prompt: str, *, system: str | None = None, fallback: str, max_tokens: int | None = None) -> str:
    """복잡한 폴백 로직을 호출부에서 반복하지 않도록: 실패하면 항상 fallback을 돌려준다."""
    text = complete(prompt, system=system, max_tokens=max_tokens)
    return text if text is not None else fallback
