"""Persistence for configured AI providers.

A JSON file under %LOCALAPPDATA%\\AlBaa, mirroring the existing
chat_history.json convention already used elsewhere in ide.py. Also owns
the one-time migration from the pre-provider-system remote_ai_url /
remote_ai_token / ai_model QSettings keys.
"""

import json
import os
import tempfile
import uuid

from .base import ProviderConfig

FILENAME = "ai_providers.json"


def _app_data_dir():
    root = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    directory = os.path.join(root, "AlBaa")
    os.makedirs(directory, exist_ok=True)
    return directory


class ProviderStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(_app_data_dir(), FILENAME)

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def load(self):
        """Return (providers, active_id). Missing/unreadable file -> ([], None)."""
        if not self.exists():
            return [], None
        try:
            with open(self.path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return [], None
        providers = [ProviderConfig(**entry) for entry in data.get("providers", [])]
        return providers, data.get("active_id")

    def save(self, providers, active_id):
        data = {
            "providers": [vars(config) for config in providers],
            "active_id": active_id,
        }
        with open(self.path, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)

    def migrate_legacy_settings(self, remote_ai_url, remote_ai_token, ai_model, default_model):
        """One-time migration from the old QSettings-based config. Only call
        this when `exists()` is False. Persists and returns (providers, active_id)."""
        ollama_config = ProviderConfig(
            id=str(uuid.uuid4()), type="ollama", label="Ollama",
            default_model=ai_model or default_model,
        )
        providers = [ollama_config]
        active_id = ollama_config.id
        if remote_ai_url and remote_ai_token:
            remote_config = ProviderConfig(
                id=str(uuid.uuid4()), type="albaa_remote", label="Al-Baa Remote Computer",
                base_url=remote_ai_url, api_key=remote_ai_token,
            )
            providers.append(remote_config)
            active_id = remote_config.id
        self.save(providers, active_id)
        return providers, active_id
