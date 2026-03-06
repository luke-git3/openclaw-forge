#!/usr/bin/env bash
# finsnap/install.sh
# Installs finsnap skill into your OpenClaw workspace.
#
# Usage:
#   ./install.sh                    # auto-detect OpenClaw workspace
#   ./install.sh /path/to/skills/   # custom install directory
#
# After install: tell your OpenClaw agent "What's AAPL trading at?"
# The skill will be automatically detected and loaded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Detect install target ──────────────────────────────────────────────────────
TARGET_DIR="${1:-}"

if [[ -z "$TARGET_DIR" ]]; then
  # Common OpenClaw workspace skill paths
  for candidate in \
    "$HOME/.openclaw/workspace/skills" \
    "$HOME/.openclaw/skills" \
    "${OPENCLAW_WORKSPACE:-}/skills"; do
    if [[ -d "$candidate" ]]; then
      TARGET_DIR="$candidate"
      break
    fi
  done
fi

if [[ -z "$TARGET_DIR" ]]; then
  echo "❌ Could not find OpenClaw skills directory."
  echo "   Pass the path as an argument: ./install.sh /path/to/skills/"
  echo "   Or set OPENCLAW_WORKSPACE env var to your workspace root."
  exit 1
fi

SKILL_INSTALL_DIR="$TARGET_DIR/finsnap"

echo "📦 Installing finsnap to: $SKILL_INSTALL_DIR"

# ── Copy skill files ───────────────────────────────────────────────────────────
mkdir -p "$SKILL_INSTALL_DIR"
cp -r "$SCRIPT_DIR/"* "$SKILL_INSTALL_DIR/"
chmod +x "$SKILL_INSTALL_DIR/scripts/fetch_quote.sh"
chmod +x "$SKILL_INSTALL_DIR/scripts/fetch_news.sh"
chmod +x "$SKILL_INSTALL_DIR/scripts/finsnap.py"

echo "✅ Files copied."

# ── Check dependencies ─────────────────────────────────────────────────────────
echo ""
echo "🔍 Checking dependencies..."

check_bin() {
  if command -v "$1" &>/dev/null; then
    echo "   ✅ $1 — found"
  else
    echo "   ❌ $1 — MISSING (required)"
    MISSING=1
  fi
}

check_pip() {
  if python3 -c "import $1" &>/dev/null; then
    echo "   ✅ python: $1 — found"
  else
    echo "   ⚠️  python: $1 — not installed (optional, but recommended)"
    echo "      Install with: pip3 install $1"
  fi
}

MISSING=0
check_bin bash
check_bin curl
check_bin python3
check_pip requests

echo ""
echo "🔑 AI synthesis (optional — skill works without these):"
[[ -n "${ANTHROPIC_API_KEY:-}" ]] && echo "   ✅ ANTHROPIC_API_KEY — set" || echo "   ⚠️  ANTHROPIC_API_KEY — not set (no AI synthesis)"
[[ -n "${OPENAI_API_KEY:-}" ]]    && echo "   ✅ OPENAI_API_KEY — set"    || echo "   ⚠️  OPENAI_API_KEY — not set (no AI synthesis)"
[[ -n "${DISCORD_WEBHOOK_URL:-}" ]] && echo "   ✅ DISCORD_WEBHOOK_URL — set" || echo "   ⚠️  DISCORD_WEBHOOK_URL — not set (no Discord push delivery)"

if [[ "$MISSING" -eq 1 ]]; then
  echo ""
  echo "❌ Required dependencies are missing. Install them and re-run."
  exit 1
fi

echo ""
echo "🎉 finsnap installed successfully!"
echo ""
echo "Test it:"
echo "   python3 $SKILL_INSTALL_DIR/scripts/finsnap.py AAPL"
echo ""
echo "Or just ask your OpenClaw agent:"
echo "   \"What's Apple trading at?\""
echo "   \"Quick snap on NVDA and MSFT\""
