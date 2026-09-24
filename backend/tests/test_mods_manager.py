import io
import json
import os
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import utils.api_client as api_client  # noqa: E402
from utils.mods_manager import ModsManager  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.hits.append(self.path)
        rule = getattr(self.server, "routes", {}).get(self.path)
        if rule is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = rule
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.routes = {}
    srv.hits = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(api_client.time, "sleep", lambda s: None)


def _url(server, path):
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def _mrpack(file_indexes):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("modrinth.index.json", json.dumps({"files": file_indexes}))
    buf.seek(0)
    return buf.read()


def _serve(server, path, data):
    server.routes[path] = data


def test_modpack_success_installs_files(server, tmp_path, no_sleep):
    server_path = tmp_path / "server"
    server_path.mkdir()

    _serve(server, "/good.jar", b"good-jar-bytes")
    _serve(server, "/cfg.toml", b"config-data")

    pack_url = _url(server, "/pack.mrpack")
    server.routes["/pack.mrpack"] = _mrpack(
        [
            {"path": "mods/good.jar", "downloads": [_url(server, "/good.jar")]},
            {"path": "config/extra.toml", "downloads": [_url(server, "/cfg.toml")]},
        ]
    )

    result = ModsManager().install_modpack(pack_url, "pack.mrpack", str(server_path))

    assert result.get("success") is True
    assert (server_path / "mods" / "good.jar").read_bytes() == b"good-jar-bytes"
    assert (server_path / "config" / "extra.toml").read_text() == "config-data"
    assert not (server_path / "temp_modpack").exists()


def test_modpack_path_traversal_rejected_and_rolled_back(server, tmp_path, no_sleep):
    server_path = tmp_path / "server"
    server_path.mkdir()
    (server_path / "pre_existing.jar").write_bytes(b"user-file")

    _serve(server, "/evil.jar", b"evil")
    _serve(server, "/good.jar", b"good")

    pack_url = _url(server, "/pack.mrpack")
    server.routes["/pack.mrpack"] = _mrpack(
        [
            # A tampered index tries to write outside the server folder.
            {"path": "../evil.jar", "downloads": [_url(server, "/evil.jar")]},
            {"path": "mods/good.jar", "downloads": [_url(server, "/good.jar")]},
            {"path": "mods/pre_existing.jar", "downloads": [_url(server, "/good.jar")]},
        ]
    )

    result = ModsManager().install_modpack(pack_url, "pack.mrpack", str(server_path))
    print("downloads hit:", server.hits)

    assert result.get("success") is False
    assert "could not be downloaded" in result.get("error", "")
    # The traversal attempt must never escape the server folder.
    assert not (tmp_path / "evil.jar").exists()
    assert not (server_path.parent / "evil.jar").exists()
    # Files written during the failed install are rolled back...
    assert not (server_path / "mods" / "good.jar").exists()
    # ...but a file the user already had is preserved.
    assert (server_path / "pre_existing.jar").read_bytes() == b"user-file"
    assert not (server_path / "temp_modpack").exists()
    # The evil path itself is not downloaded.
    assert "/evil.jar" not in server.hits


def test_modpack_download_failure_is_not_silent(server, tmp_path, no_sleep):
    server_path = tmp_path / "server"
    server_path.mkdir()

    _serve(server, "/present.jar", b"present")
    # /missing.jar has no route -> 404 from the local server.
    pack_url = _url(server, "/pack.mrpack")
    server.routes["/pack.mrpack"] = _mrpack(
        [
            {"path": "mods/present.jar", "downloads": [_url(server, "/present.jar")]},
            {"path": "mods/missing.jar", "downloads": [_url(server, "/missing.jar")]},
        ]
    )

    result = ModsManager().install_modpack(pack_url, "pack.mrpack", str(server_path))

    # Previously a failed dependency was logged and success was still reported;
    # now the pack must be reported as failed and rolled back.
    assert result.get("success") is False
    assert "missing.jar" in result.get("error", "")
    assert not (server_path / "mods" / "present.jar").exists(), "partial install rolled back"


def test_modpack_missing_index_is_rejected(server, tmp_path, no_sleep):
    server_path = tmp_path / "server"
    server_path.mkdir()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("overrides/whatever.txt", "x")
    server.routes["/bad.mrpack"] = buf.getvalue()

    result = ModsManager().install_modpack(
        _url(server, "/bad.mrpack"), "bad.mrpack", str(server_path)
    )
    assert result.get("success") is False
    assert "modrinth.index.json" in result.get("error", "")
    assert not (server_path / "temp_modpack").exists()


def test_delete_mod_rejects_path_traversal(tmp_path):
    server_path = tmp_path / "server"
    mods_dir = server_path / "mods"
    mods_dir.mkdir(parents=True)
    victim = server_path / "server.properties"
    victim.write_text("important")

    manager = ModsManager()

    # A crafted name must not be able to delete files outside the mods folder.
    assert manager.delete_mod("../../server.properties", str(server_path)) is False
    assert victim.exists()

    real = mods_dir / "real.jar"
    real.write_bytes(b"jar")
    assert manager.delete_mod("../mods/real.jar", str(server_path)) is True
    assert not real.exists()

def test_modpack_rollback_restores_overwritten_files(server, tmp_path, no_sleep):
    """A failed install must restore files that already existed, not merely
    skip deleting them: the hardened download pipeline removes the destination
    on failure, so without a backup the user's file would be destroyed."""
    server_path = tmp_path / "server"
    mods_dir = server_path / "mods"
    mods_dir.mkdir(parents=True)
    pre_existing = mods_dir / "pre_existing.jar"
    pre_existing.write_bytes(b"user-content")

    _serve(server, "/new.jar", b"pack-content")
    # /missing.jar is not routed -> 404 -> the install fails.

    pack_url = _url(server, "/pack.mrpack")
    server.routes["/pack.mrpack"] = _mrpack(
        [
            {"path": "mods/pre_existing.jar", "downloads": [_url(server, "/new.jar")]},
            {"path": "mods/missing.jar", "downloads": [_url(server, "/missing.jar")]},
        ]
    )

    result = ModsManager().install_modpack(pack_url, "pack.mrpack", str(server_path))

    assert result.get("success") is False
    assert pre_existing.read_bytes() == b"user-content", "overwritten file must be restored"
    assert not (mods_dir / "missing.jar").exists()
    assert not (server_path / "temp_modpack").exists()
