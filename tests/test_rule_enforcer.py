"""Unit tests for rule-enforcer.py hook script."""

import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

# Load the module with hyphenated name using importlib
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "rule-enforcer.py"


def _load_rule_enforcer_module() -> ModuleType:
    """Load the rule-enforcer module with hyphenated filename."""
    spec = importlib.util.spec_from_file_location("rule_enforcer", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load rule-enforcer module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["rule_enforcer"] = module
    spec.loader.exec_module(module)
    return module


rule_enforcer = _load_rule_enforcer_module()

is_forbidden_python_command: Callable[[str], bool] = rule_enforcer.is_forbidden_python_command
is_forbidden_precommit_command: Callable[[str], bool] = rule_enforcer.is_forbidden_precommit_command
main: Callable[[], None] = rule_enforcer.main


class TestIsForbiddenPythonCommand:
    """Tests for is_forbidden_python_command function."""

    # =========================================================================
    # Forbidden commands - should return True
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            # Direct python commands
            "python script.py",
            "python3 script.py",
            "python -m pytest",
            "python3 -m pytest",
            "python -c 'print(1)'",
            "python3 -c 'print(1)'",
            # Direct pip commands
            "pip install requests",
            "pip3 install requests",
            "pip uninstall package",
            "pip3 uninstall package",
            "pip freeze",
            "pip3 freeze",
            "pip list",
            "pip3 list",
        ],
    )
    def test_forbidden_direct_commands(self, command: str) -> None:
        """Direct python/pip commands should be forbidden."""
        assert is_forbidden_python_command(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            # With leading whitespace
            "  python script.py",
            "  python3 script.py",
            "\tpip install requests",
            "   pip3 install package",
        ],
    )
    def test_forbidden_with_whitespace(self, command: str) -> None:
        """Commands with leading whitespace should still be detected."""
        assert is_forbidden_python_command(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            # Mixed case (lowercased during check)
            "Python script.py",
            "PYTHON script.py",
            "Python3 script.py",
            "PIP install requests",
            "Pip3 install package",
        ],
    )
    def test_forbidden_case_insensitive(self, command: str) -> None:
        """Detection should be case-insensitive."""
        assert is_forbidden_python_command(command) is True

    # =========================================================================
    # Allowed commands - should return False
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            # uv commands
            "uv run script.py",
            "uv run python script.py",
            "uv run --with requests script.py",
            "uv run pytest tests/",
            "uv pip install requests",
            "uv pip list",
            "uv sync",
            "uv lock",
            "uv venv",
            # uvx commands
            "uvx ruff check .",
            "uvx black .",
            "uvx pytest",
        ],
    )
    def test_allowed_uv_commands(self, command: str) -> None:
        """uv and uvx commands should be allowed."""
        assert is_forbidden_python_command(command) is False

    @pytest.mark.parametrize(
        "command",
        [
            # Non-python commands
            "ls -la",
            "git status",
            "npm install",
            "cargo build",
            "go run main.go",
            "echo hello",
            "cat file.py",
            "grep python file.txt",
        ],
    )
    def test_allowed_other_commands(self, command: str) -> None:
        """Non-python/pip commands should be allowed."""
        assert is_forbidden_python_command(command) is False

    @pytest.mark.parametrize(
        "command",
        [
            # Commands containing python/pip but not starting with them
            "echo python",
            "which python",
            "which python3",
            "type python",
            "whereis pip",
            "grep 'python' file.txt",
            "cat python_script.py",
            "ls python*",
            "file python.exe",
        ],
    )
    def test_allowed_commands_containing_python_keyword(self, command: str) -> None:
        """Commands containing python/pip in arguments should be allowed."""
        assert is_forbidden_python_command(command) is False

    @pytest.mark.parametrize(
        "command",
        [
            # Similar but different commands
            "pythonw script.py",  # pythonw is different
            "python2 script.py",  # python2 not explicitly blocked
            "pip2 install package",  # pip2 not explicitly blocked
        ],
    )
    def test_edge_case_similar_commands(self, command: str) -> None:
        """Similar but different executables should be allowed."""
        # Note: pythonw, python2, pip2 are not in the forbidden list
        assert is_forbidden_python_command(command) is False

    # =========================================================================
    # Edge cases
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            "",
            "   ",
            "\t\n",
        ],
    )
    def test_empty_or_whitespace_command(self, command: str) -> None:
        """Empty or whitespace-only commands should be allowed."""
        assert is_forbidden_python_command(command) is False

    def test_command_without_space(self) -> None:
        """Commands need trailing space to match (e.g., 'python' alone)."""
        # The function checks for "python " with space, so bare "python" is allowed
        assert is_forbidden_python_command("python") is False
        assert is_forbidden_python_command("pip") is False

    @pytest.mark.parametrize(
        "command",
        [
            # Commands where python/pip appear as substrings
            "mypython script.py",
            "cpython script.py",
            "pypip install",
            "pipenv install",
        ],
    )
    def test_commands_with_python_as_substring(self, command: str) -> None:
        """Commands where python/pip is a substring should be allowed."""
        assert is_forbidden_python_command(command) is False


class TestIsForbiddenPrecommitCommand:
    """Tests for is_forbidden_precommit_command function."""

    # =========================================================================
    # Forbidden commands - should return True
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            # Direct pre-commit commands
            "pre-commit run",
            "pre-commit run --all-files",
            "pre-commit install",
            "pre-commit uninstall",
            "pre-commit autoupdate",
            "pre-commit clean",
            "pre-commit gc",
            "pre-commit sample-config",
        ],
    )
    def test_forbidden_precommit_commands(self, command: str) -> None:
        """Direct pre-commit commands should be forbidden."""
        assert is_forbidden_precommit_command(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            # With leading whitespace
            "  pre-commit run",
            "  pre-commit run --all-files",
            "\tpre-commit install",
            "   pre-commit autoupdate",
        ],
    )
    def test_forbidden_with_whitespace(self, command: str) -> None:
        """Commands with leading whitespace should still be detected."""
        assert is_forbidden_precommit_command(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            # Mixed case (lowercased during check)
            "Pre-Commit run",
            "PRE-COMMIT run --all-files",
            "Pre-commit install",
            "PRE-commit autoupdate",
        ],
    )
    def test_forbidden_case_insensitive(self, command: str) -> None:
        """Detection should be case-insensitive."""
        assert is_forbidden_precommit_command(command) is True

    # =========================================================================
    # Allowed commands - should return False
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            # prek commands (the allowed alternative)
            "prek run",
            "prek run --all-files",
            "prek install",
        ],
    )
    def test_allowed_prek_commands(self, command: str) -> None:
        """prek commands should be allowed."""
        assert is_forbidden_precommit_command(command) is False

    @pytest.mark.parametrize(
        "command",
        [
            # Commands where pre-commit appears as argument, not command
            "echo pre-commit",
            "grep pre-commit",
            "which pre-commit",
            "type pre-commit",
            "cat pre-commit-config.yaml",
            "rm .pre-commit-config.yaml",
            "git commit -m 'fix pre-commit config'",
        ],
    )
    def test_allowed_precommit_as_argument(self, command: str) -> None:
        """Commands containing pre-commit in arguments should be allowed."""
        assert is_forbidden_precommit_command(command) is False

    @pytest.mark.parametrize(
        "command",
        [
            # Non-pre-commit commands
            "ls -la",
            "git status",
            "npm install",
            "uv run script.py",
            "uvx ruff check .",
            "python script.py",  # Forbidden by other rule, but not this one
        ],
    )
    def test_allowed_other_commands(self, command: str) -> None:
        """Non-pre-commit commands should be allowed by this check."""
        assert is_forbidden_precommit_command(command) is False

    # =========================================================================
    # Edge cases
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            "",
            "   ",
            "\t\n",
        ],
    )
    def test_empty_or_whitespace_command(self, command: str) -> None:
        """Empty or whitespace-only commands should be allowed."""
        assert is_forbidden_precommit_command(command) is False

    def test_command_without_space(self) -> None:
        """Bare 'pre-commit' without arguments should be allowed."""
        # The function checks for "pre-commit " with space
        assert is_forbidden_precommit_command("pre-commit") is False

    @pytest.mark.parametrize(
        "command",
        [
            # Commands where pre-commit is a substring
            "mypre-commit run",
            "pre-commitx run",
        ],
    )
    def test_commands_with_precommit_as_substring(self, command: str) -> None:
        """Commands where pre-commit is a substring should be allowed."""
        assert is_forbidden_precommit_command(command) is False


class TestMain:
    """Tests for main function (JSON input/output protocol)."""

    def run_script(self, input_data: dict) -> tuple[str, int]:
        """Run the rule-enforcer script with given input and return output and exit code."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout, result.returncode

    # =========================================================================
    # Deny cases - forbidden python/pip commands
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            "python script.py",
            "python3 -m pytest",
            "pip install requests",
            "pip3 freeze",
        ],
    )
    def test_deny_forbidden_bash_command(self, command: str) -> None:
        """Forbidden Bash commands should be denied with proper JSON output."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        output = json.loads(stdout)

        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "deny"
        assert "uv run" in hook_output["permissionDecisionReason"]
        assert "uvx" in hook_output["permissionDecisionReason"]

    # =========================================================================
    # Deny cases - forbidden pre-commit commands
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            "pre-commit run",
            "pre-commit run --all-files",
            "pre-commit install",
            "pre-commit autoupdate",
        ],
    )
    def test_deny_forbidden_precommit_command(self, command: str) -> None:
        """Forbidden pre-commit commands should be denied with proper JSON output."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        output = json.loads(stdout)

        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "deny"
        assert "prek" in hook_output["permissionDecisionReason"]

    # =========================================================================
    # Allow cases - permitted commands
    # =========================================================================

    @pytest.mark.parametrize(
        "command",
        [
            "uv run script.py",
            "uvx ruff check .",
            "git status",
            "ls -la",
        ],
    )
    def test_allow_permitted_bash_command(self, command: str) -> None:
        """Permitted Bash commands should be allowed (no output, exit 0)."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        assert stdout == ""  # No output means allowed

    @pytest.mark.parametrize(
        "tool_name",
        [
            "Edit",
            "Write",
            "Read",
            "Glob",
            "Grep",
            "WebFetch",
            "NotebookEdit",
        ],
    )
    def test_allow_non_bash_tools(self, tool_name: str) -> None:
        """Non-Bash tools should always be allowed."""
        input_data = {
            "tool_name": tool_name,
            "tool_input": {"some": "data"},
        }
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        assert stdout == ""

    # =========================================================================
    # Error handling - fail open
    # =========================================================================

    def test_fail_open_on_invalid_json(self) -> None:
        """Invalid JSON input should fail open (exit 0, no output)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert result.stdout == ""

    def test_fail_open_on_missing_tool_name(self) -> None:
        """Missing tool_name should fail open."""
        input_data = {"tool_input": {"command": "python script.py"}}
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        assert stdout == ""

    def test_fail_open_on_missing_tool_input(self) -> None:
        """Missing tool_input should fail open."""
        input_data = {"tool_name": "Bash"}
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        assert stdout == ""

    def test_fail_open_on_missing_command(self) -> None:
        """Missing command in tool_input should fail open."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {},
        }
        stdout, exit_code = self.run_script(input_data)

        assert exit_code == 0
        assert stdout == ""

    def test_fail_open_on_empty_input(self) -> None:
        """Empty input should fail open."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert result.stdout == ""


class TestMainWithMock:
    """Tests for main function using mocks for stdin."""

    def test_main_deny_python_command(self) -> None:
        """Test main function denies python commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "python script.py"},
        }

        with patch("sys.stdin.read", return_value=json.dumps(input_data)):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_called_once()

                output = json.loads(mock_print.call_args[0][0])
                assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_main_deny_precommit_command(self) -> None:
        """Test main function denies pre-commit commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pre-commit run --all-files"},
        }

        with patch("sys.stdin.read", return_value=json.dumps(input_data)):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_called_once()

                output = json.loads(mock_print.call_args[0][0])
                assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
                assert "prek" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_main_allow_prek_command(self) -> None:
        """Test main function allows prek commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "prek run --all-files"},
        }

        with patch("sys.stdin.read", return_value=json.dumps(input_data)):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_not_called()

    def test_main_allow_uv_command(self) -> None:
        """Test main function allows uv commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "uv run script.py"},
        }

        with patch("sys.stdin.read", return_value=json.dumps(input_data)):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_not_called()

    def test_main_allow_non_bash_tool(self) -> None:
        """Test main function allows non-Bash tools."""
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/some/file.py"},
        }

        with patch("sys.stdin.read", return_value=json.dumps(input_data)):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_not_called()

    def test_main_handles_exception_gracefully(self) -> None:
        """Test main function fails open on exceptions."""
        with patch("sys.stdin.read", side_effect=Exception("Read error")):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_print.assert_not_called()
