"""
Code Analyzer — Analyze project codebase structure, routes, models, and migrations.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Analyzes codebase structure for agent context building."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    async def analyze_structure(self, path: str = ".") -> str:
        """Analyze the overall project structure."""
        target = self.base_path / path
        if not target.exists():
            return f"Path '{path}' does not exist"

        lines = [f"Project Structure: {self.base_path.name}\n"]

        # Detect project type
        project_type = self._detect_project_type()
        lines.append(f"Detected Type: {project_type}\n")

        # Build directory tree (max 3 levels deep)
        lines.append("Directory Tree:")
        self._build_tree(target, lines, prefix="", max_depth=3, current_depth=0)

        # Count files by extension
        ext_counts = {}
        for file in target.rglob("*"):
            if file.is_file() and not self._is_ignored(file):
                ext = file.suffix or "(no extension)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        if ext_counts:
            lines.append("\nFile Types:")
            for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:15]:
                lines.append(f"  {ext}: {count} files")

        return "\n".join(lines)

    def _detect_project_type(self) -> str:
        """Detect the type of project based on key files."""
        if (self.base_path / "composer.json").exists():
            if (self.base_path / "artisan").exists():
                return "Laravel (PHP)"
            return "PHP (Composer)"
        if (self.base_path / "package.json").exists():
            pkg = (self.base_path / "package.json").read_text(errors="ignore")
            if "next" in pkg:
                return "Next.js"
            if "vue" in pkg:
                return "Vue.js"
            if "react" in pkg:
                return "React"
            return "Node.js"
        if (self.base_path / "requirements.txt").exists() or (self.base_path / "pyproject.toml").exists():
            if (self.base_path / "manage.py").exists():
                return "Django (Python)"
            return "Python"
        if (self.base_path / "Cargo.toml").exists():
            return "Rust"
        if (self.base_path / "go.mod").exists():
            return "Go"
        return "Unknown"

    def _build_tree(self, path: Path, lines: list, prefix: str, max_depth: int, current_depth: int):
        """Build a directory tree representation."""
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        # Filter out common ignored directories
        entries = [e for e in entries if not self._is_ignored(e)]

        for i, entry in enumerate(entries[:30]):  # Limit to 30 entries
            is_last = (i == len(entries) - 1) or (i == 29)
            connector = "└── " if is_last else "├── "
            next_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                count = sum(1 for _ in entry.rglob("*") if _.is_file() and not self._is_ignored(_))
                lines.append(f"{prefix}{connector}📁 {entry.name}/ ({count} files)")
                self._build_tree(entry, lines, next_prefix, max_depth, current_depth + 1)
            else:
                size = entry.stat().st_size
                lines.append(f"{prefix}{connector}📄 {entry.name} ({self._human_size(size)})")

    def _is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        ignored = {
            ".git", "node_modules", "vendor", "__pycache__", ".env",
            ".idea", ".vscode", "storage", "bootstrap/cache",
            ".next", "dist", "build", "target", ".DS_Store",
        }
        return any(part in ignored for part in path.parts)

    def _human_size(self, size: int) -> str:
        """Convert bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.0f}TB"

    async def find_related_files(self, keyword: str) -> str:
        """Find files related to a keyword."""
        results = []
        for file in self.base_path.rglob("*"):
            if file.is_file() and not self._is_ignored(file):
                if keyword.lower() in file.name.lower():
                    results.append(str(file.relative_to(self.base_path)))

                # Also check file contents for small files
                if file.suffix in (".php", ".py", ".js", ".ts", ".vue", ".blade.php"):
                    try:
                        content = file.read_text(encoding="utf-8", errors="ignore")
                        if len(content) < 50000 and keyword.lower() in content.lower():
                            if str(file.relative_to(self.base_path)) not in results:
                                results.append(str(file.relative_to(self.base_path)))
                    except Exception:
                        pass

        if results:
            return f"Files related to '{keyword}':\n" + "\n".join(f"  - {r}" for r in results[:20])
        return f"No files found related to '{keyword}'"
