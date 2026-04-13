"""
File Tools — Read, write, modify, and list files in the target project.
"""

import os
import aiofiles
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileTools:
    """File operations scoped to a target project directory."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve and validate a path is within the project directory."""
        resolved = (self.base_path / relative_path).resolve()
        # Security check — ensure path is within the project
        if not str(resolved).startswith(str(self.base_path)):
            raise ValueError(f"Path '{relative_path}' is outside the project directory")
        return resolved

    async def read_file(self, path: str) -> str:
        """Read the contents of a file."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist"
        try:
            async with aiofiles.open(resolved, "r", encoding="utf-8") as f:
                content = await f.read()
            logger.info(f"Read file: {path} ({len(content)} chars)")
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    async def write_file(self, path: str, content: str) -> str:
        """Write content to a file (creates directories if needed)."""
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(resolved, "w", encoding="utf-8") as f:
                await f.write(content)
            logger.info(f"Wrote file: {path} ({len(content)} chars)")
            return f"Successfully wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    async def modify_file(self, path: str, search: str, replace: str) -> str:
        """Find and replace text in a file."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist"

        try:
            async with aiofiles.open(resolved, "r", encoding="utf-8") as f:
                content = await f.read()

            if search not in content:
                return f"Error: Search text not found in {path}"

            new_content = content.replace(search, replace, 1)

            async with aiofiles.open(resolved, "w", encoding="utf-8") as f:
                await f.write(new_content)

            logger.info(f"Modified file: {path}")
            return f"Successfully modified {path}"
        except Exception as e:
            return f"Error modifying file: {e}"

    async def append_file(self, path: str, content: str) -> str:
        """Append content to a file."""
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(resolved, "a", encoding="utf-8") as f:
                await f.write(content)
            return f"Successfully appended to {path}"
        except Exception as e:
            return f"Error appending to file: {e}"

    async def list_directory(self, path: str = ".") -> str:
        """List contents of a directory."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return f"Error: Directory '{path}' does not exist"
        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory"

        try:
            items = []
            for item in sorted(resolved.iterdir()):
                rel_path = item.relative_to(self.base_path)
                if item.is_dir():
                    items.append(f"📁 {rel_path}/")
                else:
                    size = item.stat().st_size
                    items.append(f"📄 {rel_path} ({size:,} bytes)")
            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"

    async def file_exists(self, path: str) -> bool:
        """Check if a file exists."""
        return self._resolve_path(path).exists()

    async def delete_file(self, path: str) -> str:
        """Delete a file."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist"
        try:
            resolved.unlink()
            return f"Deleted {path}"
        except Exception as e:
            return f"Error deleting file: {e}"
