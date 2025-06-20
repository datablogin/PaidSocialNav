# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MetaGraphAPI is a unified Python application for managing paid social media advertising campaigns across multiple platforms. It provides a single interface to create, manage, and monitor ads on Meta (Facebook, Instagram, WhatsApp), Reddit, Pinterest, TikTok, and X (Twitter).

## Development Environment

- **Python Version**: Python 3.11 or higher required
- **IDE**: PyCharm configuration included
- **Virtual Environment**: `.venv/` directory present

## Project Structure

The project is currently empty with only basic scaffolding:
```
MetaGraphAPI/
├── pyproject.toml     # Python project configuration
├── .venv/             # Python virtual environment
└── .idea/             # PyCharm IDE configuration
```

## Build and Development Commands

Since the project has no code yet, standard Python development practices should be followed:

### Virtual Environment
```bash
# Activate virtual environment (macOS/Linux)
source .venv/bin/activate

# Install dependencies (once added to pyproject.toml)
pip install -e .
```

## Architecture Notes

The project is a blank slate. When implementing:
1. Consider using a standard Python project structure (e.g., `src/metagraphapi/` or `metagraphapi/`)
2. Follow Python packaging best practices
3. Add appropriate testing framework (pytest recommended)
4. Consider API framework choice (FastAPI, Flask, Django REST Framework, etc.)

## Important Considerations

- This is a fresh project with no existing code patterns to follow
- First commit has not been made yet (files are staged)
- No dependencies have been specified yet