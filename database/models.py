"""
Database ORM Models — Projects, Tasks, Agents, Messages, Activity Logs.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, JSON, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending|planning|in_progress|review|completed|failed
    current_phase = Column(String, default="init")  # init|product|development|testing|review
    target_path = Column(String, nullable=True)  # Path to target codebase
    tech_stack = Column(String, nullable=True)  # Detected or chosen tech stack
    spec_document = Column(Text, nullable=True)  # Generated spec (markdown)
    result_summary = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)  # Project-specific config overrides
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="project", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="project", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "current_phase": self.current_phase,
            "target_path": self.target_path,
            "tech_stack": self.tech_stack,
            "spec_document": self.spec_document,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending|queued|in_progress|blocked|completed|failed
    assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    agent_type = Column(String, nullable=True)  # Which agent type should handle this
    phase = Column(String, default="development")  # product|development|testing
    priority = Column(Integer, default=0)
    depends_on = Column(JSON, nullable=True)  # List of task IDs that must complete first
    execution_mode = Column(String, default="auto")  # auto|serial|parallel
    input_context = Column(Text, nullable=True)  # Context/data from previous tasks
    output_result = Column(Text, nullable=True)  # Result from agent
    files_created = Column(JSON, nullable=True)  # List of created file paths
    files_modified = Column(JSON, nullable=True)  # List of modified file paths
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assigned_agent = relationship("Agent", back_populates="current_tasks", foreign_keys=[assigned_agent_id])

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "assigned_agent_id": self.assigned_agent_id,
            "agent_type": self.agent_type,
            "phase": self.phase,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "execution_mode": self.execution_mode,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    agent_type = Column(String, nullable=False)  # product_manager|backend_dev|db_engineer|etc
    display_name = Column(String, nullable=False)
    status = Column(String, default="idle")  # idle|active|waiting|completed|error
    current_task_id = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    total_tokens_used = Column(Integer, default=0)
    total_api_calls = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    last_active_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="agents")
    current_tasks = relationship("Task", back_populates="assigned_agent", foreign_keys=[Task.assigned_agent_id])
    activities = relationship("ActivityLog", back_populates="agent", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "total_tokens_used": self.total_tokens_used,
            "total_api_calls": self.total_api_calls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    from_agent_id = Column(String, nullable=False)
    to_agent_id = Column(String, nullable=True)  # NULL = broadcast
    message_type = Column(String, nullable=False)  # question|answer|blocker|info|decision|new_task
    content = Column(Text, nullable=False)
    is_blocking = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolution = Column(Text, nullable=True)
    related_task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "message_type": self.message_type,
            "content": self.content,
            "is_blocking": self.is_blocking,
            "is_resolved": self.is_resolved,
            "resolution": self.resolution,
            "related_task_id": self.related_task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    event_type = Column(String, nullable=False)
    # Event types: agent_spawned|task_started|task_completed|task_failed|
    #              message_sent|message_received|file_created|file_modified|
    #              git_commit|error|decision|phase_changed|spec_created|
    #              reading_file|writing_file|running_command|thinking
    description = Column(Text, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Extra data (file paths, command output, etc.)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    project = relationship("Project", back_populates="activity_logs")
    agent = relationship("Agent", back_populates="activities")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "description": self.description,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
