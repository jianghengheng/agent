"""Vercel Serverless Function entry point for the FastAPI backend."""

import sys
from pathlib import Path

# Add the src directory to Python path so ai_multi_agent package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai_multi_agent.app import create_app  # noqa: E402

app = create_app()
