import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    llm_model_path: Path
    service_account_path: Path


def _resolve(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        llm_model_path=PACKAGE_DIR / "models" / os.environ["LLM_NAME"],
        service_account_path=_resolve(os.environ["SERVICE_ACCOUNT_PATH"]),
    )
