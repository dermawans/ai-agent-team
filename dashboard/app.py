"""
Dashboard — FastAPI web application with WebSocket for real-time monitoring.
"""

import asyncio
import json
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from config import config

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).parent
app = FastAPI(title="AI Agent Team Dashboard")

# Mount static files and templates
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")
templates = Jinja2Templates(directory=DASHBOARD_DIR / "templates")


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Broadcast event to all connected clients."""
        message = json.dumps(data, default=str)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


ws_manager = ConnectionManager()


async def broadcast_event(event: dict):
    """Global broadcast function — passed to orchestrator as callback."""
    await ws_manager.broadcast(event)


# === Routes ===

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; receive any client messages
            data = await websocket.receive_text()
            # Client can send commands via WebSocket if needed
            try:
                msg = json.loads(data)
                await handle_ws_message(msg)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def handle_ws_message(msg: dict):
    """Handle messages from the dashboard client."""
    msg_type = msg.get("type")

    if msg_type == "get_projects":
        from core.orchestrator import Orchestrator
        orchestrator = Orchestrator(broadcast_callback=broadcast_event)
        projects = await orchestrator.get_all_projects()
        await ws_manager.broadcast({
            "type": "projects_list",
            "data": [p.to_dict() for p in projects]
        })

    elif msg_type == "get_project_detail":
        project_id = msg.get("project_id")
        if project_id:
            await send_project_detail(project_id)

    elif msg_type == "create_project":
        from core.orchestrator import Orchestrator
        orchestrator = Orchestrator(broadcast_callback=broadcast_event)
        project = await orchestrator.create_project(
            title=msg.get("title", "Untitled Project"),
            description=msg.get("description", ""),
            target_path=msg.get("target_path"),
        )
        # Start project execution in background
        asyncio.create_task(orchestrator.run_project(project.id))

    elif msg_type == "resume_project":
        project_id = msg.get("project_id")
        if project_id:
            from core.orchestrator import Orchestrator
            orchestrator = Orchestrator(broadcast_callback=broadcast_event)
            asyncio.create_task(orchestrator.resume_project(project_id))


async def send_project_detail(project_id: str):
    """Send full project detail to all connected clients."""
    from core.orchestrator import Orchestrator
    from core.task_manager import TaskManager
    from core.message_bus import MessageBus

    orchestrator = Orchestrator()
    task_manager = TaskManager()
    message_bus = MessageBus()

    project = await orchestrator._get_project(project_id)
    if not project:
        return

    tasks = await task_manager.get_project_tasks(project_id)
    agents = await orchestrator.get_project_agents(project_id)
    messages = await message_bus.get_conversation(project_id, limit=100)
    progress = await task_manager.get_progress(project_id)

    # Get activity logs
    from sqlalchemy import select
    from database.models import ActivityLog
    from database.connection import db_manager
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(ActivityLog)
            .where(ActivityLog.project_id == project_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(100)
        )
        logs = list(result.scalars().all())

    await ws_manager.broadcast({
        "type": "project_detail",
        "data": {
            "project": project.to_dict(),
            "tasks": [t.to_dict() for t in tasks],
            "agents": [a.to_dict() for a in agents],
            "messages": [m.to_dict() for m in messages],
            "logs": [l.to_dict() for l in logs],
            "progress": progress,
        }
    })


def start_dashboard():
    """Start the dashboard server."""
    import uvicorn
    uvicorn.run(
        app,
        host=config.DASHBOARD.HOST,
        port=config.DASHBOARD.PORT,
        log_level="info",
    )
