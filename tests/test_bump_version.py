"""Tests for version file bumping."""

import json
import textwrap
from pathlib import Path

from myk_claude_tools.release.bump_version import BumpResult, bump_version_files


class TestBumpVersionFiles:
    """Tests for bump_version_files function."""

    def test_bump_pyproject_toml(self, tmp_path: Path) -> None:
        """Bump version in pyproject.toml."""
        content = textwrap.dedent("""\
            [project]
            name = "my-package"
            version = "1.0.0"
            description = "A package"
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        assert result.updated[0]["old_version"] == "1.0.0"
        assert result.updated[0]["new_version"] == "2.0.0"
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'version = "2.0.0"' in new_content
        assert 'name = "my-package"' in new_content

    def test_bump_package_json(self, tmp_path: Path) -> None:
        """Bump version in package.json."""
        data = {"name": "my-pkg", "version": "1.0.0", "main": "index.js"}
        (tmp_path / "package.json").write_text(json.dumps(data, indent=2))
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        new_data = json.loads((tmp_path / "package.json").read_text())
        assert new_data["version"] == "1.1.0"
        assert new_data["name"] == "my-pkg"

    def test_bump_setup_cfg(self, tmp_path: Path) -> None:
        """Bump version in setup.cfg."""
        content = textwrap.dedent("""\
            [metadata]
            name = my-package
            version = 1.0.0

            [options]
            packages = find:
        """)
        (tmp_path / "setup.cfg").write_text(content)
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "setup.cfg").read_text()
        assert "version = 1.1.0" in new_content
        assert "name = my-package" in new_content

    def test_bump_cargo_toml(self, tmp_path: Path) -> None:
        """Bump version in Cargo.toml."""
        content = textwrap.dedent("""\
            [package]
            name = "my-crate"
            version = "1.0.0"
            edition = "2021"
        """)
        (tmp_path / "Cargo.toml").write_text(content)
        result = bump_version_files("1.0.1", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "Cargo.toml").read_text()
        assert 'version = "1.0.1"' in new_content

    def test_bump_gradle(self, tmp_path: Path) -> None:
        """Bump version in build.gradle."""
        content = "plugins { id 'java' }\nversion = '1.0.0'\ngroup = 'com.example'\n"
        (tmp_path / "build.gradle").write_text(content)
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "build.gradle").read_text()
        assert "version = '1.1.0'" in new_content

    def test_bump_python_version(self, tmp_path: Path) -> None:
        """Bump __version__ in __init__.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('__version__ = "1.0.0"\n')
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (pkg_dir / "__init__.py").read_text()
        assert '__version__ = "1.1.0"' in new_content

    def test_bump_multiple_files(self, tmp_path: Path) -> None:
        """Bump version in multiple files at once."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 2

    def test_bump_with_files_filter(self, tmp_path: Path) -> None:
        """Only bump specified files when --files is given."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = bump_version_files("2.0.0", files=["pyproject.toml"], root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        assert result.updated[0]["path"] == "pyproject.toml"
        pkg_data = json.loads((tmp_path / "package.json").read_text())
        assert pkg_data["version"] == "1.0.0"

    def test_bump_no_version_files(self, tmp_path: Path) -> None:
        """Return error when no version files found."""
        (tmp_path / "README.md").write_text("# Hello")
        result = bump_version_files("1.0.0", root=tmp_path)
        assert result.status == "failed"
        assert result.error is not None

    def test_bump_files_filter_nonexistent(self, tmp_path: Path) -> None:
        """Return error when filtered file doesn't exist in detected files."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        result = bump_version_files("2.0.0", files=["nonexistent.toml"], root=tmp_path)
        assert result.status == "failed"

    def test_preserves_file_content(self, tmp_path: Path) -> None:
        """Ensure only the version line changes, rest is preserved."""
        content = textwrap.dedent("""\
            [project]
            name = "my-package"
            version = "1.0.0"
            description = "A great package"
            requires-python = ">=3.10"

            [build-system]
            requires = ["hatchling"]
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        bump_version_files("2.0.0", root=tmp_path)
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'name = "my-package"' in new_content
        assert 'description = "A great package"' in new_content
        assert 'requires-python = ">=3.10"' in new_content
        assert 'requires = ["hatchling"]' in new_content

    def test_bump_result_to_dict(self) -> None:
        """Test BumpResult to_dict conversion."""
        result = BumpResult(
            status="success",
            version="2.0.0",
            updated=[{"path": "pyproject.toml", "old_version": "1.0.0", "new_version": "2.0.0"}],
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["version"] == "2.0.0"
        updated = d["updated"]
        assert isinstance(updated, list)
        assert len(updated) == 1

    def test_bump_result_error_to_dict(self) -> None:
        """Test BumpResult error to_dict conversion."""
        result = BumpResult(status="failed", error="No version files found")
        d = result.to_dict()
        assert d == {"status": "failed", "error": "No version files found"}

    def test_bump_setup_cfg_dynamic_version(self, tmp_path: Path) -> None:
        """Skip setup.cfg with dynamic version directive."""
        content = textwrap.dedent("""\
            [metadata]
            name = my-package
            version = attr: mypackage.__version__
        """)
        (tmp_path / "setup.cfg").write_text(content)
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "failed"
        # The file should be untouched
        assert (tmp_path / "setup.cfg").read_text() == content

    def test_bump_pyproject_toml_correct_section(self, tmp_path: Path) -> None:
        """Only bump version in [project] section, not other sections."""
        content = textwrap.dedent("""\
            [tool.commitizen]
            version = "0.0.0"

            [project]
            name = "my-package"
            version = "1.0.0"
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        bump_version_files("2.0.0", root=tmp_path)
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'version = "2.0.0"' in new_content
        # The tool.commitizen version should be unchanged
        assert new_content.startswith('[tool.commitizen]\nversion = "0.0.0"')

    def test_bump_read_only_file(self, tmp_path: Path) -> None:
        """Handle read-only files gracefully."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "pyproject.toml").chmod(0o444)
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.skipped) == 1
        assert "I/O error" in result.skipped[0]["reason"]
        # Cleanup: restore permissions for tmp_path cleanup
        (tmp_path / "pyproject.toml").chmod(0o644)

    def test_bump_files_filter_partial_match(self, tmp_path: Path) -> None:
        """Report unmatched file paths in skipped when some files match."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        result = bump_version_files("2.0.0", files=["pyproject.toml", "nonexistent.toml"], root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        assert any("nonexistent.toml" in s["path"] for s in result.skipped)

    def test_bump_setup_cfg_correct_section(self, tmp_path: Path) -> None:
        """Only bump version in [metadata] section, not other sections."""
        content = textwrap.dedent("""\
            [tool:pytest]
            version = 99.99.99

            [metadata]
            name = my-package
            version = 1.0.0
        """)
        (tmp_path / "setup.cfg").write_text(content)
        bump_version_files("2.0.0", root=tmp_path)
        new_content = (tmp_path / "setup.cfg").read_text()
        assert "version = 2.0.0" in new_content
        # [tool:pytest] version should be unchanged
        assert "version = 99.99.99" in new_content

    def test_bump_pyproject_with_subtables(self, tmp_path: Path) -> None:
        """Bump version even when [project] has sub-tables after it."""
        content = textwrap.dedent("""\
            [project]
            name = "my-package"
            version = "1.0.0"

            [project.urls]
            Homepage = "https://example.com"

            [build-system]
            requires = ["hatchling"]
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        bump_version_files("2.0.0", root=tmp_path)
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'version = "2.0.0"' in new_content
        assert 'Homepage = "https://example.com"' in new_content
