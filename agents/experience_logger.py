from typing import Dict, List, Any, Optional
from agents.experience_store import ExperienceRecord


# Tool categories for args_summary generation
FILE_TOOLS = {"search_file", "read_file", "list_files", "create_and_edit_file",
              "delete_file", "rename_file", "find_file_broadly", "find_directory_broadly",
              "change_working_directory"}
CODE_TOOLS = {"run_code", "check_syntax", "run_tests", "lint_code"}
TRAVEL_TOOLS = {"search_flights", "book_travel", "get_booking", "list_bookings", "cancel_booking"}
CONTENT_FIELDS = {"new_str", "old_str", "content", "body"}


def summarize_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a compact summary of tool arguments.

    Per spec Section 3: include identifying parameters (paths, names, codes),
    replace large content with length/type metadata, truncate at 200 chars.
    """
    summary = {}
    content_length = 0
    has_content = False
    for key, value in args.items():
        str_val = str(value)
        if key in CONTENT_FIELDS:
            # Replace content blobs with a single content_length entry
            content_length = max(content_length, len(str_val))
            has_content = True
        elif len(str_val) > 200:
            summary[key] = str_val[:200]
        else:
            summary[key] = value
    if has_content:
        summary["content_length"] = content_length
    return summary


CATEGORY_MAP = {
    "file_ops": {"search_file", "read_file", "list_files", "create_and_edit_file",
                 "delete_file", "rename_file", "find_file_broadly", "find_directory_broadly",
                 "change_working_directory"},
    "code": {"run_code", "check_syntax", "run_tests", "lint_code"},
    "document": {"create_pdf", "create_docx", "create_excel", "create_pptx",
                 "read_pdf", "read_docx", "read_excel", "read_pptx",
                 "edit_pdf", "edit_docx", "edit_excel", "edit_pptx"},
    "travel": {"search_flights", "book_travel", "get_booking", "list_bookings", "cancel_booking"},
    "github": {"github_create_branch", "github_commit_file", "github_commit_local_file",
               "github_create_pr", "create_github_issue"},
    "multimedia": {"recognize_image", "recognize_video", "recognize_audio"},
    "email": {"open_gmail_and_compose"},
    "browser": {"playwright_navigate"},
}


class ExperienceLogger:
    """Builds ExperienceRecord instances from execution context."""

    @staticmethod
    def infer_category(tool_names: List[str]) -> str:
        """Infer task category from the tools used."""
        if not tool_names:
            return "general"
        for category, tools in CATEGORY_MAP.items():
            if any(name in tools for name in tool_names):
                return category
        return "general"

    def build_record(
        self,
        task_description: str,
        task_category: str,
        task_complexity: str,
        plan_summary: str,
        tools_planned: List[str],
        tool_executions: List[Dict[str, Any]],
        user_corrections: List[str],
        approval_actions: List[Dict[str, Any]],
        outcome: str,
    ) -> ExperienceRecord:
        """Build an ExperienceRecord from raw execution data.

        Args:
            tool_executions: List of dicts with keys:
                name, args, result, success (bool), error (str or None)
        """
        tools_executed = [t["name"] for t in tool_executions]
        tool_results = [
            {
                "tool_name": t["name"],
                "args_summary": summarize_tool_args(t["name"], t.get("args", {})),
                "success": t.get("success", True),
                "error": t.get("error"),
            }
            for t in tool_executions
        ]

        return ExperienceRecord(
            task_description=task_description,
            task_category=task_category,
            task_complexity=task_complexity,
            plan_summary=plan_summary,
            tools_planned=tools_planned,
            tools_executed=tools_executed,
            tool_results=tool_results,
            user_corrections=user_corrections,
            approval_actions=approval_actions,
            outcome=outcome,
        )
