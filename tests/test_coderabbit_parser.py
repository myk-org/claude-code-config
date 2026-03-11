"""Unit tests for CodeRabbit review body comment parsers.

This test suite covers:
- Parsing real-world review body format
- Handling bodies with no outside diff comments
- Multiple files in one review body
- Single-line references
- Edge cases (empty body, CAUTION-only, AI prompt exclusion)
- Nitpick comment parsing
- Combined review body parsing (outside diff + nitpick)
"""

from __future__ import annotations

from myk_claude_tools.reviews.coderabbit_parser import (
    _strip_blockquote_prefix,
    parse_duplicate_comments,
    parse_nitpick_comments,
    parse_outside_diff_comments,
    parse_review_body_comments,
)

# =============================================================================
# Sample review bodies for testing
# =============================================================================

# A realistic CodeRabbit review body with two comments in one file.
SAMPLE_BODY_TWO_COMMENTS = """\
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.
>
>
>
> <details>
> <summary>\u26a0\ufe0f Outside diff range comments (2)</summary><blockquote>
>
> <details>
> <summary>src/jenkins_job_insight/main.py (2)</summary><blockquote>
>
> `552-572`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_
>
> **HIGH \u2014 `_generate_html_report` failure silently kills a successful analysis response**
>
> Body text here explaining the issue in detail.
>
> <details>
> <summary>\U0001f6e1\ufe0f Proposed fix \u2014 isolate HTML report errors</summary>
>
> ```diff
> -old code
> +new code
> ```
> </details>
>
> <details>
> <summary>\U0001f916 Prompt for AI Agents</summary>
>
> ```
> prompt text that should be excluded
> ```
>
> </details>
>
> ---
>
> `553-572`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_
>
> **MAJOR \u2014 Another issue title**
>
> Body text for the second comment.
>
> </blockquote></details>
>
> </blockquote></details>
"""

# A body with comments across multiple files.
SAMPLE_BODY_MULTI_FILE = """\
> [!CAUTION]
> Some comments are outside the diff.
>
> <details>
> <summary>\u26a0\ufe0f Outside diff range comments (3)</summary><blockquote>
>
> <details>
> <summary>src/api/handler.py (2)</summary><blockquote>
>
> `10-20`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_
>
> **Missing error handling in API handler**
>
> The handler does not catch ValueError.
>
> ---
>
> `30`: _\U0001f4dd Nitpick_ | _\U0001f7e2 Trivial_
>
> **Unused import**
>
> Remove unused import of `os`.
>
> </blockquote></details>
>
> <details>
> <summary>tests/test_handler.py (1)</summary><blockquote>
>
> `5-15`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e1 Medium_
>
> **Test does not assert return value**
>
> Add assertion for the return value.
>
> </blockquote></details>
>
> </blockquote></details>
"""

# A body with a single-line reference (no range).
SAMPLE_BODY_SINGLE_LINE = """\
> <details>
> <summary>\u26a0\ufe0f Outside diff range comments (1)</summary><blockquote>
>
> <details>
> <summary>utils/helper.py (1)</summary><blockquote>
>
> `42`: _\U0001f4dd Nitpick_ | _\U0001f7e2 Trivial_
>
> **Consider renaming variable**
>
> The variable name `x` is not descriptive.
>
> </blockquote></details>
>
> </blockquote></details>
"""

# A body with no outside diff comments at all.
SAMPLE_BODY_NO_OUTSIDE = """\
> [!NOTE]
> This review only has inline comments, nothing outside the diff range.
>
> The code looks good overall.
"""

# A body with the CAUTION block but no details section.
SAMPLE_BODY_CAUTION_ONLY = """\
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.
"""

# A body with a trailing AI prompt section outside the blockquote.
SAMPLE_BODY_TRAILING_AI_PROMPT = """\
> <details>
> <summary>\u26a0\ufe0f Outside diff range comments (1)</summary><blockquote>
>
> <details>
> <summary>src/main.py (1)</summary><blockquote>
>
> `100-110`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_
>
> **Resource leak in connection pool**
>
> The connection is never closed.
>
> </blockquote></details>
>
> </blockquote></details>
>
> <details>
> <summary>\U0001f916 Prompt for AI Agents</summary>
>
> ```
> This trailing prompt should be excluded from parsing
> ```
>
> </details>
"""
# A body with a nitpick section (using the broom emoji header).
SAMPLE_BODY_NITPICK = """\
> [!TIP]
> Some nitpick comments are available.
>
> <details>
> <summary>\U0001f9f9 Nitpick comments (2)</summary><blockquote>
>
> <details>
> <summary>src/utils/helpers.py (2)</summary><blockquote>
>
> `15-20`: _\U0001f4dd Nitpick_ | _\U0001f7e2 Trivial_
>
> **Consider using a more descriptive variable name**
>
> The variable `x` could be renamed to `count` for clarity.
>
> ---
>
> `45`: _\U0001f4dd Nitpick_ | _\U0001f7e2 Trivial_
>
> **Unused import**
>
> The import of `os` is not used in this module.
>
> <details>
> <summary>\U0001f916 Prompt for AI Agents</summary>
>
> ```
> Remove the unused import of os from src/utils/helpers.py
> ```
>
> </details>
>
> </blockquote></details>
>
> </blockquote></details>
"""

# A body with BOTH outside-diff AND nitpick sections.
SAMPLE_BODY_DUPLICATE = """\
> <details>
> <summary>♻️ Duplicate comments (1)</summary><blockquote>
>
> <details>
> <summary>CLAUDE.md (1)</summary><blockquote>
>
> `516-516`: _🛠️ Refactor suggestion_ | _🟠 Major_
>
> **HIGH: Replace the repeated path rule with a cross-reference.**
>
> Line 516 now duplicates the new MUST section below instead of pointing to it.
>
> <details>
> <summary>Proposed doc fix</summary>
>
> ```diff
> -1. Create test file `tests/<feature>/test_<feature>_migration.py`
> +1. Create the test file in the feature subdirectory described in **Test File Location (MUST)**
> ```
> </details>
>
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```
> prompt text that should be excluded
> ```
>
> </details>
>
> </blockquote></details>
>
> </blockquote></details>
"""

SAMPLE_BODY_COMBINED = """\
> [!CAUTION]
> Some comments are outside the diff.
>
> <details>
> <summary>\u26a0\ufe0f Outside diff range comments (1)</summary><blockquote>
>
> <details>
> <summary>src/main.py (1)</summary><blockquote>
>
> `100-110`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_
>
> **Resource leak in connection pool**
>
> The connection is never closed.
>
> </blockquote></details>
>
> </blockquote></details>
>
> <details>
> <summary>\U0001f9f9 Nitpick comments (1)</summary><blockquote>
>
> <details>
> <summary>src/config.py (1)</summary><blockquote>
>
> `5`: _\U0001f4dd Nitpick_ | _\U0001f7e2 Trivial_
>
> **Magic number should be a constant**
>
> Replace `42` with a named constant.
>
> </blockquote></details>
>
> </blockquote></details>
"""


# =============================================================================
# Test classes
# =============================================================================


class TestParseOutsideDiffComments:
    """Tests for parse_outside_diff_comments()."""

    def test_parses_two_comments_in_one_file(self) -> None:
        """Should parse two comments from a single file block."""
        result = parse_outside_diff_comments(SAMPLE_BODY_TWO_COMMENTS)

        assert len(result) == 2

        # First comment
        assert result[0]["path"] == "src/jenkins_job_insight/main.py"
        assert result[0]["line"] == 552
        assert result[0]["end_line"] == 572
        assert result[0]["category"] == "Potential issue"
        assert result[0]["severity"] == "Major"
        assert "failure silently kills" in result[0]["body"]

        # Second comment
        assert result[1]["path"] == "src/jenkins_job_insight/main.py"
        assert result[1]["line"] == 553
        assert result[1]["end_line"] == 572
        assert result[1]["category"] == "Potential issue"
        assert result[1]["severity"] == "Major"
        assert "Another issue title" in result[1]["body"]

    def test_excludes_ai_prompt_section(self) -> None:
        """AI prompt sections should be excluded from the comment body."""
        result = parse_outside_diff_comments(SAMPLE_BODY_TWO_COMMENTS)

        assert len(result) >= 1
        # The first comment has an AI prompt block that should be removed
        assert "prompt text that should be excluded" not in result[0]["body"]
        assert "Prompt for AI Agents" not in result[0]["body"]

    def test_keeps_proposed_fix_section(self) -> None:
        """Proposed fix sections should be kept in the comment body."""
        result = parse_outside_diff_comments(SAMPLE_BODY_TWO_COMMENTS)

        assert len(result) >= 1
        assert "Proposed fix" in result[0]["body"]
        assert "```diff" in result[0]["body"]

    def test_parses_multiple_files(self) -> None:
        """Should parse comments across multiple file blocks."""
        result = parse_outside_diff_comments(SAMPLE_BODY_MULTI_FILE)

        assert len(result) == 3

        # First file, first comment
        assert result[0]["path"] == "src/api/handler.py"
        assert result[0]["line"] == 10
        assert result[0]["end_line"] == 20

        # First file, second comment (single line)
        assert result[1]["path"] == "src/api/handler.py"
        assert result[1]["line"] == 30
        assert result[1]["end_line"] is None
        assert result[1]["category"] == "Nitpick"
        assert result[1]["severity"] == "Trivial"

        # Second file
        assert result[2]["path"] == "tests/test_handler.py"
        assert result[2]["line"] == 5
        assert result[2]["end_line"] == 15

    def test_parses_single_line_reference(self) -> None:
        """Should handle single-line references (no range)."""
        result = parse_outside_diff_comments(SAMPLE_BODY_SINGLE_LINE)

        assert len(result) == 1
        assert result[0]["path"] == "utils/helper.py"
        assert result[0]["line"] == 42
        assert result[0]["end_line"] is None
        assert result[0]["category"] == "Nitpick"
        assert result[0]["severity"] == "Trivial"
        assert "renaming variable" in result[0]["body"]

    def test_no_outside_diff_comments(self) -> None:
        """Should return empty list when no outside diff section exists."""
        result = parse_outside_diff_comments(SAMPLE_BODY_NO_OUTSIDE)

        assert result == []

    def test_empty_body(self) -> None:
        """Should return empty list for empty body."""
        assert parse_outside_diff_comments("") == []

    def test_none_like_empty(self) -> None:
        """Should return empty list for whitespace-only body."""
        assert parse_outside_diff_comments("   \n\n  ") == []

    def test_caution_only_no_details(self) -> None:
        """Should return empty list when CAUTION block exists but no details section."""
        result = parse_outside_diff_comments(SAMPLE_BODY_CAUTION_ONLY)

        assert result == []

    def test_trailing_ai_prompt_excluded(self) -> None:
        """A trailing AI prompt section outside the blockquote should not interfere."""
        result = parse_outside_diff_comments(SAMPLE_BODY_TRAILING_AI_PROMPT)

        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"
        assert result[0]["line"] == 100
        assert result[0]["end_line"] == 110
        assert "trailing prompt should be excluded" not in result[0]["body"]

    def test_body_field_includes_title(self) -> None:
        """The body field should include the bold title."""
        result = parse_outside_diff_comments(SAMPLE_BODY_SINGLE_LINE)

        assert len(result) == 1
        assert result[0]["body"].startswith("**Consider renaming variable**")

    def test_returns_all_required_keys(self) -> None:
        """Each result dict should have all required keys."""
        result = parse_outside_diff_comments(SAMPLE_BODY_SINGLE_LINE)

        assert len(result) == 1
        required_keys = {"path", "line", "end_line", "body", "category", "severity"}
        assert required_keys.issubset(result[0].keys())

    def test_file_path_with_spaces(self) -> None:
        """Should handle file paths containing spaces."""
        body = (
            "> <details>\n"
            "> <summary>\u26a0\ufe0f Outside diff range comments (1)</summary><blockquote>\n"
            ">\n"
            "> <details>\n"
            "> <summary>docs/My File.md (1)</summary><blockquote>\n"
            ">\n"
            "> `10-20`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_\n"
            ">\n"
            "> **Title here**\n"
            ">\n"
            "> Body text.\n"
            ">\n"
            "> </blockquote></details>\n"
            ">\n"
            "> </blockquote></details>\n"
        )
        result = parse_outside_diff_comments(body)
        assert len(result) == 1
        assert result[0]["path"] == "docs/My File.md"

    def test_truncated_html_returns_empty(self) -> None:
        """Truncated HTML with unclosed tags should return empty list."""
        body = (
            "> <details>\n"
            "> <summary>\u26a0\ufe0f Outside diff range comments (1)</summary><blockquote>\n"
            "> <details>\n"
            "> <summary>file.py (1)</summary><blockquote>\n"
            "> `10-20`: text"
        )
        result = parse_outside_diff_comments(body)
        assert result == []

    def test_outside_section_without_count(self) -> None:
        """Should parse even if the count is missing from the summary."""
        body = (
            "> <details>\n"
            "> <summary>\u26a0\ufe0f Outside diff range comments</summary><blockquote>\n"
            ">\n"
            "> <details>\n"
            "> <summary>src/main.py</summary><blockquote>\n"
            ">\n"
            "> `10-20`: _\u26a0\ufe0f Potential issue_ | _\U0001f7e0 Major_\n"
            ">\n"
            "> **Title**\n"
            ">\n"
            "> Body.\n"
            ">\n"
            "> </blockquote></details>\n"
            ">\n"
            "> </blockquote></details>\n"
        )
        result = parse_outside_diff_comments(body)
        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"


class TestStripBlockquotePrefix:
    """Tests for _strip_blockquote_prefix helper."""

    def test_strips_standard_prefix(self) -> None:
        """Standard '> ' prefix should be stripped."""
        text = "> line one\n> line two\n> line three"
        result = _strip_blockquote_prefix(text)
        assert result == "line one\nline two\nline three"

    def test_handles_bare_angle_bracket(self) -> None:
        """A bare '>' (no trailing space) should become an empty line."""
        text = "> line one\n>\n> line three"
        result = _strip_blockquote_prefix(text)
        assert result == "line one\n\nline three"

    def test_preserves_non_quoted_lines(self) -> None:
        """Lines without '> ' prefix should be preserved as-is."""
        text = "no prefix\n> quoted\nnot quoted"
        result = _strip_blockquote_prefix(text)
        assert result == "no prefix\nquoted\nnot quoted"


class TestParseNitpickComments:
    """Tests for parse_nitpick_comments()."""

    def test_parses_nitpick_comments(self) -> None:
        """Should parse nitpick comments from the nitpick section."""
        result = parse_nitpick_comments(SAMPLE_BODY_NITPICK)
        assert len(result) == 2
        assert result[0]["path"] == "src/utils/helpers.py"
        assert result[0]["line"] == 15
        assert result[0]["end_line"] == 20
        assert result[0]["category"] == "Nitpick"
        assert result[0]["severity"] == "Trivial"
        assert "descriptive variable name" in result[0]["body"]

        assert result[1]["path"] == "src/utils/helpers.py"
        assert result[1]["line"] == 45
        assert result[1]["end_line"] is None

    def test_excludes_ai_prompt_section(self) -> None:
        """AI prompt sections should be excluded from nitpick comment bodies."""
        result = parse_nitpick_comments(SAMPLE_BODY_NITPICK)
        assert len(result) == 2
        assert "Prompt for AI Agents" not in result[1]["body"]
        assert "Remove the unused import" not in result[1]["body"]

    def test_empty_body(self) -> None:
        """Should return empty list for empty body."""
        assert parse_nitpick_comments("") == []

    def test_no_cross_contamination_with_outside_diff(self) -> None:
        """Nitpick parser should NOT find outside-diff comments."""
        result = parse_nitpick_comments(SAMPLE_BODY_COMBINED)
        assert len(result) == 1
        assert result[0]["path"] == "src/config.py"
        # Should NOT include the outside-diff comment
        assert all(c["path"] != "src/main.py" for c in result)


class TestParseDuplicateComments:
    """Tests for parse_duplicate_comments()."""

    def test_parses_duplicate_comment(self) -> None:
        """Should parse duplicate comments from the duplicate section."""
        result = parse_duplicate_comments(SAMPLE_BODY_DUPLICATE)
        assert len(result) == 1
        assert result[0]["path"] == "CLAUDE.md"
        assert result[0]["line"] == 516
        assert result[0]["end_line"] == 516
        assert result[0]["category"] == "Refactor suggestion"
        assert result[0]["severity"] == "Major"
        assert "Replace the repeated path rule" in result[0]["body"]

    def test_excludes_ai_prompt_section(self) -> None:
        """AI prompt sections should be excluded from duplicate comment bodies."""
        result = parse_duplicate_comments(SAMPLE_BODY_DUPLICATE)
        assert len(result) == 1
        assert "prompt text that should be excluded" not in result[0]["body"]
        assert "Prompt for AI Agents" not in result[0]["body"]

    def test_keeps_proposed_fix(self) -> None:
        """Proposed fix sections should be kept in the body."""
        result = parse_duplicate_comments(SAMPLE_BODY_DUPLICATE)
        assert len(result) == 1
        assert "Proposed doc fix" in result[0]["body"]

    def test_empty_body(self) -> None:
        """Should return empty list for empty body."""
        assert parse_duplicate_comments("") == []

    def test_no_cross_contamination(self) -> None:
        """Duplicate parser should NOT find outside-diff or nitpick comments."""
        result = parse_duplicate_comments(SAMPLE_BODY_COMBINED)
        assert result == []


class TestParseReviewBodyComments:
    """Tests for parse_review_body_comments()."""

    def test_combined_body(self) -> None:
        """Should return both outside_diff and nitpick comments."""
        result = parse_review_body_comments(SAMPLE_BODY_COMBINED)
        assert len(result["outside_diff"]) == 1
        assert len(result["nitpick"]) == 1
        assert result["outside_diff"][0]["path"] == "src/main.py"
        assert result["nitpick"][0]["path"] == "src/config.py"
        assert result["duplicate"] == []

    def test_only_outside_diff(self) -> None:
        """Body with only outside-diff should have empty nitpick list."""
        result = parse_review_body_comments(SAMPLE_BODY_TWO_COMMENTS)
        assert len(result["outside_diff"]) == 2
        assert result["nitpick"] == []
        assert result["duplicate"] == []

    def test_only_nitpick(self) -> None:
        """Body with only nitpick should have empty outside_diff list."""
        result = parse_review_body_comments(SAMPLE_BODY_NITPICK)
        assert result["outside_diff"] == []
        assert len(result["nitpick"]) == 2
        assert result["duplicate"] == []

    def test_empty_body(self) -> None:
        """Empty body should return empty lists for all types."""
        result = parse_review_body_comments("")
        assert result == {"outside_diff": [], "nitpick": [], "duplicate": []}

    def test_body_with_duplicate_section(self) -> None:
        """Body with only duplicate section should have empty outside_diff and nitpick."""
        result = parse_review_body_comments(SAMPLE_BODY_DUPLICATE)
        assert result["outside_diff"] == []
        assert result["nitpick"] == []
        assert len(result["duplicate"]) == 1
        assert result["duplicate"][0]["path"] == "CLAUDE.md"
