"""Versioned prompt assets shared by every AI task."""

from app.modules.prompts.registry import (
    ANALYSIS_SYSTEM_PROMPT,
    REVIEW_GENERATION_SYSTEM_PROMPT,
    SCRIPT_GENERATION_SYSTEM_PROMPT,
    PromptAsset,
    resolve_prompt_asset,
)

__all__ = [
    "ANALYSIS_SYSTEM_PROMPT",
    "REVIEW_GENERATION_SYSTEM_PROMPT",
    "SCRIPT_GENERATION_SYSTEM_PROMPT",
    "PromptAsset",
    "resolve_prompt_asset",
]
