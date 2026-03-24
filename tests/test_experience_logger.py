import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestArgsSummary:
    def test_file_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("create_and_edit_file", {
            "path": "foo.py",
            "old_str": "",
            "new_str": "x" * 5000,
        })
        assert summary["path"] == "foo.py"
        assert "content_length" in summary
        assert isinstance(summary["content_length"], int)
        # Should NOT contain the full 5000-char string
        assert len(str(summary)) < 300

    def test_code_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("run_code", {
            "command": "python " + "x" * 500,
        })
        assert len(summary["command"]) <= 200

    def test_travel_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("search_flights", {
            "origin": "LAX",
            "destination": "JFK",
            "departure_date": "2026-05-15",
            "adults": 1,
        })
        assert summary["origin"] == "LAX"
        assert summary["destination"] == "JFK"

    def test_generic_tool_summary_truncates(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("some_tool", {
            "big_field": "x" * 1000,
        })
        assert len(str(summary["big_field"])) <= 200


class TestInferCategory:
    def test_file_tools_detected(self):
        from agents.experience_logger import ExperienceLogger
        assert ExperienceLogger.infer_category(["read_file", "list_files"]) == "file_ops"

    def test_code_tools_detected(self):
        from agents.experience_logger import ExperienceLogger
        assert ExperienceLogger.infer_category(["run_code"]) == "code"

    def test_travel_tools_detected(self):
        from agents.experience_logger import ExperienceLogger
        assert ExperienceLogger.infer_category(["search_flights"]) == "travel"

    def test_empty_returns_general(self):
        from agents.experience_logger import ExperienceLogger
        assert ExperienceLogger.infer_category([]) == "general"

    def test_unknown_returns_general(self):
        from agents.experience_logger import ExperienceLogger
        assert ExperienceLogger.infer_category(["unknown_tool"]) == "general"


class TestExperienceLogger:
    def test_build_record_from_execution(self):
        from agents.experience_logger import ExperienceLogger
        logger = ExperienceLogger()
        record = logger.build_record(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            plan_summary="List files, then delete .log files",
            tools_planned=["list_files", "delete_file"],
            tool_executions=[
                {"name": "list_files", "args": {"path": "."}, "result": "file1.log\nfile2.log", "success": True},
                {"name": "delete_file", "args": {"path": "file1.log"}, "result": "Deleted", "success": True},
            ],
            user_corrections=[],
            approval_actions=[],
            outcome="success",
        )
        assert record.task_description == "Delete old log files"
        assert record.tools_executed == ["list_files", "delete_file"]
        assert len(record.tool_results) == 2
        assert record.tool_results[0]["success"] is True
        assert record.outcome == "success"

    def test_build_record_captures_denials(self):
        from agents.experience_logger import ExperienceLogger
        logger = ExperienceLogger()
        record = logger.build_record(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            plan_summary="Delete .log files",
            tools_planned=["delete_file"],
            tool_executions=[],
            user_corrections=["User denied delete_file, asked to list first"],
            approval_actions=[{"tool_name": "delete_file", "action": "denied"}],
            outcome="partial",
        )
        assert len(record.user_corrections) == 1
        assert record.approval_actions[0]["action"] == "denied"
