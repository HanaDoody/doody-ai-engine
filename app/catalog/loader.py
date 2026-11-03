"""data/*.json 카탈로그 로딩·검증.

"정의"는 AI 엔진 소유(정적). 사용자 이력은 백엔드 DB에 있다.
"""
import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def _load(name: str) -> object:
    with open(_DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def missions() -> list[dict]:
    return _load("mission_templates.json")  # type: ignore[return-value]


def contacts() -> list[dict]:
    return _load("contact_templates.json")  # type: ignore[return-value]


def goals() -> dict:
    return _load("goal_templates.json")  # type: ignore[return-value]


def onboarding_questions() -> list[dict]:
    return _load("onboarding_templates.json")  # type: ignore[return-value]


def gate_config() -> dict:
    return _load("gate_config.json")  # type: ignore[return-value]


def dudy_templates() -> list[dict]:
    return _load("dudy_templates.json")  # type: ignore[return-value]


def pins() -> list[dict]:
    return _load("pin_templates.json")  # type: ignore[return-value]


def copy_templates() -> dict:
    return _load("copy_templates.json")  # type: ignore[return-value]


def llm_config() -> dict:
    return _load("llm_config.json")  # type: ignore[return-value]


def crisis_terms() -> dict:
    return _load("crisis_terms.json")  # type: ignore[return-value]
