# DuplicAid

[![PyPI version](https://badge.fury.io/py/duplicaid.svg)](https://badge.fury.io/py/duplicaid)
[![Tests](https://github.com/jstet/duplicaid/workflows/Release/badge.svg)](https://github.com/jstet/duplicaid/actions)
[![Python versions](https://img.shields.io/pypi/pyversions/duplicaid.svg)](https://pypi.org/project/duplicaid/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

DuplicAid is a CLI tool for managing PostgreSQL backups via WAL-G (point-in-time recovery) and logical dumps. It provides a unified interface for creating, listing, and restoring backups from PostgreSQL instances running in Docker containers.

⚠️ The package depends on the image `lafayettegabe/wald`, which is a PostgreSQL container with WAL-G support and `tiredofit/docker-db-backup:4.1.21` for logical backups.

## Features

- **WAL-G Integration**: Create and restore point-in-time backups using WAL-G
- **Logical Backups**: Create and restore database dumps via tiredofit/db-backup or pg_dump
- **Dual Execution Modes**: Manage backups locally or on remote servers via SSH
- **Rich CLI Interface**: Beautiful command-line interface with progress indicators and tables
- **Configuration Management**: Easy setup and management of connection settings

## Installation

Install duplicaid using uv:

```bash
# Install from PyPI
uv add duplicaid

# Or install from source
git clone <repository-url>
cd duplicaid
uv sync --extra dev
```

## Configuration

Duplicaid stores configuration in `~/.duplicaid/config.yml` and supports two execution modes:

### Execution Modes

**Remote Mode** (default):
- Manages PostgreSQL containers on a remote server via SSH
- Requires SSH key authentication
- All Docker commands executed on remote server

**Local Mode**:
- Manages PostgreSQL containers on the local machine
- No SSH connection required
- Docker commands executed locally

### Setup

Initialize configuration interactively:

```bash
duplicaid config init
```

### Configuration Options

- **Execution Mode**: `remote` or `local`
- **Remote Server** (remote mode only): SSH connection details (host, user, port, key path)
- **Container Names**: PostgreSQL and backup container names
- **Paths**: Docker Compose file location
- **Databases**: List of databases to manage

### Example Configurations

**Remote Mode:**
```yaml
execution_mode: remote
remote:
  host: your-server.example.com
  user: root
  port: 22
  ssh_key_path: /home/user/.ssh/id_rsa
containers:
  postgres: postgres
  backup: db-backup
paths:
  docker_compose: /home/correlaid/postgres/docker-compose.yml
databases:
  - funding_scraper
  - u25
```

**Local Mode:**
```yaml
execution_mode: local
containers:
  postgres: postgres
  backup: db-backup
paths:
  docker_compose: /home/user/postgres/docker-compose.yml
databases:
  - funding_scraper
  - u25
```

## Quick Start

1. **Initialize Configuration**:
   ```bash
   duplicaid config init
   ```

2. **Check Status**:
   ```bash
   duplicaid status
   ```

3. **Create a Backup**:
   ```bash
   # WAL-G backup (all databases)
   duplicaid backup walg

   # Logical backup for specific database
   duplicaid backup logical --db my_database
   ```

4. **List Backups**:
   ```bash
   duplicaid list walg
   ```

## Commands Reference

### Configuration Management

```bash
# Initialize configuration
duplicaid config init

# Show current configuration
duplicaid config show

# Add/remove databases
duplicaid config add-db my_database
duplicaid config remove-db my_database
```

### Backup Operations

```bash
# Create WAL-G backup (point-in-time)
duplicaid backup walg

# Create logical backup for all databases
duplicaid backup logical

# Create logical backup for specific database
duplicaid backup logical --db database_name
```

### Restore Operations

```bash
# Restore from latest WAL-G backup
duplicaid restore walg

# Restore from specific WAL-G backup
duplicaid restore walg --backup backup_20240101T120000Z

# Point-in-time recovery
duplicaid restore walg --to "2024-01-01 12:00:00"

# Restore logical backup
duplicaid restore logical database_name /path/to/backup.sql.gz
```

### Listing Backups

```bash
# List WAL-G backups
duplicaid list walg

# List logical backups
duplicaid list logical
```

### System Information

```bash
# Show system status
duplicaid status

# Discover databases
duplicaid discover
```

## Architecture

### Remote Mode
```
Local Machine          Remote Server

  duplicaid      SSH
    CLI                PostgreSQL Container
                       (lafayettegabe/wald)

                          Backup Container
                        (tiredofit/db-backup)
```

### Local Mode
```
Local Machine

  duplicaid CLI
       |
   PostgreSQL Container
   (lafayettegabe/wald)
       |
   Backup Container
 (tiredofit/db-backup)
```

## Backup Types

### WAL-G Backups
- **Type**: Physical backups with continuous WAL archiving
- **Use Case**: Point-in-time recovery, full server restoration
- **Storage**: S3-compatible storage
- **Recovery**: Can restore to any point in time

### Logical Backups
- **Type**: SQL dumps using pg_dump
- **Use Case**: Database-specific backups, cross-version compatibility
- **Storage**: S3-compatible storage (compressed)
- **Recovery**: Database-specific restoration

## Requirements

### Common Requirements
- Python 3.12+
- Docker and Docker Compose
- PostgreSQL with WAL-G (e.g., lafayettegabe/wald:latest)
- tiredofit/db-backup container for logical backups

### Remote Mode Additional Requirements
- SSH access to remote server
- SSH key authentication configured

### Local Mode Additional Requirements
- Docker daemon running locally
- Access to local Docker socket

## Development

### Setup

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd duplicaid
   uv sync --extra dev
   ```

2. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

3. **Run tests**:
   ```bash
   uv run pytest
   ```

4. **Code formatting**:
   ```bash
   uv run black .
   uv run ruff check .
   ```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:
- **black**: Code formatting
- **ruff**: Linting and formatting
- **pytest**: Run test suite
- **Standard hooks**: Trailing whitespace, file endings, YAML validation

### Project Structure

```
duplicaid/
├── pyproject.toml          # Project configuration and dependencies
├── README.md               # This file
├── src/
│   └── duplicaid/          # Main package
│       ├── __init__.py
│       ├── cli.py          # CLI interface
│       ├── config.py       # Configuration management
│       ├── backup.py       # Backup operations
│       ├── ssh.py          # SSH connectivity
│       ├── executor.py     # Command execution
│       ├── discovery.py    # Database discovery
│       └── local.py        # Local operations
└── tests/                  # Test suite
    ├── conftest.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_integration.py
    └── test_local_executor.py
```

### Testing

The test suite includes:
- **Unit tests**: Test individual components
- **Integration tests**: Test component interactions
- **CLI tests**: Test command-line interface

Run specific test types:
```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration

# With coverage
uv run pytest --cov=duplicaid
```

### Integration Testing

Integration tests require Docker containers. Use the Makefile for container management:

```bash
# Start test containers
make setup-test

# Run integration tests manually
uv run pytest -m integration

# Stop test containers
make teardown-test

# Run integration tests with automatic container management
make test-integration

# Clean up containers and Docker system
make clean
```

### Development Workflow

This project uses automated releases with semantic commits.

#### Quick Start
```bash
# 1. Create feature branch
git checkout -b feat/new-feature

# 2. Make changes and commit
make commit  # Interactive semantic commit

# 3. Push and create PR
git push origin feat/new-feature

# 4. Merge PR → Auto-release to PyPI
```

#### Semantic Commits
```bash
git commit -m "fix: resolve timeout"      # → patch release
git commit -m "feat: add encryption"      # → minor release
git commit -m "feat!: redesign API"       # → major release
```

#### Commands
```bash
make commit       # Interactive semantic commit
make bump-patch   # Manual version bump
make release      # Full release process
```

#### Automation
- **PRs**: Auto-test, lint, format
- **Main branch**: Auto-version, auto-publish to PyPI
- **Pre-commit**: Enforce quality and commit format

### Building and Publishing

```bash
# Manual build (for testing)
uv build

# Automated publishing (via GitHub Actions)
# → Happens automatically on main branch pushes
# → No manual PyPI uploads needed

# Emergency manual publish (not recommended)
uv publish
```
