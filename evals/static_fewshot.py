# evals/static_fewshot.py
"""Static few-shot examples for Baseline B.

Contains the same 10 lessons EATP would learn dynamically, but
hardcoded as static text in the prompt. This is the fairest
comparison: same knowledge, different delivery mechanism.
"""

STATIC_EXAMPLES = """## Task Execution Guidelines

1. BEFORE DELETING OR RENAMING FILES: Always use list_files first to show which files will be affected. Never perform destructive file operations without listing affected files first.

2. BEFORE EDITING A FILE: Always use read_file first to understand the current contents. Never edit a file without reading it first — you might overwrite important content.

3. BEFORE RUNNING CODE: Use check_syntax first to catch errors statically. Running buggy code wastes time and may produce side effects.

4. BEFORE RUNNING SCRIPTS WITH IMPORTS: Verify that required packages are installed before running. Use run_code with a quick import check first.

5. BEFORE PROCESSING DATA FILES: Read the source data file to verify its structure, column names, and format match what your processing code expects.

6. BEFORE BULK OPERATIONS: List all affected items and show the total count before proceeding. Never perform bulk deletes, moves, or renames without confirming scope.

7. BEFORE CREATING DOCUMENTS: Read any existing document or template first. If the user references an existing file, inspect it before creating a new version.

8. BEFORE COMMITTING TO ACTIONS: Review search or list results before booking travel, creating PRs, or other irreversible actions. Confirm key details first.

9. BEFORE FILE FORMAT CONVERSIONS: Read the file header or first few lines to verify the format matches expectations before running conversion scripts.

10. AFTER CREATING FILES: Use read_file to verify the output file contains what you intended. Catch issues early rather than reporting success on incomplete work.
"""
