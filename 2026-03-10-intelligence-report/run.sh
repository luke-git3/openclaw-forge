#!/bin/bash
# Beacon — Quick-start script
# Usage:
#   ./run.sh            → run pipeline once (no delivery)
#   ./run.sh --deliver  → run pipeline + deliver to Discord
#   ./run.sh --server   → start the dashboard server (port 7460)
#   ./run.sh --demo     → show the OpenClaw tool call mappings

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEACON_DIR="$SCRIPT_DIR/beacon"

echo "🔭 Beacon Intelligence Pipeline"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Install Python 3.10+ and retry."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"

# Check if in a virtual environment; offer to create one
if [[ -z "$VIRTUAL_ENV" && ! -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
    echo ""
    echo "ℹ  No virtual environment detected."
    echo "   Run: python3 -m venv .venv && source .venv/bin/activate"
    echo "   Then re-run this script."
    echo ""
fi

cd "$BEACON_DIR"

case "${1:-}" in
    --server)
        echo "Starting dashboard server on http://localhost:7460 ..."
        python3 server.py
        ;;
    --demo)
        echo "OpenClaw tool call mappings:"
        python3 openclaw_agent.py
        ;;
    --deliver)
        echo "Running pipeline with Discord delivery..."
        if [[ -z "$BEACON_DISCORD_WEBHOOK" ]]; then
            echo "⚠  BEACON_DISCORD_WEBHOOK not set — delivery will be skipped."
        fi
        python3 pipeline.py --deliver
        ;;
    *)
        echo "Running pipeline (no delivery)..."
        python3 pipeline.py
        ;;
esac
