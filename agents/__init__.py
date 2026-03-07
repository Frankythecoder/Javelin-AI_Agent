"""Javelin AI Agent package.

This package was refactored from a single agents.py file.
All public names are re-exported here for backward compatibility.
"""

from agents.control import (
    AgentControlState,
    ToolDefinition,
    ApprovalAwareTool,
    tool_definition_to_langchain,
)

from agents.helpers import (
    find_file_broadly,
    find_directory_broadly,
    _normalize_url,
    is_prompt_injection,
)

from agents.file_tools import (
    search_file_tool,
    read_file_tool,
    list_files_tool,
    delete_file_tool,
    create_and_edit_file_tool,
    create_new_file,
    rename_file_tool,
    find_file_broadly_tool,
    find_directory_broadly_tool,
    change_working_directory_tool,
    SEARCH_FILE_DEFINITION,
    READ_FILE_DEFINITION,
    LIST_FILES_DEFINITION,
    DELETE_FILE_DEFINITION,
    CREATE_AND_EDIT_FILE_DEFINITION,
    RENAME_FILE_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION,
    FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
)

from agents.code_tools import (
    run_code_tool,
    check_syntax_tool,
    run_tests_tool,
    lint_code_tool,
    RUN_CODE_DEFINITION,
    CHECK_SYNTAX_DEFINITION,
    RUN_TESTS_DEFINITION,
    LINT_CODE_DEFINITION,
)

from agents.github_tools import (
    github_create_branch_tool,
    github_create_pr_tool,
    github_commit_file_tool,
    github_commit_local_file_tool,
    create_github_issue_tool,
    GITHUB_CREATE_BRANCH_DEFINITION,
    GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION,
    GITHUB_MCP_DEFINITION,
    CREATE_GITHUB_ISSUE_DEFINITION,
)

from agents.email_tools import (
    open_gmail_and_compose_tool,
    playwright_mcp_tool,
    OPEN_GMAIL_AND_COMPOSE_DEFINITION,
    PLAYWRIGHT_MCP_DEFINITION,
)

from agents.multimedia_tools import (
    recognize_image_tool,
    recognize_video_tool,
    recognize_audio_tool,
    RECOGNIZE_IMAGE_DEFINITION,
    RECOGNIZE_VIDEO_DEFINITION,
    RECOGNIZE_AUDIO_DEFINITION,
)

from agents.travel_tools import (
    search_flights_tool,
    book_travel_tool,
    get_booking_tool,
    cancel_booking_tool,
    list_bookings_tool,
    SEARCH_FLIGHTS_DEFINITION,
    BOOK_TRAVEL_DEFINITION,
    GET_BOOKING_DEFINITION,
    CANCEL_BOOKING_DEFINITION,
    LIST_BOOKINGS_DEFINITION,
)

from agents.document_tools import (
    create_pdf,
    create_docx,
    create_excel,
    create_pptx,
    CREATE_PDF_DEFINITION,
    CREATE_DOCX_DEFINITION,
    CREATE_EXCEL_DEFINITION,
    CREATE_PPTX_DEFINITION,
)

from agents.document_rw_tools import (
    read_pdf_tool,
    read_docx_tool,
    read_excel_tool,
    read_pptx_tool,
    edit_pdf_tool,
    edit_docx_tool,
    edit_excel_tool,
    edit_pptx_tool,
    READ_PDF_DEFINITION,
    READ_DOCX_DEFINITION,
    READ_EXCEL_DEFINITION,
    READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION,
    EDIT_DOCX_DEFINITION,
    EDIT_EXCEL_DEFINITION,
    EDIT_PPTX_DEFINITION,
)

from agents.core import Agent, AgentState, main
