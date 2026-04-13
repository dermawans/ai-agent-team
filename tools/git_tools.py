"""
Git Tools — Git operations for agents (commit, branch, push, diff).
"""

import logging
from pathlib import Path
from git import Repo, InvalidGitRepositoryError
import asyncio

logger = logging.getLogger(__name__)


class GitTools:
    """Git operations scoped to a target project directory."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self._repo = None

    def _get_repo(self) -> Repo:
        """Get or initialize the Git repo."""
        if self._repo is None:
            try:
                self._repo = Repo(self.base_path)
            except InvalidGitRepositoryError:
                # Initialize a new repo
                self._repo = Repo.init(self.base_path)
                logger.info(f"Initialized new Git repo at {self.base_path}")
        return self._repo

    async def init(self) -> str:
        """Initialize a Git repository."""
        def _init():
            repo = Repo.init(self.base_path)
            self._repo = repo
            return f"Initialized Git repo at {self.base_path}"
        return await asyncio.to_thread(_init)

    async def status(self) -> str:
        """Get git status."""
        def _status():
            repo = self._get_repo()
            changed = [item.a_path for item in repo.index.diff(None)]
            staged = [item.a_path for item in repo.index.diff("HEAD")] if repo.head.is_valid() else []
            untracked = repo.untracked_files

            lines = []
            if staged:
                lines.append(f"Staged: {', '.join(staged)}")
            if changed:
                lines.append(f"Modified: {', '.join(changed)}")
            if untracked:
                lines.append(f"Untracked: {', '.join(untracked)}")
            if not lines:
                lines.append("Working directory clean")
            return "\n".join(lines)

        return await asyncio.to_thread(_status)

    async def add(self, files: list[str] = None) -> str:
        """Stage files (or all if no files specified)."""
        def _add():
            repo = self._get_repo()
            if files:
                repo.index.add(files)
                return f"Staged: {', '.join(files)}"
            else:
                repo.git.add(A=True)
                return "Staged all changes"

        return await asyncio.to_thread(_add)

    async def commit(self, message: str) -> str:
        """Add all changes and commit."""
        def _commit():
            repo = self._get_repo()
            repo.git.add(A=True)
            if repo.index.diff("HEAD") or repo.untracked_files or not repo.head.is_valid():
                commit = repo.index.commit(message)
                return f"Committed: {commit.hexsha[:8]} - {message}"
            return "Nothing to commit"

        return await asyncio.to_thread(_commit)

    async def create_branch(self, name: str) -> str:
        """Create and checkout a new branch."""
        def _branch():
            repo = self._get_repo()
            if not repo.head.is_valid():
                # Need initial commit first
                repo.git.add(A=True)
                repo.index.commit("Initial commit")
            new_branch = repo.create_head(name)
            new_branch.checkout()
            return f"Created and checked out branch: {name}"

        return await asyncio.to_thread(_branch)

    async def checkout(self, branch: str) -> str:
        """Checkout an existing branch."""
        def _checkout():
            repo = self._get_repo()
            repo.git.checkout(branch)
            return f"Checked out branch: {branch}"

        return await asyncio.to_thread(_checkout)

    async def diff(self) -> str:
        """Get diff of current changes."""
        def _diff():
            repo = self._get_repo()
            return repo.git.diff() or "No changes"

        return await asyncio.to_thread(_diff)

    async def push(self, remote: str = "origin", branch: str = None) -> str:
        """Push to remote."""
        def _push():
            repo = self._get_repo()
            active_branch = branch or repo.active_branch.name
            try:
                repo.git.push(remote, active_branch)
                return f"Pushed to {remote}/{active_branch}"
            except Exception as e:
                return f"Push failed: {e}"

        return await asyncio.to_thread(_push)

    async def log(self, n: int = 10) -> str:
        """Get recent commit log."""
        def _log():
            repo = self._get_repo()
            if not repo.head.is_valid():
                return "No commits yet"
            commits = list(repo.iter_commits(max_count=n))
            lines = []
            for c in commits:
                lines.append(f"{c.hexsha[:8]} {c.message.strip()}")
            return "\n".join(lines)

        return await asyncio.to_thread(_log)

    async def create_github_repo(self, name: str, private: bool = True) -> str:
        """Create a GitHub repository using gh CLI."""
        visibility = "--private" if private else "--public"
        proc = await asyncio.create_subprocess_exec(
            "gh", "repo", "create", name, visibility,
            "--source=.", "--push",
            cwd=str(self.base_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return f"GitHub repo created: {name} ({stdout.decode().strip()})"
        else:
            return f"GitHub repo creation failed: {stderr.decode().strip()}"
