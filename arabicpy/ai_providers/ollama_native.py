"""Ollama's native /api/generate endpoint.

Kept as its own provider rather than folded into OpenAICompatibleProvider:
arabicpy/ai.py and arabicpy/ai_server.py both rely on the Qwen3-specific
"think": False field (native-endpoint-only) to keep <think>...</think>
reasoning blocks out of the visible answer -- the shipped default models
are qwen3:8b/qwen3:1.7b. A user who specifically wants Ollama's
OpenAI-compatible surface can already get it via "Custom OpenAI-compatible"
pointed at http://127.0.0.1:11434/v1.
"""

from .base import AIProvider, ProviderCapabilities

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaNativeProvider(AIProvider):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True)

    def send_chat(self, messages, *, model, stream=False):
        base_url = (self.config.base_url or DEFAULT_BASE_URL).rstrip("/")
        url = f"{base_url}/api/generate"
        body = self._build_body(messages, model, stream)
        return self.transport.post(
            url, {}, body, stream=stream, sse=False,
            extract_delta=_extract_delta, extract_final=_extract_final,
        )

    @staticmethod
    def _build_body(messages, model, stream):
        return {
            "model": model,
            "prompt": _collapse_prompt(messages),
            "stream": stream,
            "think": False,
        }


def _collapse_prompt(messages):
    return "\n\n".join(message.content for message in messages)


def _extract_delta(chunk):
    return chunk.get("response") or None


def _extract_final(payload):
    return (payload.get("response") or "").strip()
