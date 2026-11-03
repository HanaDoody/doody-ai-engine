"""Goal vector lookup from goal_templates.json."""
from app.catalog import loader
from app.schemas.state import ARIVector


def goal_vector(goal_choice: str) -> ARIVector:
    """Convert a goal choice id to the configured goal ARI vector."""
    goals = loader.goals()
    if goal_choice not in goals:
        raise ValueError(f"unknown goal_choice: {goal_choice}")
    goal = goals[goal_choice]["g"]
    return ARIVector(**goal)
