# License

`claude-code-config` is released under the MIT License. That is a permissive open source license: you can use the project, copy it, change it, redistribute it, and build on it, including for internal or commercial work. The full legal text is in the repository root `LICENSE`, and it applies to the software and associated documentation files in this repository.

## What You Can Do

- Use the project privately, internally, or commercially.
- Fork the repository and customize its agents, rules, plugins, scripts, and Python utilities.
- Copy code or configuration into your own tooling.
- Redistribute the original project or a modified version.
- Sell software or services that include this project.
- Keep your changes private; MIT does not require you to publish modifications.

> **Tip:** If you are adapting this repository for your own Claude Code setup, the MIT license lets you do that without asking for additional permission.

## What You Need To Keep

MIT is simple, but it does have one important condition: if you redistribute the software or a substantial portion of it, keep the copyright notice and permission notice with it.

In this repository, that notice starts with `Copyright (c) 2026 myk-org`.

```5:13:LICENSE
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

> **Note:** The safest default is to include the root `LICENSE` file whenever you redistribute this project, a fork of it, or a substantial copied portion.

## How The Project Declares MIT

This repository uses a single top-level `LICENSE` file, and its published artifacts repeat that MIT designation in their metadata.

The Python package `myk-claude-tools` declares MIT in `pyproject.toml`:

```1:14:pyproject.toml
[project]
name = "myk-claude-tools"
version = "1.7.2"
description = "CLI utilities for Claude Code plugins"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [{ name = "myk-org" }]
keywords = ["claude", "cli", "github", "code-review"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
```

Plugin manifests also mark themselves as MIT, for example `plugins/myk-github/.claude-plugin/plugin.json`:

```1:10:plugins/myk-github/.claude-plugin/plugin.json
{
  "name": "myk-github",
  "version": "1.4.3",
  "description": "GitHub operations for Claude Code - PR reviews, releases, review handling, and CodeRabbit rate limits",
  "author": {
    "name": "myk-org"
  },
  "repository": "https://github.com/myk-org/claude-code-config",
  "license": "MIT",
  "keywords": ["github", "pr-review", "refine-review", "release", "code-review", "coderabbit", "rate-limit"]
}
```

## Example Of Code You May Reuse

The license covers real project code, not just metadata. For example, the CLI entry point in `myk_claude_tools/cli.py` is part of the MIT-licensed repository and can be reused or adapted under the same notice requirement:

```12:27:myk_claude_tools/cli.py
@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""


cli.add_command(coderabbit_commands.coderabbit, name="coderabbit")
cli.add_command(db_commands.db, name="db")
cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")


def main() -> None:
    """Entry point."""
    cli()
```

The same practical rule applies across the repository contents, including hook scripts in `scripts/`, tests in `tests/`, and automation files such as `tox.toml` and `.pre-commit-config.yaml`, unless a specific file says otherwise.

## What MIT Does Not Promise

MIT is permissive, but it also says the software is provided "AS IS." That means there is no warranty that the project will fit your exact use case, remain bug-free, or come with support obligations.

> **Warning:** The MIT license covers this repository's code and documentation. Third-party dependencies and external tools referenced by the project, such as packages in `pyproject.toml` or hooks listed in `.pre-commit-config.yaml`, keep their own licenses.

For exact legal terms, read the root `LICENSE` file directly. This page is a practical summary, not legal advice.
