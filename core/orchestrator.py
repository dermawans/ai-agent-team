"""
Orchestrator — The Lead Agent that coordinates the entire project lifecycle.
Receives projects, runs product & dev phases, spawns agents, and manages execution.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from database.models import (
    Project, Task, Agent as AgentModel,
    ActivityLog, generate_uuid, utcnow
)
from database.connection import db_manager
from core.llm_client import LLMClient
from core.agent import Agent
from core.agent_registry import AGENT_TYPES, get_agent_summary
from core.task_manager import TaskManager
from core.message_bus import MessageBus
from core.scheduler import Scheduler

logger = logging.getLogger(__name__)


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Lead Agent (Orchestrator) of an AI development team.
Your job is to coordinate a team of specialized AI agents to complete software projects.

You have these capabilities:
1. Analyze project requirements
2. Decide which specialist agents to spawn
3. Create the product specification
4. Break down specs into actionable tasks with dependencies
5. Coordinate task execution
6. Handle escalations from sub-agents
7. Compile and report final results

Available agent types:
{agent_summary}

IMPORTANT RULES:
- Always analyze the project before deciding which agents to spawn
- Consider dependencies between tasks (e.g., DB migration must come before controller)
- Tasks that don't depend on each other should be marked for parallel execution
- When reporting to the user, be clear and structured
"""


class Orchestrator:
    """Lead Agent — the brain that orchestrates the entire agent team."""

    def __init__(self, broadcast_callback=None):
        self.llm = LLMClient()
        self.task_manager = TaskManager(broadcast_callback=broadcast_callback)
        self.message_bus = MessageBus(broadcast_callback=broadcast_callback)
        self._broadcast_callback = broadcast_callback
        self._active_agents: dict[str, Agent] = {}  # agent_id -> Agent instance

    async def create_project(
        self,
        title: str,
        description: str,
        target_path: str = None,
    ) -> Project:
        """Create a new project and begin orchestration."""
        project = Project(
            id=generate_uuid(),
            title=title,
            description=description,
            target_path=target_path,
            status="pending",
            current_phase="init",
        )

        async with db_manager.get_session() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)

        logger.info(f"Project created: [{project.id[:8]}] {title}")

        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "project_created",
                "data": project.to_dict()
            })

        return project

    async def run_project(self, project_id: str):
        """
        Run the full project lifecycle:
        1. Product Phase — generate spec
        2. Planning Phase — break down into tasks
        3. Development Phase — execute tasks with agents
        4. Review Phase — compile results
        """
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        try:
            # Phase 1: Product — Generate specification
            await self._update_project(project_id, status="planning", current_phase="product")
            await self._log_activity(project_id, None, "phase_changed", "Starting Product Phase")

            spec = await self._run_product_phase(project)

            # Save spec to file for review
            await self._save_project_doc(project, "SPEC.md", spec)
            await self._log_activity(project_id, None, "writing_file", "Saved SPEC.md")

            # Phase 2: Planning — Break spec into tasks
            await self._update_project(project_id, current_phase="planning", spec_document=spec)
            await self._log_activity(project_id, None, "phase_changed", "Starting Planning Phase")

            task_plan = await self._plan_tasks(project, spec)
            tasks = await self.task_manager.create_tasks_from_plan(project_id, task_plan)

            # Save task plan to file for review
            task_plan_md = self._format_task_plan_md(task_plan)
            await self._save_project_doc(project, "TASK_PLAN.md", task_plan_md)
            await self._log_activity(project_id, None, "writing_file", "Saved TASK_PLAN.md")

            # Phase 3: Development — Execute tasks
            await self._update_project(project_id, status="in_progress", current_phase="development")
            await self._log_activity(project_id, None, "phase_changed",
                                     f"Starting Development Phase ({len(tasks)} tasks)")

            await self._run_development_phase(project, tasks)

            # Phase 4: Review — Compile results
            await self._update_project(project_id, current_phase="review")
            await self._log_activity(project_id, None, "phase_changed", "Starting Review Phase")

            summary = await self._compile_results(project)

            # Save summary to file
            await self._save_project_doc(project, "BUILD_SUMMARY.md", summary)
            await self._log_activity(project_id, None, "writing_file", "Saved BUILD_SUMMARY.md")

            await self._update_project(project_id, status="completed",
                                       result_summary=summary, completed_at=utcnow())
            await self._log_activity(project_id, None, "phase_changed", "Project completed!")

        except Exception as e:
            error_msg = f"Project failed: {str(e)}"
            logger.error(error_msg)
            await self._update_project(project_id, status="failed",
                                       result_summary=error_msg)
            await self._log_activity(project_id, None, "error", error_msg)
            raise

    async def resume_project(self, project_id: str):
        """
        Resume a failed or interrupted project.
        Picks up from where it left off:
        - If spec exists → skip product phase
        - If tasks exist → skip planning phase
        - Re-run only pending/failed tasks in development phase
        """
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        await self._log_activity(project_id, None, "phase_changed",
                                 f"Resuming project from phase: {project.current_phase}")
        await self._update_project(project_id, status="in_progress")

        try:
            existing_tasks = await self.task_manager.get_project_tasks(project_id)

            # Decide where to resume based on current state
            if not project.spec_document:
                # No spec yet — start from product phase
                await self._log_activity(project_id, None, "thinking",
                                         "No spec found, restarting from Product Phase")
                await self._update_project(project_id, current_phase="product")
                spec = await self._run_product_phase(project)
                await self._update_project(project_id, current_phase="planning",
                                           spec_document=spec)
                task_plan = await self._plan_tasks(project, spec)
                existing_tasks = await self.task_manager.create_tasks_from_plan(
                    project_id, task_plan)

            elif not existing_tasks:
                # Spec exists but no tasks — resume from planning
                await self._log_activity(project_id, None, "thinking",
                                         "Spec found but no tasks, resuming from Planning Phase")
                await self._update_project(project_id, current_phase="planning")
                # Reload project to get spec_document
                project = await self._get_project(project_id)
                task_plan = await self._plan_tasks(project, project.spec_document)
                existing_tasks = await self.task_manager.create_tasks_from_plan(
                    project_id, task_plan)

            else:
                # Tasks exist — just resume execution
                progress = await self.task_manager.get_progress(project_id)
                await self._log_activity(
                    project_id, None, "thinking",
                    f"Resuming: {progress['completed']}/{progress['total']} tasks done, "
                    f"{progress['failed']} failed, {progress['pending']} pending")

            # Reset failed tasks to pending so they can be retried
            for task in existing_tasks:
                if task.status == "failed":
                    await self.task_manager.update_status(task.id, "pending",
                                                          error_message=None)
                    await self._log_activity(project_id, None, "thinking",
                                             f"Reset failed task: {task.title}")
                elif task.status == "in_progress":
                    # Stuck in_progress tasks — reset to pending
                    await self.task_manager.update_status(task.id, "pending")
                    await self._log_activity(project_id, None, "thinking",
                                             f"Reset stuck task: {task.title}")

            # Development Phase — run remaining tasks
            await self._update_project(project_id, current_phase="development")
            remaining_tasks = await self.task_manager.get_project_tasks(project_id)
            pending_count = sum(1 for t in remaining_tasks
                              if t.status in ("pending", "queued"))

            if pending_count > 0:
                await self._log_activity(project_id, None, "phase_changed",
                                         f"Executing {pending_count} remaining tasks")
                await self._run_development_phase(project, remaining_tasks)
            else:
                await self._log_activity(project_id, None, "thinking",
                                         "All tasks already completed!")

            # Review Phase
            await self._update_project(project_id, current_phase="review")
            summary = await self._compile_results(project)
            await self._update_project(project_id, status="completed",
                                       result_summary=summary, completed_at=utcnow())
            await self._log_activity(project_id, None, "phase_changed",
                                     "Project completed!")

        except Exception as e:
            error_msg = f"Project resume failed: {str(e)}"
            logger.error(error_msg)
            await self._update_project(project_id, status="failed",
                                       result_summary=error_msg)
            await self._log_activity(project_id, None, "error", error_msg)
            raise

    async def _run_product_phase(self, project: Project) -> str:
        """Generate a project specification using Product Team agents."""
        await self._log_activity(project.id, None, "thinking", "Analyzing project requirements...")

        # Step 1: Decide which product agents to use
        analysis_prompt = f"""Analyze this project and create a detailed specification.

Project Title: {project.title}
Project Description: {project.description}
Target Path: {project.target_path or 'New project (no existing codebase)'}

Create a comprehensive specification that includes:
1. Project Overview
2. User Stories with Acceptance Criteria
3. Feature List (must-have vs nice-to-have)
4. Data Model (entities, fields, relationships)
5. UI/UX Requirements (pages, forms, navigation flows)
6. API Endpoints (if applicable)
7. Technical Recommendations (framework, database, etc.)
8. Non-Functional Requirements

If the target path points to an existing project, your spec should describe new features
to be added to it, not rebuild the entire project.

Output the spec in clean, structured markdown."""

        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(agent_summary=get_agent_summary())

        response = await self.llm.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.7,
        )

        spec = response.content
        await self._log_activity(project.id, None, "spec_created",
                                 f"Specification created ({len(spec)} chars)")

        return spec

    async def _plan_tasks(self, project: Project, spec: str) -> list[dict]:
        """Break the spec into actionable tasks with dependencies."""
        await self._log_activity(project.id, None, "thinking", "Breaking spec into tasks...")

        planning_prompt = f"""Based on this specification, create a detailed task breakdown.

## Specification
{spec}

## Target
Path: {project.target_path or 'New project'}

## Instructions
Create a JSON array of tasks. Each task should have:
- "title": Clear task title
- "description": Detailed description of what needs to be done
- "agent_type": Which agent should handle it. Options: {list(AGENT_TYPES.keys())}
- "phase": "development" or "testing"
- "priority": 1-10 (10 = highest)
- "depends_on_indices": Array of indices (0-based) of tasks that must complete first
- "execution_mode": "auto" (scheduler decides), "serial" (must wait), or "parallel" (can run independently)

IMPORTANT:
- Order tasks logically (setup first, then core features, then testing)
- DB tasks should come before backend tasks that need those tables
- Frontend tasks can often run in parallel with backend tasks
- Testing tasks should depend on the code they test
- If this is a new project, include a "devops" task first for project scaffolding

Respond with ONLY valid JSON array, no other text.
Example format:
[
  {{"title": "Setup project scaffolding", "description": "...", "agent_type": "devops", "phase": "development", "priority": 10, "depends_on_indices": [], "execution_mode": "serial"}},
  {{"title": "Create database migrations", "description": "...", "agent_type": "db_engineer", "phase": "development", "priority": 9, "depends_on_indices": [0], "execution_mode": "serial"}}
]"""

        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(agent_summary=get_agent_summary())

        response = await self.llm.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": planning_prompt}],
            temperature=0.3,  # Lower temp for structured output
        )

        # Parse JSON from response
        content = response.content.strip() if response.content else ""

        if not content:
            logger.warning("Empty response from LLM, retrying...")
            response = await self.llm.chat(
                system_prompt="You output ONLY valid JSON arrays. No markdown, no explanation, no thinking.",
                messages=[{"role": "user", "content": planning_prompt}],
                temperature=0.1,
            )
            content = response.content.strip() if response.content else ""

        # Handle case where LLM wraps JSON in code block
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    content = part
                    break

        # Try to find JSON array in the content
        if not content.startswith("["):
            import re
            match = re.search(r'\[[\s\S]*\]', content)
            if match:
                content = match.group(0)

        try:
            task_plan = json.loads(content)
        except json.JSONDecodeError:
            # Retry with stricter prompt
            logger.warning(f"Failed to parse task plan JSON (content: {content[:100]}...), retrying...")
            response = await self.llm.chat(
                system_prompt="You output ONLY valid JSON arrays. No markdown, no explanation, no code blocks, no thinking. Start with [ and end with ].",
                messages=[{"role": "user", "content": planning_prompt}],
                temperature=0.1,
            )
            retry_content = response.content.strip() if response.content else ""
            if "```" in retry_content:
                parts = retry_content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("["):
                        retry_content = part
                        break
            task_plan = json.loads(retry_content)

        await self._log_activity(project.id, None, "thinking",
                                 f"Created {len(task_plan)} tasks")

        return task_plan

    async def _run_development_phase(self, project: Project, tasks: list[Task]):
        """Execute development tasks using specialized agents."""
        # Determine which agent types we need
        needed_types = set()
        for task in tasks:
            if task.agent_type:
                needed_types.add(task.agent_type)

        # Spawn agents
        for agent_type in needed_types:
            await self._spawn_agent(project.id, agent_type)

        # Create scheduler and run
        scheduler = Scheduler(
            task_manager=self.task_manager,
            execute_fn=lambda task_id: self._execute_task(project.id, task_id)
        )

        await scheduler.run(project.id)

    async def _execute_task(self, project_id: str, task_id: str):
        """Execute a single task with the appropriate agent."""
        task = await self.task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Find the agent for this task type
        agent = self._find_agent(project_id, task.agent_type)
        if not agent:
            # Spawn a new agent if needed
            agent = await self._spawn_agent(project_id, task.agent_type)

        # Update task status
        await self.task_manager.update_status(task_id, "in_progress",
                                              assigned_agent_id=agent.id)

        # Execute
        result = await agent.execute_task(task)

        # Collect file changes from result
        files_created = self._extract_files(result, "created")
        files_modified = self._extract_files(result, "modified")

        # Mark complete
        await self.task_manager.complete_task(
            task_id,
            output_result=result,
            files_created=files_created,
            files_modified=files_modified,
        )

    async def _spawn_agent(self, project_id: str, agent_type: str) -> Agent:
        """Spawn a new specialized agent."""
        agent_def = AGENT_TYPES.get(agent_type)
        if not agent_def:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Create agent record in database
        agent_db = AgentModel(
            id=generate_uuid(),
            project_id=project_id,
            agent_type=agent_type,
            display_name=agent_def["display_name"],
            system_prompt=agent_def["system_prompt"],
            status="idle",
        )

        async with db_manager.get_session() as session:
            session.add(agent_db)
            await session.commit()
            await session.refresh(agent_db)

        # Create the agent instance with tools
        from tools.file_tools import FileTools
        from tools.git_tools import GitTools
        from tools.shell_tools import ShellTools
        from tools.code_analyzer import CodeAnalyzer

        # Get project path
        project = await self._get_project(project_id)
        target_path = project.target_path or "."

        # Build tool set based on allowed tools
        available_tools = {
            "file_read": FileTools(target_path).read_file,
            "file_write": FileTools(target_path).write_file,
            "file_modify": FileTools(target_path).modify_file,
            "list_directory": FileTools(target_path).list_directory,
            "shell_run": ShellTools(target_path).run,
            "git_commit": GitTools(target_path).commit,
            "git_push": GitTools(target_path).push,
            "code_analyze": CodeAnalyzer(target_path).analyze_structure,
        }

        agent_tools = {}
        for tool_name in agent_def.get("allowed_tools", []):
            # Map registry tool names to actual tool functions
            tool_mapping = {
                "file_read": ["file_read", "list_directory"],
                "file_write": ["file_write", "file_modify"],
                "shell_run": ["shell_run"],
                "git_commit": ["git_commit"],
                "git_push": ["git_push"],
                "code_analyzer": ["code_analyze", "list_directory"],
            }
            for actual_tool in tool_mapping.get(tool_name, []):
                if actual_tool in available_tools:
                    agent_tools[actual_tool] = available_tools[actual_tool]

        agent = Agent(
            agent_db=agent_db,
            llm_client=LLMClient(),  # Each agent gets its own LLM client
            message_bus=self.message_bus,
            task_manager=self.task_manager,
            tools=agent_tools,
            broadcast_callback=self._broadcast_callback,
        )

        # Set the project path so agent knows where to write files
        agent._project_path = target_path

        self._active_agents[agent_db.id] = agent

        await self._log_activity(project_id, agent_db.id, "agent_spawned",
                                 f"Spawned {agent_def['icon']} {agent_def['display_name']}")

        logger.info(f"Agent spawned: {agent_def['display_name']} ({agent_type})")

        return agent

    def _find_agent(self, project_id: str, agent_type: str) -> Optional[Agent]:
        """Find an existing agent instance by type."""
        for agent in self._active_agents.values():
            if agent.project_id == project_id and agent.agent_type == agent_type:
                return agent
        return None

    async def _compile_results(self, project: Project) -> str:
        """Compile all task results into a final report."""
        tasks = await self.task_manager.get_project_tasks(project.id)
        progress = await self.task_manager.get_progress(project.id)

        report_parts = [
            f"# Project Report: {project.title}",
            f"\n## Summary",
            f"- Total Tasks: {progress['total']}",
            f"- Completed: {progress['completed']}",
            f"- Failed: {progress['failed']}",
            f"- Completion: {progress['percentage']}%",
            f"\n## Tasks",
        ]

        for task in tasks:
            status_icon = "✅" if task.status == "completed" else "❌"
            report_parts.append(f"\n### {status_icon} {task.title}")
            report_parts.append(f"- Agent: {task.agent_type}")
            report_parts.append(f"- Status: {task.status}")
            if task.files_created:
                report_parts.append(f"- Files Created: {', '.join(task.files_created)}")
            if task.files_modified:
                report_parts.append(f"- Files Modified: {', '.join(task.files_modified)}")
            if task.error_message:
                report_parts.append(f"- Error: {task.error_message}")

        return "\n".join(report_parts)

    def _extract_files(self, result: str, action: str) -> list[str]:
        """Extract file paths mentioned in agent output."""
        # Simple extraction — looks for file paths in the output
        files = []
        for line in result.split("\n"):
            line = line.strip()
            if action == "created" and ("created" in line.lower() or "[new]" in line.lower()):
                # Try to extract path
                for word in line.split():
                    if "/" in word or "\\" in word:
                        cleaned = word.strip("'\"`,;:")
                        if cleaned:
                            files.append(cleaned)
            elif action == "modified" and ("modified" in line.lower() or "[mod]" in line.lower()):
                for word in line.split():
                    if "/" in word or "\\" in word:
                        cleaned = word.strip("'\"`,;:")
                        if cleaned:
                            files.append(cleaned)
        return files

    async def _get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        async with db_manager.get_session() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            return result.scalar_one_or_none()

    async def _update_project(self, project_id: str, **kwargs):
        """Update project fields."""
        async with db_manager.get_session() as session:
            kwargs["updated_at"] = utcnow()
            stmt = update(Project).where(Project.id == project_id).values(**kwargs)
            await session.execute(stmt)
            await session.commit()

        if self._broadcast_callback:
            project = await self._get_project(project_id)
            if project:
                await self._broadcast_callback({
                    "type": "project_updated",
                    "data": project.to_dict()
                })

    async def _log_activity(self, project_id: str, agent_id: str, event_type: str,
                            description: str, metadata: dict = None):
        """Log an orchestrator activity."""
        log = ActivityLog(
            id=generate_uuid(),
            project_id=project_id,
            agent_id=agent_id,
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

    async def get_all_projects(self) -> list[Project]:
        """Get all projects."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Project).order_by(Project.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_project_agents(self, project_id: str) -> list[AgentModel]:
        """Get all agents for a project."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentModel)
                .where(AgentModel.project_id == project_id)
                .order_by(AgentModel.created_at)
            )
            return list(result.scalars().all())

    async def _save_project_doc(self, project: Project, filename: str, content: str):
        """Save a document file to the project's target directory."""
        import os
        target_path = project.target_path or "."
        os.makedirs(target_path, exist_ok=True)
        filepath = os.path.join(target_path, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved project doc: {filepath}")

    def _format_task_plan_md(self, task_plan: list[dict]) -> str:
        """Format the task plan as a readable markdown document."""
        lines = [
            "# Task Plan\n",
            "Auto-generated task breakdown for this project.\n",
            "| # | Task | Agent | Phase | Priority | Dependencies |",
            "|---|------|-------|-------|----------|--------------|",
        ]
        for i, task in enumerate(task_plan):
            deps = task.get("depends_on_indices", [])
            deps_str = ", ".join([f"#{d}" for d in deps]) if deps else "None"
            lines.append(
                f"| {i} | {task.get('title', 'N/A')} | "
                f"{task.get('agent_type', 'N/A')} | "
                f"{task.get('phase', 'N/A')} | "
                f"{task.get('priority', 'N/A')} | "
                f"{deps_str} |"
            )

        lines.append("\n## Task Details\n")
        for i, task in enumerate(task_plan):
            lines.append(f"### Task #{i}: {task.get('title', 'N/A')}")
            lines.append(f"- **Agent:** {task.get('agent_type', 'N/A')}")
            lines.append(f"- **Phase:** {task.get('phase', 'N/A')}")
            lines.append(f"- **Priority:** {task.get('priority', 'N/A')}")
            lines.append(f"- **Mode:** {task.get('execution_mode', 'auto')}")
            deps = task.get("depends_on_indices", [])
            if deps:
                lines.append(f"- **Depends on:** {', '.join([f'Task #{d}' for d in deps])}")
            lines.append(f"\n{task.get('description', 'No description')}\n")

        return "\n".join(lines)
