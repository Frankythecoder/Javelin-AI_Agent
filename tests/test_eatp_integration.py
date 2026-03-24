import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal Django setup for testing
import django
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY="test-key",
        INSTALLED_APPS=['chat'],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
    )
    django.setup()


class TestEATPIntegration:
    def test_agent_has_experience_store(self):
        """Agent.__init__ should create an ExperienceStore instance."""
        from agents.core import Agent
        from agents.experience_store import ExperienceStore
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-5.4", lambda: ("", False), [])
        assert hasattr(agent, 'experience_store')
        assert isinstance(agent.experience_store, ExperienceStore)

    def test_system_prompt_includes_experiences_when_available(self):
        """When experience store has relevant records, system prompt should include them."""
        from agents.core import Agent
        from agents.experience_store import ExperienceRecord
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-5.4", lambda: ("", False), [])

        # Mock the experience store
        mock_record = ExperienceRecord(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["List files before deleting"],
        )
        agent.experience_store.retrieve = MagicMock(return_value=[mock_record])
        agent.experience_store.format_for_prompt = MagicMock(
            return_value="## Lessons from Past Experience\n\nTASK: \"Delete old log files\"\nLESSON: List files before deleting"
        )

        # Mock the graph to capture the messages it receives
        captured_messages = []
        original_invoke = agent._graph.invoke
        def capture_invoke(state, config=None):
            captured_messages.extend(state["messages"])
            # Return a minimal valid result
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "test",
                "response_history": [],
                "execution_path": ["test"],
                "dry_run_plan": [],
                "pending_tools": [],
            }
        agent._graph.invoke = capture_invoke

        agent.chat_once(conversation_history=[], message="Delete old log files")

        # The system message should contain the experience section
        system_msg = captured_messages[0].content
        assert "Lessons from Past Experience" in system_msg

    def test_no_experiences_leaves_prompt_unchanged(self):
        """When experience store is empty, system prompt should be unchanged."""
        from agents.core import Agent
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-5.4", lambda: ("", False), [])

        agent.experience_store.retrieve = MagicMock(return_value=[])
        agent.experience_store.format_for_prompt = MagicMock(return_value="")

        captured_messages = []
        def capture_invoke(state, config=None):
            captured_messages.extend(state["messages"])
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "test",
                "response_history": [],
                "execution_path": ["test"],
                "dry_run_plan": [],
                "pending_tools": [],
            }
        agent._graph.invoke = capture_invoke

        agent.chat_once(conversation_history=[], message="Hello")

        system_msg = captured_messages[0].content
        assert "Lessons from Past Experience" not in system_msg


class TestExperienceLogging:
    def test_successful_execution_logs_experience(self):
        """After a successful chat_once, an experience should be logged."""
        from agents.core import Agent
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-5.4", lambda: ("", False), [])

        # Mock experience store
        agent.experience_store.retrieve = MagicMock(return_value=[])
        agent.experience_store.format_for_prompt = MagicMock(return_value="")
        agent.experience_store.add = MagicMock()

        # Mock graph to return success
        def mock_invoke(state, config=None):
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "Done!",
                "response_history": [],
                "execution_path": ["__start__", "classify_task", "call_model", "format_output"],
                "dry_run_plan": [],
                "pending_tools": [],
                "task_class": "heavy",
            }
        agent._graph.invoke = mock_invoke

        agent.chat_once(conversation_history=[], message="List files in current directory")

        # Experience should have been logged
        assert agent.experience_store.add.called
        logged_record = agent.experience_store.add.call_args[0][0]
        assert logged_record.task_description == "List files in current directory"
        assert logged_record.outcome == "success"


class TestExecuteDryRunLogging:
    def test_approved_dry_run_logs_experience_with_actual_results(self):
        """execute_dry_run should log an experience with actual tool results."""
        from agents.core import Agent
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-5.4", lambda: ("", False), [])

        # Mock experience store
        agent.experience_store.retrieve = MagicMock(return_value=[])
        agent.experience_store.format_for_prompt = MagicMock(return_value="")
        agent.experience_store.add = MagicMock()

        # Mock graph for the follow-up invocation
        def mock_invoke(state, config=None):
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "Done!",
                "response_history": [],
                "execution_path": ["test"],
                "dry_run_plan": [],
                "pending_tools": [],
                "task_class": "heavy",
            }
        agent._graph.invoke = mock_invoke

        # Mock tool execution
        agent._execute_tool_by_name = MagicMock(return_value="File listed: foo.txt, bar.txt")

        dry_run_plan = [
            {"id": "tc_1", "name": "list_files", "arguments": {"path": "."}},
        ]
        history = [
            {"role": "user", "content": "List files in current directory"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "tc_1", "function": {"name": "list_files", "arguments": "{\"path\": \".\"}"}}
            ]},
        ]

        agent.execute_dry_run(dry_run_plan, history)

        # Should have logged an experience
        assert agent.experience_store.add.called
        logged = agent.experience_store.add.call_args[0][0]
        assert logged.task_description == "List files in current directory"
        assert "list_files" in logged.tools_executed
