import os
import sys
import tempfile
import pytest

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server import (
    _detect_geyser,
    _verify_pinggy_binary,
    PINGGY_CLI_ASSETS,
    AppState,
    state,
)


def test_detect_geyser_empty_server():
    class DummyHandler:
        def __init__(self, path):
            self.server_path = path

    with tempfile.TemporaryDirectory() as temp_dir:
        class DummyState:
            server_handler = DummyHandler(temp_dir)

        info = _detect_geyser(DummyState())
        assert info["installed"] is False
        assert info["bedrock_port"] == 19132
        assert info["floodgate_installed"] is False


def test_detect_geyser_with_plugin_and_config():
    class DummyHandler:
        def __init__(self, path):
            self.server_path = path

    with tempfile.TemporaryDirectory() as temp_dir:
        plugins_dir = os.path.join(temp_dir, "plugins")
        os.makedirs(plugins_dir, exist_ok=True)
        # Create a dummy geyser jar
        with open(os.path.join(plugins_dir, "Geyser-Spigot.jar"), "w") as f:
            f.write("dummy jar")
        # Create a dummy floodgate jar
        with open(os.path.join(plugins_dir, "floodgate-spigot.jar"), "w") as f:
            f.write("dummy jar")

        geyser_conf_dir = os.path.join(plugins_dir, "Geyser-Spigot")
        os.makedirs(geyser_conf_dir, exist_ok=True)
        with open(os.path.join(geyser_conf_dir, "config.yml"), "w") as f:
            f.write("""
bedrock:
  address: 0.0.0.0
  port: 19135
  clone-remote-port: false
""")

        class DummyState:
            server_handler = DummyHandler(temp_dir)

        info = _detect_geyser(DummyState())
        assert info["installed"] is True
        assert info["floodgate_installed"] is True
        assert info["bedrock_port"] == 19135
        assert info["type"] == "plugin"


def test_pinggy_assets_are_pinned():
    assert PINGGY_CLI_ASSETS, "expected pinned Pinggy assets"
    for name, (size, sha256) in PINGGY_CLI_ASSETS.items():
        assert size > 50 * 1024 * 1024, name
        assert len(sha256) == 64, name


def test_verify_pinggy_binary_checks_size_and_hash(tmp_path):
    import hashlib

    payload = b"fake-pinggy-binary"
    path = tmp_path / "pinggy"
    path.write_bytes(payload)
    good_hash = hashlib.sha256(payload).hexdigest()

    assert _verify_pinggy_binary(str(path), len(payload), good_hash) is True
    assert _verify_pinggy_binary(str(path), len(payload), "0" * 64) is False
    assert _verify_pinggy_binary(str(path), len(payload) + 1, good_hash) is False
    assert _verify_pinggy_binary(str(tmp_path / "missing"), 0, good_hash) is False
