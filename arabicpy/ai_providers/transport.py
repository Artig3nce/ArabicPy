"""Shared QNetworkAccessManager-based HTTP transport for AI providers.

Centralizes network I/O, SSE/NDJSON streaming framing, and error
classification in one place so provider classes only need to build a
URL/headers/body and supply pure functions that extract text from an
already-parsed JSON chunk -- no provider ever touches Qt networking
directly. This replaces the old curl.exe/QProcess transport, which was
Windows-only and never actually streamed.
"""

import json

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from .base import AIRequestHandle, ProviderAuthError, ProviderConnectionError


class HttpJsonTransport:
    """Owns one shared QNetworkAccessManager for all requests it sends."""

    def __init__(self, parent=None):
        self._manager = QNetworkAccessManager(parent)

    def post(self, url, headers, body, *, stream=False, sse=True, extract_delta=None, extract_final=None) -> AIRequestHandle:
        """POST `body` as JSON to `url`.

        Non-streaming: the full JSON response is parsed once `extract_final(payload) -> str`
        is called against it. Streaming: each line of the response is parsed as JSON
        (after stripping an `"data: "` SSE prefix when `sse=True`, or as raw
        newline-delimited JSON when `sse=False`) and passed to
        `extract_delta(chunk) -> str | None`; non-empty deltas are emitted live via
        `token_received` and accumulated into the final `finished` text.
        """
        handle = AIRequestHandle()
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        for name, value in headers.items():
            request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))

        reply = self._manager.post(request, json.dumps(body, ensure_ascii=False).encode("utf-8"))
        handle._bind_reply(reply)

        buffer = bytearray()
        line_buffer = bytearray()
        accumulated = []

        def on_ready_read():
            chunk = bytes(reply.readAll())
            if not stream:
                buffer.extend(chunk)
                return
            line_buffer.extend(chunk)
            while b"\n" in line_buffer:
                line, _, rest = bytes(line_buffer).partition(b"\n")
                del line_buffer[:]
                line_buffer.extend(rest)
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                if sse:
                    if not text.startswith("data:"):
                        continue
                    text = text[len("data:"):].strip()
                    if text == "[DONE]":
                        continue
                try:
                    chunk_payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                delta = extract_delta(chunk_payload) if extract_delta else None
                if delta:
                    accumulated.append(delta)
                    handle.token_received.emit(delta)

        def on_finished():
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            error = reply.error()
            if error == QNetworkReply.NetworkError.OperationCanceledError:
                # Still emit `finished` (Qt itself fires this signal after abort()) so
                # the caller's busy-state cleanup and queue-advance always run, exactly
                # like the old QProcess.kill() path used to via its own `finished` signal.
                handle.finished.emit("".join(accumulated))
                reply.deleteLater()
                return
            if error != QNetworkReply.NetworkError.NoError:
                message = reply.errorString()
                if status in (401, 403):
                    handle.failed.emit(str(ProviderAuthError(message)))
                else:
                    handle.failed.emit(str(ProviderConnectionError(message)))
                reply.deleteLater()
                return
            if stream:
                handle.finished.emit("".join(accumulated))
                reply.deleteLater()
                return
            try:
                payload = json.loads(bytes(buffer))
            except json.JSONDecodeError:
                handle.failed.emit("The server returned an invalid response.")
                reply.deleteLater()
                return
            try:
                text = extract_final(payload) if extract_final else ""
            except (KeyError, IndexError, TypeError):
                text = ""
            if not text:
                handle.failed.emit("The server returned an empty or unexpected response.")
                reply.deleteLater()
                return
            handle.finished.emit(text)
            reply.deleteLater()

        reply.readyRead.connect(on_ready_read)
        reply.finished.connect(on_finished)
        return handle
