# Scribe Guides

Step-by-step guides for using and maintaining the Scribe system.

## Available Guides

### [Setup Guide](setup.md)
How to install and configure Scribe for first use.

### [Usage Guide](usage.md)
Complete guide to using all CLI commands including backup and database maintenance.

### [Evaluation Guide](evaluation.md)
How to evaluate translation quality for historical accuracy, including enhanced Hebrew evaluation.

### [Backup Guide](backup.md)
Complete guide to the backup and restore system.

### [Database Maintenance Guide](database-maintenance.md)
Database auditing, validation, and maintenance procedures.

### [Utilities Guide](utilities.md)
Guide to one-off scripts and maintenance utilities (use with caution).

### [Troubleshooting Guide](troubleshooting.md)
Common issues and their solutions, including system recovery procedures.

## Quick Start

1. **Setup**: Install dependencies with `uv pip install -r requirements.txt`
2. **Configure**: Create `.env` file with API keys
3. **Add Files**: `uv run python scribe_cli.py add /path/to/media/`
4. **Process**: `uv run python scribe_cli.py process`
5. **Monitor**: `uv run python scribe_cli.py status`

## For New Users

Start with the [Setup Guide](setup.md), then follow the [Usage Guide](usage.md) for your first processing run.

## For Developers

See the [Architecture Documentation](../architecture/) for technical details about the system design.