#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote (web) sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# setuptools must be current before langdetect can build
pip install --quiet --upgrade setuptools
pip install --quiet -r requirements.txt
