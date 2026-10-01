"""Regression tests for how the Agent configures its LLM clients.

These guard two settings that previously broke the agent at runtime:

* ``reasoning_effort`` must be "none" — reasoning models reject function
  tools on /v1/chat/completions otherwise (invalid_request_error).
* ``request_timeout`` must be generous enough to cover a long generation.
  A complex task that writes a large file in one tool call emits ~10k
  completion tokens and takes 60-90s; the old 30s budget cut those off
  with APITimeoutError partway through a task.
"""
import importlib
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

# Long generations observed at ~75s; anything below this reintroduces the bug.
MIN_SAFE_TIMEOUT = 120


def _agent():
    from openai import OpenAI
    from agents.core import Agent
    client = MagicMock(spec=OpenAI)
    client.api_key = "test-key"
    return Agent(client, None, None, [])


def test_request_timeout_allows_long_generations():
    agent = _agent()
    for llm in (agent.llm, agent.llm_mini):
        assert llm.request_timeout >= MIN_SAFE_TIMEOUT, (
            f"request_timeout={llm.request_timeout}s is too low; long tool-call "
            f"generations take 60-90s and will fail at call_model"
        )


def test_request_timeout_is_env_overridable():
    import agents.core as core
    original = os.environ.get("LLM_REQUEST_TIMEOUT")
    os.environ["LLM_REQUEST_TIMEOUT"] = "42"
    try:
        importlib.reload(core)
        assert core._REQUEST_TIMEOUT == 42.0
    finally:
        if original is None:
            os.environ.pop("LLM_REQUEST_TIMEOUT", None)
        else:
            os.environ["LLM_REQUEST_TIMEOUT"] = original
        importlib.reload(core)


def test_reasoning_effort_is_none_for_function_tools():
    agent = _agent()
    for llm in (agent.llm, agent.llm_mini):
        assert llm.reasoning_effort == "none"


def test_stays_on_chat_completions():
    """Responses API would change AIMessage.content to structured blocks,
    which the rest of the class treats as a plain string."""
    agent = _agent()
    assert not agent.llm.use_responses_api


def _astra_agent():
    from openai import OpenAI
    from agents.core import Agent
    client = MagicMock(spec=OpenAI)
    client.api_key = "test-key"
    return Agent(client, "gpt-6-astra", None, [], light_model_name="gpt-5.6-terra")


def test_astra_uses_responses_api_with_supported_effort():
    """gpt-6-astra rejects reasoning_effort='none', and rejects function tools
    on chat completions at any other effort, so it must use the Responses API."""
    agent = _astra_agent()
    assert agent.llm.use_responses_api
    assert agent.llm.reasoning_effort in ("low", "medium", "high", "xhigh")
    # The light model is unaffected.
    assert not agent.llm_mini.use_responses_api
    assert agent.llm_mini.reasoning_effort == "none"


def test_responses_api_content_is_flattened_to_string():
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from agents.core import _TextContentChatOpenAI

    msg = AIMessage(
        content=[
            {"type": "function_call", "name": "ping", "arguments": "{}", "call_id": "c1"},
            {"type": "text", "text": "Hello ", "annotations": []},
            {"type": "text", "text": "world", "annotations": []},
        ],
        tool_calls=[{"name": "ping", "args": {}, "id": "c1"}],
    )
    result = _TextContentChatOpenAI._flatten(ChatResult(generations=[ChatGeneration(message=msg)]))
    out = result.generations[0].message
    assert out.content == "Hello world"
    assert out.tool_calls[0]["id"] == "c1"
