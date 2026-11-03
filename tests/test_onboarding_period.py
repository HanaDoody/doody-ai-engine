"""Goal-based onboarding period recommendation endpoint tests."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recommend_period_by_goal():
    res = client.post(
        "/onboarding/recommend-period",
        json={"user_id": "u1", "goal_choice": "face_money"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recommended_period"] == "1m"
    assert body["message"] == "1개월을 추천해요. 작은 단계로 나눠볼게요."
    assert body["options"] == ["today", "1w", "1m", "3m"]


def test_recommend_period_unknown_goal_falls_back():
    res = client.post(
        "/onboarding/recommend-period",
        json={"user_id": "u1", "goal_choice": "nonexistent"},
    )
    assert res.status_code == 200
    assert res.json()["recommended_period"] == "1w"
