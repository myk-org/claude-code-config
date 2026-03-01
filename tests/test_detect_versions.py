"""Tests for version file detection."""

import json
import textwrap
from pathlib import Path

from myk_claude_tools.release.detect_versions import VersionFile, detect_version_files


class TestDetectVersionFiles:
    """Tests for detect_version_files function."""

    def test_pyproject_toml(self, tmp_path: Path) -> None:
        """Detect version in pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "my-package"
                version = "1.2.3"
                description = "A package"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "pyproject.toml"
        assert result[0].current_version == "1.2.3"
        assert result[0].file_type == "pyproject"

    def test_package_json(self, tmp_path: Path) -> None:
        """Detect version in package.json."""
        (tmp_path / "package.json").write_text(json.dumps({"name": "my-pkg", "version": "2.0.1", "main": "index.js"}))
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "package.json"
        assert result[0].current_version == "2.0.1"
        assert result[0].file_type == "package_json"

    def test_setup_cfg(self, tmp_path: Path) -> None:
        """Detect version in setup.cfg."""
        (tmp_path / "setup.cfg").write_text(
            textwrap.dedent("""\
                [metadata]
                name = my-package
                version = 0.9.0

                [options]
                packages = find:
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "setup.cfg"
        assert result[0].current_version == "0.9.0"
        assert result[0].file_type == "setup_cfg"

    def test_cargo_toml(self, tmp_path: Path) -> None:
        """Detect version in Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent("""\
                [package]
                name = "my-crate"
                version = "3.1.4"
                edition = "2021"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "Cargo.toml"
        assert result[0].current_version == "3.1.4"
        assert result[0].file_type == "cargo"

    def test_build_gradle(self, tmp_path: Path) -> None:
        """Detect version in build.gradle."""
        (tmp_path / "build.gradle").write_text(
            textwrap.dedent("""\
                plugins {
                    id 'java'
                }
                version = '1.0.5'
                group = 'com.example'
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "build.gradle"
        assert result[0].current_version == "1.0.5"
        assert result[0].file_type == "gradle"

    def test_build_gradle_kts(self, tmp_path: Path) -> None:
        """Detect version in build.gradle.kts."""
        (tmp_path / "build.gradle.kts").write_text(
            textwrap.dedent("""\
                plugins {
                    kotlin("jvm") version "1.9.0"
                }
                version = "2.3.0"
                group = "com.example"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "build.gradle.kts"
        assert result[0].current_version == "2.3.0"
        assert result[0].file_type == "gradle"

    def test_init_py_version(self, tmp_path: Path) -> None:
        """Detect __version__ in __init__.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('__version__ = "0.5.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "mypackage/__init__.py"
        assert result[0].current_version == "0.5.0"
        assert result[0].file_type == "python_version"

    def test_version_py(self, tmp_path: Path) -> None:
        """Detect __version__ in version.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "version.py").write_text('__version__ = "1.0.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "mypackage/version.py"
        assert result[0].current_version == "1.0.0"
        assert result[0].file_type == "python_version"

    def test_multiple_file_types(self, tmp_path: Path) -> None:
        """Detect multiple version files in one repo."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = detect_version_files(tmp_path)
        assert len(result) == 2
        paths = {r.path for r in result}
        assert paths == {"pyproject.toml", "package.json"}

    def test_no_version_files(self, tmp_path: Path) -> None:
        """Return empty list when no version files exist."""
        (tmp_path / "README.md").write_text("# Hello")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_skips_excluded_dirs(self, tmp_path: Path) -> None:
        """Skip __init__.py files in excluded directories."""
        venv_dir = tmp_path / ".venv" / "lib" / "somepackage"
        venv_dir.mkdir(parents=True)
        (venv_dir / "__init__.py").write_text('__version__ = "9.9.9"\n')

        node_dir = tmp_path / "node_modules" / "somepkg"
        node_dir.mkdir(parents=True)
        (node_dir / "__init__.py").write_text('__version__ = "8.8.8"\n')

        result = detect_version_files(tmp_path)
        assert result == []

    def test_malformed_pyproject_no_version(self, tmp_path: Path) -> None:
        """Handle pyproject.toml without a version field."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "my-package"
                description = "No version here"
            """)
        )
        result = detect_version_files(tmp_path)
        assert result == []

    def test_malformed_package_json(self, tmp_path: Path) -> None:
        """Handle package.json without valid JSON."""
        (tmp_path / "package.json").write_text("not json at all")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_init_py_without_version(self, tmp_path: Path) -> None:
        """Skip __init__.py files that don't have __version__."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Just a package\n")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_version_file_dataclass(self) -> None:
        """Test VersionFile to_dict conversion."""
        vf = VersionFile(path="pyproject.toml", current_version="1.0.0", file_type="pyproject")
        d = vf.to_dict()
        assert d == {"path": "pyproject.toml", "current_version": "1.0.0", "type": "pyproject"}

    def test_gradle_double_quote(self, tmp_path: Path) -> None:
        """Detect version with double quotes in build.gradle."""
        (tmp_path / "build.gradle").write_text('version "4.0.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "4.0.0"

    def test_prerelease_version(self, tmp_path: Path) -> None:
        """Detect pre-release version strings."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0-rc.1"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "1.0.0-rc.1"

    def test_setup_cfg_dynamic_version(self, tmp_path: Path) -> None:
        """Skip setup.cfg with dynamic version (attr: directive)."""
        (tmp_path / "setup.cfg").write_text(
            textwrap.dedent("""\
                [metadata]
                name = my-package
                version = attr: mypackage.__version__
            """)
        )
        result = detect_version_files(tmp_path)
        assert result == []

    def test_pyproject_toml_wrong_section(self, tmp_path: Path) -> None:
        """Only detect version from [project] section, not other sections."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [tool.commitizen]
                version = "0.0.0"

                [project]
                name = "my-package"
                version = "1.2.3"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "1.2.3"

    def test_cargo_toml_wrong_section(self, tmp_path: Path) -> None:
        """Only detect version from [package] section, not dependencies."""
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent("""\
                [dependencies]
                serde = { version = "1.0" }

                [package]
                name = "my-crate"
                version = "2.0.0"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "2.0.0"
