"""Persistent background AI host for الباء."""

import os
import secrets
import time

from arabicpy.ai_server import AlBaaAIServer


def token_path():
    root = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AlBaa")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "ai_server_token.txt")


def load_token():
    path = token_path()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as stream:
            token = stream.read().strip()
            if token:
                return token
    token = secrets.token_urlsafe(24)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(token)
    return token


def main():
    server = AlBaaAIServer(load_token())
    server.start()
    try:
        while server.httpd is not None:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
