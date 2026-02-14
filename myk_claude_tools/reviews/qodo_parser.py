"""Parse Qodo PR review comments into structured suggestion data.

This module extracts actionable suggestions from Qodo's /improve and /review
comment formats. It uses only stdlib (re) for parsing the well-structured HTML.

Supported formats:
  - /improve: HTML table with code suggestions (category, diff, importance)
  - /review:  "Recommended focus areas" with code blocks and descriptions
"""

from __future__ import annotations

import re
from typing import Any


def parse_qodo_comment(body: str) -> list[dict[str, Any]]:
    """Dispatch to the appropriate parser based on comment format.

    Args:
        body: Raw Markdown/HTML body of a Qodo PR comment.

    Returns:
        List of parsed suggestion dicts, or empty list if format is unrecognised.
    """
    if not body:
        return []

    if "## PR Code Suggestions" in body:
        return parse_improve_comment(body)

    if "## PR Reviewer Guide" in body:
        return parse_review_comment(body)

    return []


# ---------------------------------------------------------------------------
# /improve parser
# ---------------------------------------------------------------------------

_APPLIED_SUGGESTION_RE = re.compile(r"<summary>\s*✅\s*")

_CATEGORY_RE = re.compile(
    r"<td[^>]*>(?:\s*<br>)?\s*(?:rowspan=\d+\s*>)?(?:\s*<br>)?\s*([^<]+?)\s*</td>",
)

_IMPROVE_TITLE_RE = re.compile(
    r"<details><summary>(?P<title>.+?)</summary>",
    re.DOTALL,
)

_IMPROVE_DESC_RE = re.compile(
    r"___\s*\n\s*\*\*(?P<desc>.+?)\*\*",
    re.DOTALL,
)

_IMPROVE_PATH_RE = re.compile(
    r"\[(?P<path>[^\]]+?)\s*\[(?P<lines>[^\]]+)\]\]\((?P<url>[^)]+)\)",
)

_IMPROVE_PATH_NO_LINES_RE = re.compile(
    r"\[(?P<path>[^\]\[]+?)\]\((?P<url>[^)]+)\)",
)

_IMPROVE_DIFF_RE = re.compile(
    r"```diff\s*\n(?P<diff>.+?)```",
    re.DOTALL,
)

_IMPORTANCE_RE = re.compile(
    r"Suggestion importance\[1-10\]:\s*(?P<score>\d+)",
)

_IMPACT_RE = re.compile(
    r"<td\s+align=center>\s*(?P<impact>\w+)\s*(?:\n|</td>)",
)


def _extract_path_from_link_text(text: str) -> tuple[str | None, int | None, int | None]:
    """Parse file path and optional line range from link text.

    Handles formats:
        ``"tests/test_file.py [10-20]"``  -> ("tests/test_file.py", 10, 20)
        ``"tests/test_file.py [10]"``     -> ("tests/test_file.py", 10, None)
        ``"tests/test_file.py"``          -> ("tests/test_file.py", None, None)
        ``""``                            -> (None, None, None)

    Returns:
        Tuple of (path, start_line, end_line).
    """
    if not text or not text.strip():
        return None, None, None

    text = text.strip()

    # Try "path [start-end]"
    m = re.match(r"^(?P<path>.+?)\s+\[(?P<start>\d+)-(?P<end>\d+)\]$", text)
    if m:
        return m.group("path").strip(), int(m.group("start")), int(m.group("end"))

    # Try "path [line]"
    m = re.match(r"^(?P<path>.+?)\s+\[(?P<line>\d+)\]$", text)
    if m:
        return m.group("path").strip(), int(m.group("line")), None

    # Plain path (no brackets)
    return text, None, None


def parse_improve_comment(body: str) -> list[dict[str, Any]]:
    """Parse a Qodo ``/improve`` comment into a list of suggestions.

    Only the **latest suggestions** section is parsed; everything after the
    ``#### Previous suggestions`` marker is ignored.  Applied suggestions
    (marked with a checkmark and strikethrough) are also skipped.

    Returns:
        List of suggestion dicts with keys: title, category, path, line,
        end_line, diff, importance, impact, body, qodo_type.
    """
    if not body:
        return []

    # Truncate at "Previous suggestions" to only process latest
    prev_marker = "#### Previous suggestions"
    marker_idx = body.find(prev_marker)
    if marker_idx != -1:
        body = body[:marker_idx]

    results: list[dict[str, Any]] = []

    # Split body into table row blocks using <tr> tags
    rows = re.split(r"<tr>", body)

    for row in rows:
        # Skip rows without suggestion details
        if "<details><summary>" not in row:
            continue

        # Skip applied suggestions (checkmark in details summary)
        if _APPLIED_SUGGESTION_RE.search(row):
            continue

        # --- Category ---
        category: str | None = None
        cat_match = _CATEGORY_RE.search(row)
        if cat_match:
            category = cat_match.group(1).strip()

        # --- Title ---
        title: str | None = None
        title_match = _IMPROVE_TITLE_RE.search(row)
        if title_match:
            raw_title = title_match.group("title")
            # Skip if title contains strikethrough (applied suggestion)
            if "<s>" in raw_title:
                continue
            # Clean HTML tags from title
            title = re.sub(r"<[^>]+>", "", raw_title).strip()

        if not title:
            continue

        # --- Description ---
        desc: str | None = None
        desc_match = _IMPROVE_DESC_RE.search(row)
        if desc_match:
            desc = desc_match.group("desc").strip()

        # --- File path and lines ---
        path: str | None = None
        start_line: int | None = None
        end_line: int | None = None

        path_match = _IMPROVE_PATH_RE.search(row)
        if path_match:
            link_text = f"{path_match.group('path')} [{path_match.group('lines')}]"
            path, start_line, end_line = _extract_path_from_link_text(link_text)
        else:
            path_match_no_lines = _IMPROVE_PATH_NO_LINES_RE.search(row)
            if path_match_no_lines:
                path = path_match_no_lines.group("path").strip()

        # --- Diff ---
        diff: str | None = None
        diff_match = _IMPROVE_DIFF_RE.search(row)
        if diff_match:
            diff = diff_match.group("diff").strip()

        # --- Importance ---
        importance: int | None = None
        imp_match = _IMPORTANCE_RE.search(row)
        if imp_match:
            importance = int(imp_match.group("score"))

        # --- Impact ---
        impact: str | None = None
        imp_td_match = _IMPACT_RE.search(row)
        if imp_td_match:
            impact = imp_td_match.group("impact").strip()

        # --- Build body text ---
        body_parts: list[str] = []
        if desc:
            body_parts.append(desc)
        if path:
            line_info = ""
            if start_line is not None and end_line is not None:
                line_info = f" [{start_line}-{end_line}]"
            elif start_line is not None:
                line_info = f" [{start_line}]"
            body_parts.append(f"{path}{line_info}")
        if diff:
            body_parts.append(f"```diff\n{diff}\n```")

        results.append({
            "title": title,
            "category": category,
            "path": path,
            "line": start_line,
            "end_line": end_line,
            "diff": diff,
            "importance": importance,
            "impact": impact,
            "body": "\n".join(body_parts) if body_parts else title,
            "qodo_type": "improve",
        })

    return results


# ---------------------------------------------------------------------------
# /review parser
# ---------------------------------------------------------------------------

_REVIEW_FOCUS_RE = re.compile(
    r"Recommended focus areas for review",
    re.IGNORECASE,
)

_REVIEW_DETAILS_RE = re.compile(
    r"<details>\s*<summary>\s*(?P<summary>.*?)</summary>\s*(?P<content>.*?)</details>",
    re.DOTALL,
)

_REVIEW_TITLE_RE = re.compile(
    r"<strong>(?P<title>[^<]+)</strong>",
)

_REVIEW_CODE_BLOCK_RE = re.compile(
    r"```\w*\s*\n(?P<code>.+?)```",
    re.DOTALL,
)


def parse_review_comment(body: str) -> list[dict[str, Any]]:
    """Parse a Qodo ``/review`` comment into a list of focus areas.

    Only the "Recommended focus areas for review" section is parsed.
    Ticket compliance, test indicators, security checks and tool usage
    guide sections are ignored.

    Returns:
        List of focus-area dicts with keys: title, category, path, line,
        end_line, diff, importance, impact, body, qodo_type.
    """
    if not body:
        return []

    # Find the focus area section
    focus_match = _REVIEW_FOCUS_RE.search(body)
    if not focus_match:
        return []

    # Extract from the focus-area marker to end of body
    focus_section = body[focus_match.start() :]

    results: list[dict[str, Any]] = []

    # Find all <details> blocks in the focus section
    for det_match in _REVIEW_DETAILS_RE.finditer(focus_section):
        summary = det_match.group("summary")
        content = det_match.group("content")

        # --- Title ---
        title: str | None = None
        title_match = _REVIEW_TITLE_RE.search(summary)
        if title_match:
            title = title_match.group("title").strip()

        if not title:
            continue

        # --- Description ---
        # Text after </a> and before </summary> (within summary block)
        desc: str | None = None
        desc_match = re.search(r"</a>\s*\n?\s*(?P<desc>.+)", summary, re.DOTALL)
        if desc_match:
            raw_desc = desc_match.group("desc").strip()
            # Clean HTML tags
            raw_desc = re.sub(r"<[^>]+>", "", raw_desc).strip()
            if raw_desc:
                desc = raw_desc

        # --- Code block ---
        code: str | None = None
        code_match = _REVIEW_CODE_BLOCK_RE.search(content)
        if code_match:
            code = code_match.group("code").strip()

        # --- Build body text ---
        body_parts: list[str] = []
        if desc:
            body_parts.append(desc)
        if code:
            body_parts.append(f"```\n{code}\n```")

        results.append({
            "title": title,
            "category": None,
            "path": None,
            "line": None,
            "end_line": None,
            "diff": None,
            "importance": None,
            "impact": None,
            "body": "\n".join(body_parts) if body_parts else title,
            "qodo_type": "review",
        })

    return results
