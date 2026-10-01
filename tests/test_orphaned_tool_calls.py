"""Regression tests for tool-call / tool-response pairing repair.

OpenAI rejects a history where either:
  * an AIMessage's tool_calls lack matching ToolMessages, or
  * a ToolMessage has no preceding AIMessage that requested it.

Both shapes occur in practice: a plan can be stopped or partially denied
mid-execution, and trimming can drop a parent AIMessage.
"""
import os
import sys
from unittest.mock import MagicMock

import django
from django.conf import settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY="test-key",
        MODEL_NAME="gpt-6-sol",
        LIGHT_MODEL_NAME="gpt-5.6-terra",
        INSTALLED_APPS=['chat'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    )
    django.setup()

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage  # noqa: E402


def _agent():
    from openai import OpenAI
    from agents.core import Agent
    client = MagicMock(spec=OpenAI)
    client.api_key = "test-key"
    return Agent(client, None, None, [])


def _ai(*ids):
    return AIMessage(content="", tool_calls=[
        {"name": "read_file", "args": {}, "id": i, "type": "tool_call"} for i in ids])


def assert_valid(messages):
    """Assert the sequence satisfies both OpenAI pairing rules."""
    for i, m in enumerate(messages):
        if isinstance(m, AIMessage) and m.tool_calls:
            answered = set()
            for nxt in messages[i + 1:]:
                if isinstance(nxt, ToolMessage):
                    answered.add(nxt.tool_call_id)
                else:
                    break
            missing = {tc["id"] for tc in m.tool_calls} - answered
            assert not missing, f"[{i}] tool_calls with no response: {sorted(missing)}"
        if isinstance(m, ToolMessage):
            parent = None
            for prev in reversed(messages[:i]):
                if isinstance(prev, AIMessage) and prev.tool_calls:
                    parent = prev
                    break
                if not isinstance(prev, ToolMessage):
                    break
            assert parent is not None and m.tool_call_id in {tc["id"] for tc in parent.tool_calls}, \
                f"[{i}] ToolMessage {m.tool_call_id} has no requesting AIMessage"


def test_partially_answered_plan_stays_valid():
    """Plan stopped after one of two tools ran."""
    msgs = [SystemMessage(content="s"), HumanMessage(content="go"),
            _ai("a", "b"), ToolMessage(content="result A", tool_call_id="a")]
    assert_valid(_agent()._strip_orphaned_tool_calls(msgs))


def test_partially_answered_plan_preserves_executed_result():
    """The tool that DID run must not be discarded."""
    msgs = [SystemMessage(content="s"), HumanMessage(content="go"),
            _ai("a", "b"), ToolMessage(content="result A", tool_call_id="a")]
    out = _agent()._strip_orphaned_tool_calls(msgs)
    assert any(isinstance(m, ToolMessage) and m.content == "result A" for m in out), \
        "executed tool result was lost"


def test_completely_unanswered_plan_stays_valid():
    """Documented case: approval interrupted before any tool ran."""
    msgs = [SystemMessage(content="s"), HumanMessage(content="go"), _ai("a")]
    assert_valid(_agent()._strip_orphaned_tool_calls(msgs))


def test_toolmessage_without_parent_is_dropped():
    """Trimming can drop the parent AIMessage, leaving a stray ToolMessage."""
    msgs = [SystemMessage(content="s"), ToolMessage(content="x", tool_call_id="ghost"),
            HumanMessage(content="go")]
    assert_valid(_agent()._strip_orphaned_tool_calls(msgs))


def test_orphan_in_middle_of_history_is_repaired():
    """The broken pair is not the trailing block."""
    msgs = [SystemMessage(content="s"), HumanMessage(content="go"),
            _ai("a", "b"), ToolMessage(content="A", tool_call_id="a"),
            AIMessage(content="continuing"), HumanMessage(content="next"),
            _ai("c"), ToolMessage(content="C", tool_call_id="c")]
    assert_valid(_agent()._strip_orphaned_tool_calls(msgs))


def test_valid_history_is_unchanged():
    msgs = [SystemMessage(content="s"), HumanMessage(content="go"),
            _ai("a", "b"), ToolMessage(content="A", tool_call_id="a"),
            ToolMessage(content="B", tool_call_id="b"), AIMessage(content="done")]
    out = _agent()._strip_orphaned_tool_calls(msgs)
    assert_valid(out)
    assert len(out) == len(msgs)
    assert out[-1].content == "done"
