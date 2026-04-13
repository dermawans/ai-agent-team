"""
Shell Tools — Sandboxed shell command execution for agents.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Allowed command prefixes for safety
ALLOWED_COMMANDS = [
    "php", "composer", "npm", "npx", "node", "python", "pip",
    "artisan", "pytest", "cargo", "go", "dotnet", "mvn", "gradle",
    "git", "gh", "mkdir", "ls", "dir", "cat", "type", "echo",
    "curl", "wget", "tar", "unzip", "cp", "copy",
]

# Blocked patterns for safety
BLOCKED_PATTERNS = [
    "rm -rf /", "del /s /q C:", "format", "shutdown",
    ":(){ :|:& };:", "mkfs", "dd if=",
]


class ShellTools:
    """Sandboxed shell command execution scoped to a project directory."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def _is_allowed(self, command: str) -> bool:
        """Check if a command is allowed."""
        cmd_lower = command.strip().lower()

        # Check blocked patterns
        for blocked in BLOCKED_PATTERNS:
            if blocked in cmd_lower:
                return False

        # Check allowed prefixes
        first_word = cmd_lower.split()[0] if cmd_lower else ""
        # Allow if first word matches or ends with an allowed command
        for allowed in ALLOWED_COMMANDS:
            if first_word == allowed or first_word.endswith(allowed):
                return True

        return False

    async def run(self, command: str, timeout: int = 120) -> str:
        """
        Run a shell command in the project directory.

        Args:
            command: Shell command to execute
            timeout: Max execution time in seconds

        Returns:
            Command output (stdout + stderr)
        """
        if not self._is_allowed(command):
            return f"Error: Command '{command}' is not allowed for security reasons."

        logger.info(f"Shell: {command}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.base_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = ""
            if output:
                result += output
            if errors:
                result += f"\nSTDERR:\n{errors}"
            if proc.returncode != 0:
                result += f"\nExit code: {proc.returncode}"

            # Truncate very long output
            if len(result) > 10000:
                result = result[:10000] + "\n... (output truncated)"

            return result.strip() or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
