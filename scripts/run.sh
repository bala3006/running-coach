#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'Python 3 is required. Install Python 3.11 or newer and retry.\n' >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import fastapi, mcp, uvicorn, running_coach' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -e .
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  printf 'Created .env from .env.example. Review OLLAMA_MODEL and optional integration settings.\n'
fi

exec .venv/bin/python -m uvicorn running_coach.app:app \
  --host 127.0.0.1 \
  --port "${PORT:-8000}"
