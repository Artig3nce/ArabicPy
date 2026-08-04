"""Al-Baa Code's modular AI provider system.

Every provider implements `AIProvider` (see base.py) and is looked up
through `registry.py`'s type registry -- the Open/Closed extension point
for adding new providers without changing any calling code.
"""

from .base import (
    AIProvider, AIRequestHandle, ChatMessage, ProviderAuthError,
    ProviderCapabilities, ProviderConfig, ProviderConnectionError, ProviderError,
)
from .registry import PROVIDER_TYPES, ProviderTypeSpec, create_provider, list_provider_types
from .store import ProviderStore
from .transport import HttpJsonTransport

__all__ = [
    "AIProvider", "AIRequestHandle", "ChatMessage", "ProviderAuthError",
    "ProviderCapabilities", "ProviderConfig", "ProviderConnectionError", "ProviderError",
    "PROVIDER_TYPES", "ProviderTypeSpec", "create_provider", "list_provider_types",
    "ProviderStore", "HttpJsonTransport",
]
