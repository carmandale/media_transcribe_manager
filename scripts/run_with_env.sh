#!/bin/bash
# Wrapper script to ensure .env is loaded for all uv run commands
# Solves issue #87: env not loaded for "uv run" processes

set -a  # Export all variables
if [ -f .env ]; then
    source .env
fi
set +a

# Execute the command passed as arguments
exec "$@"