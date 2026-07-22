"""Runtime configuration.

Reads optional settings from environment variables (see .env.example).
No API key is ever hardcoded here; external LLM planners are extension
points for the future and are not required to run this project today.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load a .env file (if present) into the process environment. python-dotenv
# searches upward from this file's directory, so this works regardless of
# the current working directory the CLI is invoked from. It is a no-op if
# no .env file exists, which is the default/expected state of this project.
load_dotenv()

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_TASKS_FILE = PACKAGE_DIR / "tasks" / "sample_tasks.yaml"
RESULTS_DIR = Path.cwd() / "results"

MAX_EXECUTION_STEPS = 30
DEFAULT_RANDOM_SEED = 42


@dataclass(frozen=True)
class Settings:
    """Small, explicit settings object (avoids scattering os.environ calls)."""

    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY") or None
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY") or None
    model_name: str | None = os.environ.get("MODEL_NAME") or None
    log_level: str = os.environ.get("GENIAC_CAP_LOG_LEVEL", "INFO")
    random_seed: int = int(os.environ.get("GENIAC_CAP_SEED", DEFAULT_RANDOM_SEED))


settings = Settings()
