#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "AgentLens competition demo"
echo "=========================="
echo

echo "1. Backend verification"
cd "$ROOT_DIR/backend"
uv run pytest
uv run ruff check .
echo

echo "2. Frontend build verification"
cd "$ROOT_DIR/frontend"
npm run build
echo

echo "3. Core local AgentLens demo"
cd "$ROOT_DIR/backend"
uv run agentlens-demo --fixture ../examples/demo_session.json
echo

echo "4. Slack Block Kit preview"
uv run agentlens-demo --fixture ../examples/demo_session.json --slack
echo

echo "5. Optional live Codex adapter preview"
echo "Run manually when Codex auth is available:"
echo "cd backend"
echo "uv run agentlens-demo --codex-prompt \"Do not modify files. Inspect the repository at a high level and answer with the names of the top-level files/directories you used. Keep it brief.\""
echo

echo "Demo checklist: docs/competition_demo.md"
