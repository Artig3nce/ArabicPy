"""Anthropic's Messages API -- a genuinely different wire shape (system
prompt is a top-level field, not a message; auth is x-api-key, not Bearer)."""

from .base import AIProvider, ProviderCapabilities

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(AIProvider):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True)

    def send_chat(self, messages, *, model, stream=False):
        url = f"{self.config.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        body = self._build_body(messages, model, stream)
        return self.transport.post(
            url, headers, body, stream=stream, sse=True,
            extract_delta=_extract_delta, extract_final=_extract_final,
        )

    @staticmethod
    def _build_body(messages, model, stream):
        system_text = "\n\n".join(message.content for message in messages if message.role == "system")
        turns = [
            {"role": message.role, "content": message.content}
            for message in messages if message.role != "system"
        ]
        body = {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": turns,
            "stream": stream,
        }
        if system_text:
            body["system"] = system_text
        return body


def _extract_delta(chunk):
    if chunk.get("type") != "content_block_delta":
        return None
    return chunk.get("delta", {}).get("text") or None


def _extract_final(payload):
    content = payload.get("content") or []
    if not content:
        return ""
    return (content[0].get("text") or "").strip()
