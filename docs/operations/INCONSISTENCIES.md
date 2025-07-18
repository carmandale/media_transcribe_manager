# Documentation Inconsistencies

This document tracks inconsistencies between different documentation files that need to be resolved.

## Package Manager Inconsistency

### Issue:
- **README.md** uses `pip install -r requirements.txt` and `python scribe_cli.py`
- **CLAUDE.md** correctly notes to use `uv` package manager
- **Actual usage** requires `uv run python scribe_cli.py`

### Resolution:
✅ FIXED - README.md and CLAUDE.md now consistently use `uv` commands.

## Missing Documentation Files

### Referenced but Not Created:
1. `docs/architecture/system-components.md`
2. ~~`docs/guides/troubleshooting.md`~~ ✅ CREATED
3. `docs/api/database.md`
4. `docs/api/pipeline.md`
5. `docs/api/cli-commands.md`
6. `docs/decisions/001-cleanup-refactor.md`
7. `docs/decisions/002-hebrew-evaluation.md`

### Resolution:
✅ PARTIAL - Created troubleshooting.md. Other files should be created as needed or references removed.

## Command Prefix Inconsistency

### Issue:
- Some docs show `python scribe_cli.py`
- Others show `uv run python scribe_cli.py`
- Actual requirement is `uv run python`

### Resolution:
✅ FIXED - All documentation now uses `uv run python` prefix consistently.

## Status Command Issues

### Issue:
- Documentation shows `status --detailed` as working
- Actual behavior: throws KeyError due to missing database methods

### Resolution:
✅ FIXED - Database methods added and status commands now work correctly.

## Project Structure

### Issue:
- README.md doesn't show the `docs/` directory in project structure
- CLAUDE.md includes it

### Resolution:
✅ FIXED - README.md now includes docs/ directory and evaluate_hebrew.py in structure.

## evaluate_hebrew.py Documentation

### Issue:
- New script created but not documented

### Resolution:
✅ FIXED - Added to README.md, CLAUDE.md, and evaluation.md guide.

## Summary

### Fixed:
- ✅ All commands use `uv run python` consistently
- ✅ README.md updated with complete structure
- ✅ evaluate_hebrew.py documented
- ✅ troubleshooting.md created
- ✅ Status commands working

### Remaining:
- Several API documentation files referenced but not created
- ADR files for decisions not created

These remaining files can be created as needed for future development.