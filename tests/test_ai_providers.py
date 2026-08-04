import pytest

from arabicpy.ai_providers import ChatMessage, ProviderConfig, ProviderError, ProviderStore, create_provider
from arabicpy.ai_providers.registry import PROVIDER_TYPES
from arabicpy.ai_providers.ollama_native import OllamaNativeProvider
from arabicpy.ai_providers.openai_compatible import OpenAICompatibleProvider
from arabicpy.ai_providers.anthropic import AnthropicProvider
from arabicpy.ai_providers.albaa_remote import AlBaaRemoteHostProvider
from arabicpy.ai_providers import openai_compatible, anthropic as anthropic_module, ollama_native, albaa_remote


# -- registry --

def test_registry_has_all_seven_types():
    assert set(PROVIDER_TYPES) == {
        "openai", "anthropic", "ollama", "lmstudio", "openrouter", "custom_openai", "albaa_remote",
    }


def test_create_provider_maps_ollama_to_native_class():
    config = ProviderConfig(id="x", type="ollama", label="Ollama")
    provider = create_provider(config)
    assert isinstance(provider, OllamaNativeProvider)


@pytest.mark.parametrize("type_id, expected_class", [
    ("openai", OpenAICompatibleProvider),
    ("lmstudio", OpenAICompatibleProvider),
    ("openrouter", OpenAICompatibleProvider),
    ("custom_openai", OpenAICompatibleProvider),
    ("anthropic", AnthropicProvider),
    ("albaa_remote", AlBaaRemoteHostProvider),
])
def test_create_provider_maps_type_to_expected_class(type_id, expected_class):
    config = ProviderConfig(id="x", type=type_id, label="Test", base_url="http://example.test")
    provider = create_provider(config)
    assert isinstance(provider, expected_class)


def test_create_provider_unknown_type_raises():
    config = ProviderConfig(id="x", type="not-a-real-type", label="Test")
    with pytest.raises(ProviderError):
        create_provider(config)


def test_create_provider_fills_default_base_url_when_empty():
    config = ProviderConfig(id="x", type="openai", label="Test")
    provider = create_provider(config)
    assert provider.config.base_url == PROVIDER_TYPES["openai"].default_base_url


def test_create_provider_keeps_explicit_base_url():
    config = ProviderConfig(id="x", type="openai", label="Test", base_url="https://my-proxy.example/v1")
    provider = create_provider(config)
    assert provider.config.base_url == "https://my-proxy.example/v1"


# -- store --

def test_provider_store_round_trip(tmp_path):
    store = ProviderStore(path=str(tmp_path / "ai_providers.json"))
    providers = [
        ProviderConfig(id="a", type="openai", label="My OpenAI", api_key="sk-1", default_model="gpt-4o"),
        ProviderConfig(id="b", type="ollama", label="Home Ollama"),
    ]
    store.save(providers, "a")

    loaded_providers, active_id = store.load()
    assert active_id == "a"
    assert [config.id for config in loaded_providers] == ["a", "b"]
    assert loaded_providers[0].api_key == "sk-1"
    assert loaded_providers[0].default_model == "gpt-4o"


def test_provider_store_missing_file_returns_empty(tmp_path):
    store = ProviderStore(path=str(tmp_path / "does_not_exist.json"))
    providers, active_id = store.load()
    assert providers == []
    assert active_id is None


def test_migrate_legacy_settings_with_remote_configured(tmp_path):
    store = ProviderStore(path=str(tmp_path / "ai_providers.json"))
    providers, active_id = store.migrate_legacy_settings(
        remote_ai_url="http://my-desktop:8765", remote_ai_token="secret-token",
        ai_model="qwen3:8b", default_model="qwen3:1.7b",
    )
    assert len(providers) == 2
    assert providers[0].type == "ollama"
    assert providers[0].default_model == "qwen3:8b"
    assert providers[1].type == "albaa_remote"
    assert providers[1].base_url == "http://my-desktop:8765"
    assert providers[1].api_key == "secret-token"
    assert active_id == providers[1].id

    # Persisted correctly.
    reloaded_providers, reloaded_active_id = store.load()
    assert [config.id for config in reloaded_providers] == [config.id for config in providers]
    assert reloaded_active_id == active_id


def test_migrate_legacy_settings_without_remote(tmp_path):
    store = ProviderStore(path=str(tmp_path / "ai_providers.json"))
    providers, active_id = store.migrate_legacy_settings(
        remote_ai_url="", remote_ai_token="", ai_model="", default_model="qwen3:1.7b",
    )
    assert len(providers) == 1
    assert providers[0].type == "ollama"
    assert providers[0].default_model == "qwen3:1.7b"
    assert active_id == providers[0].id


# -- OpenAICompatibleProvider (OpenAI / OpenRouter / LM Studio / Custom) --

def test_openai_compatible_build_body():
    messages = [ChatMessage("system", "Be helpful."), ChatMessage("user", "Hi")]
    body = OpenAICompatibleProvider._build_body(messages, "gpt-4o-mini", True)
    assert body == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": "Be helpful."}, {"role": "user", "content": "Hi"}],
        "stream": True,
    }


def test_openai_compatible_extract_delta_and_final():
    assert openai_compatible._extract_delta({"choices": [{"delta": {"content": "Hel"}}]}) == "Hel"
    assert openai_compatible._extract_delta({"choices": []}) is None
    assert openai_compatible._extract_final(
        {"choices": [{"message": {"content": " Hello there "}}]}
    ) == "Hello there"


# -- AnthropicProvider --

def test_anthropic_build_body_extracts_system_message():
    messages = [ChatMessage("system", "Be helpful."), ChatMessage("user", "Hi")]
    body = AnthropicProvider._build_body(messages, "claude-sonnet-4-5", False)
    assert body["system"] == "Be helpful."
    assert body["messages"] == [{"role": "user", "content": "Hi"}]
    assert body["max_tokens"] == 4096


def test_anthropic_build_body_without_system_message():
    body = AnthropicProvider._build_body([ChatMessage("user", "Hi")], "claude-sonnet-4-5", False)
    assert "system" not in body


def test_anthropic_extract_delta_and_final():
    assert anthropic_module._extract_delta(
        {"type": "content_block_delta", "delta": {"text": "Hel"}}
    ) == "Hel"
    assert anthropic_module._extract_delta({"type": "message_start"}) is None
    assert anthropic_module._extract_final({"content": [{"text": " Hello "}]}) == "Hello"


# -- OllamaNativeProvider --

def test_ollama_native_build_body_collapses_prompt():
    messages = [ChatMessage("system", "Be helpful."), ChatMessage("user", "Hi")]
    body = OllamaNativeProvider._build_body(messages, "qwen3:8b", False)
    assert body["prompt"] == "Be helpful.\n\nHi"
    assert body["think"] is False
    assert body["model"] == "qwen3:8b"


def test_ollama_native_extract_delta_and_final():
    assert ollama_native._extract_delta({"response": "Hel"}) == "Hel"
    assert ollama_native._extract_delta({"response": "", "done": True}) is None
    assert ollama_native._extract_final({"response": " Hello "}) == "Hello"


# -- AlBaaRemoteHostProvider --

def test_albaa_remote_collapses_prompt_and_extracts_answer():
    messages = [ChatMessage("system", "Be helpful."), ChatMessage("user", "Hi")]
    assert albaa_remote._collapse_prompt(messages) == "Be helpful.\n\nHi"
    assert albaa_remote._extract_final({"answer": " Hello "}) == "Hello"
