"""Comprehensive unit tests for the qodo_parser module.

This test suite covers:
- parse_qodo_comment() dispatch logic
- parse_improve_comment() /improve HTML parsing
- parse_review_comment() /review HTML parsing
- _extract_path_from_link_text() helper
"""

from __future__ import annotations

from myk_claude_tools.reviews.qodo_parser import (
    _extract_path_from_link_text,
    parse_improve_comment,
    parse_qodo_comment,
    parse_review_comment,
)

# =============================================================================
# Fixtures - representative HTML snippets from real Qodo output
# =============================================================================

IMPROVE_HTML = """\
## PR Code Suggestions ✨
<!-- 55865d7 -->

Latest suggestions up to 55865d7

<table><thead><tr><td><strong>Category</strong></td><td align=left><strong>Suggestion\
</strong></td><td align=center><strong>Impact</strong></td></tr><tbody><tr><td rowspan=1>\
Enhancement</td>
<td>

<details><summary>Assert failure path call behavior</summary>

___

**In test, add assertions to verify mock call behavior.**

[tests/test_post_review_replies.py [1039-1061]](https://github.com/myk-org/claude-code-config/pull/111/files#diff-abc)

```diff
-del mock_deps, mock_resolve
+del mock_deps
 mock_post.return_value = False
+assert mock_post.call_count == 1
+mock_resolve.assert_not_called()
```

`[To ensure code accuracy, apply this suggestion manually]`

<details><summary>Suggestion importance[1-10]: 7</summary>

__

Why: Explanation here

</details></details></td><td align=center>Medium

</td></tr><tr><td rowspan=1><br>best practice</td>
<td>

<details><summary>Render retry command robustly</summary>

___

**Use shlex.join for better robustness.**

[myk_claude_tools/reviews/post.py [469-474]](https://github.com/myk-org/claude-code-config/pull/111/files#diff-def)

```diff
+retry_cmd = ["myk-claude-tools", "reviews", "post", str(json_path_obj)]
 print(
-    f"old code"
+    f"new code",
     flush=True,
 )
```

- [ ] **Apply / Chat**

<details><summary>Suggestion importance[1-10]: 6</summary>

__

Why: Another explanation

</details></details></td><td align=center>Low

</td></tr></tbody></table>

#### Previous suggestions

<details><summary>✅ Suggestions up to commit bd77209</summary>
<br><table>...old stuff that should be ignored...</table>
</details>
"""

REVIEW_HTML = """\
## PR Reviewer Guide 🔍

<table>
<tr><td>🎫 Ticket compliance analysis 🔶 ... </td></tr>
<tr><td>🧪 PR contains tests</td></tr>
<tr><td>🔒 No security concerns identified</td></tr>
<tr><td>⚡&nbsp;<strong>Recommended focus areas for review</strong><br><br>

<details><summary><a href='https://github.com/myk-org/claude-code-config/pull/111/files\
#diff-0ffecR466-R474'><strong>Retry Command</strong></a>

The stdout retry instruction needs absolute path for reliable copy-paste.
</summary>

```python
if failed_count > 0:
    eprint(f"Failed: {failed_count} threads")
    print(f"ACTION REQUIRED: {failed_count} thread(s) failed.")
    sys.exit(1)
```

</details>

<details><summary><a href='https://github.com/myk-org/claude-code-config/pull/111/files\
#diff-0ffecR468-R474'><strong>Output Flushing</strong></a>

Consider explicitly flushing stdout to avoid losing the instruction in buffered environments.
</summary>

```python
print(
    f"ACTION REQUIRED: {failed_count} thread(s) failed to post.",
    flush=True,
)
```

</details>

</td></tr>
</table>
"""


# =============================================================================
# Tests for parse_qodo_comment() - Dispatch Logic
# =============================================================================


class TestParseQodoComment:
    """Tests for parse_qodo_comment() dispatcher."""

    def test_dispatches_improve_comment(self) -> None:
        """Body with '## PR Code Suggestions' should dispatch to improve parser."""
        results = parse_qodo_comment(IMPROVE_HTML)
        assert len(results) >= 1
        assert all(r["qodo_type"] == "improve" for r in results)

    def test_dispatches_review_comment(self) -> None:
        """Body with '## PR Reviewer Guide' should dispatch to review parser."""
        results = parse_qodo_comment(REVIEW_HTML)
        assert len(results) >= 1
        assert all(r["qodo_type"] == "review" for r in results)

    def test_returns_empty_for_unknown_format(self) -> None:
        """Body without known markers should return empty list."""
        assert parse_qodo_comment("Just a random comment body.") == []

    def test_returns_empty_for_empty_string(self) -> None:
        """Empty string should return empty list."""
        assert parse_qodo_comment("") == []

    def test_returns_empty_for_plain_markdown(self) -> None:
        """Plain Markdown without Qodo headers should return empty list."""
        body = "## Some Other Section\n\nNot a Qodo comment."
        assert parse_qodo_comment(body) == []

    def test_review_body_containing_improve_marker_in_code_block(self) -> None:
        """A /review body that quotes the improve marker in a code block.

        When a review comment's focus area contains a code block showing
        parser source code with the literal string '## PR Code Suggestions',
        the dispatcher should still route to the review parser (not improve)
        because the body starts with '## PR Reviewer Guide'.
        """
        body = """\
## PR Reviewer Guide 🔍

<table>
<tr><td>⚡&nbsp;<strong>Recommended focus areas for review</strong><br><br>

<details><summary><a href='https://example.com'><strong>Dispatch Bug</strong></a>

Description of the issue.
</summary>

```python
if "## PR Code Suggestions" in body:
    return parse_improve_comment(body)
```

</details>

</td></tr>
</table>
"""
        results = parse_qodo_comment(body)
        assert len(results) == 1
        assert results[0]["qodo_type"] == "review"
        assert results[0]["title"] == "Dispatch Bug"


# =============================================================================
# Tests for parse_improve_comment() - /improve Parsing
# =============================================================================


class TestParseImproveComment:
    """Tests for parse_improve_comment() /improve HTML parsing."""

    def test_parses_two_suggestions_from_real_html(self) -> None:
        """Real-world HTML with two suggestions should yield two results."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert len(results) == 2

    def test_first_suggestion_title(self) -> None:
        """First suggestion title should be extracted."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["title"] == "Assert failure path call behavior"

    def test_first_suggestion_category(self) -> None:
        """First suggestion category should be 'Enhancement'."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["category"] == "Enhancement"

    def test_first_suggestion_path(self) -> None:
        """First suggestion path should be extracted from link text."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["path"] == "tests/test_post_review_replies.py"

    def test_first_suggestion_lines(self) -> None:
        """First suggestion line range should be extracted."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["line"] == 1039
        assert results[0]["end_line"] == 1061

    def test_first_suggestion_diff(self) -> None:
        """First suggestion diff should contain removed and added lines."""
        results = parse_improve_comment(IMPROVE_HTML)
        diff = results[0]["diff"]
        assert diff is not None
        assert "-del mock_deps, mock_resolve" in diff
        assert "+del mock_deps" in diff

    def test_first_suggestion_importance(self) -> None:
        """First suggestion importance should be 7."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["importance"] == 7

    def test_first_suggestion_impact(self) -> None:
        """First suggestion impact should be 'Medium'."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["impact"] == "Medium"

    def test_first_suggestion_qodo_type(self) -> None:
        """All improve suggestions should have qodo_type='improve'."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[0]["qodo_type"] == "improve"

    def test_second_suggestion_category(self) -> None:
        """Second suggestion category should be 'best practice'."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[1]["category"] == "best practice"

    def test_second_suggestion_path(self) -> None:
        """Second suggestion path should be extracted."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[1]["path"] == "myk_claude_tools/reviews/post.py"

    def test_second_suggestion_importance(self) -> None:
        """Second suggestion importance should be 6."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[1]["importance"] == 6

    def test_second_suggestion_impact(self) -> None:
        """Second suggestion impact should be 'Low'."""
        results = parse_improve_comment(IMPROVE_HTML)
        assert results[1]["impact"] == "Low"

    def test_previous_suggestions_are_ignored(self) -> None:
        """Content after '#### Previous suggestions' should be skipped."""
        results = parse_improve_comment(IMPROVE_HTML)
        # Only 2 latest suggestions, not the old ones in "Previous suggestions"
        assert len(results) == 2
        # None of the results should reference old content
        for r in results:
            assert "old stuff" not in (r.get("body") or "")

    def test_applied_suggestions_are_skipped(self) -> None:
        """Suggestions with checkmark and strikethrough should be skipped."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>✅ <s>Already applied suggestion</s></summary>

___

**Some description.**

[file.py [1-5]](https://github.com/example)

```diff
-old
+new
```

<details><summary>Suggestion importance[1-10]: 5</summary>

</details></details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 0

    def test_strikethrough_in_title_is_skipped(self) -> None:
        """Suggestion with <s> in the title (applied) should be skipped."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary><s>Applied title</s></summary>

___

**Description.**

[file.py [1-5]](https://github.com/example)

```diff
-old
+new
```

<details><summary>Suggestion importance[1-10]: 5</summary>

</details></details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 0

    def test_empty_body_returns_empty(self) -> None:
        """Empty body should return empty list."""
        assert parse_improve_comment("") == []

    def test_no_table_rows_returns_empty(self) -> None:
        """Body with header but no rows should return empty list."""
        html = "## PR Code Suggestions ✨\n<table><thead></thead></table>"
        assert parse_improve_comment(html) == []

    def test_body_field_contains_description_and_diff(self) -> None:
        """The body field should combine description, path, and diff."""
        results = parse_improve_comment(IMPROVE_HTML)
        body = results[0]["body"]
        assert "In test, add assertions" in body
        assert "test_post_review_replies.py" in body
        assert "```diff" in body

    def test_suggestion_without_diff(self) -> None:
        """Suggestion without a diff block should have diff=None."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>No diff suggestion</summary>

___

**Just a description, no code diff.**

[file.py [10-20]](https://github.com/example)

<details><summary>Suggestion importance[1-10]: 3</summary>

</details></details></td><td align=center>Low

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        assert results[0]["diff"] is None
        assert results[0]["title"] == "No diff suggestion"

    def test_suggestion_without_importance(self) -> None:
        """Suggestion without importance details should have importance=None."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>No importance</summary>

___

**Description here.**

[file.py [5-10]](https://github.com/example)

```diff
-old
+new
```

</details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        assert results[0]["importance"] is None

    def test_noise_row_from_code_block_containing_tr_is_skipped(self) -> None:
        """A <tr> inside a code block should not create a false suggestion row.

        When a code example contains the literal text '<tr>', the regex split
        creates a fragment that has <details><summary> (from the importance
        metadata) but no ___ description marker.  This row must be skipped.
        """
        html = """\
## PR Code Suggestions ✨

<table><thead><tr><td><strong>Category</strong></td><td align=left>\
<strong>Suggestion</strong></td><td align=center><strong>Impact</strong>\
</td></tr><tbody><tr><td rowspan=1>High-level</td>
<td>

<details><summary>Use a dedicated parser</summary>

___

**Replace regex parsing with a library.**


<details>
<summary>
<a href="https://github.com/example/pull/1/files#diffR17-R332">\
src/parser.py [17-332]</a>
</summary>

```python
rows = re.split(r"<tr>", body)
for row in rows:
    pass
```
</details>


<details><summary>Suggestion importance[1-10]: 8</summary>

__

Why: Regex parsing is fragile.

</details></details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        # Should get exactly 1 suggestion, not 2 (no noise from code block <tr>)
        assert len(results) == 1
        assert results[0]["title"] == "Use a dedicated parser"

    def test_noise_row_importance_only_is_skipped(self) -> None:
        """A row fragment with only importance metadata should not be parsed."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr>some code with <tr> in it

<details><summary>Suggestion importance[1-10]: 8</summary>

__

Why: Some reason.

</details></details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        # No ___ marker means this is not a real suggestion
        assert len(results) == 0

    def test_path_extracted_from_anchor_tag(self) -> None:
        """Path should be extracted from <a> tag when markdown link is absent."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>Improve parsing</summary>

___

**Use a better approach.**

<details>
<summary>
<a href="https://github.com/example/pull/1/files#diffR17-R50">\
src/utils/parser.py [17-50]</a>
</summary>

```python
# example code
```
</details>

<details><summary>Suggestion importance[1-10]: 7</summary>

__

Why: Explanation.

</details></details></td><td align=center>Medium

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        assert results[0]["path"] == "src/utils/parser.py"
        assert results[0]["line"] == 17
        assert results[0]["end_line"] == 50

    def test_path_anchor_tag_single_line(self) -> None:
        """Path from <a> tag with single line number should be extracted."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Bug</td>
<td>

<details><summary>Fix null check</summary>

___

**Add null check.**

<details>
<summary>
<a href="https://github.com/example/pull/1/files#diffR42">\
src/handler.py [42]</a>
</summary>

```python
if value is None:
    return
```
</details>

<details><summary>Suggestion importance[1-10]: 5</summary>

</details></details></td><td align=center>Low

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        assert results[0]["path"] == "src/handler.py"
        assert results[0]["line"] == 42
        assert results[0]["end_line"] is None

    def test_path_anchor_tag_no_lines(self) -> None:
        """Path from <a> tag without line numbers should extract path only."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>Refactor module</summary>

___

**Split into smaller functions.**

<details>
<summary>
<a href="https://github.com/example/pull/1/files#diff-abc">src/big_module.py</a>
</summary>

```python
pass
```
</details>

<details><summary>Suggestion importance[1-10]: 4</summary>

</details></details></td><td align=center>Low

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        assert results[0]["path"] == "src/big_module.py"
        assert results[0]["line"] is None
        assert results[0]["end_line"] is None

    def test_anchor_tag_non_path_text_ignored(self) -> None:
        """<a> tag text without path-like content should not be used as path."""
        html = """\
## PR Code Suggestions ✨

<table><tbody><tr><td rowspan=1>Enhancement</td>
<td>

<details><summary>Add feature</summary>

___

**Some description.**

See <a href="https://example.com">click here</a> for more info.

<details><summary>Suggestion importance[1-10]: 3</summary>

</details></details></td><td align=center>Low

</td></tr></tbody></table>
"""
        results = parse_improve_comment(html)
        assert len(results) == 1
        # "click here" has no dot or slash, should not be used as a path
        assert results[0]["path"] is None


# =============================================================================
# Tests for parse_review_comment() - /review Parsing
# =============================================================================


class TestParseReviewComment:
    """Tests for parse_review_comment() /review HTML parsing."""

    def test_parses_two_focus_areas_from_real_html(self) -> None:
        """Real-world HTML with two focus areas should yield two results."""
        results = parse_review_comment(REVIEW_HTML)
        assert len(results) == 2

    def test_first_focus_area_title(self) -> None:
        """First focus area title should be 'Retry Command'."""
        results = parse_review_comment(REVIEW_HTML)
        assert results[0]["title"] == "Retry Command"

    def test_second_focus_area_title(self) -> None:
        """Second focus area title should be 'Output Flushing'."""
        results = parse_review_comment(REVIEW_HTML)
        assert results[1]["title"] == "Output Flushing"

    def test_focus_area_has_description(self) -> None:
        """Focus area body should contain the description text."""
        results = parse_review_comment(REVIEW_HTML)
        assert "absolute path" in results[0]["body"]

    def test_focus_area_has_code_block(self) -> None:
        """Focus area body should contain the code block."""
        results = parse_review_comment(REVIEW_HTML)
        assert "failed_count" in results[0]["body"]

    def test_focus_area_fields_are_none(self) -> None:
        """Review focus areas should have None for improve-specific fields."""
        results = parse_review_comment(REVIEW_HTML)
        for r in results:
            assert r["category"] is None
            assert r["path"] is None
            assert r["line"] is None
            assert r["end_line"] is None
            assert r["diff"] is None
            assert r["importance"] is None
            assert r["impact"] is None

    def test_focus_area_qodo_type(self) -> None:
        """All review focus areas should have qodo_type='review'."""
        results = parse_review_comment(REVIEW_HTML)
        assert all(r["qodo_type"] == "review" for r in results)

    def test_empty_body_returns_empty(self) -> None:
        """Empty body should return empty list."""
        assert parse_review_comment("") == []

    def test_no_focus_section_returns_empty(self) -> None:
        """Body without focus area section should return empty list."""
        html = """\
## PR Reviewer Guide 🔍

<table>
<tr><td>🎫 Ticket compliance analysis 🔶 ... </td></tr>
<tr><td>🧪 PR contains tests</td></tr>
</table>
"""
        assert parse_review_comment(html) == []

    def test_skips_ticket_compliance(self) -> None:
        """Ticket compliance row should not appear in results."""
        results = parse_review_comment(REVIEW_HTML)
        titles = [r["title"] for r in results]
        assert "Ticket compliance" not in " ".join(titles)

    def test_skips_security_check(self) -> None:
        """Security check row should not appear in results."""
        results = parse_review_comment(REVIEW_HTML)
        for r in results:
            assert "security" not in r["title"].lower()

    def test_second_focus_area_description(self) -> None:
        """Second focus area should have flushing description."""
        results = parse_review_comment(REVIEW_HTML)
        assert "flushing" in results[1]["body"].lower()

    def test_second_focus_area_code(self) -> None:
        """Second focus area code block should contain flush=True."""
        results = parse_review_comment(REVIEW_HTML)
        assert "flush=True" in results[1]["body"]

    def test_tool_usage_guide_is_excluded(self) -> None:
        """The 'Tool usage guide' boilerplate should not be parsed as a focus area."""
        html = """\
## PR Reviewer Guide 🔍

<table>
<tr><td>⚡&nbsp;<strong>Recommended focus areas for review</strong><br><br>

<details><summary><a href='https://example.com'><strong>Real Focus Area</strong></a>

Some real description here.
</summary>

```python
print("real code")
```

</details>

</td></tr>
</table>
<hr>

<details> <summary><strong>Tool usage guide:</strong></summary><hr>

**Overview:**
The `review` tool scans the PR code changes.

- When commenting, use the following template:
```
/review --pr_reviewer.some_config1=...
```
- With a configuration file:
```
[pr_reviewer]
some_config1=...
```

See the review usage page for a comprehensive guide.

</details>
"""
        results = parse_review_comment(html)
        assert len(results) == 1
        assert results[0]["title"] == "Real Focus Area"
        # Verify the tool usage guide title is not in any result
        titles = [r["title"] for r in results]
        assert all("Tool usage guide" not in t for t in titles)

    def test_review_without_tool_guide_still_works(self) -> None:
        """Review body without tool usage guide should parse normally."""
        # The existing REVIEW_HTML fixture has no tool usage guide
        results = parse_review_comment(REVIEW_HTML)
        assert len(results) == 2


# =============================================================================
# Tests for _extract_path_from_link_text() - Helper
# =============================================================================


class TestExtractPathFromLinkText:
    """Tests for _extract_path_from_link_text() path extraction."""

    def test_path_with_line_range(self) -> None:
        """Path with [start-end] should return path and both lines."""
        path, start, end = _extract_path_from_link_text("tests/test_file.py [10-20]")
        assert path == "tests/test_file.py"
        assert start == 10
        assert end == 20

    def test_path_with_single_line(self) -> None:
        """Path with [line] should return path and start line only."""
        path, start, end = _extract_path_from_link_text("src/main.py [42]")
        assert path == "src/main.py"
        assert start == 42
        assert end is None

    def test_path_without_lines(self) -> None:
        """Path without brackets should return path and None lines."""
        path, start, end = _extract_path_from_link_text("src/utils.py")
        assert path == "src/utils.py"
        assert start is None
        assert end is None

    def test_empty_string(self) -> None:
        """Empty string should return all None."""
        path, start, end = _extract_path_from_link_text("")
        assert path is None
        assert start is None
        assert end is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only string should return all None."""
        path, start, end = _extract_path_from_link_text("   ")
        assert path is None
        assert start is None
        assert end is None

    def test_nested_directory_path(self) -> None:
        """Deeply nested path should be handled correctly."""
        path, start, end = _extract_path_from_link_text("a/b/c/d/file.py [100-200]")
        assert path == "a/b/c/d/file.py"
        assert start == 100
        assert end == 200

    def test_path_with_leading_trailing_whitespace(self) -> None:
        """Leading and trailing whitespace should be stripped."""
        path, start, end = _extract_path_from_link_text("  src/file.py [5-10]  ")
        assert path == "src/file.py"
        assert start == 5
        assert end == 10
