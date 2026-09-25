"""Tests for configuration management."""
import re
from pathlib import Path

import pytest

from app.config import LLMSettings, Settings, get_settings, reset_settings_cache
from app.settings_loader import MissingSettingError

# Shipped templates live at the package root, next to the venv and alembic dir.
_PACKAGE_ROOT = Path(__file__).parents[2]
_CHUNKING_TEMPLATES = (".env.example", ".env.prod.example")
_ALL_TEMPLATES = (".env.example", ".env.prod.example", ".env.docker.example")


def _template_values(template: str) -> dict[str, str]:
    """Read KEY=value pairs from a shipped template.

    Mirrors ``app.settings_loader._read_env_file`` so the test reads the template
    the way an operator's deployment does: comments and blank lines skipped, key
    and value stripped.
    """
    values: dict[str, str] = {}
    for raw_line in (_PACKAGE_ROOT / template).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def test_grouped_llm_settings() -> None:
    settings = Settings(
        environment="testing",
        llm={
            "provider": "ollama",
            "base_url": "http://ollama:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
            "temperature": 0.3,
            "max_output_tokens": 150,
        },
    )
    assert settings.llm.provider == "ollama"
    assert settings.llm.temperature == 0.3
    assert settings.knowledge.embedding_dimensions == 768


def test_all_url_defaults_are_empty() -> None:
    settings = Settings(_env_file=None, environment="testing")

    assert settings.llm.base_url == ""
    assert settings.database_url == ""
    assert settings.redis_url == ""
    assert settings.keycloak_issuer_url == ""
    assert settings.keycloak_jwks_url == ""
    assert settings.keycloak_admin_url == ""
    assert settings.trace.otel_endpoint is None
    assert settings.cors_origins == ""


def test_production_requires_explicit_values() -> None:
    with pytest.raises(MissingSettingError) as exc_info:
        Settings(_env_file=None, environment="production")

    message = str(exc_info.value)
    for key in (
        "DATABASE_URL",
        "REDIS_URL",
        "CORS_ORIGINS",
        "KEYCLOAK_ISSUER_URL",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_EMBEDDING_MODEL",
    ):
        assert key in message


def test_settings_defaults() -> None:
    """Test that default settings are correctly set when no env overrides exist."""
    settings = Settings()
    assert settings.environment in ("development", "testing")
    assert settings.port == 8000
    assert settings.whisper_model == "base"
    assert settings.enable_radio_effects is True


def test_knowledge_chunking_defaults_are_stable() -> None:
    """Keep shipped knowledge chunking aligned with the ingest contract."""
    settings = Settings(_env_file=None, environment="testing")

    assert settings.knowledge.chunk_size == 1000
    assert settings.knowledge.chunk_overlap == 150


def test_trace_retention_default_matches_adr_contract() -> None:
    """Keep shipped provenance retention aligned with ADR-009."""
    settings = Settings(_env_file=None, environment="testing")

    assert settings.trace.retention_days == 90


def test_external_fallback_default_matches_adr_contract() -> None:
    """Keep the code default for external fallback aligned with ADR-007."""
    settings = Settings(_env_file=None, environment="testing")

    assert settings.llm.allow_external_fallback is False


@pytest.mark.parametrize("template", _CHUNKING_TEMPLATES)
def test_shipped_templates_match_the_chunking_contract(template: str) -> None:
    """A default that silently disagrees with ADR-008 is a defect.

    ``Settings`` defaults are already guarded above, but operators copy these
    templates, and ``KnowledgeIngestor`` writes the effective values to
    ``ingest_events.chunk_size``/``chunk_overlap`` so a chunk can be reproduced.
    A template carrying the wrong overlap silently corrupts that provenance row
    in every environment created from it, so assert the concrete values.
    """
    values = _template_values(template)

    assert int(values["KNOWLEDGE_CHUNK_SIZE"]) == 1000
    assert int(values["KNOWLEDGE_CHUNK_OVERLAP"]) == 150


@pytest.mark.parametrize("template", _CHUNKING_TEMPLATES)
def test_shipped_templates_match_the_trace_retention_contract(template: str) -> None:
    """Keep the template retention at the ADR-009 90-day value."""
    values = _template_values(template)

    assert int(values["TRACE_RETENTION_DAYS"]) == 90


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_shipped_templates_keep_external_fallback_disabled(template: str) -> None:
    """Keep Groq fallback opt-in in every template, per ADR-007.

    Every template declares this key, so the assertion is equality against the
    contract rather than a documented override: no template ships
    ``LLM_ALLOW_EXTERNAL_FALLBACK=true``.
    """
    values = _template_values(template)

    assert values["LLM_ALLOW_EXTERNAL_FALLBACK"].lower() == "false"


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_shipped_templates_document_the_scene_registry_path(template: str) -> None:
    """Every template must expose the custom-scene option, Docker included."""
    assert "SCENES_PATH" in _template_values(template)


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_shipped_templates_carry_no_inline_value_comments(template: str) -> None:
    """An inline comment after a value becomes part of the value.

    ``_read_env_file`` splits on the first ``=`` and keeps the remainder
    verbatim, so ``TTS_LANGUAGE=en  # en or es`` loads as the literal string
    ``"en  # en or es"``. That value reached ``gTTS(lang=...)`` and raised
    ``ValueError: Language not supported``. Document allowed values on their own
    comment line. Only whitespace followed by ``#`` is treated as a comment
    here, so a value may still legitimately contain a ``#``.
    """
    for name, value in _template_values(template).items():
        assert not re.search(r"\s+#", value), (
            f"{template}:{name}={value!r} has an inline comment; the settings "
            f"loader reads it as part of the value"
        )


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_shipped_templates_declare_comments_on_their_own_line(template: str) -> None:
    """Close the class: no line in a shipped template may carry a trailing comment.

    The templates were fixed once (``TTS_LANGUAGE="en  # en or es"`` reached
    ``gTTS`` and raised ``ValueError: Language not supported``), but nothing
    stopped the next one from reappearing.  ``#`` is legal at position 0 and
    nowhere else, so assert the whole file rather than the parsed values: the
    loader skips whole-line comments, which is exactly why an inline one is
    silently read as part of the value.

    This checks the templates we ship, not the loader.  A value in a real
    deployment may legitimately contain a ``#`` — a password or a secret — so
    ``_read_env_file`` must keep the remainder of the line verbatim rather than
    strip a trailing comment for us.
    """
    offenders = [
        f"{number}: {raw_line!r}"
        for number, raw_line in enumerate(
            (_PACKAGE_ROOT / template).read_text(encoding="utf-8").splitlines(), start=1
        )
        if raw_line.strip() and not raw_line.lstrip().startswith("#") and "#" in raw_line
    ]

    assert offenders == [], (
        f"{template} declares an inline comment; put it on its own line so the "
        f"settings loader cannot read it as part of the value"
    )


def _matches_code_default(raw: str, expected: object) -> bool:
    """Compare a raw template string against a code default of any type."""
    if isinstance(expected, bool):
        return raw.lower() == str(expected).lower()
    if isinstance(expected, (int, float)):
        return float(raw) == pytest.approx(float(expected))
    return raw == str(expected)


def test_shipped_templates_and_code_defaults_agree() -> None:
    """Guard the whole class: no template may drift from the code defaults.

    Each key must be declared in every template that configures the subsystem,
    and must equal the code default. This catches a new drift of the kind ADR-009
    catalogues, without asserting anything about values an operator must
    replace with their own (hosts, credentials, database names, model names).

    If a template must legitimately differ from the code default, do not weaken
    this check: drop the key from ``code_defaults`` and add a named test that
    asserts the documented reason for the divergence.
    """
    settings = Settings(_env_file=None, environment="testing")
    code_defaults = {
        "KNOWLEDGE_CHUNK_SIZE": settings.knowledge.chunk_size,
        "KNOWLEDGE_CHUNK_OVERLAP": settings.knowledge.chunk_overlap,
        "KNOWLEDGE_EMBEDDING_DIMENSIONS": settings.knowledge.embedding_dimensions,
        "KNOWLEDGE_TOP_K": settings.knowledge.top_k,
        "KNOWLEDGE_DEFAULT_CHUNK_QUOTA": settings.knowledge.default_chunk_quota,
        "TRACE_RETENTION_DAYS": settings.trace.retention_days,
        "LLM_TEMPERATURE": settings.llm.temperature,
        "LLM_MAX_OUTPUT_TOKENS": settings.llm.max_output_tokens,
        "LLM_TIMEOUT_SECONDS": settings.llm.timeout_seconds,
        "WHISPER_MODEL": settings.whisper_model,
        "TTS_LANGUAGE": settings.tts_language,
        "AUDIO_FORMAT": settings.audio.audio_format,
        "SAMPLE_RATE": settings.audio.sample_rate,
        "ENABLE_RADIO_EFFECTS": settings.audio.enable_radio_effects,
        "NOISE_LEVEL": settings.audio.noise_level,
        "STATIC_LEVEL": settings.audio.static_level,
    }

    for template in _ALL_TEMPLATES:
        values = _template_values(template)
        for name, expected in code_defaults.items():
            if name not in values:
                continue
            assert _matches_code_default(values[name], expected), (
                f"{template}:{name}={values[name]!r} drifted from the code "
                f"default {expected!r}"
            )


def test_cors_origins_list_multiple() -> None:
    """Test CORS origins are correctly parsed from a comma-separated string."""
    settings = Settings(cors_origins="http://localhost:3000,https://example.com")
    origins = settings.cors_origins_list
    assert len(origins) == 2
    assert "http://localhost:3000" in origins
    assert "https://example.com" in origins


def test_cors_origins_list_single() -> None:
    """Test CORS origins with a single entry produces a one-element list."""
    settings = Settings(cors_origins="http://localhost:3000")
    assert settings.cors_origins_list == ["http://localhost:3000"]


def test_cors_origins_list_trims_whitespace() -> None:
    """Test that whitespace around each origin is stripped."""
    settings = Settings(cors_origins=" http://localhost:3000 , https://example.com ")
    origins = settings.cors_origins_list
    assert origins == ["http://localhost:3000", "https://example.com"]


def test_cors_origins_wildcard_blocked_in_production() -> None:
    """Test wildcard CORS is blocked in production."""
    settings = Settings(
        environment="production",
        database_url="postgresql+asyncpg://x/y",
        redis_url="redis://x",
        cors_origins="*",
        keycloak_issuer_url="https://auth.example/realms/horus",
        llm={
            "provider": "ollama",
            "base_url": "http://llm:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
        },
    )
    with pytest.raises(ValueError, match="Wildcard CORS origin"):
        _ = settings.cors_origins_list


def test_settings_custom_values() -> None:
    """Test that custom values can be passed and override defaults."""
    settings = Settings(
        environment="testing",
        port=9000,
        ollama_llm_model="llama3:8b",
        enable_radio_effects=False,
        noise_level=0.05,
    )
    assert settings.environment == "testing"
    assert settings.port == 9000
    assert settings.ollama_llm_model == "llama3:8b"
    assert settings.enable_radio_effects is False
    assert settings.noise_level == pytest.approx(0.05)


def test_llm_host_values_require_configuration() -> None:
    """LLM host and model values must be explicitly configured."""
    settings = Settings(_env_file=None, environment="testing")
    assert settings.ollama_base_url == ""
    assert settings.ollama_llm_model == ""


def test_audio_processing_defaults() -> None:
    """Test audio processing settings have sensible defaults."""
    settings = Settings()
    assert settings.sample_rate == 16000
    assert settings.chunk_size == 1024
    assert settings.audio_format == "wav"


def test_issuer_aliases_are_accepted_only_outside_production() -> None:
    common = {
        "keycloak_issuer_url": "https://auth.example/realms/horus",
        "keycloak_issuer_aliases": "https://alias.example/realms/horus",
    }

    development = Settings(environment="development", **common)
    production = Settings(
        environment="production",
        database_url="postgresql+asyncpg://x/y",
        redis_url="redis://x",
        cors_origins="https://app.example",
        llm={
            "provider": "ollama",
            "base_url": "http://llm:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
        },
        **common,
    )

    assert "https://alias.example/realms/horus" in development.accepted_keycloak_issuers
    assert production.accepted_keycloak_issuers == {
        "https://auth.example/realms/horus"
    }


def test_get_settings_reads_grouped_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setenv("KNOWLEDGE_TOP_K", "9")
    reset_settings_cache()

    try:
        settings = get_settings()
        assert settings.llm.provider == "ollama"
        assert settings.llm.base_url == "https://llm.example/v1"
        assert settings.llm.model == "test-model"
        assert settings.llm.embedding_model == "test-embedding-model"
        assert settings.knowledge.top_k == 9
    finally:
        reset_settings_cache()


def test_legacy_name_shadows_the_grouped_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """``OLLAMA_BASE_URL`` must win when both names are set — CI relies on it.

    The rule is stated in four places (``settings_loader._LEGACY_ENV``,
    ``config._LEGACY_GROUP_FIELDS``, ``docs/development.md`` and the architecture
    index) and, until now, was asserted nowhere: the only in-repo mention under
    ``tests/`` was the env-isolation list.  ``.github/workflows/ci.yml`` sets both
    ``LLM_BASE_URL`` and ``OLLAMA_BASE_URL`` and relies on the shadowing, so an
    inverted precedence would change CI's LLM base URL silently and nothing would
    fail.

    Two surfaces can set this value — the environment loader and the ``Settings``
    keyword — and they are two implementations of one rule, so assert the concrete
    value *and* that the two agree, as ADR-009's standing rule requires.
    """
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LLM_BASE_URL", "http://grouped.example:11434")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://legacy.example:11434")
    monkeypatch.setenv("LLM_MODEL", "grouped-model")
    monkeypatch.setenv("OLLAMA_LLM_MODEL", "legacy-model")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "grouped-embedding")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "legacy-embedding")
    reset_settings_cache()

    try:
        settings = get_settings()
    finally:
        reset_settings_cache()

    assert settings.llm.base_url == "http://legacy.example:11434"
    assert settings.llm.model == "legacy-model"
    assert settings.llm.embedding_model == "legacy-embedding"

    keyword = Settings(
        _env_file=None,
        environment="testing",
        llm={
            "base_url": "http://grouped.example:11434",
            "model": "grouped-model",
            "embedding_model": "grouped-embedding",
        },
        ollama_base_url="http://legacy.example:11434",
        ollama_llm_model="legacy-model",
        ollama_embedding_model="legacy-embedding",
    )
    assert (keyword.llm.base_url, keyword.llm.model, keyword.llm.embedding_model) == (
        settings.llm.base_url,
        settings.llm.model,
        settings.llm.embedding_model,
    )


def test_a_constructed_group_plus_a_legacy_keyword_is_refused_loudly() -> None:
    """A legacy keyword must never be silently dropped by a constructed group.

    ``Settings.__init__`` merges a legacy keyword into its group, but only when
    the group is absent or a dict.  Handed a constructed ``LLMSettings`` neither
    branch fires, the legacy value disappears, and the caller silently receives
    the dataclass defaults — a wrong configuration with no signal, which is the
    class of defect this branch exists to close.  Four lines of refusal cost more
    than a deployment that quietly talks to the wrong endpoint.
    """
    with pytest.raises(ValueError) as exc_info:
        Settings(
            _env_file=None,
            environment="testing",
            llm=LLMSettings(provider="ollama", base_url="http://grouped.example:11434"),
            ollama_base_url="http://legacy.example:11434",
        )

    message = str(exc_info.value)
    assert "llm" in message
    assert "ollama_base_url" in message
    assert "dict" in message
