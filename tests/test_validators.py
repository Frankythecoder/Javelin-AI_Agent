# tests/test_validators.py
import os
import pytest
from evals.validators import (
    file_exists, file_contains, response_mentions, tool_was_called,
    script_runs, tool_called_before, correct_tool_order, composite,
    default_validator,
)


@pytest.fixture
def workdir(tmp_path):
    """Create a temp workdir with some test files."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\n")
    return str(tmp_path)


def _make_result(tool_history=None, response="Task completed."):
    """Helper to build a result dict with tool history."""
    history = []
    for name in (tool_history or []):
        history.append({"role": "tool", "name": name, "content": "ok"})
    return {"response": response, "history": history}


class TestFileExists:
    def test_existing_file(self, workdir):
        assert file_exists("hello.py")(_make_result(), workdir) is True

    def test_missing_file(self, workdir):
        assert file_exists("nope.txt")(_make_result(), workdir) is False


class TestFileContains:
    def test_substring_found(self, workdir):
        assert file_contains("data.csv", "Alice")(_make_result(), workdir) is True

    def test_substring_missing(self, workdir):
        assert file_contains("data.csv", "Bob")(_make_result(), workdir) is False

    def test_file_missing(self, workdir):
        assert file_contains("nope.txt", "x")(_make_result(), workdir) is False


class TestResponseMentions:
    def test_keyword_found(self):
        assert response_mentions("completed")(_make_result(response="Task completed."), "") is True

    def test_keyword_case_insensitive(self):
        assert response_mentions("COMPLETED")(_make_result(response="Task completed."), "") is True

    def test_keyword_missing(self):
        assert response_mentions("failed")(_make_result(response="Task completed."), "") is False


class TestToolWasCalled:
    def test_tool_present(self):
        assert tool_was_called("read_file")(_make_result(["read_file", "run_code"]), "") is True

    def test_tool_absent(self):
        assert tool_was_called("delete_file")(_make_result(["read_file"]), "") is False


class TestToolCalledBefore:
    def test_correct_order(self):
        result = _make_result(["list_files", "delete_file"])
        assert tool_called_before("list_files", "delete_file")(result, "") is True

    def test_wrong_order(self):
        result = _make_result(["delete_file", "list_files"])
        assert tool_called_before("list_files", "delete_file")(result, "") is False

    def test_missing_tool(self):
        result = _make_result(["list_files"])
        assert tool_called_before("list_files", "delete_file")(result, "") is False


class TestCorrectToolOrder:
    def test_tools_in_order(self):
        result = _make_result(["list_files", "read_file", "create_and_edit_file"])
        assert correct_tool_order("list_files", "create_and_edit_file")(result, "") is True

    def test_tools_out_of_order(self):
        result = _make_result(["create_and_edit_file", "list_files"])
        assert correct_tool_order("list_files", "create_and_edit_file")(result, "") is False


class TestScriptRuns:
    def test_valid_script(self, workdir):
        assert script_runs("hello.py")(_make_result(), workdir) is True

    def test_missing_script(self, workdir):
        assert script_runs("nope.py")(_make_result(), workdir) is False


class TestComposite:
    def test_all_pass(self):
        v = composite(response_mentions("done"), tool_was_called("read_file"))
        result = _make_result(["read_file"], "done")
        assert v(result, "") is True

    def test_one_fails(self):
        v = composite(response_mentions("done"), tool_was_called("delete_file"))
        result = _make_result(["read_file"], "done")
        assert v(result, "") is False


class TestDefaultValidator:
    def test_passes_with_tool_call(self):
        result = _make_result(["read_file"], "All good.")
        assert default_validator(result, "") is True

    def test_fails_with_error_response(self):
        result = _make_result(["read_file"], "Error: something broke")
        assert default_validator(result, "") is False

    def test_fails_with_no_tools(self):
        result = _make_result([], "All good.")
        assert default_validator(result, "") is False
