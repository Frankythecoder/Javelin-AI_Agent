from typing import Dict, Any
from agents.control import ToolDefinition


# Module-level holder for last experience ID (set by experience logger after each task)
_last_experience_id: str = ""
_last_rating_info: Dict[str, Any] = {}


def set_last_experience_id(experience_id: str) -> None:
    """Called by the experience logger after storing a record."""
    global _last_experience_id
    _last_experience_id = experience_id


def get_last_rating() -> Dict[str, Any]:
    """Get the most recent rating info (for attaching to experience records)."""
    return _last_rating_info


def rate_experience_tool(args: Dict[str, Any]) -> str:
    """Rate how well the agent handled the last task."""
    global _last_rating_info
    rating = args.get("rating", 0)
    feedback = args.get("feedback", "")

    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return "Rating must be an integer between 1 and 5."

    _last_rating_info = {
        "rating": rating,
        "feedback": feedback,
        "experience_id": _last_experience_id,
    }

    response = f"Rating of {rating}/5 recorded."
    if feedback:
        response += f" Feedback noted: {feedback}"
    response += " Thank you — this helps me improve."
    return response


RATE_EXPERIENCE_DEFINITION = ToolDefinition(
    name="rate_experience",
    description="Rate how well the agent handled the last task. Provide a rating from 1-5 and optional feedback on what could be improved.",
    parameters={
        "type": "object",
        "properties": {
            "rating": {
                "type": "integer",
                "description": "Rating from 1 (poor) to 5 (excellent)",
            },
            "feedback": {
                "type": "string",
                "description": "Optional feedback on what could be improved",
            },
        },
        "required": ["rating"],
    },
    function=rate_experience_tool,
    requires_approval=False,
)
