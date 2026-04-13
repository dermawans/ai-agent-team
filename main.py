"""
AI Agent Team System — Main Entry Point
Run with: python main.py

Commands:
  python main.py                      — Start dashboard (default)
  python main.py --project "Title"    — Create and run a project via CLI
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
)


BANNER = """
[bold magenta]
    +==========================================+
    |        AI Agent Team System              |
    |     Custom Multi-Agent Orchestrator      |
    +==========================================+
[/bold magenta]
"""


async def start_dashboard():
    """Start the web dashboard."""
    from database.connection import db_manager
    from dashboard.app import app, broadcast_event
    from config import config
    import uvicorn

    # Initialize database
    await db_manager.initialize()

    console.print(BANNER)
    console.print(f"[green]Dashboard running at:[/green] [bold]http://{config.DASHBOARD.HOST}:{config.DASHBOARD.PORT}[/bold]")
    console.print(f"[dim]Press Ctrl+C to stop[/dim]\n")

    # Run uvicorn
    config_uv = uvicorn.Config(
        app,
        host=config.DASHBOARD.HOST,
        port=config.DASHBOARD.PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config_uv)
    await server.serve()


async def run_cli_project(title: str, description: str, target_path: str = None):
    """Create and run a project via CLI (no dashboard)."""
    from database.connection import db_manager
    from core.orchestrator import Orchestrator
    from rich.live import Live
    from rich.table import Table

    # Initialize database
    await db_manager.initialize()

    console.print(BANNER)

    # Create orchestrator
    orchestrator = Orchestrator(broadcast_callback=cli_broadcast)

    # Create project
    console.print(Panel(f"[bold]{title}[/bold]\n\n{description}", title="📦 New Project"))

    project = await orchestrator.create_project(
        title=title,
        description=description,
        target_path=target_path,
    )

    console.print(f"\n[green]Project created:[/green] {project.id[:8]}")
    console.print("[yellow]Starting agent team...[/yellow]\n")

    # Run project
    try:
        await orchestrator.run_project(project.id)

        # Print results
        console.print("\n")
        console.print(Panel(
            project.result_summary or "Project completed!",
            title="✅ Project Report",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"\n[red]Project failed: {e}[/red]")
        raise


async def cli_broadcast(event: dict):
    """Print events to CLI instead of WebSocket."""
    event_type = event.get("type", "")
    data = event.get("data", {})

    icons = {
        'activity_log': '📌',
        'agent_status_changed': '🤖',
        'task_created': '📋',
        'task_updated': '📋',
        'project_updated': '📦',
        'message_sent': '💬',
    }

    icon = icons.get(event_type, '•')

    if event_type == "activity_log":
        desc = data.get("description", "")
        event_icon = {
            'agent_spawned': '🤖',
            'task_started': '▶️',
            'task_completed': '✅',
            'thinking': '💭',
            'phase_changed': '📊',
            'spec_created': '📋',
            'writing_file': '✏️',
            'reading_file': '🔍',
            'running_command': '⚡',
            'git_commit': '🔀',
            'error': '🔴',
        }.get(data.get("event_type", ""), '📌')
        console.print(f"  {event_icon} {desc}")

    elif event_type == "message_sent":
        content = data.get("content", "")[:100]
        msg_type = data.get("message_type", "info")
        console.print(f"  💬 [{msg_type}] {content}")


def main():
    parser = argparse.ArgumentParser(description="AI Agent Team System")
    parser.add_argument("--project", "-p", help="Project title (CLI mode)")
    parser.add_argument("--description", "-d", help="Project description")
    parser.add_argument("--target", "-t", help="Target codebase path")

    args = parser.parse_args()

    if args.project:
        if not args.description:
            console.print("[red]Error: --description is required with --project[/red]")
            sys.exit(1)
        asyncio.run(run_cli_project(args.project, args.description, args.target))
    else:
        asyncio.run(start_dashboard())


if __name__ == "__main__":
    main()
