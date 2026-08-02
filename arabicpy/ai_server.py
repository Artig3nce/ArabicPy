"""Authenticated LAN bridge between AlBaa Android apps and local Ollama."""

import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .ai import DEFAULT_MODEL, SYSTEM_PROMPT
from .rag import context_for


def local_ipv4():
    """Return the LAN address selected by the operating system."""
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(("8.8.8.8", 80))
        return connection.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        connection.close()


class AlBaaAIServer:
    def __init__(self, token, port=8765, model=DEFAULT_MODEL):
        self.token = token
        self.port = port
        self.model = model
        self.httpd = None
        self.thread = None

    @property
    def address(self):
        return f"http://{local_ipv4()}:{self.port}"

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def send_json(self, status, value):
                body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    self.send_json(200, {"status": "ok", "model": owner.model})
                else:
                    self.send_json(404, {"error": "not_found"})

            def do_POST(self):
                if self.path == "/shutdown":
                    if self.headers.get("Authorization") != f"Bearer {owner.token}":
                        self.send_json(401, {"error": "unauthorized"})
                        return
                    self.send_json(200, {"status": "stopping"})
                    threading.Thread(target=owner.stop, daemon=True).start()
                    return
                if self.path != "/generate":
                    self.send_json(404, {"error": "not_found"})
                    return
                if self.headers.get("Authorization") != f"Bearer {owner.token}":
                    self.send_json(401, {"error": "unauthorized"})
                    return
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 100_000)
                    request_data = json.loads(self.rfile.read(length).decode("utf-8"))
                    question = str(request_data.get("question", "")).strip()
                    if not question:
                        self.send_json(400, {"error": "empty_question"})
                        return
                    payload = json.dumps({
                        "model": owner.model,
                        "prompt": (
                            f"{SYSTEM_PROMPT}\n\n"
                            f"معرفة موثقة مسترجعة من قاعدة الباء:\n{context_for(question)}\n\n"
                            f"سؤال مستخدم تطبيق الهاتف:\n{question}"
                        ),
                        "stream": False,
                        "think": False,
                    }).encode("utf-8")
                    ollama_request = urllib.request.Request(
                        "http://127.0.0.1:11434/api/generate", data=payload,
                        headers={"Content-Type": "application/json"}, method="POST",
                    )
                    with urllib.request.urlopen(ollama_request, timeout=300) as response:
                        answer = json.loads(response.read().decode("utf-8")).get("response", "")
                    self.send_json(200, {"answer": answer.strip()})
                except (ValueError, json.JSONDecodeError):
                    self.send_json(400, {"error": "invalid_request"})
                except (urllib.error.URLError, TimeoutError, OSError):
                    self.send_json(503, {"error": "ollama_unavailable"})

            def log_message(self, _format, *_args):
                return

        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.thread = None
