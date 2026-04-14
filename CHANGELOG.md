# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.1] - 2026-04-15

### Added
- **Anthropic (Claude) Support** — Integrated the Anthropic Messages API. Users can now use Claude 3.5 Sonnet or other Claude models as their primary AI provider.
- **Enhanced Token Tracking** — Standardized token usage reporting for Anthropic responses.

---

## [1.1.0] - 2026-04-13

### Added
- **Project Documentation Output** — Every project now auto-generates 3 documentation files in the target folder:
  - `SPEC.md` — Full product specification (after Product Phase)
  - `TASK_PLAN.md` — Task breakdown with dependencies table (after Planning Phase)
  - `BUILD_SUMMARY.md` — Final build report (after Review Phase)
- **Resume & Retry** — Failed projects can be resumed from the dashboard with a single click. The system picks up from the last successful checkpoint.
- **`.gitignore`** — Added to exclude `.env`, `__pycache__/`, and `data/*.db` from version control.

### Changed
- **LLM Model** — Switched default from `gemini-2.0-flash` (discontinued) to `gemini-2.5-flash`.
- **Agent File Output** — Agents now write real files to disk using `--- FILE: path ---` markers. Previously agents only "thought" about code without creating actual files.
- **Agent System Prompts** — All agent prompts rewritten to produce complete, production-ready code (no placeholders, no snippets).
- **JSON Parsing** — Task plan parser now uses multi-strategy extraction (regex, code block parsing, retry) to handle various LLM output formats.
- **Token Tracking** — Fixed `NoneType` crash when `usage_metadata` attributes are `None`.

### Fixed
- **`database is locked`** — Resolved SQLite concurrent write errors by enabling WAL mode, `busy_timeout=30s`, write serialization via `asyncio.Lock()`, and single connection pool.
- **`NoneType is not iterable`** — Added `None` guard for `response.candidates[0].content.parts`.
- **`unsupported operand type(s) for +: 'int' and 'NoneType'`** — Token count attributes can be `None`; added `or 0` fallback.
- **Gemini 2.5 Thinking Parts** — Disabled `thinking_budget` and added `response.text` fallback to handle Gemini 2.5's thinking response format.
- **Blocked Tasks Hang** — Scheduler now auto-skips blocked tasks (marks as `failed: dependency task failed`) instead of hanging forever.
- **Empty LLM Response** — Auto-retry when LLM returns empty content.
- **Windows Encoding** — Replaced Unicode box-drawing characters in banner with ASCII-safe alternatives for `cp1252` compatibility.
- **SQLAlchemy Reserved Keyword** — Renamed `metadata` column to `extra_data` in `ActivityLog` model.

---

## [1.0.0] - 2026-04-12

### Added
- **Core Engine**
  - `Orchestrator` — Lead Agent that manages the full project lifecycle (Product → Planning → Development → Review).
  - `Agent` — Base agent class with LLM interaction, tool usage, and inter-agent messaging.
  - `AgentRegistry` — 7 specialized agent types: Product Manager, Tech Lead, DB Engineer, Backend Dev, Frontend Dev, QA Tester, DevOps.
  - `TaskManager` — CRUD operations for tasks with status tracking and dependency management.
  - `Scheduler` — Dependency-aware task execution engine with parallel and serial execution support.
  - `MessageBus` — Inter-agent communication system (questions, blockers, info, decisions).
  - `LLMClient` — Multi-provider LLM wrapper supporting Gemini, OpenAI, and Ollama.

- **Web Dashboard**
  - Real-time WebSocket-based monitoring UI.
  - Project sidebar with status indicators.
  - Agent Tree panel showing team hierarchy and live status.
  - Task Flow panel with dependency visualization.
  - Live Activity Log with auto-scroll.
  - Agent Communication panel for inter-agent messages.
  - Agent Detail drawer with full activity timeline.
  - Project creation form with title, description, and target path.

- **Agent Tools**
  - `FileTools` — Sandboxed file read/write/modify/list operations.
  - `GitTools` — Git commit and push operations.
  - `ShellTools` — Allowlisted shell command execution.
  - `CodeAnalyzer` — Codebase structure analysis.

- **Database**
  - SQLite with async SQLAlchemy ORM.
  - Models: Project, Task, Agent, ActivityLog, AgentMessage.

- **Configuration**
  - `.env`-based configuration with sensible defaults.
  - Multi-provider LLM support (Gemini/OpenAI/Ollama).
  - Configurable autonomy levels (safe/semi_auto/full_auto).
