"""
AI Agent Team System - Configuration
Loads environment variables and provides typed configuration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class LLMConfig:
    """LLM provider configuration."""
    PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # Rate limiting
    MAX_RPM = int(os.getenv("LLM_MAX_RPM", "14"))  # Requests per minute (Gemini free = 15)
    MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
    RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "2.0"))


class ProjectConfig:
    """Project defaults."""
    DEFAULT_DIR = os.getenv("DEFAULT_PROJECT_DIR", str(Path.home() / "Projects"))
    AUTONOMOUS_LEVEL = os.getenv("AUTONOMOUS_LEVEL", "semi_auto")  # safe | semi_auto | full_auto


class DashboardConfig:
    """Dashboard settings."""
    HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    PORT = int(os.getenv("DASHBOARD_PORT", "8420"))


class GitConfig:
    """Git settings."""
    AUTO_COMMIT = os.getenv("GIT_AUTO_COMMIT", "true").lower() == "true"
    AUTO_PUSH = os.getenv("GIT_AUTO_PUSH", "false").lower() == "true"
    DEFAULT_BRANCH = os.getenv("GIT_DEFAULT_BRANCH", "main")
    GITHUB_AUTO_CREATE_REPO = os.getenv("GITHUB_AUTO_CREATE_REPO", "false").lower() == "true"
    GITHUB_DEFAULT_VISIBILITY = os.getenv("GITHUB_DEFAULT_VISIBILITY", "private")


class DatabaseConfig:
    """Database settings."""
    URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'agent_team.db'}")


class Config:
    """Main configuration aggregator."""
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    LLM = LLMConfig()
    PROJECT = ProjectConfig()
    DASHBOARD = DashboardConfig()
    GIT = GitConfig()
    DATABASE = DatabaseConfig()

    @classmethod
    def ensure_dirs(cls):
        """Ensure required directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_dirs()
