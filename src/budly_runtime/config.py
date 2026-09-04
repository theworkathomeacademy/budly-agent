from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class FeatureFlags:
    budly_llm_enabled: bool = False
    budly_structured_output_enabled: bool = True
    budly_knowledge_retrieve_enabled: bool = False
    budly_session_memory_enabled: bool = True
    budly_model_fallback_enabled: bool = True
    budly_conversation_logging_enabled: bool = True
    budly_durable_memory_enabled: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str = "development"
    flags: FeatureFlags = field(default_factory=FeatureFlags)
    recent_turn_limit: int = 10
    summary_trigger_turns: int = 8
    max_input_chars: int = 8000
    max_repair_attempts: int = 1
    primary_role: str = "mock-primary"
    fallback_role: str = "mock-fallback"
    complex_escalation_role: str = "TBD"
    summarization_role: str = "mock-summarizer"
    session_ttl_seconds: int = 1800
    max_output_chars: int = 4000

    def __post_init__(self) -> None:
        if self.environment.lower() not in {"automated_test", "development", "staging", "production"}:
            raise ValueError("unsupported runtime environment")
        if not 8 <= self.recent_turn_limit <= 12:
            raise ValueError("recent_turn_limit must be 8..12")
        if self.summary_trigger_turns < 2:
            raise ValueError("summary_trigger_turns must be >= 2")
        if self.max_repair_attempts != 1:
            raise ValueError("Phase 1 permits exactly one repair attempt")
        if not 60 <= self.session_ttl_seconds <= 7200:
            raise ValueError("session_ttl_seconds must be 60..7200")
        if not 500 <= self.max_output_chars <= 8000:
            raise ValueError("max_output_chars must be 500..8000")
        if self.flags.budly_durable_memory_enabled:
            raise ValueError("durable customer memory is prohibited in Slice 1")


@dataclass(frozen=True)
class ProductionSettings:
    """Validated server-only configuration for the Slice 1 HTTP runtime."""

    environment: str
    bind_host: str
    port: int
    shared_secret: str
    model_provider: str
    model_name: str
    model_api_key: str
    knowledge_path: Path
    request_timeout_seconds: float = 15.0
    provider_retry_count: int = 1
    allow_unrestricted_bind: bool = False

    @classmethod
    def from_environment(cls, env: dict[str, str] | None = None) -> "ProductionSettings":
        values = os.environ if env is None else env
        environment = values.get("BUDLY_RUNTIME_ENV", "development").strip().lower()
        allow_unrestricted = values.get("BUDLY_ALLOW_UNRESTRICTED_BIND", "false").strip().lower() in {"1", "true", "yes"}
        settings = cls(
            environment=environment,
            bind_host=values.get("BUDLY_RUNTIME_HOST", "127.0.0.1").strip(),
            port=int(values.get("BUDLY_RUNTIME_PORT", "8791")),
            shared_secret=values.get("BUDLY_RUNTIME_SHARED_SECRET", ""),
            model_provider=values.get("BUDLY_MODEL_PROVIDER", "").strip().lower(),
            model_name=values.get("BUDLY_MODEL_NAME", "").strip(),
            model_api_key=values.get("BUDLY_MODEL_API_KEY", ""),
            knowledge_path=Path(values.get("BUDLY_KNOWLEDGE_PATH", "config")),
            request_timeout_seconds=float(values.get("BUDLY_MODEL_TIMEOUT_SECONDS", "15")),
            provider_retry_count=int(values.get("BUDLY_MODEL_RETRY_COUNT", "1")),
            allow_unrestricted_bind=allow_unrestricted,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.environment not in {"development", "staging", "production"}:
            raise ValueError("BUDLY_RUNTIME_ENV must be development, staging, or production")
        if not 1 <= self.port <= 65535:
            raise ValueError("BUDLY_RUNTIME_PORT is invalid")
        if len(self.shared_secret) < 32:
            raise ValueError("BUDLY_RUNTIME_SHARED_SECRET must contain at least 32 characters")
        if self.model_provider != "openai":
            raise ValueError("Slice 1 supports only the registry-approved openai adapter")
        if not self.model_name or not self.model_api_key:
            raise ValueError("BUDLY_MODEL_NAME and BUDLY_MODEL_API_KEY are required")
        if not 1 <= self.request_timeout_seconds <= 30:
            raise ValueError("BUDLY_MODEL_TIMEOUT_SECONDS must be 1..30")
        if self.provider_retry_count not in {0, 1}:
            raise ValueError("BUDLY_MODEL_RETRY_COUNT must be 0 or 1")
        if not str(self.knowledge_path).strip():
            raise ValueError("BUDLY_KNOWLEDGE_PATH is required")
        if self.environment == "production" and self.bind_host in {"0.0.0.0", "::"} and not self.allow_unrestricted_bind:
            # Direct host public binding prohibited without explicit reverse-proxy / container bridge declaration
            raise ValueError("production runtime cannot bind an unrestricted interface without reverse proxy / container configuration")
