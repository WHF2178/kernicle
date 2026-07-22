# Kernicle - Quick Reference Guide

## Project Structure

```
Kernicle/
├── src/
│   └── kernicle/
│       ├── __init__.py          # Version info
│       ├── cli.py               # Typer CLI commands
│       ├── config.py            # Configuration & paths
│       └── services/
│           ├── __init__.py
│           ├── timeparse.py     # Time range parsing
│           ├── journal.py       # journalctl wrappers
│           └── archive.py       # Session management
├── tests/
│   └── test_timeparse.py        # Unit tests
├── pyproject.toml               # Project config & dependencies
├── README.md                    # Main documentation
├── setup.sh                     # Automated setup script
└── .gitignore                   # Git ignore rules
```

## Setup Instructions

### Option 1: Automated Setup (Recommended)

```bash
cd /home/s4u/Desktop/Kernicle
./setup.sh
```

This script will:
1. Check Python version
2. Create virtual environment
3. Install Kernicle with dev dependencies
4. Run tests to verify installation

### Option 2: Manual Setup

```bash
cd /home/s4u/Desktop/Kernicle

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Usage Examples

### Activate Virtual Environment (always do this first!)

```bash
cd /home/s4u/Desktop/Kernicle
source venv/bin/activate
```

### Check Installation

```bash
kernicle --version
```

### Capture Logs

**Kernel logs only (last 5 minutes):**
```bash
sudo kernicle push --range "last:5m" --kernel-only
```

**Both kernel and system logs (last 30 minutes):**
```bash
sudo kernicle push --range "last:30m" --all
```

**Using ISO datetime:**
```bash
sudo kernicle push --range "2025-12-30T12:00:00Z" --all
```

**Supported time ranges:**
- `last:30s` - Last 30 seconds
- `last:5m` - Last 5 minutes
- `last:2h` - Last 2 hours
- `last:1d` - Last 1 day
- `2025-12-30T12:00:00Z` - ISO datetime (UTC)

### View Sessions

```bash
kernicle show --limit 5
```

### View a Session Report

```bash
cat ~/.kernicle/archives/session-*/report.txt
```

## Fixing Permissions

To avoid using `sudo` every time:

```bash
# Add your user to systemd-journal group
sudo usermod -a -G systemd-journal $USER

# Log out and back in for changes to take effect
# Or use: newgrp systemd-journal
```

Verify permissions:
```bash
journalctl -k --since "5 minutes ago" --no-pager | head -5
```

## Development Commands

### Run Tests
```bash
pytest
```

### Run Tests with Coverage
```bash
pytest --cov=kernicle --cov-report=term-missing
```

### Run Tests Verbosely
```bash
pytest -v
```

### Run Specific Test File
```bash
pytest tests/test_timeparse.py
```

### Check Code Style (future)
```bash
# TODO: Add in later sprint
# black src/ tests/
# ruff check src/ tests/
```

## Session Archive Structure

Each capture creates a session in `~/.kernicle/archives/`:

```
~/.kernicle/archives/session-20251230-120000/
├── sources/
│   ├── journalctl-kernel.log    # Kernel logs
│   └── journalctl-system.log    # System logs (if --all)
├── report.txt                   # Human-readable report
└── manifest.json                # Machine-readable metadata
```

## Troubleshooting

### "journalctl command not found"
- Make sure systemd is installed: `systemctl --version`

### "Permission denied"
- Run with sudo: `sudo kernicle push ...`
- Or add user to group: `sudo usermod -a -G systemd-journal $USER`

### "kernicle: command not found"
- Activate virtual environment: `source venv/bin/activate`
- Reinstall: `pip install -e .`

### Tests fail
- Make sure dev dependencies are installed: `pip install -e ".[dev]"`
- Check Python version: `python3 --version` (need 3.10+)

## What's in Sprint 1

✅ **Implemented:**
- Flexible time range parsing
- Kernel and system log capture
- Structured session archives
- Beautiful CLI with Rich
- Basic unit tests

❌ **Not in Sprint 1 (coming later):**
- Panic detection
- Error metrics
- ZIP archives
- Git integration
- Background sessions
- Encryption

## Next Steps After Setup

1. **Test basic functionality:**
   ```bash
   sudo kernicle push --range "last:1m" --kernel-only
   kernicle show
   ```

2. **Check the generated report:**
   ```bash
   ls -la ~/.kernicle/archives/
   cat ~/.kernicle/archives/session-*/report.txt
   ```

3. **Fix permissions (optional):**
   ```bash
   sudo usermod -a -G systemd-journal $USER
   # Log out and back in
   ```

4. **Start developing Sprint 2 features** (later)

## Getting Help

- Run `kernicle --help` for command help
- Run `kernicle push --help` for push command options
- Check README.md for detailed documentation
- Review report.txt in any session for Sprint roadmap
