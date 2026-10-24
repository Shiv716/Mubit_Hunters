"""Runtime settings, read from environment variables only. Never hard-code secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
POLICY_DIR = BACKEND_DIR / "policy"


def _load_dotenv() -> None:
    """Minimal .env loader so the demo runs without python-dotenv. Existing env vars win."""
    for candidate in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    # "mubit" calls the live Mubit gateway; "stub" is an offline deterministic stand-in for tests/demo
    # without credentials. The stub is NOT Mubit and is labelled as such everywhere it appears.
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "mubit" if os.getenv("MUBIT_API_KEY") else "stub"))
    mubit_api_key: str | None = field(default_factory=lambda: os.getenv("MUBIT_API_KEY"))
    # openai -> {base}/chat/completions ; anthropic -> {base}/v1/messages. Both are Mubit gateway routes.
    mubit_route: str = field(default_factory=lambda: os.getenv("MUBIT_ROUTE", "openai").lower())
    # Empty means "use the route's default" (filled in __post_init__).
    mubit_base_url: str = field(default_factory=lambda: os.getenv("MUBIT_BASE_URL", ""))
    mubit_model: str = field(default_factory=lambda: os.getenv("MUBIT_MODEL", ""))
    mubit_max_tokens: int = field(default_factory=lambda: int(os.getenv("MUBIT_MAX_TOKENS", "1500")))
    # json_schema | json_object | none. Starter credit may refuse some options; the adapter falls back.
    # json_object exists only on the openai route.
    mubit_response_format: str = field(default_factory=lambda: os.getenv("MUBIT_RESPONSE_FORMAT", "json_schema"))
    # full | metadata | off -> sent as x-middleware-record. Mubit records request+reply by default.
    mubit_record: str = field(default_factory=lambda: os.getenv("MUBIT_RECORD", "full"))
    mubit_timeout_s: float = field(default_factory=lambda: float(os.getenv("MUBIT_TIMEOUT_S", "60")))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("PCN_DB_PATH", str(BACKEND_DIR / "pcn_copilot.db"))))
    evidence_dir: Path = field(default_factory=lambda: Path(os.getenv("PCN_EVIDENCE_DIR", str(BACKEND_DIR / "evidence_store"))))
    precedent_top_k: int = field(default_factory=lambda: int(os.getenv("PRECEDENT_TOP_K", "3")))

    def __post_init__(self) -> None:
        if self.mubit_route not in ROUTE_DEFAULTS:
            raise ValueError(f"MUBIT_ROUTE must be one of {sorted(ROUTE_DEFAULTS)}, got {self.mubit_route!r}")
        base, model = ROUTE_DEFAULTS[self.mubit_route]
        if not self.mubit_base_url:
            object.__setattr__(self, "mubit_base_url", base)
        if not self.mubit_model:
            object.__setattr__(self, "mubit_model", model)


# Route -> (Mubit base URL, starter-credit model named in Mubit's quickstart). Check your console's Connect page.
ROUTE_DEFAULTS = {
    "openai": ("https://api.mubit.ai/openai/v1", "gpt-6-luna"),
    "anthropic": ("https://api.mubit.ai/anthropic", "claude-haiku-4-5"),
}


def get_settings() -> Settings:
    return Settings()
