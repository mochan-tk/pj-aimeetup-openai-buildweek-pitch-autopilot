#!/usr/bin/env python3
"""Collect bounded, factual development evidence from a Git repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


MAX_COMMITS = 50
MAX_SOURCE_FILES = 10
MAX_SOURCE_LINES = 200
SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}


class CollectionError(RuntimeError):
    """Raised when repository facts cannot be collected."""


def _git(repo: Path, *args: str) -> str:
    command = ["git", "-C", str(repo), *args]
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise CollectionError("git is not installed or is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
        raise CollectionError(detail) from exc
    return result.stdout


def _read_readme_at_head(repo: Path) -> str:
    root_files = _git(repo, "ls-tree", "--name-only", "HEAD").splitlines()
    readme = next(
        (name for name in root_files if Path(name).name.lower().startswith("readme")),
        None,
    )
    if readme is None:
        return ""
    return _git(repo, "show", f"HEAD:{readme}")


def _collect_commits(repo: Path) -> list[dict[str, str]]:
    raw = _git(
        repo,
        "log",
        f"-{MAX_COMMITS}",
        "--format=%H%x00%cI%x00%s%x00",
    )
    fields = raw.split("\0")
    commits: list[dict[str, str]] = []
    for index in range(0, len(fields) - 2, 3):
        commit_hash = fields[index].lstrip("\n")
        if not commit_hash:
            continue
        date, subject = fields[index + 1 : index + 3]
        stat = _git(
            repo,
            "show",
            "--stat",
            "--format=",
            "--no-renames",
            commit_hash,
        ).strip()
        commits.append(
            {"hash": commit_hash, "date": date, "subject": subject, "stat": stat}
        )
    return commits


def _collect_sources(repo: Path) -> list[dict[str, str]]:
    tracked = _git(repo, "ls-files", "-z").split("\0")
    candidates: list[tuple[int, str, Path]] = []
    for relative in tracked:
        if not relative or Path(relative).suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        path = repo / relative
        if not path.is_file():
            continue
        candidates.append((path.stat().st_mtime_ns, relative, path))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    sources = []
    for _, relative, path in candidates[:MAX_SOURCE_FILES]:
        with path.open("r", encoding="utf-8", errors="replace") as source:
            head = "".join(line for _, line in zip(range(MAX_SOURCE_LINES), source))
        sources.append({"path": relative, "head": head})
    return sources


def _collect_screenshots(repo: Path) -> list[str]:
    screenshot_dir = repo / "assets" / "screenshots"
    if not screenshot_dir.is_dir():
        return []
    return sorted(
        path.relative_to(repo).as_posix()
        for path in screenshot_dir.rglob("*")
        if path.is_file()
    )


def collect(repo_path: str) -> dict:
    """Return bounded repository facts matching the frozen context contract."""
    repo = Path(repo_path).expanduser().resolve()
    if not repo.is_dir():
        raise CollectionError(f"repository path does not exist or is not a directory: {repo}")

    try:
        inside_work_tree = _git(repo, "rev-parse", "--is-inside-work-tree").strip()
    except CollectionError as exc:
        raise CollectionError(f"not a Git repository: {repo} ({exc})") from exc
    if inside_work_tree != "true":
        raise CollectionError(f"not a Git working tree: {repo}")

    head = _git(repo, "rev-parse", "HEAD").strip()
    return {
        "repo": {
            "name": repo.name,
            "path": str(repo),
            "head": head,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        "commits": _collect_commits(repo),
        "readme": _read_readme_at_head(repo),
        "sources": _collect_sources(repo),
        "screenshots": _collect_screenshots(repo),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect bounded development facts from a Git repository."
    )
    parser.add_argument("repo", help="path to a Git working tree")
    parser.add_argument("-o", "--output", required=True, help="output JSON path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        context = collect(args.repo)
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(context, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (CollectionError, OSError) as exc:
        print(f"collect.py: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
