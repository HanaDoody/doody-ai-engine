"""환경설정 / 상수. (.env 로딩)"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """런타임 설정. 환경변수에서 읽는다."""

    app_version: str = "0.7.0"
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    # 프로덕션에서 소스(llm_config.enabled=false)를 안 건드리고 LLM을 켜는 env 스위치.
    llm_enabled: bool = os.getenv("LLM_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
