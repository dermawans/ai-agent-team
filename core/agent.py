"""
Base Agent — Foundation class for all specialized agents.
Handles LLM interaction, file writing from response, messaging, and activity logging.
"""

import json
import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import update
from database.models import Agent as AgentModel, ActivityLog, generate_uuid, utcnow
from database.connection import db_manager
from core.llm_client import LLMClient
from core.message_bus import MessageBus
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)


class Agent:
    """
    Base class for all AI agents in the system.
    Each agent has a role, system prompt, and generates code that gets written to disk.
    """

    def __init__(
        self,
        agent_db: AgentModel,
        llm_client: LLMClient,
        message_bus: MessageBus,
        task_manager: TaskManager,
        tools: dict = None,
        broadcast_callback=None,
    ):
        self.id = agent_db.id
        self.agent_type = agent_db.agent_type
        self.display_name = agent_db.display_name
        self.system_prompt = agent_db.system_prompt
        self.project_id = agent_db.project_id
        self.llm = llm_client
        self.message_bus = message_bus
        self.task_manager = task_manager
        self.tools = tools or {}
        self._broadcast_callback = broadcast_callback
        self._conversation_history: list[dict] = []
        self._status = "idle"
        self._project_path = "."  # Set by orchestrator when spawning

    async def execute_task(self, task) -> str:
        """
        Execute a task: ask LLM to generate code, then extract and write files to disk.
        """
        await self._set_status("active", current_task_id=task.id)
        await self._log_activity("task_started", f"Starting task: {task.title}")

        try:
            # Build the task prompt
            task_prompt = await self._build_task_prompt(task)
            self._conversation_history.append({"role": "user", "content": task_prompt})

            # Check for pending messages from other agents
            pending_msgs = await self.message_bus.get_pending_messages(self.id, self.project_id)
            if pending_msgs:
                msg_context = "\n\nMessages from other agents:\n"
                for msg in pending_msgs:
                    msg_context += f"- [{msg.message_type}] from {msg.from_agent_id[:8]}: {msg.content}\n"
                self._conversation_history[-1]["content"] += msg_context

            await self._log_activity("thinking", f"Generating code for: {task.title}")

            # Call LLM
            response = await self.llm.chat(
                system_prompt=self.system_prompt,
                messages=self._conversation_history,
            )

            final_result = response.content or ""
            self._conversation_history.append({"role": "assistant", "content": final_result})

            # Extract file blocks and write them to disk
            files_written = await self._extract_and_write_files(final_result)

            if files_written:
                await self._log_activity("writing_file",
                    f"Created {len(files_written)} files: {', '.join(files_written[:5])}")
            else:
                await self._log_activity("thinking", "No file blocks found in response (advisory task)")

            # Check if agent wants to send a message to another agent
            messages_to_send = self._extract_messages(final_result)
            for msg in messages_to_send:
                await self.message_bus.send(
                    project_id=self.project_id,
                    from_agent_id=self.id,
                    to_agent_id=msg.get("to"),
                    message_type=msg.get("type", "info"),
                    content=msg.get("content", ""),
                    blocking=msg.get("blocking", False),
                    related_task_id=task.id,
                )

            await self._log_activity("task_completed", f"Completed: {task.title}")
            await self._set_status("idle")

            return final_result

        except Exception as e:
            error_msg = f"Error executing task: {str(e)}"
            await self._log_activity("error", error_msg)
            await self._set_status("error")
            raise

    async def _extract_and_write_files(self, content: str) -> list[str]:
        """
        Extract file blocks from LLM response and write them to disk.

        Supports formats:
        1. --- FILE: path/to/file.ext ---
           content
           --- END FILE ---

        2. ```filepath:path/to/file.ext
           content
           ```

        3. ```language
           // file: path/to/file.ext
           content
           ```
        """
        files_written = []
        project_path = self._project_path

        # Ensure project directory exists
        os.makedirs(project_path, exist_ok=True)

        # Pattern 1: --- FILE: path --- ... --- END FILE ---
        file_pattern1 = r'---\s*FILE:\s*(.+?)\s*---\s*\n(.*?)\n---\s*END\s*FILE\s*---'
        for match in re.finditer(file_pattern1, content, re.DOTALL):
            filepath = match.group(1).strip()
            file_content = match.group(2)
            if await self._write_project_file(project_path, filepath, file_content):
                files_written.append(filepath)

        if files_written:
            return files_written

        # Pattern 2: ```filepath:path/to/file or ```path/to/file.ext
        file_pattern2 = r'```(?:filepath:)?([^\n`]+\.[a-zA-Z]{1,10})\s*\n(.*?)```'
        lang_tags = {'python', 'javascript', 'php', 'html', 'css', 'json', 'bash',
                     'shell', 'sql', 'yaml', 'yml', 'xml', 'tool_call', 'agent_message',
                     'markdown', 'md', 'text', 'plaintext', 'diff', 'log', 'conf',
                     'blade.php', 'env', 'txt'}
        for match in re.finditer(file_pattern2, content, re.DOTALL):
            filepath = match.group(1).strip()
            file_content = match.group(2)
            if filepath.lower() not in lang_tags and ('/' in filepath or '\\' in filepath):
                if await self._write_project_file(project_path, filepath, file_content):
                    files_written.append(filepath)

        if files_written:
            return files_written

        # Pattern 3: Look for file paths in code blocks with comments
        code_blocks = re.finditer(r'```\w*\n(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            block_content = block.group(1)
            first_line = block_content.split('\n')[0].strip()
            file_indicators = [
                r'(?://|#|/\*|<!--)\s*(?:file|filename|path):\s*(.+)',
            ]
            for indicator in file_indicators:
                fmatch = re.match(indicator, first_line, re.IGNORECASE)
                if fmatch:
                    filepath = fmatch.group(1).strip().rstrip('*/ -->')
                    remaining_content = '\n'.join(block_content.split('\n')[1:])
                    if await self._write_project_file(project_path, filepath, remaining_content):
                        files_written.append(filepath)
                    break

        return files_written

    async def _write_project_file(self, project_path: str, filepath: str, content: str) -> bool:
        """Write a file to the project directory safely."""
        # Clean the filepath
        filepath = filepath.strip().strip('"').strip("'")
        filepath = filepath.lstrip('/').lstrip('\\')

        if not filepath or '..' in filepath:
            return False

        full_path = os.path.join(project_path, filepath)

        # Security: ensure we're still inside project_path
        abs_project = os.path.abspath(project_path)
        abs_file = os.path.abspath(full_path)
        if not abs_file.startswith(abs_project):
            logger.warning(f"Blocked file write outside project: {filepath}")
            return False

        # Create parent directories
        os.makedirs(os.path.dirname(abs_file) or '.', exist_ok=True)

        # Write the file
        with open(abs_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Wrote file: {filepath}")
        return True

    async def _build_task_prompt(self, task) -> str:
        """Build a comprehensive prompt for the task."""
        prompt_parts = [
            f"# Task: {task.title}",
            f"\n## Description\n{task.description}",
        ]

        # Add input context from previous tasks
        if task.input_context:
            prompt_parts.append(f"\n## Context from Previous Tasks\n{task.input_context}")

        # Add project target path
        prompt_parts.append(f"\n## Working Directory\nProject path: {self._project_path}")

        # CRITICAL: Tell the agent HOW to output files
        prompt_parts.append("""
## CRITICAL: File Output Format
You MUST output ALL code files using this EXACT format so they can be saved to disk:

--- FILE: relative/path/to/file.ext ---
complete file content here
--- END FILE ---

Example:
--- FILE: app/Models/Contact.php ---
<?php
namespace App\\Models;
use Illuminate\\Database\\Eloquent\\Model;
class Contact extends Model {
    protected $fillable = ['name', 'email', 'phone', 'category'];
}
--- END FILE ---

RULES:
1. Use --- FILE: ... --- and --- END FILE --- markers for EVERY file
2. Use relative paths from the project root
3. Include COMPLETE file contents, never use placeholders
4. Create ALL files needed for this task
5. Each file must have real, working code
""")

        # Inter-agent communication
        prompt_parts.append("""
## Inter-Agent Communication
If you need info from other agents, include:
```agent_message
{"to": "agent_type", "type": "question", "content": "your question"}
```
""")

        return "\n".join(prompt_parts)

    def _extract_messages(self, content: str) -> list[dict]:
        """Extract inter-agent messages from LLM response."""
        messages = []
        if "```agent_message" not in content:
            return messages

        parts = content.split("```agent_message")
        for part in parts[1:]:
            json_end = part.find("```")
            if json_end > 0:
                try:
                    msg = json.loads(part[:json_end].strip())
                    messages.append(msg)
                except json.JSONDecodeError:
                    pass

        return messages

    async def _set_status(self, status: str, current_task_id: str = None):
        """Update agent status in database."""
        self._status = status
        async with db_manager.get_session() as session:
            values = {"status": status, "last_active_at": utcnow()}
            if current_task_id:
                values["current_task_id"] = current_task_id
            stmt = update(AgentModel).where(AgentModel.id == self.id).values(**values)
            await session.execute(stmt)
            await session.commit()

        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "agent_status_changed",
                "data": {
                    "agent_id": self.id,
                    "status": status,
                    "current_task_id": current_task_id,
                    "display_name": self.display_name,
                }
            })

    async def _log_activity(self, event_type: str, description: str, metadata: dict = None):
        """Log an activity for this agent."""
        log = ActivityLog(
            id=generate_uuid(),
            project_id=self.project_id,
            agent_id=self.id,
            event_type=event_type,
            description=description,
            extra_data=metadata,
        )

        async with db_manager.get_session() as session:
            session.add(log)
            await session.commit()

        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "activity_log",
                "data": log.to_dict()
            })

    async def send_message(self, to_agent_type: str, message_type: str,
                           content: str, blocking: bool = False):
        """Send a message to another agent by type."""
        from sqlalchemy import select
        async with db_manager.get_session() as session:
            query = select(AgentModel).where(
                AgentModel.project_id == self.project_id,
                AgentModel.agent_type == to_agent_type,
            )
            result = await session.execute(query)
            target = result.scalar_one_or_none()

        if target:
            await self.message_bus.send(
                project_id=self.project_id,
                from_agent_id=self.id,
                to_agent_id=target.id,
                message_type=message_type,
                content=content,
                blocking=blocking,
            )
        else:
            logger.warning(f"No agent of type '{to_agent_type}' found in project.")

    async def check_and_respond_to_messages(self):
        """Check for pending messages and respond using LLM."""
        pending = await self.message_bus.get_pending_messages(self.id, self.project_id)

        for msg in pending:
            if msg.from_agent_id == self.id:
                continue

            self._conversation_history.append({
                "role": "user",
                "content": f"Another agent ({msg.from_agent_id[:8]}) sent you a {msg.message_type}:\n\n{msg.content}\n\nPlease respond."
            })

            response = await self.llm.chat(
                system_prompt=self.system_prompt,
                messages=self._conversation_history,
            )

            self._conversation_history.append({"role": "assistant", "content": response.content})

            await self.message_bus.respond_to(
                original_message=msg,
                from_agent_id=self.id,
                response_content=response.content,
            )

            await self._log_activity("message_received",
                                     f"Responded to {msg.message_type} from {msg.from_agent_id[:8]}")
