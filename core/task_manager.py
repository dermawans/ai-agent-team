"""
Task Manager — CRUD operations for tasks, dependency tracking, and status management.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from database.models import Task, generate_uuid, utcnow
from database.connection import db_manager

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages the lifecycle of tasks within a project."""

    def __init__(self, broadcast_callback=None):
        self._broadcast_callback = broadcast_callback

    async def create_task(
        self,
        project_id: str,
        title: str,
        description: str,
        agent_type: str = None,
        phase: str = "development",
        priority: int = 0,
        depends_on: list[str] = None,
        execution_mode: str = "auto",
        input_context: str = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            id=generate_uuid(),
            project_id=project_id,
            title=title,
            description=description,
            agent_type=agent_type,
            phase=phase,
            priority=priority,
            depends_on=depends_on or [],
            execution_mode=execution_mode,
            input_context=input_context,
            status="pending",
        )

        async with db_manager.get_session() as session:
            session.add(task)
            await session.commit()
            await session.refresh(task)

        logger.info(f"Task created: [{task.id[:8]}] {title}")

        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "task_created",
                "data": task.to_dict()
            })

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        async with db_manager.get_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            return result.scalar_one_or_none()

    async def get_project_tasks(self, project_id: str, phase: str = None) -> list[Task]:
        """Get all tasks for a project, optionally filtered by phase."""
        async with db_manager.get_session() as session:
            query = select(Task).where(Task.project_id == project_id)
            if phase:
                query = query.where(Task.phase == phase)
            query = query.order_by(Task.priority.desc(), Task.created_at)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_status(self, task_id: str, status: str, **kwargs):
        """Update task status and optional fields."""
        values = {"status": status}

        if status == "in_progress":
            values["started_at"] = utcnow()
        elif status in ("completed", "failed"):
            values["completed_at"] = utcnow()

        values.update(kwargs)

        async with db_manager.get_session() as session:
            stmt = update(Task).where(Task.id == task_id).values(**values)
            await session.execute(stmt)
            await session.commit()

        logger.info(f"Task [{task_id[:8]}] status → {status}")

        if self._broadcast_callback:
            task = await self.get_task(task_id)
            if task:
                await self._broadcast_callback({
                    "type": "task_updated",
                    "data": task.to_dict()
                })

    async def assign_agent(self, task_id: str, agent_id: str):
        """Assign an agent to a task."""
        await self.update_status(task_id, "queued", assigned_agent_id=agent_id)
        logger.info(f"Task [{task_id[:8]}] assigned to agent [{agent_id[:8]}]")

    async def complete_task(self, task_id: str, output_result: str = None,
                           files_created: list[str] = None, files_modified: list[str] = None):
        """Mark a task as completed with results."""
        await self.update_status(
            task_id, "completed",
            output_result=output_result,
            files_created=files_created,
            files_modified=files_modified,
        )

    async def fail_task(self, task_id: str, error_message: str):
        """Mark a task as failed."""
        await self.update_status(task_id, "failed", error_message=error_message)

    async def get_ready_tasks(self, project_id: str) -> list[Task]:
        """
        Get tasks that are ready to execute:
        - Status is 'pending' or 'queued'
        - All dependencies are completed
        """
        all_tasks = await self.get_project_tasks(project_id)

        # Build a set of completed task IDs
        completed_ids = {t.id for t in all_tasks if t.status == "completed"}

        ready = []
        for task in all_tasks:
            if task.status not in ("pending", "queued"):
                continue

            # Check if all dependencies are satisfied
            deps = task.depends_on or []
            if all(dep_id in completed_ids for dep_id in deps):
                ready.append(task)

        return sorted(ready, key=lambda t: t.priority, reverse=True)

    async def get_blocked_tasks(self, project_id: str) -> list[Task]:
        """Get tasks that are blocked (have unmet dependencies)."""
        all_tasks = await self.get_project_tasks(project_id)
        completed_ids = {t.id for t in all_tasks if t.status == "completed"}

        blocked = []
        for task in all_tasks:
            if task.status != "pending":
                continue
            deps = task.depends_on or []
            if deps and not all(dep_id in completed_ids for dep_id in deps):
                blocked.append(task)

        return blocked

    async def get_progress(self, project_id: str) -> dict:
        """Get progress summary for a project."""
        tasks = await self.get_project_tasks(project_id)
        total = len(tasks)
        if total == 0:
            return {"total": 0, "completed": 0, "in_progress": 0,
                    "pending": 0, "failed": 0, "percentage": 0}

        by_status = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1

        completed = by_status.get("completed", 0)
        return {
            "total": total,
            "completed": completed,
            "in_progress": by_status.get("in_progress", 0),
            "pending": by_status.get("pending", 0) + by_status.get("queued", 0),
            "failed": by_status.get("failed", 0),
            "blocked": by_status.get("blocked", 0),
            "percentage": round((completed / total) * 100) if total > 0 else 0,
        }

    async def create_tasks_from_plan(self, project_id: str, task_plan: list[dict]) -> list[Task]:
        """
        Create multiple tasks from a structured plan (output of Tech Lead).

        Expected format per item:
        {
            "title": "Create users migration",
            "description": "...",
            "agent_type": "db_engineer",
            "phase": "development",
            "priority": 10,
            "depends_on_indices": [0, 1],  # indices in this list
            "execution_mode": "auto"
        }
        """
        created_tasks = []

        for item in task_plan:
            # Resolve dependency indices to actual task IDs
            depends_on = []
            for dep_idx in item.get("depends_on_indices", []):
                if 0 <= dep_idx < len(created_tasks):
                    depends_on.append(created_tasks[dep_idx].id)

            task = await self.create_task(
                project_id=project_id,
                title=item["title"],
                description=item.get("description", item["title"]),
                agent_type=item.get("agent_type"),
                phase=item.get("phase", "development"),
                priority=item.get("priority", 0),
                depends_on=depends_on,
                execution_mode=item.get("execution_mode", "auto"),
                input_context=item.get("input_context"),
            )
            created_tasks.append(task)

        return created_tasks
