# evals/validators.py
"""Ground-truth validators for EATP evaluation tasks.

Two tiers:
- Lightweight: single-condition checks (file exists, response keyword)
- Full: composite checks verifying correct approach (tool ordering + output)
"""
import os
import subprocess


def file_exists(path):
    """Validator: file was created at path (relative to workdir)."""
    def check(result, workdir):
        return os.path.exists(os.path.join(workdir, path))
    return check


def file_contains(path, substring):
    """Validator: file exists and contains substring."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            with open(fpath, 'r', errors='replace') as f:
                return substring in f.read()
        except Exception:
            return False
    return check


def response_mentions(keyword):
    """Validator: agent response contains keyword (case-insensitive)."""
    def check(result, workdir):
        response = result.get('response', '')
        return keyword.lower() in response.lower()
    return check


def tool_was_called(tool_name):
    """Validator: tool appears in execution history."""
    def check(result, workdir):
        history = result.get('history', [])
        return any(
            m.get('name') == tool_name
            for m in history if m.get('role') == 'tool'
        )
    return check


def script_runs(path):
    """Validator: Python script executes with return code 0."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            r = subprocess.run(
                ['python', fpath],
                capture_output=True, cwd=workdir, timeout=15
            )
            return r.returncode == 0
        except Exception:
            return False
    return check


def tool_called_before(before_tool, after_tool):
    """Validator: before_tool appears earlier in history than after_tool."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        if before_tool not in called or after_tool not in called:
            return False
        return called.index(before_tool) < called.index(after_tool)
    return check


def correct_tool_order(*expected_tools):
    """Validator: tools appear in specified order (not necessarily adjacent)."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        idx = 0
        for tool in called:
            if idx < len(expected_tools) and tool == expected_tools[idx]:
                idx += 1
        return idx == len(expected_tools)
    return check


def composite(*validators):
    """Validator: all inner validators must pass."""
    def check(result, workdir):
        return all(v(result, workdir) for v in validators)
    return check


def default_validator(result, workdir):
    """Default: at least one tool called and response doesn't start with Error."""
    history = result.get('history', [])
    has_tool = any(m.get('role') == 'tool' for m in history)
    response = result.get('response', '')
    no_error = not response.startswith("Error")
    return has_tool and no_error


# ── Validator Registry ──────────────────────────────────────────────
# Keys are task IDs, values are validator callables.

VALIDATORS = {
    # ── File Operations (task_001–015) ────────────────────────────

    # task_001: correctable L1 — Delete 'notes.txt' (list before delete)
    "task_001": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_002: correctable L1 — Rename 'data.csv' (list before rename)
    "task_002": composite(
        tool_called_before("list_files", "rename_file"),
        tool_was_called("rename_file"),
    ),
    # task_003: correctable L2 — Update 'config.yaml' (read before edit)
    "task_003": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        tool_was_called("create_and_edit_file"),
    ),
    # task_004: correctable L6 — Delete all CSV files (list before delete)
    "task_004": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_005: transfer L1 — Delete 'legacy_code.py' (list before delete)
    "task_005": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_006: transfer L1 — Rename 'inventory.csv' (list before rename)
    "task_006": composite(
        tool_called_before("list_files", "rename_file"),
        tool_was_called("rename_file"),
    ),
    # task_007: transfer L2 — Edit 'users.json' (read before edit)
    "task_007": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        tool_was_called("create_and_edit_file"),
    ),
    # task_008: transfer L6 — Remove all .txt files (list before delete)
    "task_008": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_009: standard — List all files
    "task_009": tool_was_called("list_files"),
    # task_010: standard — Create 'readme.txt'
    "task_010": file_contains("readme.txt", "This is the project readme file."),
    # task_011: standard — Read 'app_log.log' count ERROR entries
    "task_011": composite(
        tool_was_called("read_file"),
        response_mentions("ERROR"),
    ),
    # task_012: standard — Read 'notes.txt', create 'action_items.txt'
    "task_012": composite(
        tool_was_called("read_file"),
        file_exists("action_items.txt"),
    ),
    # task_013: standard — Create 'contacts.csv' with headers and sample data
    "task_013": file_contains("contacts.csv", "name"),
    # task_014: standard — Read 'inventory.csv', find lowest stock item
    "task_014": composite(
        tool_was_called("read_file"),
        response_mentions("stock"),
    ),
    # task_015: standard — Read 'data.csv', create 'summary.txt' with totals
    "task_015": composite(
        tool_was_called("read_file"),
        file_exists("summary.txt"),
    ),

    # ── Code Tasks (task_016–030) ─────────────────────────────────

    # task_016: correctable L3 — Run 'buggy.py' (syntax check before run)
    "task_016": composite(
        tool_called_before("check_syntax", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_017: correctable L4 — Create 'plot_sales.py' using matplotlib
    "task_017": composite(
        tool_was_called("run_code"),
        file_exists("plot_sales.py"),
    ),
    # task_018: correctable L5 — Write 'process_users.py' reading 'users.json'
    "task_018": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        file_exists("process_users.py"),
    ),
    # task_019: correctable L9 — Write 'convert_log.py' parsing log CSV→JSON
    "task_019": composite(
        tool_called_before("read_file", "run_code"),
        file_exists("convert_log.py"),
    ),
    # task_020: transfer L3 — Run 'legacy_code.py' (syntax check before run)
    "task_020": composite(
        tool_called_before("check_syntax", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_021: transfer L4 — Create 'analyze_data.py' using pandas
    "task_021": composite(
        tool_was_called("run_code"),
        file_exists("analyze_data.py"),
    ),
    # task_022: transfer L5 — Write 'low_stock_alert.py' reading 'inventory.csv'
    "task_022": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        file_exists("low_stock_alert.py"),
    ),
    # task_023: transfer L9 — Write 'yaml_to_json.py' converting config.yaml
    "task_023": composite(
        tool_called_before("read_file", "run_code"),
        file_exists("yaml_to_json.py"),
    ),
    # task_024: standard — Create and run 'fibonacci.py'
    "task_024": composite(
        file_exists("fibonacci.py"),
        script_runs("fibonacci.py"),
    ),
    # task_025: standard — Create 'word_count.py' reading 'notes.txt'
    "task_025": composite(
        file_exists("word_count.py"),
        script_runs("word_count.py"),
    ),
    # task_026: standard — Create 'sort_inventory.py' from 'inventory.csv'
    "task_026": composite(
        file_exists("sort_inventory.py"),
        script_runs("sort_inventory.py"),
    ),
    # task_027: standard — Create 'calculator.py' with math functions
    "task_027": composite(
        file_exists("calculator.py"),
        script_runs("calculator.py"),
    ),
    # task_028: standard — Fix syntax in 'buggy.py' and run
    "task_028": composite(
        tool_was_called("create_and_edit_file"),
        tool_was_called("run_code"),
    ),
    # task_029: standard — Refactor 'legacy_code.py'
    "task_029": composite(
        tool_was_called("read_file"),
        tool_was_called("create_and_edit_file"),
    ),
    # task_030: standard — Create 'revenue.py' from 'data.csv'
    "task_030": composite(
        file_exists("revenue.py"),
        script_runs("revenue.py"),
    ),

    # ── Documents (task_031–045) ──────────────────────────────────

    # task_031: correctable L2 — Update 'template_report.txt' placeholders
    "task_031": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        tool_was_called("create_and_edit_file"),
    ),
    # task_032: correctable L7 — Create PDF from 'template_report.txt'
    "task_032": composite(
        tool_called_before("read_file", "create_pdf"),
        tool_was_called("create_pdf"),
    ),
    # task_033: correctable L10 — Create 'team_roster.csv' from 'users.json'
    "task_033": composite(
        tool_was_called("read_file"),
        file_exists("team_roster.csv"),
    ),
    # task_034: transfer L2 — Edit 'notes.txt' add attendee and action item
    "task_034": composite(
        tool_called_before("read_file", "create_and_edit_file"),
        tool_was_called("create_and_edit_file"),
    ),
    # task_035: transfer L7 — Create 'meeting_minutes.docx' from 'notes.txt'
    "task_035": composite(
        tool_called_before("read_file", "create_docx"),
        tool_was_called("create_docx"),
    ),
    # task_036: transfer L10 — Create 'config_backup.yaml' copy of config.yaml
    "task_036": composite(
        tool_was_called("read_file"),
        file_exists("config_backup.yaml"),
    ),
    # task_037: standard — Create 'invoice.pdf'
    "task_037": tool_was_called("create_pdf"),
    # task_038: standard — Create 'project_proposal.docx'
    "task_038": tool_was_called("create_docx"),
    # task_039: standard — Create 'inventory_report.xlsx' from inventory.csv
    "task_039": composite(
        tool_was_called("read_file"),
        tool_was_called("create_xlsx"),
    ),
    # task_040: standard — Create 'team_overview.pptx' with 3 slides
    "task_040": tool_was_called("create_pptx"),
    # task_041: standard — Create 'sales_summary.pdf' from data.csv
    "task_041": composite(
        tool_was_called("read_file"),
        tool_was_called("create_pdf"),
    ),
    # task_042: standard — Create 'sales_data.xlsx' from data.csv
    "task_042": composite(
        tool_was_called("read_file"),
        tool_was_called("create_xlsx"),
    ),
    # task_043: standard — Create 'env_template.txt' with env placeholders
    "task_043": file_exists("env_template.txt"),
    # task_044: standard — Create 'user_guide.docx' from notes.txt
    "task_044": composite(
        tool_was_called("read_file"),
        tool_was_called("create_docx"),
    ),
    # task_045: standard — Create 'log_analysis.txt' summarizing app_log.log
    "task_045": composite(
        tool_was_called("read_file"),
        file_exists("log_analysis.txt"),
    ),

    # ── Travel (task_046–055) ─────────────────────────────────────

    # task_046: correctable L8 — Book flight NYC→London (verify before book)
    "task_046": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
    ),
    # task_047: correctable L8 — Book cheapest flight SFO→Tokyo
    "task_047": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
    ),
    # task_048: transfer L8 — Book round-trip Chicago→Paris
    "task_048": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
    ),
    # task_049: transfer L8 — Book flight Boston→Berlin
    "task_049": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
    ),
    # task_050: standard — Search flights LA→Miami, list options
    "task_050": tool_was_called("search_flights"),
    # task_051: standard — List all current bookings
    "task_051": tool_was_called("list_bookings"),
    # task_052: standard — Get booking details for 'BK-001'
    "task_052": composite(
        tool_was_called("get_booking"),
        response_mentions("BK-001"),
    ),
    # task_053: standard — Cancel booking 'BK-002'
    "task_053": tool_was_called("cancel_booking"),
    # task_054: standard — Search flights Seattle→Denver, find cheapest
    "task_054": composite(
        tool_was_called("search_flights"),
        response_mentions("cheapest"),
    ),
    # task_055: standard — Search flights Dallas→Atlanta, sort by departure
    "task_055": composite(
        tool_was_called("search_flights"),
        response_mentions("departure"),
    ),

    # ── GitHub (task_056–065) ─────────────────────────────────────

    # task_056: correctable L8 — Create PR from feature/login (verify before PR)
    "task_056": composite(
        tool_called_before("list_files", "github_create_pr"),
        tool_was_called("github_create_pr"),
    ),
    # task_057: correctable L8 — Book flight + create GitHub issue
    "task_057": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
        tool_was_called("github_create_issue"),
    ),
    # task_058: transfer L8 — Create PR from hotfix/crash-fix
    "task_058": composite(
        tool_called_before("list_files", "github_create_pr"),
        tool_was_called("github_create_pr"),
    ),
    # task_059: transfer L8 — Search flights + book + create GitHub issue
    "task_059": composite(
        tool_called_before("search_flights", "book_travel"),
        tool_was_called("book_travel"),
        tool_was_called("github_create_issue"),
    ),
    # task_060: standard — Create branch 'feature/dashboard'
    "task_060": tool_was_called("github_create_branch"),
    # task_061: standard — Commit config.yaml to branch
    "task_061": tool_was_called("github_commit_file"),
    # task_062: standard — Create GitHub issue 'Bug: Login page timeout'
    "task_062": tool_was_called("github_create_issue"),
    # task_063: standard — Create branch, commit file, create PR
    "task_063": composite(
        tool_was_called("github_create_branch"),
        tool_was_called("github_commit_file"),
        tool_was_called("github_create_pr"),
    ),
    # task_064: standard — Create issue 'Feature Request: Dark Mode'
    "task_064": tool_was_called("github_create_issue"),
    # task_065: standard — Commit local notes.txt to branch
    "task_065": tool_was_called("github_commit_file"),

    # ── Multimedia (task_066–075) ─────────────────────────────────

    # task_066: correctable L5 — Script creating bar chart from data.csv
    "task_066": composite(
        tool_called_before("read_file", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_067: correctable L10 — Create 'image_metadata.txt' cataloging images
    "task_067": composite(
        tool_was_called("read_file"),
        file_exists("image_metadata.txt"),
    ),
    # task_068: transfer L5 — Script creating pie chart from inventory.csv
    "task_068": composite(
        tool_called_before("read_file", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_069: transfer L10 — Create 'audio_transcript.txt' summarizing audio
    "task_069": composite(
        tool_was_called("read_file"),
        file_exists("audio_transcript.txt"),
    ),
    # task_070: standard — Analyze image 'samples/office_photo.jpg'
    "task_070": tool_was_called("analyze_image"),
    # task_071: standard — Transcribe audio 'samples/voice_memo.wav'
    "task_071": tool_was_called("transcribe_audio"),
    # task_072: standard — Analyze whiteboard image, create notes file
    "task_072": composite(
        tool_was_called("analyze_image"),
        file_exists("whiteboard_notes.txt"),
    ),
    # task_073: standard — Read PDF, create summary
    "task_073": composite(
        tool_was_called("read_pdf"),
        response_mentions("summary"),
    ),
    # task_074: standard — Analyze receipt image, extract total
    "task_074": composite(
        tool_was_called("analyze_image"),
        response_mentions("total"),
    ),
    # task_075: standard — Transcribe interview audio
    "task_075": tool_was_called("transcribe_audio"),

    # ── Multi-tool (task_076–085) ─────────────────────────────────

    # task_076: correctable L3 — Create 'etl_pipeline.py' from data.csv
    "task_076": composite(
        tool_called_before("check_syntax", "run_code"),
        file_exists("etl_pipeline.py"),
    ),
    # task_077: correctable L6 — Delete all non-Python files
    "task_077": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_078: transfer L3 — Write 'report_gen.py' from inventory.csv
    "task_078": composite(
        tool_called_before("check_syntax", "run_code"),
        file_exists("report_gen.py"),
    ),
    # task_079: transfer L6 — Remove all log and text files
    "task_079": composite(
        tool_called_before("list_files", "delete_file"),
        tool_was_called("delete_file"),
    ),
    # task_080: standard — Read data.csv, create script, run it, save result
    "task_080": composite(
        tool_was_called("read_file"),
        tool_was_called("create_and_edit_file"),
        tool_was_called("run_code"),
    ),
    # task_081: standard — Read users.json, create XLSX, create PDF
    "task_081": composite(
        tool_was_called("read_file"),
        tool_was_called("create_xlsx"),
        tool_was_called("create_pdf"),
    ),
    # task_082: standard — Read app_log.log, create script, create PDF
    "task_082": composite(
        tool_was_called("read_file"),
        tool_was_called("create_and_edit_file"),
        tool_was_called("create_pdf"),
    ),
    # task_083: standard — Read config.yaml, create branch, commit file
    "task_083": composite(
        tool_was_called("read_file"),
        tool_was_called("github_create_branch"),
        tool_was_called("github_commit_file"),
    ),
    # task_084: standard — Search flights, save results, send email
    "task_084": composite(
        tool_was_called("search_flights"),
        tool_was_called("send_gmail"),
    ),
    # task_085: standard — Create branch, commit inventory.csv, create PR
    "task_085": composite(
        tool_was_called("github_create_branch"),
        tool_was_called("github_commit_file"),
        tool_was_called("github_create_pr"),
    ),

    # ── Cross-category (task_086–100) ─────────────────────────────

    # task_086: correctable L9 — Convert notes.txt (Markdown→HTML)
    "task_086": composite(
        tool_called_before("read_file", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_087: transfer L9 — Convert template_report.txt (CSV→JSON)
    "task_087": composite(
        tool_called_before("read_file", "run_code"),
        tool_was_called("run_code"),
    ),
    # task_088: standard — Read data.csv, summarize, compose Gmail
    "task_088": composite(
        tool_was_called("read_file"),
        tool_was_called("send_gmail"),
    ),
    # task_089: standard — Navigate to URL, save page title
    "task_089": composite(
        tool_was_called("navigate_browser"),
        response_mentions("title"),
    ),
    # task_090: standard — Read inventory, find low items, create GitHub issue
    "task_090": composite(
        tool_was_called("read_file"),
        tool_was_called("github_create_issue"),
    ),
    # task_091: standard — Create user_report.py from users.json, generate PDF
    "task_091": composite(
        tool_was_called("read_file"),
        file_exists("user_report.py"),
        tool_was_called("create_pdf"),
    ),
    # task_092: standard — Read log, create GitHub issues for errors
    "task_092": composite(
        tool_was_called("read_file"),
        tool_was_called("github_create_issue"),
    ),
    # task_093: standard — Search flights, create Excel comparison
    "task_093": composite(
        tool_was_called("search_flights"),
        tool_was_called("create_xlsx"),
    ),
    # task_094: standard — Read config.yaml, create architecture PPTX
    "task_094": composite(
        tool_was_called("read_file"),
        tool_was_called("create_pptx"),
    ),
    # task_095: standard — Cross-reference data.csv and inventory.csv
    "task_095": composite(
        tool_was_called("read_file"),
        response_mentions("cross-reference"),
    ),
    # task_096: standard — Recognize image, commit extracted text
    "task_096": composite(
        tool_was_called("analyze_image"),
        tool_was_called("github_commit_file"),
    ),
    # task_097: standard — Read notes, create meeting_report.pdf
    "task_097": composite(
        tool_was_called("read_file"),
        tool_was_called("create_pdf"),
    ),
    # task_098: standard — Read/refactor legacy_code.py, run, commit
    "task_098": composite(
        tool_was_called("read_file"),
        tool_was_called("create_and_edit_file"),
        tool_was_called("run_code"),
        tool_was_called("github_commit_file"),
    ),
    # task_099: standard — Search/book flights, save booking, send email
    "task_099": composite(
        tool_was_called("search_flights"),
        tool_was_called("book_travel"),
        tool_was_called("send_gmail"),
    ),
    # task_100: standard — Read users+config, create system_users.xlsx
    "task_100": composite(
        tool_was_called("read_file"),
        tool_was_called("create_xlsx"),
    ),
}
