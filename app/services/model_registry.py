# app/services/model_registry.py
# Registry of model capabilities and helper utilities
# Add this file to the repo at app/services/model_registry.py

from typing import Dict, Any, List

# Example capability map. Extend with real model IDs and accurate token limits.
MODEL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    # Cerebras examples
    "cerebras/llama-4-maverick-17b-128e-instruct": {
        "family": "cerebras",
        "max_tokens": 131072,
        "streaming": True,
        "recommended_temperature": 0.7,
    },
    "cerebras/llama-3.1-70b": {
        "family": "cerebras",
        "max_tokens": 65536,
        "streaming": False,
        "recommended_temperature": 0.7,
    },

    # NVIDIA / OpenAI-style examples
    "meta/llama-3.1-405b-instruct": {
        "family": "nvidia",
        "max_tokens": 32768,
        "streaming": False,
        "recommended_temperature": 0.7,
    },

    # Fallbacks / smaller models
    "gpt-small": {
        "family": "fallback",
        "max_tokens": 4096,
        "streaming": False,
        "recommended_temperature": 0.7,
    }
}

DEFAULT_MODEL_SEQUENCE: List[str] = [
    # Prefer higher-capacity models first when available
    "cerebras/llama-4-maverick-17b-128e-instruct",
    "meta/llama-3.1-405b-instruct",
    "cerebras/llama-3.1-70b",
    "gpt-small"
]


def get_model_capability(model_id: str) -> Dict[str, Any]:
    return MODEL_CAPABILITIES.get(model_id, {
        "family": "unknown",
        "max_tokens": 4096,
        "streaming": False,
        "recommended_temperature": 0.7
    })


def choose_model(preferred_family: str = "", hints: List[str] = None) -> str:
    """
    Choose best model id according to available capabilities and optional preference.
    - preferred_family: e.g., 'cerebras' to prefer Cerebras models
    - hints: additional model id hints the orchestrator might provide
    """
    hints = hints or []
    # 1) If a hint matches existing model, prefer it
    for h in hints:
        if h in MODEL_CAPABILITIES:
            return h

    # 2) If preferred_family is set, prefer models from that family
    if preferred_family:
        for m in DEFAULT_MODEL_SEQUENCE:
            cap = MODEL_CAPABILITIES.get(m)
            if cap and cap.get("family") == preferred_family:
                return m

    # 3) fallback to default ordering
    for m in DEFAULT_MODEL_SEQUENCE:
        if m in MODEL_CAPABILITIES:
            return m

    # 4) last resort: return first key
    return next(iter(MODEL_CAPABILITIES.keys()))
