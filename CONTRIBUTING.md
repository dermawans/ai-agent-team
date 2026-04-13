# Contributing to AI Agent Team

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Bugs

1. Check if the bug is already reported in [Issues](https://github.com/dermawans/ai-agent-team/issues)
2. If not, create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Terminal/dashboard error logs
   - Python version and OS

### Suggesting Features

Open an issue with the `enhancement` label and describe:
- What problem does this solve?
- How should it work?
- Any examples or mockups?

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test your changes locally
5. Commit with clear messages: `git commit -m "feat: add new agent type"`
6. Push and create a Pull Request

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     New feature
fix:      Bug fix
docs:     Documentation changes
refactor: Code refactoring
test:     Adding tests
chore:    Maintenance tasks
```

## Development Setup

```bash
# Clone
git clone https://github.com/dermawans/ai-agent-team.git
cd ai-agent-team

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Add your API key to .env
# GEMINI_API_KEY=your_key_here

# Run
python main.py
```

## Areas for Contribution

- 🤖 **New Agent Types** — Add specialized agents in `core/agent_registry.py`
- 🔌 **LLM Providers** — Add support for Anthropic, Cohere, etc. in `core/llm_client.py`
- 🎨 **Dashboard UI** — Improve the web dashboard in `dashboard/`
- 🧪 **Testing** — Add unit/integration tests
- 📚 **Documentation** — Improve README, add tutorials
- 🌐 **i18n** — Add multi-language support

## Code Style

- Python: Follow PEP 8
- Use type hints where possible
- Add docstrings to classes and public methods
- Keep functions focused and under 50 lines

## Questions?

Open an issue or start a discussion. We're happy to help! 🙌
