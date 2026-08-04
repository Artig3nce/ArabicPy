"""Core AI provider abstraction: the interface every provider implements.

`ide.py`'s chat panel depends only on the types in this module -- never on
a concrete provider or on the HTTP transport -- so adding a new provider
never requires touching the panel (Dependency Inversion).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ProviderCapabilities:
    streaming: bool = True
    tool_calling: bool = False
    embeddings: bool = False


@dataclass
class ProviderConfig:
    id: str
    type: str
    label: str
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""


class ProviderError(Exception):
    """Base class for provider-layer failures, carrying a user-facing message."""


class ProviderAuthError(ProviderError):
    """The provider rejected the request as unauthenticated/unauthorized."""


class ProviderConnectionError(ProviderError):
    """The provider could not be reached at all."""


class AIRequestHandle(QObject):
    """A single in-flight (or completed) chat request.

    Mirrors the QProcess/QNetworkReply signal idiom already used
    throughout ide.py, so callers connect to signals instead of polling.
    """

    token_received = Signal(str)  # one streamed delta of text
    finished = Signal(str)  # full accumulated answer text
    failed = Signal(str)  # user-facing error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reply = None

    def _bind_reply(self, reply):
        self._reply = reply

    def cancel(self):
        if self._reply is not None:
            self._reply.abort()


class AIProvider(ABC):
    """One configured AI backend. Concrete subclasses only need to implement
    `capabilities` and `send_chat` -- everything else has a sensible default."""

    def __init__(self, config: ProviderConfig, transport=None):
        self.config = config
        if transport is None:
            from .transport import HttpJsonTransport
            transport = HttpJsonTransport()
        self.transport = transport

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    def send_chat(self, messages: list[ChatMessage], *, model: str, stream: bool = False) -> AIRequestHandle:
        ...

    def list_models(self) -> list[str]:
        return []

    def test_connection(self) -> AIRequestHandle:
        """Default: a trivial one-message request, just to check reachability/auth."""
        return self.send_chat(
            [ChatMessage(role="user", content="ping")],
            model=self.config.default_model,
            stream=False,
        )
