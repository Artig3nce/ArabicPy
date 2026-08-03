"""Embedded llama.cpp runtime configuration for AlBaa."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmbeddedModel:
    id: str
    label_ar: str
    hf_model: str
    filename: str
    download_url: str
    download_gb: float


MODELS = {
    "qwen3:1.7b": EmbeddedModel(
        "qwen3:1.7b", "Laptop — Light", "Qwen/Qwen3-1.7B-GGUF:Q8_0",
        "Qwen3-1.7B-Q8_0.gguf",
        "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf?download=true",
        2.2,
    ),
    "qwen3:8b": EmbeddedModel(
        "qwen3:8b", "Desktop — Stronger", "Qwen/Qwen3-8B-GGUF:Q4_K_M",
        "Qwen3-8B-Q4_K_M.gguf",
        "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true",
        5.1,
    ),
}

EMBEDDED_PORT = 11435
EMBEDDED_BASE_URL = f"http://127.0.0.1:{EMBEDDED_PORT}"


def application_dir() -> Path:
    """Directory containing the executable (or repository while developing)."""
    if getattr(sys, "frozen", False):
        # PyInstaller one-folder builds keep bundled binaries under _MEIPASS
        # (normally dist/AlBaa/_internal), not beside AlBaa.exe.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent.parent


def llama_server_path() -> Path | None:
    """Find the AlBaa-bundled llama.cpp server, with a developer fallback."""
    names = ("llama-server.exe", "llama-server")
    roots = (
        application_dir() / "ai-engine",
        application_dir() / "vendor" / "llama.cpp",
    )
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    installed = shutil.which("llama-server")
    return Path(installed) if installed else None


def model_directory() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    directory = (Path(root) if root else Path.home()) / "AlBaa" / "models"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def model_path(model_id: str) -> Path:
    return model_directory() / MODELS[model_id].filename


def server_arguments(model_id: str, local_model: Path | None = None) -> list[str]:
    """Return safe local-only llama-server arguments for a supported model."""
    profile = MODELS[model_id]
    threads = max(2, (os.cpu_count() or 4) - 1)
    model_arguments = ["-m", str(local_model)] if local_model else ["-hf", profile.hf_model]
    return [
        *model_arguments,
        "--host", "127.0.0.1",
        "--port", str(EMBEDDED_PORT),
        "--ctx-size", "4096",
        "--threads", str(threads),
        "--jinja",
    ]
