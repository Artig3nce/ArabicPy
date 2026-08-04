"""OpenAI Chat Completions wire format.

One class, parametrized only by base_url/api_key, covers OpenAI,
OpenRouter, LM Studio, and any Custom OpenAI-compatible endpoint.
"""

from .base import AIProvider, ProviderCapabilities


class OpenAICompatibleProvider(AIProvider):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True)

    def send_chat(self, messages, *, model, stream=False):
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        body = self._build_body(messages, model, stream)
        return self.transport.post(
            url, headers, body, stream=stream, sse=True,
            extract_delta=_extract_delta, extract_final=_extract_final,
        )

    @staticmethod
    def _build_body(messages, model, stream):
        return {
            "model": model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": stream,
        }


def _extract_delta(chunk):
    choices = chunk.get("choices") or []
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content") or None


def _extract_final(payload):
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()
