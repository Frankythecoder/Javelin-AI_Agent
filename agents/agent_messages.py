import json
from typing import Dict, List, Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

from agents.helpers import is_prompt_injection


class AgentMessagesMixin:
    """Mixin providing message conversion, trimming, summarisation and
    code-generation helpers that are used by the Agent class.

    Attributes expected on ``self`` (provided by Agent.__init__):
        llm          – ChatOpenAI (heavy model, no tools bound)
        max_history  – int
        tools        – list of ToolDefinition
    """

    # ----------------------------------------------------------------
    #  Message format conversion helpers
    # ----------------------------------------------------------------

    def _dicts_to_messages(self, history: List[Dict[str, Any]]) -> List[BaseMessage]:
        """Convert frontend dict-format history to LangChain message objects."""
        messages = []
        for msg in history:
            role = msg.get("role")
            if role == "system":
                messages.append(SystemMessage(content=msg.get("content", "")))
            elif role == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif role == "assistant":
                kwargs: Dict[str, Any] = {"content": msg.get("content") or ""}
                if msg.get("tool_calls"):
                    kwargs["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"])
                                    if isinstance(tc["function"]["arguments"], str)
                                    else tc["function"]["arguments"],
                        }
                        for tc in msg["tool_calls"]
                    ]
                messages.append(AIMessage(**kwargs))
            elif role == "tool":
                messages.append(ToolMessage(
                    content=msg.get("content", ""),
                    tool_call_id=msg.get("tool_call_id", ""),
                    name=msg.get("name", ""),
                ))
        return messages

    def _strip_orphaned_tool_calls(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Remove trailing AIMessage with tool_calls that have no matching ToolMessages.

        This happens when execution is stopped during plan approval — the
        AIMessage with tool_calls is saved to history but no ToolMessages
        were ever appended.  OpenAI rejects such sequences, so we strip
        them before the next LLM call.
        """
        if not messages:
            return messages

        # Walk backwards to find the last AIMessage with tool_calls
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                # Check if ALL tool_calls have matching ToolMessages after this index
                tool_call_ids = {tc["id"] for tc in msg.tool_calls}
                responded_ids = {
                    m.tool_call_id for m in messages[i + 1:]
                    if isinstance(m, ToolMessage)
                }
                if not tool_call_ids.issubset(responded_ids):
                    # Orphaned — remove this AIMessage
                    return messages[:i] + messages[i + 1:]
                # Found a complete AIMessage with tool_calls — history is valid
                break
            # Stop searching at first non-tool, non-AI message going backwards
            if not isinstance(msg, ToolMessage):
                break

        return messages

    def _messages_to_dicts(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Convert LangChain messages back to the frontend dict format."""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                d: Dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    d["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"])
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(d)
            elif isinstance(msg, ToolMessage):
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "name": msg.name,
                    "content": msg.content,
                })
        return result

    # ----------------------------------------------------------------
    #  Dry-run plan helpers (unchanged logic)
    # ----------------------------------------------------------------

    def _summarize_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """Return a one-line, human-readable description of a tool call for the dry-run plan."""
        summaries = {
            'read_file':                lambda a: f"Read file: {a.get('path', '')}",
            'list_files':               lambda a: f"List files in: {a.get('path', '.')}",
            'search_file':              lambda a: f"Search for file: {a.get('filename', '')}",
            'find_file_broadly':        lambda a: f"Find file: {a.get('filename', '')}",
            'find_directory_broadly':   lambda a: f"Find directory: {a.get('dirname', '')}",
            'create_and_edit_file':     lambda a: f"Edit/create file: {a.get('path', '')}",
            'delete_file':              lambda a: f"Delete: {a.get('path', '')}",
            'rename_file':              lambda a: f"Rename {a.get('old_path', '')} \u2192 {a.get('new_path', '')}",
            'run_code':                 lambda a: f"Run command: {a.get('command', '')}",
            'check_syntax':             lambda a: f"Check syntax of: {a.get('path', '')}",
            'run_tests':                lambda a: f"Run tests: {a.get('command', 'auto-detect')}",
            'lint_code':                lambda a: f"Lint: {a.get('path', '')}",
            'change_working_directory': lambda a: f"Change directory to: {a.get('path', '')}",
            'create_pdf':               lambda a: f"Create PDF: {a.get('filename', '')}",
            'create_docx':              lambda a: f"Create DOCX: {a.get('filename', '')}",
            'create_excel':             lambda a: f"Create Excel: {a.get('filename', '')}",
            'create_pptx':              lambda a: f"Create PPTX: {a.get('filename', '')}",
            'open_gmail_and_compose':   lambda a: f"Compose email to: {a.get('recipient', '')}",
            'recognize_image':          lambda a: f"Analyze image: {a.get('path', '')}",
            'recognize_video':          lambda a: f"Analyze video: {a.get('path', '')}",
            'recognize_audio':          lambda a: f"Analyze audio: {a.get('path', '')}",
            'github_create_branch':     lambda a: f"Create GitHub branch: {a.get('name', '')}",
            'github_commit_file':       lambda a: f"Commit to GitHub branch '{a.get('branch', '')}': {a.get('path', '')}",
            'github_commit_local_file': lambda a: f"Commit local file to GitHub branch '{a.get('branch', '')}': {a.get('local_path', '')}",
            'github_create_pr':         lambda a: f'Create GitHub PR: "{a.get("title", "")}"',
            'playwright_navigate':      lambda a: f"Navigate to: {a.get('url', '')}",
        }
        summarizer = summaries.get(name)
        return summarizer(args) if summarizer else f"Call '{name}' with: {json.dumps(args)}"

    def _generate_plan_summary(self, dry_run_plan: List[Dict[str, Any]], user_request: str = "") -> str:
        """Ask the model to produce a plain-English, start-to-finish summary
        of the dry-run plan.  The user's original request is included so the
        summary stays grounded.  Falls back to a generic string on any failure
        so the card still renders."""
        steps = "\n".join(
            f"{i + 1}. {step['summary']}  \u2014  {step['name']}({json.dumps(step['arguments'])})"
            for i, step in enumerate(dry_run_plan)
        )
        user_ctx = f"The user asked: \"{user_request}\"\n\n" if user_request else ""

        try:
            resp = self.llm.invoke([
                SystemMessage(content=(
                    "You are about to execute an action plan on behalf of the user. "
                    "Summarise the plan below in 2-4 clear sentences of plain English. "
                    "Describe what will happen from start to finish and what the end "
                    "result will be. Do not repeat raw tool names or JSON \u2014 translate "
                    "everything into natural language."
                )),
                HumanMessage(content=f"{user_ctx}Planned actions:\n\n{steps}\n\nSummarise what this plan will do:")
            ])
            summary = resp.content
            if summary and summary.strip():
                return summary.strip()
        except Exception as e:
            print(f"[dry_run] summary generation failed: {e}")

        return "Here is the planned action(s). Review and approve or deny before execution:"

    # ----------------------------------------------------------------
    #  Backward-compat helpers
    # ----------------------------------------------------------------

    def _convert_tools_to_openai_format(self):
        """Convert tools to OpenAI format (kept for backward compatibility)."""
        openai_tools = []
        for tool in self.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return openai_tools

    def _trim_messages(self, messages: List[Any]) -> List[Any]:
        """
        Trim message history to stay within token limits.
        Keeps the system message and ensures tool messages are not separated from their tool_calls.
        Works with both LangChain message objects and plain dicts.

        When trimming occurs, generates an LLM summary of the dropped messages
        and inserts it as a SystemMessage after the main system prompt, so the
        agent retains awareness of earlier conversation context.
        """
        if len(messages) <= self.max_history + 1:
            return messages

        first = messages[0]
        is_system = (
            isinstance(first, SystemMessage)
            or (isinstance(first, dict) and first.get("role") == "system")
        )
        system_message = first if is_system else None

        # Keep the most recent messages
        start_index = len(messages) - self.max_history

        # Ensure we don't start in the middle of a tool response sequence
        def _is_tool(m):
            if isinstance(m, ToolMessage):
                return True
            if isinstance(m, dict) and m.get("role") == "tool":
                return True
            return False

        while start_index > 1 and _is_tool(messages[start_index]):
            start_index -= 1

        # Collect messages that will be dropped (excluding system message)
        dropped_start = 1 if is_system else 0
        dropped_messages = messages[dropped_start:start_index]

        recent_messages = messages[start_index:]

        # Generate summary of dropped messages if there are any
        if dropped_messages:
            # Only summarize LangChain message objects (not dicts) to avoid
            # double-summarizing when called from execute_dry_run
            has_langchain_msgs = any(
                isinstance(m, (HumanMessage, AIMessage, ToolMessage))
                for m in dropped_messages
            )
            if has_langchain_msgs:
                self._conversation_summary = self._summarize_messages(dropped_messages)

        trimmed = []
        if system_message:
            trimmed.append(system_message)

        # Insert conversation summary as a SystemMessage right after the system prompt
        if self._conversation_summary:
            summary_msg = SystemMessage(
                content=f"[Conversation context from earlier messages]\n{self._conversation_summary}"
            )
            trimmed.append(summary_msg)

        trimmed.extend(recent_messages)

        return trimmed

    def _summarize_messages(self, messages: List[Any]) -> str:
        """Summarize a list of messages into a concise context string using the LLM.

        Called when _trim_messages is about to drop older messages, so the agent
        retains awareness of earlier conversation context.

        Args:
            messages: List of LangChain message objects to summarize.

        Returns:
            A short summary string (3-5 bullet points).
        """
        # Build a plain-text transcript of the messages to summarize
        transcript_parts = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                user_content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
                transcript_parts.append(f"User: {user_content[:500]}")
            elif isinstance(msg, AIMessage):
                text = (msg.content if isinstance(msg.content, str) else str(msg.content or ""))[:500]
                if msg.tool_calls:
                    tool_names = ", ".join(tc["name"] for tc in msg.tool_calls)
                    text += f" [Called tools: {tool_names}]"
                transcript_parts.append(f"Assistant: {text}")
            elif isinstance(msg, ToolMessage):
                # Truncate long tool results to keep the summarization prompt small
                raw = msg.content if isinstance(msg.content, str) else str(msg.content or "")
                content = raw[:500]
                transcript_parts.append(f"Tool ({msg.name}): {content}")

        transcript = "\n".join(transcript_parts)

        # If there's an existing summary, include it so the LLM extends rather than restarts
        existing_context = ""
        if self._conversation_summary:
            existing_context = (
                f"Previous conversation summary:\n{self._conversation_summary}\n\n"
                "The following messages occurred AFTER the above summary. "
                "Update the summary to include this new context.\n\n"
            )

        try:
            resp = self.llm.invoke([
                SystemMessage(content=(
                    "You are a conversation summarizer. Produce a concise summary "
                    "in 3-5 bullet points. Focus on: what the user asked for, what "
                    "was accomplished, what files/paths were involved, and any "
                    "unfinished work or errors. Be factual and brief."
                )),
                HumanMessage(content=(
                    f"{existing_context}"
                    f"Conversation to summarize:\n\n{transcript}\n\n"
                    "Summary:"
                )),
            ])
            summary = resp.content.strip() if resp.content else ""
            if summary:
                return summary
        except Exception as e:
            print(f"[memory] Summary generation failed: {e}")

        # Fallback: return a basic extraction if LLM fails
        return self._conversation_summary or ""

    def _detect_interrupted_task(self, messages: List[Any], user_message: str) -> Optional[str]:
        """Detect if the previous conversation was interrupted and the user wants to continue.

        Scans the last messages for interruption patterns (denied tools, errors,
        incomplete tool sequences) and checks if the user's new message is a
        "continue" intent.

        Args:
            messages: List of LangChain message objects (the current conversation).
            user_message: The user's new message text.

        Returns:
            A context string to inject before the user's message, or None if no
            continuation is detected.
        """
        if not user_message or not messages:
            return None

        # Check if user message is a "continue" intent
        continue_phrases = {
            "continue", "go on", "resume", "keep going", "try again", "retry",
            "proceed", "carry on", "go ahead", "finish it", "complete it",
            "do it", "yes continue", "yes go on", "please continue",
        }
        normalized = user_message.lower().strip().rstrip(".!?")
        if normalized not in continue_phrases:
            return None

        # Scan last 5 messages for interruption signals
        recent = messages[-5:] if len(messages) >= 5 else messages
        interruption_context = None

        # Pattern 1: Assistant has tool_calls but no matching tool responses
        for i, msg in enumerate(recent):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_ids = {tc["id"] for tc in msg.tool_calls}
                # Check if ALL tool calls have corresponding ToolMessage responses
                abs_index = len(messages) - len(recent) + i
                remaining = messages[abs_index + 1:]
                responded_ids = {
                    m.tool_call_id for m in remaining
                    if isinstance(m, ToolMessage)
                }
                unresponded = tool_call_ids - responded_ids
                if unresponded:
                    tool_names = [
                        tc["name"] for tc in msg.tool_calls
                        if tc["id"] in unresponded
                    ]
                    interruption_context = (
                        f"The agent was about to execute tools [{', '.join(tool_names)}] "
                        f"but execution was interrupted before they completed."
                    )
                    break

        # Pattern 2: Last tool message contains denial
        if not interruption_context:
            for msg in reversed(recent):
                if isinstance(msg, ToolMessage):
                    content_lower = msg.content.lower()
                    if "denied" in content_lower or "user has denied" in content_lower:
                        interruption_context = (
                            f"The user previously denied the tool '{msg.name}'. "
                            f"The task was not completed."
                        )
                    break

        # Pattern 3: Last assistant message has error content
        if not interruption_context:
            for msg in reversed(recent):
                if isinstance(msg, AIMessage):
                    content_lower = (msg.content or "").lower()
                    if any(kw in content_lower for kw in ["error", "failed", "could not", "unable to"]):
                        interruption_context = (
                            f"The previous task encountered an issue. "
                            f"Last agent message: {(msg.content or '')[:200]}"
                        )
                    break

        if not interruption_context:
            return None

        return (
            f"[System note: The previous task was interrupted. "
            f"Context: {interruption_context} "
            f"The user wants to continue. Resume the task from where it left off.]"
        )

    def generate_code(self, task_description: str, language: str = "python", stepwise: bool = True) -> str:
        """
        Generate complex code using the LLM with advanced prompt engineering.
        Args:
            task_description (str): Description of the code to generate.
            language (str): Programming language for the code.
            stepwise (bool): Whether to use a stepwise prompt for better results.
        Returns:
            str: Generated code.
        """
        if is_prompt_injection(task_description):
            return "Security Warning: Potential prompt injection detected in task description. Generation blocked."

        if stepwise:
            prompt = (
                f"""
                Write a complete, well-structured {language} program for the following task:
                {task_description}

                Please follow these steps:
                1. Start by outlining the main components or functions needed.
                2. Implement each component step by step, with clear comments.
                3. At the end, provide the full code in a single code block.
                4. Ensure the code is ready to run and includes all necessary parts (imports, main function, etc.).
                """
            )
        else:
            prompt = f"Write a complete {language} program for the following task: {task_description}"

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
