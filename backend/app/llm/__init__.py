"""Provider-independent language-model module."""

from app.llm.routing import FallbackLLM, build_llm
from app.llm.scene_constraints import SceneConstraints, merge
from app.llm.types import (
    EmbeddingResult,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    LLMModule,
    LLMTransientError,
    LLMUnavailableError,
    LLMUsageError,
)

__all__ = [
    "EmbeddingResult",
    "FallbackLLM",
    "GenerationPurpose",
    "GenerationRequest",
    "GenerationResult",
    "LLMModule",
    "LLMTransientError",
    "LLMUnavailableError",
    "LLMUsageError",
    "SceneConstraints",
    "build_llm",
    "merge",
]
