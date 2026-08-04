"""Al-Baa's own proprietary bridge protocol -- connects to another Al-Baa
Code install's "AI Network" LAN/Tailscale bridge (arabicpy/ai_server.py,
untouched by this redesign). Preserves the exact wire shape the old
configure_remote_ai() flow used, so existing "connect to a remote Al-Baa
computer" setups keep working after migration. Not one of the 6 explicitly
requested provider types, but dropping it would break an existing feature --
and it doubles as proof that even a fully proprietary protocol is cheap to
add behind the same AIProvider interface.
"""

from .base import AIProvider, ProviderCapabilities


class AlBaaRemoteHostProvider(AIProvider):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=False)

    def send_chat(self, messages, *, model, stream=False):
        url = f"{self.config.base_url.rstrip('/')}/generate"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        body = {"question": _collapse_prompt(messages)}
        return self.transport.post(url, headers, body, stream=False, extract_final=_extract_final)


def _collapse_prompt(messages):
    return "\n\n".join(message.content for message in messages)


def _extract_final(payload):
    return (payload.get("answer") or "").strip()
