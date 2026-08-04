"""Provider-type registry -- the Open/Closed extension point.

Adding a new OpenAI-compatible service needs only one new entry here.
Adding a genuinely different wire protocol needs one small AIProvider
subclass plus one entry. Nothing outside this module (ide.py included)
needs to change either way.
"""

from dataclasses import dataclass
from typing import Callable

from .albaa_remote import AlBaaRemoteHostProvider
from .anthropic import AnthropicProvider
from .base import AIProvider, ProviderConfig, ProviderError
from .ollama_native import OllamaNativeProvider
from .openai_compatible import OpenAICompatibleProvider


@dataclass(frozen=True)
class ProviderTypeSpec:
    id: str
    display_name: str
    default_base_url: str
    requires_api_key: bool
    factory: Callable[[ProviderConfig, object], AIProvider]
    example_models: tuple = ()


PROVIDER_TYPES: dict[str, ProviderTypeSpec] = {
    "openai": ProviderTypeSpec(
        "openai", "OpenAI", "https://api.openai.com/v1", True,
        lambda config, transport: OpenAICompatibleProvider(config, transport),
        ("gpt-4o", "gpt-4o-mini"),
    ),
    "anthropic": ProviderTypeSpec(
        "anthropic", "Anthropic (Claude)", "https://api.anthropic.com", True,
        lambda config, transport: AnthropicProvider(config, transport),
        ("claude-opus-4-5", "claude-sonnet-4-5"),
    ),
    "ollama": ProviderTypeSpec(
        "ollama", "Ollama", "http://127.0.0.1:11434", False,
        lambda config, transport: OllamaNativeProvider(config, transport),
        (),
    ),
    "lmstudio": ProviderTypeSpec(
        "lmstudio", "LM Studio", "http://127.0.0.1:1234/v1", False,
        lambda config, transport: OpenAICompatibleProvider(config, transport),
        (),
    ),
    "openrouter": ProviderTypeSpec(
        "openrouter", "OpenRouter", "https://openrouter.ai/api/v1", True,
        lambda config, transport: OpenAICompatibleProvider(config, transport),
        ("openrouter/auto",),
    ),
    "custom_openai": ProviderTypeSpec(
        "custom_openai", "Custom OpenAI-compatible", "", True,
        lambda config, transport: OpenAICompatibleProvider(config, transport),
        (),
    ),
    "albaa_remote": ProviderTypeSpec(
        "albaa_remote", "Al-Baa Remote Computer", "", True,
        lambda config, transport: AlBaaRemoteHostProvider(config, transport),
        (),
    ),
}


def list_provider_types() -> list[ProviderTypeSpec]:
    return list(PROVIDER_TYPES.values())


def create_provider(config: ProviderConfig, transport=None) -> AIProvider:
    spec = PROVIDER_TYPES.get(config.type)
    if spec is None:
        raise ProviderError(f"Unknown provider type: {config.type!r}")
    if not config.base_url:
        config.base_url = spec.default_base_url
    return spec.factory(config, transport)
