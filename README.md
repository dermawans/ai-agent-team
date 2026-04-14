# 🤖 AI Agent Team System

> **v1.1.0** — [View Changelog](CHANGELOG.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![LLM](https://img.shields.io/badge/LLM-Gemini%20|%20Anthropic%20|%20OpenAI%20|%20Ollama-orange)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A custom-built **Multi-Agent AI orchestrator** that works like a virtual software development team. Give it a project description, and it will assemble a team of specialized AI agents to plan, build, and test your code — all observable through a real-time web dashboard.

**Zero framework costs. Zero vendor lock-in. 100% yours.**

---

## Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Quick Start](#-quick-start)
- [Dashboard Guide](#-dashboard-guide)
- [CLI Mode](#-cli-mode)
- [How It Works](#-how-it-works)
- [Agent Types](#-agent-types)
- [Inter-Agent Communication](#-inter-agent-communication)
- [LLM Providers](#-llm-providers)
- [Project Configuration](#-project-configuration)
- [File Structure](#-file-structure)
- [FAQ](#-faq)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Dynamic Agent Spawning** | Lead Agent analyzes your project and decides which specialist agents to create |
| **Product Planning Phase** | Auto-generates specifications, user stories, and acceptance criteria |
| **Smart Task Scheduling** | Dependency-aware execution — parallel when possible, serial when needed |
| **Inter-Agent Communication** | Agents can ask questions, report blockers, and resolve conflicts with each other |
| **Real-time Dashboard** | Web UI showing agent tree, task flow, live activity logs, and agent messages |
| **Agent Detail View** | Click any agent to see their step-by-step activity timeline |
| **Real File Output** | Agents generate complete, production-ready code files directly to disk |
| **Project Documentation** | Auto-generates `SPEC.md`, `TASK_PLAN.md`, and `BUILD_SUMMARY.md` in project folder |
| **Resume & Retry** | Failed projects can be resumed from the last checkpoint via dashboard |
| **Configurable LLM** | Supports Gemini (free), Anthropic (Claude), OpenAI, and Ollama (local) — swap anytime |
| **Git Integration** | Auto branching, commits per task, optional GitHub repo creation |
| **Code Safety** | Sandboxed file operations, allowlisted shell commands, path validation |
| **Semi-Auto Mode** | Agents work freely, you review the results before merging |

---

## 🏗 Architecture

```
                         YOU
                          |
                   [Project Description]
                          |
                          v
              +----------------------+
              |     Lead Agent       |    <-- Orchestrator
              |   (Orchestrator)     |
              +----------+-----------+
                         |
              +----------+-----------+
              |                      |
              v                      v
     +----------------+    +------------------+
     | Product Phase  |    | Development Phase|
     |                |    |                  |
     | - PM Agent     |    | - DB Engineer    |
     | - Tech Lead    |    | - Backend Dev    |
     |                |    | - Frontend Dev   |
     | Output: Spec   |    | - Tester         |
     +----------------+    | - DevOps         |
                           +------------------+
                                  |
                                  v
                         [Real Files on Disk]
                         [Git Commits]
                         [Working Code]
```

---

## 📋 Requirements

- **Python 3.10+** (tested with 3.12)
- **Git** installed and in PATH
- **Gemini API Key** (free from Google AI Studio) OR **Anthropic API Key** (Claude)
- *Optional:* GitHub CLI (`gh`) for auto repo creation
- *Optional:* Ollama for local LLM

---

## 📦 Installation

### 1. Clone / Navigate to the Project

```bash
git clone https://github.com/dermawans/ai-agent-team.git
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create Environment File

```bash
# Copy the example env file
copy .env.example .env
```

### 4. Set Your Gemini API Key

1. Go to **https://aistudio.google.com/apikey**
2. Click **"Create API Key"** (it's free!)
3. Copy the key
4. Open `.env` and replace:

```env
GEMINI_API_KEY=your_actual_api_key_here
```

---

## ⚙ Configuration

All settings are in the `.env` file:

### LLM Provider

```env
# Which LLM to use: gemini | openai | ollama
LLM_PROVIDER=gemini

# Gemini (default, free tier)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash

# Anthropic (optional)
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# OpenAI (optional)
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini

# Ollama local (optional, requires Ollama running)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
```

### Project Defaults

```env
# Where new projects are created
DEFAULT_PROJECT_DIR=your_main_project_path

# How autonomous the agents are:
#   safe      = ask before every file change
#   semi_auto = work freely, user reviews at end (recommended)
#   full_auto = work + commit + deploy without asking
AUTONOMOUS_LEVEL=semi_auto
```

### Git

```env
GIT_AUTO_COMMIT=true          # Commit after each task
GIT_AUTO_PUSH=false           # Don't push without user approval
GIT_DEFAULT_BRANCH=main       # Default branch name

# GitHub repo creation (requires `gh` CLI)
GITHUB_AUTO_CREATE_REPO=false
GITHUB_DEFAULT_VISIBILITY=private
```

### Dashboard

```env
DASHBOARD_HOST=127.0.0.1      # Localhost only
DASHBOARD_PORT=8420            # Port number
```

---

## 🚀 Quick Start

### Start the Dashboard

```bash
python main.py
```

Open your browser to **http://127.0.0.1:8420**

### Create Your First Project

1. Click **"+ New Project"** or **"Create Your First Project"**
2. Fill in the form:

| Field | Example | Description |
|-------|---------|-------------|
| **Title** | `Todo List App` | Short project name |
| **Description** | `Build a todo list web application using Laravel with user authentication, CRUD for tasks, categories, due dates, priority levels, and a clean modern UI.` | Detailed description — the more detail, the better |
| **Target Path** | `C:\laragon8\www\todo-app` | Where to create the project (leave empty for auto) |

3. Click **"Start Agent Team"**
4. Watch your AI team work in real-time!

---

## 📊 Dashboard Guide

### Layout Overview

```
+-------------+------------------------------------------------+
|             |                                                |
|  Projects   |   Project Detail                               |
|  Sidebar    |                                                |
|             |   +-- Agent Tree ---+  +-- Task Flow --------+ |
|  > #1 [ok]  |   | Lead Agent     |  | [done] DB Migration  | |
|  > #2 [wip] |   | +- PM [done]   |  | [wip]  Controller    | |
|  > #3 [new] |   | +- Backend [on]|  | [wait] Frontend      | |
|             |   | +- Frontend    |  | [wait] Tests         | |
|             |   +----------------+  +----------------------+ |
|             |                                                |
|  [+ New]    |   +-- Live Activity ----+  +-- Messages -----+ |
|             |   | 19:30 Writing file  |  | Backend > DB:   | |
|             |   | 19:29 Reading spec  |  | "field missing?"| |
|             |   | 19:28 Agent spawned |  | DB > Backend:   | |
|             |   +---------------------+  | "I'll add it"   | |
|             |                            +-----------------+ |
+-------------+------------------------------------------------+
```

### Panels Explained

#### 1. Sidebar — Project List
- Shows all your projects with status indicators
- Color dots: gray=pending, yellow=planning, cyan=in progress, green=completed, red=failed
- Click a project to view its details

#### 2. Agent Tree
- Shows the hierarchy of AI agents working on your project
- Grouped by team: Product Team / Dev Team / QA Team
- Status dots:
  - 🟢 **Green (pulsing)** = Currently active, working on a task
  - ⚪ **Gray** = Idle, waiting for assignment
  - 🟡 **Yellow (pulsing)** = Waiting for another agent's response
  - 🟣 **Purple** = Completed all tasks
  - 🔴 **Red** = Error occurred
- **Click any agent** to open the detail drawer

#### 3. Task Flow
- Shows all tasks in the project with their status
- Status icons: ✅ completed, 🔧 in progress, ⏳ pending, ❌ failed, 🚫 blocked
- Each task shows:
  - Task title
  - Assigned agent type badge
  - Dependency count (🔗)
- Stats bar at top: completed / active / pending counts

#### 4. Live Activity Log
- Real-time stream of everything happening in the project
- Icons indicate action type:
  - 🔍 Reading file
  - ✏️ Writing/creating file
  - ⚡ Running command
  - 🔀 Git commit
  - 💬 Message sent
  - 💭 Agent thinking
  - ✅ Task completed
  - 📊 Phase changed
- Shows newest entries at the bottom (auto-scrolls)

#### 5. Agent Communication
- Shows messages exchanged between agents
- Message types with colors:
  - 🔴 **Blocker** = Agent is stuck, needs help
  - 🟡 **Question** = Asking for clarification
  - 🟢 **Answer** = Responding to a question
  - 🟣 **Decision** = Final decision made
- Shows sender, recipient, and timestamp

#### 6. Agent Detail Drawer
- Opens when you click an agent in the Agent Tree
- Shows:
  - Agent name, type, and current status
  - **Activity Timeline** — chronological list of everything the agent did:
    - What files it read
    - What files it created/modified
    - What commands it ran
    - What messages it sent/received
    - What it was thinking about

### Project Progress Bar
- At the top right of the project detail
- Shows overall completion percentage
- Fills up as tasks complete

---

## 💻 CLI Mode

You can also run projects directly from the command line without the dashboard:

```bash
# Basic usage
python main.py --project "Project Title" --description "Detailed description"

# With target path (existing codebase)
python main.py -p "Add Stats Feature" -d "Add player statistics tracking with charts" -t "C:\laragon8\www\socceracademia"

# For a new project
python main.py -p "Blog Platform" -d "Build a blog platform with Laravel, markdown support, categories, and comments"
```

CLI will print all agent activity directly to the terminal.

---

## 🔧 How It Works

### Project Lifecycle

```
1. CREATE PROJECT
   You provide: title, description, optional target path
   
2. PRODUCT PHASE
   Lead Agent analyzes requirements
   Generates: SPEC.md (specification document)
   
3. PLANNING PHASE
   Lead Agent analyzes the spec
   Breaks it down into Tasks with dependencies
   Generates: TASK_PLAN.md (task breakdown)
   
4. DEVELOPMENT PHASE
   Lead Agent spawns needed Dev agents
   Scheduler starts executing tasks:
   - Independent tasks run in PARALLEL
   - Dependent tasks run in SERIAL
   Each agent writes real files to disk using --- FILE: --- markers
   Agents can communicate with each other during execution
   
5. REVIEW PHASE
   Lead Agent compiles all results
   Generates: BUILD_SUMMARY.md (project report)
   Lists all files created/modified
   
6. DONE
   You review the code, merge the branch, deploy
```

### Output Files

Every project automatically generates these documentation files in the target folder:

| File | Contents | When |
|------|----------|------|
| `SPEC.md` | Full product specification, user stories, data model, UI requirements | After Product Phase |
| `TASK_PLAN.md` | Task breakdown table with agents, priorities, and dependencies | After Planning Phase |
| `BUILD_SUMMARY.md` | Final build report — what was created, status, next steps | After Review Phase |

### Parallel vs Serial Execution

The scheduler automatically determines which tasks can run simultaneously:

```
Example: "Add user authentication feature"

SERIAL (must wait):
  [1] DB Migration (create users table)
      ↓
  [2] User Model (needs the table)
      ↓
  [3] Auth Controller (needs the model)

PARALLEL (can run together):
  [4] Login View     ← runs at same time as [5]
  [5] Register View  ← runs at same time as [4]

SERIAL (must wait for all above):
  [6] Feature Tests
```

### Conflict Resolution

When agents find inconsistencies:

```
1. Backend Dev finds: "Spec says field 'phone_2' but DB doesn't have it"
2. Backend Dev sends BLOCKER message to DB Engineer + PM
3. Backend Dev PAUSES execution
4. PM responds: "Field is required per user requirements"
5. DB Engineer responds: "I'll add the migration now"
6. DB Engineer creates new migration task
7. Backend Dev RESUMES work
```

All of this is visible in the dashboard's Agent Communication panel.

---

## 🤖 Agent Types

| Agent | Icon | Phase | What They Do |
|-------|------|-------|-------------|
| **Lead Agent** | 🏠 | All | Orchestrates everything, spawns agents, manages phases |
| **Product Manager** | 📋 | Product | Creates specs, user stories, acceptance criteria |
| **Tech Lead** | 🏗️ | Product | Reviews feasibility, defines architecture, breaks down tasks |
| **DB Engineer** | 🗄️ | Development | Database migrations, schema design, seeders |
| **Backend Dev** | ⚙️ | Development | Controllers, models, services, routes, API endpoints |
| **Frontend Dev** | 🎨 | Development | Views, templates, CSS, JavaScript, UI components |
| **QA Tester** | 🧪 | Testing | Unit tests, feature tests, integration tests |
| **DevOps** | 🚀 | Development | Project setup, deployment, CI/CD, environment config |

**The Lead Agent dynamically decides** which agents to spawn for each project. A simple CSS change might only need a Frontend Dev, while a full feature needs the whole team.

---

## 💬 Inter-Agent Communication

Agents can send these types of messages:

| Type | Purpose | Blocking? |
|------|---------|-----------|
| **question** | Ask another agent for information | Optional |
| **answer** | Respond to a question | No |
| **blocker** | Report an issue that prevents progress | Yes — sender pauses |
| **info** | Share useful information | No |
| **decision** | Communicate a final decision | No |
| **new_task** | Request a new task to be created | No |

### Escalation Chain
1. Agent tries to solve the problem itself
2. Agent asks the relevant specialist agent
3. If unresolved, escalates to Lead Agent
4. Lead Agent makes the final decision

---

## 🔌 LLM Providers

### Google Gemini (Default, Recommended)

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

**Free tier:** Limited requests/minute. The system has built-in smart retry with backoff for rate limits (429) and server overload (503).

Get your key: https://aistudio.google.com/apikey

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your_key_here
OPENAI_MODEL=gpt-4o-mini
```

**Pricing:** ~$0.15 per 1M tokens (gpt-4o-mini)

### Ollama (Local, Free, Offline)

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
```

**Requirements:** Ollama installed, GPU with 8GB+ VRAM recommended.

```bash
# Install a good coding model
ollama pull qwen2.5-coder:14b
```

### Switching Providers

Just change `LLM_PROVIDER` in `.env` and restart. No code changes needed.

---

## 📂 File Structure

```
ai-agent-team/
├── main.py                  # Entry point (CLI + Dashboard)
├── config.py                # Configuration loader
├── requirements.txt         # Python dependencies
├── .env                     # Your settings (API keys, etc.)
├── .env.example             # Settings template
│
├── core/                    # Core Engine
│   ├── orchestrator.py      # Lead Agent brain
│   ├── agent.py             # Base Agent class
│   ├── agent_registry.py    # Agent type definitions
│   ├── task_manager.py      # Task CRUD & tracking
│   ├── message_bus.py       # Inter-agent messaging
│   ├── scheduler.py         # Task execution engine
│   └── llm_client.py        # LLM API wrapper
│
├── tools/                   # Agent Tools
│   ├── file_tools.py        # File operations
│   ├── git_tools.py         # Git operations
│   ├── shell_tools.py       # Shell commands
│   └── code_analyzer.py     # Code analysis
│
├── database/                # Database
│   ├── models.py            # ORM models
│   └── connection.py        # DB connection
│
├── dashboard/               # Web Dashboard
│   ├── app.py               # FastAPI server
│   ├── templates/
│   │   └── index.html       # Dashboard UI
│   └── static/
│       ├── css/
│       │   └── dashboard.css
│       └── js/
│           ├── app.js        # Main logic
│           ├── agent_tree.js  # Agent tree component
│           ├── task_flow.js   # Task flow component
│           └── websocket.js   # WebSocket client
│
└── data/                    # Runtime data
    └── agent_team.db        # SQLite database (auto-created)
```

---

## ❓ FAQ

### Q: Is this really free?
**Yes.** The system itself is 100% free and open. The only cost is the LLM API — and Gemini's free tier (15 RPM, ~1M tokens/day) is generous enough for most use cases. You can also use Ollama for completely offline, free operation.

### Q: Will the agents actually create real files?
**Yes.** Agents create, modify, and delete real files on your filesystem. That's why we have the `semi_auto` mode — agents work freely, but you review everything before merging/deploying.

### Q: Can I add my own agent types?
**Yes.** Edit `core/agent_registry.py` to add new agent types. Define a name, system prompt, allowed tools, and phase.

### Q: What happens if an agent makes a mistake?
The code is written to a **separate Git branch** per project. If something goes wrong, simply delete the branch. Your main code is never touched until you explicitly merge.

### Q: Can I use this for non-Laravel projects?
**Yes.** The system is general-purpose. The Product Team (PM + Tech Lead) will analyze your project description and recommend the appropriate tech stack. It works with any language/framework.

### Q: What if the Gemini free tier runs out?
You'll get rate-limited. The system has built-in rate limiting and retry logic that will wait and retry automatically. For heavy usage, switch to Gemini paid tier (~$0.10 per 1M tokens) or use Ollama locally.

### Q: Can multiple people use this?
Currently designed for **single user** (localhost). For team use, change `DASHBOARD_HOST=0.0.0.0` in `.env` to allow network access — but there's no authentication yet.

---

## 🛡 Security Notes

- **File operations** are sandboxed to the project directory — agents cannot read/write files outside it
- **Shell commands** are allowlisted — only safe commands (php, npm, git, etc.) are permitted
- **API keys** are stored in `.env` (gitignored) — never committed to Git
- **Semi-auto mode** ensures you always review before any code reaches production
- **Git branching** protects your main branch from unreviewed changes

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

*Built with ❤️ by [dermawans](https://github.com/dermawans)*
