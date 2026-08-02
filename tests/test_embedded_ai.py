from arabicpy.embedded_ai import MODELS, server_arguments


def test_embedded_models_have_distinct_device_profiles():
    assert set(MODELS) == {"qwen3:1.7b", "qwen3:8b"}
    assert MODELS["qwen3:1.7b"].download_gb < MODELS["qwen3:8b"].download_gb


def test_embedded_server_is_local_only():
    arguments = server_arguments("qwen3:1.7b")
    host_index = arguments.index("--host")
    assert arguments[host_index + 1] == "127.0.0.1"
    assert "Qwen/Qwen3-1.7B-GGUF:Q8_0" in arguments


def test_embedded_server_uses_downloaded_model_path(tmp_path):
    model = tmp_path / "model.gguf"
    arguments = server_arguments("qwen3:1.7b", model)
    assert arguments[:2] == ["-m", str(model)]
