"""
Scheduler — Dependency-aware task execution engine.
Supports parallel and serial execution based on task dependencies.
"""

import asyncio
import logging
from typing import Callable, Awaitable
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Executes tasks respecting their dependency graph.

    - Tasks with no unmet dependencies run in parallel
    - Tasks with dependencies wait until predecessors complete
    - Continuously polls for newly ready tasks after each completion
    """

    def __init__(self, task_manager: TaskManager, execute_fn: Callable[[str], Awaitable[None]]):
        """
        Args:
            task_manager: TaskManager instance for querying task states
            execute_fn: Async function that executes a single task by ID.
                        Signature: async def execute(task_id: str) -> None
        """
        self.task_manager = task_manager
        self.execute_fn = execute_fn
        self._running_tasks: set[str] = set()
        self._completed_event = asyncio.Event()
        self._stop = False

    async def run(self, project_id: str):
        """
        Run the scheduler loop for a project.
        Continuously picks up ready tasks and executes them.
        Stops when all tasks are completed or failed, or _stop is set.
        """
        logger.info(f"Scheduler started for project {project_id[:8]}")
        self._stop = False

        while not self._stop:
            # Get tasks that are ready (dependencies met, status pending/queued)
            ready_tasks = await self.task_manager.get_ready_tasks(project_id)

            # Filter out tasks already running
            new_tasks = [t for t in ready_tasks if t.id not in self._running_tasks]

            if new_tasks:
                # Launch ready tasks in parallel
                for task in new_tasks:
                    self._running_tasks.add(task.id)
                    asyncio.create_task(self._execute_and_track(task.id, project_id))
                    logger.info(f"Scheduler launched task: {task.title}")

            # Check if we're done
            progress = await self.task_manager.get_progress(project_id)
            total_done = progress["completed"] + progress["failed"]

            if total_done >= progress["total"] and progress["total"] > 0:
                logger.info(f"Scheduler completed. {progress['completed']}/{progress['total']} tasks done.")
                break

            if not new_tasks and not self._running_tasks:
                # No tasks to run and nothing running — might be stuck
                blocked = await self.task_manager.get_blocked_tasks(project_id)
                if blocked:
                    logger.warning(f"Scheduler: {len(blocked)} tasks blocked — marking as skipped")
                    for task in blocked:
                        await self.task_manager.fail_task(
                            task.id,
                            "Skipped: dependency task failed"
                        )
                break

            # Wait a bit before checking again
            self._completed_event.clear()
            try:
                await asyncio.wait_for(self._completed_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

        logger.info("Scheduler loop ended.")

    async def _execute_and_track(self, task_id: str, project_id: str):
        """Execute a task and clean up when done."""
        try:
            await self.execute_fn(task_id)
        except Exception as e:
            logger.error(f"Task {task_id[:8]} execution error: {e}")
            await self.task_manager.fail_task(task_id, str(e))
        finally:
            self._running_tasks.discard(task_id)
            self._completed_event.set()  # Signal that a task completed

    def stop(self):
        """Stop the scheduler loop."""
        self._stop = True
        self._completed_event.set()

    @property
    def active_task_count(self) -> int:
        return len(self._running_tasks)
