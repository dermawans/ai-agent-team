"""
Message Bus — Inter-agent communication system.
Supports direct messages, broadcasts, blocking requests, and escalation.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from database.models import Message, Agent, generate_uuid, utcnow
from database.connection import db_manager

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Central message bus for inter-agent communication.

    Message types:
    - question: Ask another agent a question
    - answer: Respond to a question
    - blocker: Report a blocking issue that must be resolved
    - info: Share information (non-blocking)
    - decision: Communicate a final decision
    - new_task: Request a new task to be created
    """

    def __init__(self, broadcast_callback=None):
        """
        Args:
            broadcast_callback: async function(event_data) called on every message
                               for real-time dashboard updates via WebSocket.
        """
        self._broadcast_callback = broadcast_callback

    async def send(
        self,
        project_id: str,
        from_agent_id: str,
        to_agent_id: Optional[str],
        message_type: str,
        content: str,
        blocking: bool = False,
        related_task_id: str = None,
    ) -> Message:
        """
        Send a message from one agent to another (or broadcast if to_agent_id is None).

        Args:
            project_id: Project context
            from_agent_id: Sender agent ID
            to_agent_id: Recipient agent ID (None for broadcast)
            message_type: question|answer|blocker|info|decision|new_task
            content: Message content
            blocking: If True, sender should pause until response is received
            related_task_id: Optional related task ID for context

        Returns:
            The created Message object
        """
        msg = Message(
            id=generate_uuid(),
            project_id=project_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type=message_type,
            content=content,
            is_blocking=blocking,
            is_resolved=False,
            related_task_id=related_task_id,
        )

        async with db_manager.get_session() as session:
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

        target = to_agent_id or "ALL"
        logger.info(f"Message [{message_type}] from {from_agent_id} → {target}: {content[:100]}...")

        # Notify dashboard via WebSocket
        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "message_sent",
                "data": msg.to_dict()
            })

        return msg

    async def get_pending_messages(self, agent_id: str, project_id: str = None) -> list[Message]:
        """Get all unresolved messages targeted at a specific agent."""
        async with db_manager.get_session() as session:
            query = select(Message).where(
                ((Message.to_agent_id == agent_id) | (Message.to_agent_id.is_(None))),
                Message.is_resolved == False,
            )
            if project_id:
                query = query.where(Message.project_id == project_id)
            query = query.order_by(Message.created_at)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_blocking_messages(self, agent_id: str, project_id: str) -> list[Message]:
        """Get blocking messages sent BY this agent that haven't been resolved."""
        async with db_manager.get_session() as session:
            query = select(Message).where(
                Message.from_agent_id == agent_id,
                Message.project_id == project_id,
                Message.is_blocking == True,
                Message.is_resolved == False,
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def resolve_message(self, message_id: str, resolution: str = None):
        """Mark a message as resolved."""
        async with db_manager.get_session() as session:
            stmt = (
                update(Message)
                .where(Message.id == message_id)
                .values(is_resolved=True, resolution=resolution, resolved_at=utcnow())
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(f"Message {message_id} resolved.")

        if self._broadcast_callback:
            await self._broadcast_callback({
                "type": "message_resolved",
                "data": {"message_id": message_id, "resolution": resolution}
            })

    async def respond_to(
        self,
        original_message: Message,
        from_agent_id: str,
        response_content: str,
        message_type: str = "answer"
    ) -> Message:
        """
        Respond to a message and resolve the original.

        Args:
            original_message: The message being responded to
            from_agent_id: The agent sending the response
            response_content: Response content
            message_type: Usually 'answer' or 'decision'

        Returns:
            The response Message
        """
        # Send the response
        response = await self.send(
            project_id=original_message.project_id,
            from_agent_id=from_agent_id,
            to_agent_id=original_message.from_agent_id,
            message_type=message_type,
            content=response_content,
            related_task_id=original_message.related_task_id,
        )

        # Resolve the original message
        await self.resolve_message(original_message.id, resolution=response_content)

        return response

    async def get_conversation(self, project_id: str, limit: int = 50) -> list[Message]:
        """Get the full message history for a project."""
        async with db_manager.get_session() as session:
            query = (
                select(Message)
                .where(Message.project_id == project_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def has_unresolved_blockers(self, agent_id: str, project_id: str) -> bool:
        """Check if an agent has any unresolved blocking messages."""
        blockers = await self.get_blocking_messages(agent_id, project_id)
        return len(blockers) > 0
