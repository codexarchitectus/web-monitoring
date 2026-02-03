# Project Context for Claude Code

## Project Overview
Async Python service that periodically checks website availability, tracks up/down state in SQLite, and sends email notifications on state changes.

## Technical Stack
- **Language**: Python 3.11+
- **Async runtime**: asyncio
- **HTTP client**: httpx
- **Database**: SQLite via aiosqlite
- **Config**: PyYAML + Pydantic validation
- **Email**: smtplib (stdlib)
- **Testing**: pytest + pytest-asyncio + pytest-httpx
- **Linter**: ruff

## Project Structure
```
web-monitoring/
├── src/web_monitor/
│   ├── __init__.py
│   ├── main.py          # Entry point, check loop, signal handling
│   ├── config.py         # YAML loading + env var substitution
│   ├── models.py         # Pydantic models (config + data)
│   ├── checker.py        # Async HTTP availability check
│   ├── database.py       # SQLite state tracking + check log
│   └── notifier.py       # Email notifications
├── config/
│   └── config.example.yaml
├── systemd/
│   └── web-monitor.service
├── tests/
│   ├── conftest.py
│   ├── test_checker.py
│   ├── test_database.py
│   └── test_notifier.py
└── pyproject.toml
```

## Coding Standards

### Style Guidelines
- **Indentation**: 4 spaces
- **Line Length**: 100 characters
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Files**: snake_case

### Error Handling
- checker.py never raises -- all errors become CheckResult with is_up=False
- notifier.py logs email failures but does not crash the loop
- Database errors propagate (service should restart via systemd)

## Dependencies and Installation
```bash
pip install -e ".[dev]"
```

## Running the Project
```bash
# Run with custom config
python -m web_monitor.main -c config/config.example.yaml

# Run tests
pytest

# Lint
ruff check src/ tests/
```

## Environment Variables
- `SMTP_PASSWORD` - SMTP authentication password (referenced in config.yaml via `${SMTP_PASSWORD}`)

## Key Patterns
- All site checks run concurrently via asyncio.gather
- State change detection compares current result to previous site_status row
- Email is sent via asyncio.to_thread to avoid blocking the event loop
- Config supports per-site check_interval_seconds overrides
