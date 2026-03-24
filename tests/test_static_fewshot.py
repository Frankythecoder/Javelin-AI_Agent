# tests/test_static_fewshot.py
from evals.static_fewshot import STATIC_EXAMPLES


class TestStaticFewshot:
    def test_is_nonempty_string(self):
        assert isinstance(STATIC_EXAMPLES, str)
        assert len(STATIC_EXAMPLES) > 100

    def test_contains_all_ten_lessons(self):
        # Each lesson should appear as a numbered guideline
        for i in range(1, 11):
            assert f"{i}." in STATIC_EXAMPLES, f"Lesson {i} missing"

    def test_mentions_key_tools(self):
        assert "list_files" in STATIC_EXAMPLES
        assert "read_file" in STATIC_EXAMPLES
        assert "check_syntax" in STATIC_EXAMPLES

    def test_no_eatp_reference(self):
        # Static examples should not reference the experience system
        assert "experience" not in STATIC_EXAMPLES.lower()
        assert "eatp" not in STATIC_EXAMPLES.lower()
