import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRateExperienceTool:
    def test_definition_exists(self):
        from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION
        assert RATE_EXPERIENCE_DEFINITION.name == "rate_experience"
        assert RATE_EXPERIENCE_DEFINITION.requires_approval is False

    def test_definition_has_rating_param(self):
        from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION
        props = RATE_EXPERIENCE_DEFINITION.parameters["properties"]
        assert "rating" in props
        assert "feedback" in props

    def test_rate_stores_feedback(self):
        from agents.feedback_tools import rate_experience_tool
        # With no prior experience, should return a message
        result = rate_experience_tool({"rating": 5, "feedback": "Great job"})
        assert isinstance(result, str)
        assert "5" in result or "recorded" in result.lower() or "thank" in result.lower()

    def test_rate_validates_range(self):
        from agents.feedback_tools import rate_experience_tool
        result = rate_experience_tool({"rating": 0})
        assert "1" in result and "5" in result  # Should mention valid range

    def test_rate_rejects_above_range(self):
        from agents.feedback_tools import rate_experience_tool
        result = rate_experience_tool({"rating": 6})
        assert "1" in result and "5" in result
