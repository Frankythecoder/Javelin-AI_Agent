import json
from typing import Dict, List, Any, Optional, TypedDict

from openai import OpenAI
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END

from agents.control import AgentControlState, ToolDefinition, ApprovalAwareTool, tool_definition_to_langchain
from agents.helpers import is_prompt_injection
from agents.agent_messages import AgentMessagesMixin
from agents.experience_store import ExperienceStore
from agents.experience_logger import ExperienceLogger


def main():
    # Configure OpenAI with API key
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Create the model with tools
    from agents.file_tools import (
        SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, LIST_FILES_DEFINITION,
        CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION,
        FIND_FILE_BROADLY_DEFINITION, FIND_DIRECTORY_BROADLY_DEFINITION,
        CHANGE_WORKING_DIRECTORY_DEFINITION,
    )
    from agents.code_tools import RUN_CODE_DEFINITION, CHECK_SYNTAX_DEFINITION, RUN_TESTS_DEFINITION, LINT_CODE_DEFINITION
    from agents.github_tools import (
        GITHUB_CREATE_BRANCH_DEFINITION, GITHUB_COMMIT_FILE_DEFINITION,
        GITHUB_COMMIT_LOCAL_FILE_DEFINITION, GITHUB_MCP_DEFINITION, CREATE_GITHUB_ISSUE_DEFINITION,
    )
    from agents.email_tools import OPEN_GMAIL_AND_COMPOSE_DEFINITION, PLAYWRIGHT_MCP_DEFINITION
    from agents.multimedia_tools import RECOGNIZE_IMAGE_DEFINITION, RECOGNIZE_VIDEO_DEFINITION, RECOGNIZE_AUDIO_DEFINITION
    from agents.travel_tools import (
        SEARCH_FLIGHTS_DEFINITION, BOOK_TRAVEL_DEFINITION, GET_BOOKING_DEFINITION,
        LIST_BOOKINGS_DEFINITION, CANCEL_BOOKING_DEFINITION,
    )
    from agents.document_tools import CREATE_PDF_DEFINITION, CREATE_DOCX_DEFINITION, CREATE_EXCEL_DEFINITION, CREATE_PPTX_DEFINITION
    from agents.document_rw_tools import (
        READ_PDF_DEFINITION, READ_DOCX_DEFINITION, READ_EXCEL_DEFINITION, READ_PPTX_DEFINITION,
        EDIT_PDF_DEFINITION, EDIT_DOCX_DEFINITION, EDIT_EXCEL_DEFINITION, EDIT_PPTX_DEFINITION,
    )
    from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION

    tools = [
        SEARCH_FILE_DEFINITION,
        READ_FILE_DEFINITION,
        LIST_FILES_DEFINITION,
        CREATE_AND_EDIT_FILE_DEFINITION,
        DELETE_FILE_DEFINITION,
        RENAME_FILE_DEFINITION,
        RUN_CODE_DEFINITION,
        CHECK_SYNTAX_DEFINITION,
        RUN_TESTS_DEFINITION,
        LINT_CODE_DEFINITION,
        OPEN_GMAIL_AND_COMPOSE_DEFINITION,
        RECOGNIZE_IMAGE_DEFINITION,
        RECOGNIZE_VIDEO_DEFINITION,
        RECOGNIZE_AUDIO_DEFINITION,
        FIND_FILE_BROADLY_DEFINITION,
        FIND_DIRECTORY_BROADLY_DEFINITION,
        CHANGE_WORKING_DIRECTORY_DEFINITION,
        CREATE_PDF_DEFINITION,
        CREATE_DOCX_DEFINITION,
        CREATE_EXCEL_DEFINITION,
        CREATE_PPTX_DEFINITION,
        READ_PDF_DEFINITION,
        READ_DOCX_DEFINITION,
        READ_EXCEL_DEFINITION,
        READ_PPTX_DEFINITION,
        EDIT_PDF_DEFINITION,
        EDIT_DOCX_DEFINITION,
        EDIT_EXCEL_DEFINITION,
        EDIT_PPTX_DEFINITION,
        GITHUB_CREATE_BRANCH_DEFINITION,
        GITHUB_COMMIT_FILE_DEFINITION,
        GITHUB_COMMIT_LOCAL_FILE_DEFINITION,
        GITHUB_MCP_DEFINITION,
        CREATE_GITHUB_ISSUE_DEFINITION,
        PLAYWRIGHT_MCP_DEFINITION,
        SEARCH_FLIGHTS_DEFINITION,
        BOOK_TRAVEL_DEFINITION,
        GET_BOOKING_DEFINITION,
        LIST_BOOKINGS_DEFINITION,
        CANCEL_BOOKING_DEFINITION,
        RATE_EXPERIENCE_DEFINITION,
    ]
    model_name = 'gpt-4.1'

    def get_user_message():
        try:
            line = input()
            return line, True
        except EOFError:
            return "", False

    agent = Agent(client, model_name, get_user_message, tools, light_model_name='gpt-4.1-mini')
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")


class AgentState(TypedDict):
    """State for the LangGraph agent execution graph."""
    messages: list
    use_pending: bool
    dry_run_plan: list
    pending_tools: list
    status: str
    response: str
    response_history: list
    stopped: bool
    tools_enabled: bool
    execution_path: list
    task_class: str


class Agent(AgentMessagesMixin):
    def __init__(self, client, model_name, get_user_message, tools: List[ToolDefinition], max_history: int = 15, light_model_name: str = "gpt-4.1-mini"):
        self.client = client
        self.model_name = model_name
        self.get_user_message = get_user_message
        self.tools = tools
        self.max_history = max_history
        self.control = AgentControlState()

        # Convert ToolDefinitions to LangChain tools
        self.langchain_tools = [tool_definition_to_langchain(td) for td in tools]
        self.tool_map = {t.name: t for t in self.langchain_tools}

        # Create ChatOpenAI model and bind tools
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=client.api_key,
            request_timeout=30,
        )
        self.llm_with_tools = self.llm.bind_tools(self.langchain_tools)

        # Light model for simple tasks (email, templates, formatting)
        self.llm_mini = ChatOpenAI(
            model=light_model_name,
            api_key=client.api_key,
            request_timeout=30,
        )
        self.llm_mini_with_tools = self.llm_mini.bind_tools(self.langchain_tools)

        # Keep for backward compat
        self.openai_tools = self._convert_tools_to_openai_format()

        # Build the LangGraph
        self._graph = self._build_graph()

        # Test hook: set to a node name to simulate a failure there
        self._test_fail_node = None

        # Conversation summary for memory across trimmed messages
        self._conversation_summary = None

        # EATP: Experience store and logger
        self.experience_store = ExperienceStore()
        self.experience_logger = ExperienceLogger()

        # EATP: Wire feedback tool to experience store
        from agents.feedback_tools import set_experience_store
        set_experience_store(self.experience_store)

        # EATP: Session-level correction tracking (populated by callers via record_correction/record_denial)
        self._session_corrections: List[str] = []
        self._session_approval_actions: List[Dict[str, Any]] = []

        # System instruction for agentic behavior
        self.system_instruction = """
        You are an expert AI software engineer. When performing tasks:
        1. Always verify the state of the filesystem before and after your actions.
        2. If a tool returns an error, analyze the cause, fix the issue (install missing dependencies, correct code, resolve path issues), and retry. NEVER stop and report an error as your final response if you have not yet attempted to fix it.
        3. Use the 'check_syntax', 'run_tests', and 'lint_code' tools to identify and fix errors:
           - Syntax Errors: Use 'check_syntax' to catch compile-time or parse errors.
           - Logical Errors: Use 'run_tests' to verify behavior against expectations.
           - Static Analysis: Use 'lint_code' to find code smells and potential bugs.
        4. Be concise but thorough.
        5. You have FULL ACCESS to the local filesystem using absolute or relative paths. Do not claim you cannot access or retrieve files; instead, use the provided tools (like 'read_file', 'list_files', or specifying paths in tool arguments) to interact with them.
        6. Use absolute or relative paths as provided. Default to the current working directory ('.') if no path is explicitly specified. Do not assume previous paths from history apply to new, unrelated tasks. If you need to switch to a different project or directory, use the 'change_working_directory' tool.
        7. If you cannot find a file or directory in the current directory, use the 'search_file' tool or simply use 'read_file', 'list_files', or 'create_and_edit_file' with the name; the system will automatically search common directories (Desktop, Documents, Pictures, projects, repos, etc.) for you.
        8. If 'read_file' indicates a file is an image, use 'recognize_image' to analyze its contents.
        9. When writing code inside any and all types of code files, write multi-line code and avoid single-line writes.
        10. For SIMPLE tasks (single-step, clear intent, fewer than 3 tool calls): Do not ask for permission; just execute the necessary steps to complete the task. For COMPLEX tasks, follow rules 17-18 instead.
        11. In your final summary, avoid using the words "Error" or "Exception" if the task was completed successfully, as these words are used for automated failure detection. Use words like "issue", "problem", or "fault" if you must refer to them.
        12. ALWAYS report the actual output from tool executions. Never hallucinate or skip reporting the execution results.
        13. If the user denies a tool call or action, explicitly state in your response that you could not finish the task because the user denied it.
        14. For ALL GitHub operations (creating branches, committing files, raising pull requests), use ONLY the github_create_branch, github_commit_file, github_commit_local_file, and github_create_pr MCP tools. NEVER use run_code with git commands for GitHub operations. The workflow is: Step 1: github_create_branch -> Step 2: github_commit_file or github_commit_local_file -> Step 3: github_create_pr.
        15. DOCUMENT PAGE COUNT: When the user requests a document with a specific number of pages or slides, you MUST honor that request exactly:
           - For PDF/DOCX: Set the 'pages' parameter AND insert exactly (N-1) <!-- PAGE_BREAK --> markers in your content for N pages. Write 300-450 words per page to fill each page. Each <!-- PAGE_BREAK --> marker MUST be on its own line.
           - For PPTX: Set the 'pages' parameter AND include EXACTLY N headings (# or ##) for N slides. Count your headings before submitting.
           - NEVER create fewer or more pages/slides than requested. Double-check your content structure before calling the tool.
        16. TRAVEL BOOKING WORKFLOW:
           - For flights: Use 'search_flights' to find available flights. Results include Duffel offer IDs (e.g. [Offer: off_xxx]). When the user selects a flight, collect their details step-by-step per the book_travel tool description, then call 'book_travel' with the offer_id and passenger details.
           - Offers expire in approximately 30 minutes. If booking fails due to expiry, search again.
           - Use 'get_booking' to look up existing bookings by reference, 'cancel_booking' to cancel, and 'list_bookings' to show all bookings.
           - Always confirm the total price and all details with the user before calling book_travel.
        17. TASK CLASSIFICATION — Before acting on any user request, classify it:
           - SIMPLE: The task has clear intent, requires fewer than 3 tool calls, and has no ambiguity in scope or approach (e.g. "read file X", "what is 2+2", "create a hello world script"). For simple tasks, execute immediately per rule 10.
           - COMPLEX: The task is multi-step (3+ tool calls), has ambiguity in scope/approach, touches multiple files, or requires architectural decisions (e.g. "build me a REST API", "refactor the auth system", "add a TUI to this project"). For complex tasks, follow rule 18.
           If unsure, treat it as complex. It is better to ask one unnecessary question than to waste effort building the wrong thing.
        18. COMPLEX TASK PROTOCOL — When a task is classified as COMPLEX, follow these phases IN ORDER.
           PHASE 0 — EXPLORE: First, examine the project structure using 'list_files' on the current directory and read key files (e.g. requirements.txt, package.json, existing entry points, config files) to understand the current codebase. This is the ONLY phase where you may use tools before the user confirms a plan. Keep exploration brief — just enough to inform your questions and plan.
           PHASE 1 — CLARIFY (text only, no tools): Ask up to 3 focused questions to understand the user's requirements, ONE question per response (i.e. up to 3 round-trips, not 3 questions in one message). Use what you learned in Phase 0 to ask informed questions. Focus on: scope, constraints, preferred approach, and success criteria. Examples: "Should this include authentication?", "Which framework do you prefer?", "What files should I avoid changing?" Move to Phase 2 once you have enough context. SKIP this phase if the user explicitly says "just do it" or provides comprehensive details upfront.
           PHASE 2 — PLAN: Present a numbered step-by-step plan of what you will do. Include which files you will create or modify. End with "Ready to proceed?" and WAIT for the user to confirm before moving to Phase 3. If the user requests changes to the plan, revise and present again.
           PHASE 3 — EXECUTE: Carry out the plan step by step using tools. Follow all other rules (1-16) during execution. After completing each major step, briefly report what was done and what comes next.
           OVERRIDE: If at any point the user says "just do it", "skip the questions", or "go ahead", immediately move to Phase 3 and execute.
        19. PROGRESS REPORTING: When executing a multi-step plan (Phase 3 of rule 18), after each major step report: what you just completed, and what the next step is. Keep progress updates to 1-2 sentences. Example: "Step 2 complete: created models.py with User schema. Next: adding API routes in views.py."
        20. SELF-RECOVERY AND PERSISTENCE — When you encounter ANY error during task execution, you MUST NOT stop and report failure to the user. Instead, follow this recovery protocol:
           - MISSING DEPENDENCIES: If a tool returns a ModuleNotFoundError, ImportError, 'No module named', 'command not found', or similar missing-package error, immediately use 'run_code' to install it (e.g. 'pip install <package>', 'npm install <package>') and retry the failed action. Do NOT ask the user to install it — install it yourself.
           - CODE ERRORS: If code you wrote or executed produces syntax errors, runtime exceptions, type errors, logical bugs, or test failures, analyze the error output, fix the code using 'create_and_edit_file', and re-run it. Do NOT report the error as a final answer — fix it.
           - COMMAND FAILURES: If a shell command fails, read the error output, determine the cause (wrong flags, missing tools, permission issues), and try an alternative command or approach.
           - PERSISTENT ISSUES: If your first fix attempt fails, try a fundamentally different approach. For example: if a library cannot be installed, find an alternative library that provides the same functionality; if a file path is wrong, use 'search_file' to find the correct one; if a command is unavailable, find an equivalent.
           - ESCALATION: Only report failure to the user AFTER you have made at least 3 genuine attempts to resolve the issue using different approaches. When you do report failure, explain what you tried and why each approach failed.
           - NEVER say "I cannot complete this because X is not installed" or "this requires X which is not available." You have 'run_code' — use it to install X and continue.
        """

    # ----------------------------------------------------------------
    #  EATP: Session-level correction tracking
    # ----------------------------------------------------------------

    def record_correction(self, correction_text: str) -> None:
        """Record a user correction for the current session's experience log."""
        self._session_corrections.append(correction_text)

    def record_denial(self, tool_name: str, action: str = "denied") -> None:
        """Record a tool approval/denial action for the current session."""
        self._session_approval_actions.append({"tool_name": tool_name, "action": action})

    def clear_session_feedback(self) -> None:
        """Reset session-level corrections/approvals before a new task."""
        self._session_corrections.clear()
        self._session_approval_actions.clear()

    # ----------------------------------------------------------------
    #  LangGraph: build the execution graph
    # ----------------------------------------------------------------

    def _build_graph(self):
        """Build and compile the LangGraph StateGraph."""
        agent_self = self

        # -- Graph nodes --------------------------------------------------

        def classify_task(state: AgentState) -> dict:
            """Classify the user's message as heavy or light using the mini model."""
            path = state.get("execution_path", []) + ["classify_task"]

            # If task_class is already set (re-entry after tool execution), skip
            if state.get("task_class"):
                return {"execution_path": path}

            # Extract the latest user message
            user_msg = ""
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                    break

            # No user message (e.g. tool approval continuation) → default heavy
            if not user_msg:
                return {"task_class": "heavy", "execution_path": path}

            try:
                classification = agent_self.llm_mini.invoke([
                    SystemMessage(content=(
                        "Classify this user request into exactly one category. "
                        "Reply with ONLY the word \"heavy\" or \"light\".\n\n"
                        "heavy: multi-step tasks, code generation/editing, debugging, "
                        "file operations, vision/image analysis, tool-heavy workflows, "
                        "complex reasoning, planning, architecture decisions, GitHub "
                        "operations, browser automation, travel booking.\n\n"
                        "light: email/letter drafting, template filling, text formatting, "
                        "simple text generation, document content writing, presentation content."
                    )),
                    HumanMessage(content=user_msg)
                ])
                task_class = classification.content.strip().lower()
                if task_class not in ("heavy", "light"):
                    task_class = "heavy"
            except Exception:
                task_class = "heavy"

            return {"task_class": task_class, "execution_path": path}

        def call_model(state: AgentState) -> dict:
            """Invoke the LLM with current messages and bound tools."""
            path = state.get("execution_path", []) + ["call_model"]
            if state["stopped"]:
                return {"status": "stopped", "response": "\u26d4 Execution stopped mid-response.", "execution_path": path}
            try:
                if agent_self._test_fail_node == "call_model":
                    agent_self._test_fail_node = None
                    raise ConnectionError("Simulated failure: Could not reach LLM API (no internet connection)")
                llm = agent_self.llm_with_tools if state.get("task_class", "heavy") == "heavy" else agent_self.llm_mini_with_tools
                response = llm.invoke(state["messages"])
                return {"messages": state["messages"] + [response], "execution_path": path}
            except Exception as e:
                error_path = state.get("execution_path", []) + ["call_model \u2717"]
                return {
                    "status": "error",
                    "response": f"LLM call failed at **call_model**: {str(e)}",
                    "execution_path": error_path,
                    "response_history": agent_self._messages_to_dicts(state["messages"]),
                }

        def collect_dry_run(state: AgentState) -> dict:
            """Collect all tool calls into a dry-run plan without executing."""
            path = state.get("execution_path", []) + ["collect_dry_run"]
            try:
                if agent_self._test_fail_node == "collect_dry_run":
                    agent_self._test_fail_node = None
                    raise RuntimeError("Simulated failure: Could not build dry-run plan")
                ai_message = state["messages"][-1]
                plan = []
                for tc in ai_message.tool_calls:
                    plan.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": tc["args"],
                        "summary": agent_self._summarize_tool_call(tc["name"], tc["args"])
                    })

                user_request = ""
                for msg in reversed(state["messages"]):
                    if isinstance(msg, HumanMessage):
                        user_request = msg.content
                        break

                history = agent_self._messages_to_dicts(state["messages"])
                return {
                    "status": "dry_run",
                    "dry_run_plan": plan,
                    "response": agent_self._generate_plan_summary(plan, user_request),
                    "response_history": history,
                    "execution_path": path,
                }
            except Exception as e:
                error_path = state.get("execution_path", []) + ["collect_dry_run \u2717"]
                return {
                    "status": "error",
                    "response": f"Failed at **collect_dry_run**: {str(e)}",
                    "execution_path": error_path,
                    "response_history": agent_self._messages_to_dicts(state["messages"]),
                }

        def execute_or_hold_tools(state: AgentState) -> dict:
            """Execute low-risk tools immediately; hold high-risk tools for approval."""
            path = state.get("execution_path", []) + ["execute_or_hold_tools"]
            try:
                if agent_self._test_fail_node == "execute_or_hold_tools":
                    agent_self._test_fail_node = None
                    raise RuntimeError("Simulated failure: Tool execution engine crashed")
                ai_message = state["messages"][-1]
                new_messages = list(state["messages"])
                pending = []

                for tc in ai_message.tool_calls:
                    if agent_self.control.stopped:
                        return {
                            "messages": new_messages,
                            "status": "stopped",
                            "response": "\u26d4 Agent execution was stopped.",
                            "response_history": agent_self._messages_to_dicts(new_messages),
                            "execution_path": path,
                        }

                    tool = agent_self.tool_map.get(tc["name"])
                    if tool and tool.requires_approval:
                        pending.append({
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments": tc["args"]
                        })
                    else:
                        result = agent_self._execute_tool_by_name(tc["name"], tc["args"])
                        new_messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tc["id"],
                            name=tc["name"],
                        ))

                if pending:
                    history = agent_self._messages_to_dicts(new_messages)
                    return {
                        "messages": new_messages,
                        "status": "pending",
                        "pending_tools": pending,
                        "response": ai_message.content or "Approve the next action:",
                        "response_history": history,
                        "execution_path": path,
                    }

                # All tools were low-risk and already executed; loop back to model
                return {"messages": new_messages, "pending_tools": [], "execution_path": path}
            except Exception as e:
                error_path = state.get("execution_path", []) + ["execute_or_hold_tools \u2717"]
                return {
                    "messages": state["messages"],
                    "status": "error",
                    "response": f"Tool execution failed at **execute_or_hold_tools**: {str(e)}",
                    "execution_path": error_path,
                    "response_history": agent_self._messages_to_dicts(state["messages"]),
                }

        def format_output(state: AgentState) -> dict:
            """Format the final text response."""
            path = state.get("execution_path", []) + ["format_output"]
            try:
                if agent_self._test_fail_node == "format_output":
                    agent_self._test_fail_node = None
                    raise RuntimeError("Simulated failure: Could not format output")
                history = agent_self._messages_to_dicts(state["messages"])
                result = {"response_history": history, "execution_path": path}
                # If status was already set (e.g. "stopped" or "error"), preserve it
                if not state.get("status"):
                    last = state["messages"][-1]
                    result["status"] = "success"
                    result["response"] = (
                        last.content if isinstance(last, AIMessage) else "No response generated"
                    ) or "No response generated"
                return result
            except Exception as e:
                error_path = state.get("execution_path", []) + ["format_output \u2717"]
                return {
                    "status": "error",
                    "response": f"Failed at **format_output**: {str(e)}",
                    "execution_path": error_path,
                    "response_history": [],
                }

        # -- Conditional routing ------------------------------------------

        def route_after_model(state: AgentState) -> str:
            if state.get("status") in ("stopped", "error"):
                return "format_output"
            last = state["messages"][-1]
            if not isinstance(last, AIMessage) or not last.tool_calls:
                return "format_output"
            if state["use_pending"]:
                return "execute_or_hold_tools"
            return "collect_dry_run"

        def route_after_tools(state: AgentState) -> str:
            if state.get("status") in ("stopped", "error"):
                return "format_output"
            if state["pending_tools"]:
                return END
            return "call_model"

        # -- Assemble graph -----------------------------------------------

        graph = StateGraph(AgentState)
        graph.add_node("classify_task", classify_task)
        graph.add_node("call_model", call_model)
        graph.add_node("collect_dry_run", collect_dry_run)
        graph.add_node("execute_or_hold_tools", execute_or_hold_tools)
        graph.add_node("format_output", format_output)

        graph.set_entry_point("classify_task")
        graph.add_edge("classify_task", "call_model")
        graph.add_conditional_edges("call_model", route_after_model, {
            "format_output": "format_output",
            "collect_dry_run": "collect_dry_run",
            "execute_or_hold_tools": "execute_or_hold_tools",
        })
        graph.add_conditional_edges("execute_or_hold_tools", route_after_tools, {
            END: END,
            "call_model": "call_model",
            "format_output": "format_output",
        })
        graph.add_edge("collect_dry_run", END)
        graph.add_edge("format_output", END)

        return graph.compile()

    # ----------------------------------------------------------------
    #  Public API (same signatures as the original Agent)
    # ----------------------------------------------------------------

    def chat_once(self, conversation_history=None, message=None, use_pending=False):
        """
        Handle a single chat interaction for Django/API usage.

        Args:
            conversation_history: List of previous messages (optional)
            message: Single message string to process
            use_pending: If True the model's tool calls go through per-tool
                         approval (status="pending").  If False (the default,
                         used for every fresh user message) all tool calls are
                         collected into a single dry-run plan first.

        Returns:
            Dict containing status and response/tool info
        """
        try:
            # Reset stopped flag for new messages to allow continuation
            if message is not None:
                self.control.stopped = False

            if self.control.stopped:
                return {
                    "status": "stopped",
                    "response": "\u26d4 Agent execution was stopped."
                }

            # Build LangChain message list with EATP augmentation
            system_prompt = self.system_instruction
            if message and self.experience_store:
                experiences = self.experience_store.retrieve(message)
                experience_section = self.experience_store.format_for_prompt(experiences)
                if experience_section:
                    system_prompt = system_prompt + "\n\n" + experience_section
            messages = [SystemMessage(content=system_prompt)]
            if conversation_history:
                for lc_msg in self._dicts_to_messages(conversation_history):
                    if isinstance(lc_msg, SystemMessage):
                        continue
                    messages.append(lc_msg)

            # Strip orphaned tool_calls left by interrupted plan approval
            messages = self._strip_orphaned_tool_calls(messages)

            # Detect interrupted task and inject context if user wants to continue
            if message:
                continuation_context = self._detect_interrupted_task(messages, message)
                if is_prompt_injection(message):
                    return {"status": "error", "message": "Security Warning: Potential prompt injection detected. Message blocked."}
                if continuation_context:
                    messages.append(HumanMessage(content=f"{continuation_context}\n\n{message}"))
                else:
                    messages.append(HumanMessage(content=message))

            messages = self._trim_messages(messages)

            initial_state: AgentState = {
                "messages": messages,
                "use_pending": use_pending,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
                "task_class": "",
            }

            result = self._graph.invoke(initial_state, {"recursion_limit": 25})

            # EATP: Log this execution as an experience (only on actual execution, not dry_run)
            if message and self.experience_store and result.get("status") == "success":
                try:
                    # Extract tool executions from response history
                    history = result.get("response_history", [])
                    tool_executions = []
                    for msg in history:
                        if msg.get("role") == "tool":
                            content = msg.get("content", "")
                            content_lower = content.lower() if content else ""
                            is_error = (
                                content.startswith("Error") or
                                content.startswith("Exception") or
                                "Traceback" in content or
                                content.startswith("FileNotFoundError") or
                                content.startswith("Permission denied") or
                                content.startswith("Failed to")
                            )
                            tool_executions.append({
                                "name": msg.get("name", ""),
                                "args": {},
                                "result": content[:200],
                                "success": not is_error,
                                "error": content if is_error else None,
                            })
                    # Infer task category from tools used
                    used_tools = [msg.get("name", "") for msg in history if msg.get("role") == "tool"]
                    task_category = self.experience_logger.infer_category(used_tools)
                    record = self.experience_logger.build_record(
                        task_description=message,
                        task_category=task_category,
                        task_complexity=result.get("task_class", "heavy"),
                        plan_summary=result.get("response", "")[:200],
                        tools_planned=[t["name"] for t in result.get("dry_run_plan", [])],
                        tool_executions=tool_executions,
                        user_corrections=list(self._session_corrections),
                        approval_actions=list(self._session_approval_actions),
                        outcome=result.get("status", "success"),
                    )
                    self.experience_store.add(record)
                    # Wire up feedback tool to this experience
                    from agents.feedback_tools import set_last_experience_id
                    set_last_experience_id(record.id)
                except Exception:
                    pass  # Never let logging break the main flow

            # Build execution path string
            path = result.get("execution_path", []) + ["__end__"]

            # Build output in the same format the frontend expects
            output = {
                "status": result["status"],
                "response": result["response"],
                "execution_path": path,
            }
            if result["status"] == "dry_run":
                output["dry_run_plan"] = result["dry_run_plan"]
                output["history"] = result["response_history"]
            elif result["status"] == "pending":
                output["pending_tools"] = result["pending_tools"]
                output["history"] = result["response_history"]
            else:
                output["history"] = result["response_history"]

            return output

        except Exception as e:
            return {
                "status": "error",
                "response": f"Error: {str(e)}",
                "message": str(e),
                "execution_path": ["__start__", "graph_error \u2717", "__end__"],
            }

    def execute_dry_run(self, dry_run_plan: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute every tool in an approved dry-run plan, then fetch the model follow-up.

        The follow-up is processed with use_pending=True so any further tool
        calls the model issues go through per-tool approval rather than
        surfacing as another dry-run round.
        """
        try:
            # Convert dict history to LangChain messages (history already contains system msg)
            messages = self._dicts_to_messages(history)
            if not messages or not isinstance(messages[0], SystemMessage):
                messages.insert(0, SystemMessage(content=self.system_instruction))

            # Execute each approved tool
            for tool_call in dry_run_plan:
                if self.control.stopped:
                    return {"status": "stopped", "response": "\u26d4 Agent execution was stopped."}

                result = self._execute_tool_by_name(tool_call['name'], tool_call['arguments'])
                messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tool_call['id'],
                    name=tool_call['name'],
                ))

            # EATP: Log the approved dry-run execution as an experience
            if self.experience_store:
                try:
                    tool_executions = []
                    # Collect actual results from the ToolMessages appended during execution
                    tool_results_map = {}
                    for msg in messages:
                        if hasattr(msg, 'tool_call_id') and hasattr(msg, 'name'):
                            content = msg.content if msg.content else ""
                            is_error = (
                                content.startswith("Error") or
                                content.startswith("Exception") or
                                "Traceback" in content or
                                content.startswith("FileNotFoundError") or
                                content.startswith("Permission denied") or
                                content.startswith("Failed to")
                            )
                            tool_results_map[msg.tool_call_id] = {
                                "result": content[:200],
                                "success": not is_error,
                                "error": content if is_error else None,
                            }
                    for tool_call in dry_run_plan:
                        actual = tool_results_map.get(tool_call["id"], {})
                        tool_executions.append({
                            "name": tool_call["name"],
                            "args": tool_call.get("arguments", {}),
                            "result": actual.get("result", ""),
                            "success": actual.get("success", True),
                            "error": actual.get("error"),
                        })
                    # Derive outcome from actual tool results
                    all_success = all(t.get("success", True) for t in tool_executions)
                    any_success = any(t.get("success", True) for t in tool_executions)
                    if all_success:
                        outcome = "success"
                    elif any_success:
                        outcome = "partial"
                    else:
                        outcome = "failure"
                    # Extract original user message from history
                    user_msg = ""
                    for msg in reversed(history):
                        if msg.get("role") == "user":
                            user_msg = msg.get("content", "")
                            break
                    if user_msg:
                        task_category = self.experience_logger.infer_category(
                            [t["name"] for t in dry_run_plan]
                        )
                        record = self.experience_logger.build_record(
                            task_description=user_msg,
                            task_category=task_category,
                            task_complexity="heavy",
                            plan_summary="",
                            tools_planned=[t["name"] for t in dry_run_plan],
                            tool_executions=tool_executions,
                            user_corrections=list(self._session_corrections),
                            approval_actions=[{"tool_name": t["name"], "action": "approved"} for t in dry_run_plan],
                            outcome=outcome,
                        )
                        self.experience_store.add(record)
                        # Wire up feedback tool to this experience
                        from agents.feedback_tools import set_last_experience_id
                        set_last_experience_id(record.id)
                except Exception:
                    pass  # Never let logging break the main flow

            # Run the graph for follow-up in per-tool mode
            # Use task_class="heavy" to skip re-classification (dry-run execution is inherently heavy)
            initial_state: AgentState = {
                "messages": self._trim_messages(messages),
                "use_pending": True,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
                "task_class": "heavy",
            }

            result = self._graph.invoke(initial_state, {"recursion_limit": 25})

            path = result.get("execution_path", []) + ["__end__"]

            output = {
                "status": result["status"],
                "response": result["response"],
                "execution_path": path,
            }
            if result["status"] == "pending":
                output["pending_tools"] = result["pending_tools"]
            output["history"] = result["response_history"]
            return output

        except Exception as e:
            return {
                "status": "error",
                "response": f"Error executing dry run: {str(e)}",
                "message": f"Error executing dry run: {str(e)}",
                "execution_path": ["__start__", "execute_dry_run \u2717", "__end__"],
            }

    # ----------------------------------------------------------------
    #  CLI interactive mode
    # ----------------------------------------------------------------

    def run(self):
        print("Chat with OpenAI (use 'ctrl-c' or type 'quit' to exit)")

        self.messages = [SystemMessage(content=self.system_instruction)]

        while True:
            if self.control.stopped:
                print("\u26d4 Agent execution stopped.")
                break

            print("\033[94mYou\033[0m: ", end="")
            user_input, ok = self.get_user_message()
            if not ok:
                break

            # Check for quit command
            if user_input.lower().strip() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            self.messages.append(HumanMessage(content=user_input))

            try:
                response = self.llm_with_tools.invoke(
                    self._trim_messages(self.messages)
                )
                self._process_response_simple(response)
            except Exception as e:
                print(f"Error: {str(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")

    def _process_response_simple(self, ai_message):
        """Simplified response processing for CLI mode (no approval system)."""
        try:
            self.messages.append(ai_message)

            # Handle text response
            if ai_message.content:
                print(f"\033[93mOpenAI\033[0m: {ai_message.content}")

            # Handle tool calls
            if ai_message.tool_calls:
                for tc in ai_message.tool_calls:
                    args_str = json.dumps(tc["args"]).replace('\\\\n', '\\n').replace('\\n', '\n')
                    print(f"\033[92mtool\033[0m: {tc['name']}({args_str})")

                    result = self._execute_tool_by_name(tc["name"], tc["args"])

                    self.messages.append(ToolMessage(
                        content=result,
                        tool_call_id=tc["id"],
                        name=tc["name"],
                    ))

                # Get follow-up response
                try:
                    follow_up = self.llm_with_tools.invoke(
                        self._trim_messages(self.messages)
                    )
                    self._process_response_simple(follow_up)
                except Exception as e:
                    print(f"Error processing follow-up: {str(e)}")

        except Exception as e:
            print(f"Error processing response: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    # ----------------------------------------------------------------
    #  Tool execution (unchanged logic - calls original ToolDefinition.function)
    # ----------------------------------------------------------------

    def _execute_tool_by_name(self, name, args):
        """Find and execute a tool by name."""
        if self.control.stopped:
            return "\u26d4 Agent execution stopped."

        if not self.control.tools_enabled:
            return "\U0001f512 Tool execution disabled by kill switch."

        from chat.models import ToolLog
        args_str = json.dumps(args).replace('\\\\n', '\\n').replace('\\n', '\n')
        print(f"\033[96mTool Call:\033[0m {name}({args_str})")
        for tool in self.tools:
            if tool.name == name:
                try:
                    result = tool.function(args)
                    # Save log to database
                    ToolLog.objects.create(
                        tool_name=name,
                        input_args=json.dumps(args),
                        output_result=str(result)
                    )
                    return result
                except Exception as e:
                    error_msg = f"Error executing tool: {str(e)}"
                    # Save error log to database
                    ToolLog.objects.create(
                        tool_name=name,
                        input_args=json.dumps(args),
                        output_result=error_msg
                    )
                    return error_msg
        return f"Tool '{name}' not found"


if __name__ == "__main__":
    main()
