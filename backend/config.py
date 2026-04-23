import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment from either:
# - project root (flow-wise/.env)
# - backend folder (flow-wise/backend/.env)
#
# Also handle the case where the variable exists-but-empty in the process
# environment: `override=False` won't replace it, so we re-load with override.
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent

load_dotenv(_PROJECT_ROOT / ".env", override=False)
load_dotenv(_BACKEND_DIR / ".env", override=False)

if not os.getenv("CLAUDE_API_KEY"):
    load_dotenv(_PROJECT_ROOT / ".env", override=True)
    load_dotenv(_BACKEND_DIR / ".env", override=True)

CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
TEMPLATES_PATH: Path = _PROJECT_ROOT / "templates" / "templates.json"
