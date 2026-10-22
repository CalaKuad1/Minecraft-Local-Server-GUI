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


# --- Side filter and mod updates -------------------------------------------

import hashlib  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import utils.mods_manager as mods_module  # noqa: E402


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = json.dumps(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _fake_requests(monkeypatch, get=None, post=None):
    calls = []

    def _get(url, **kw):
        calls.append(("GET", url, kw))
        return get(url, **kw)

    def _post(url, **kw):
        calls.append(("POST", url, kw))
        return post(url, **kw)

    monkeypatch.setattr(mods_module, "requests", SimpleNamespace(get=_get, post=_post))
    return calls


def test_search_side_filter_adds_environment_facets(monkeypatch):
    calls = _fake_requests(monkeypatch, get=lambda url, **kw: _Resp({"hits": []}))
    manager = ModsManager()

    manager.search_mods("", side="server")
    manager.search_mods("", side="server_only")
    manager.search_mods("", side="all")

    facets = [json.loads(c[2]["params"]["facets"]) for c in calls]
    assert ["server_side:required", "server_side:optional"] in facets[0]
    assert ["client_side:optional", "client_side:unsupported"] not in facets[0]
    assert ["client_side:optional", "client_side:unsupported"] in facets[1]
    assert not any("server_side" in f for group in facets[2] for f in group)


def _install_jar(tmp_path, name, content):
    mods = tmp_path / "mods"
    mods.mkdir(exist_ok=True)
    (mods / name).write_bytes(content)
    return hashlib.sha1(content).hexdigest()


def test_check_updates_reports_only_newer_versions(tmp_path, monkeypatch):
    old = _install_jar(tmp_path, "sodium-0.5.jar", b"sodium-old")
    cur = _install_jar(tmp_path, "lithium-0.12.jar", b"lithium-current")
    _install_jar(tmp_path, "manual.jar", b"not-on-modrinth")

    current = {
        old: {"id": "s1", "project_id": "P1", "version_number": "0.5", "date_published": "2024-01-01T00:00:00Z"},
        cur: {"id": "l2", "project_id": "P2", "version_number": "0.12", "date_published": "2024-06-01T00:00:00Z"},
    }
    latest = {
        old: {"id": "s2", "version_number": "0.6", "date_published": "2024-05-01T00:00:00Z",
              "files": [{"filename": "sodium-0.6.jar", "primary": True}]},
        # Modrinth's "latest for these filters" is older than what's installed.
        cur: {"id": "l1", "version_number": "0.11", "date_published": "2024-02-01T00:00:00Z",
              "files": [{"filename": "lithium-0.11.jar", "primary": True}]},
    }
    seen = {}

    def post(url, json=None, **kw):
        seen[url.rsplit("/", 1)[-1]] = json
        return _Resp(latest if url.endswith("/update") else current)

    def get(url, **kw):
        return _Resp([{"id": "P1", "title": "Sodium", "slug": "sodium"},
                      {"id": "P2", "title": "Lithium", "slug": "lithium"}])

    _fake_requests(monkeypatch, get=get, post=post)
    result = ModsManager().check_updates(str(tmp_path), loader="fabric", version="1.21.1")

    by_name = {r["filename"]: r for r in result}
    assert set(by_name) == {"sodium-0.5.jar", "lithium-0.12.jar"}
    assert by_name["sodium-0.5.jar"]["title"] == "Sodium"
    assert by_name["sodium-0.5.jar"]["update"]["version_id"] == "s2"
    assert by_name["lithium-0.12.jar"]["update"] is None
    assert seen["update"]["loaders"] == ["fabric"]
    assert seen["update"]["game_versions"] == ["1.21.1"]


def test_update_mod_replaces_jar(tmp_path, server, monkeypatch, no_sleep):
    _install_jar(tmp_path, "sodium-0.5.jar", b"sodium-old")
    new = b"sodium-new"
    _serve(server, "/sodium-0.6.jar", new)
    version = {"files": [{"filename": "sodium-0.6.jar", "primary": True,
                          "url": _url(server, "/sodium-0.6.jar"),
                          "hashes": {"sha1": hashlib.sha1(new).hexdigest()}}]}
    _fake_requests(monkeypatch, get=lambda url, **kw: _Resp(version))

    result = ModsManager().update_mod("sodium-0.5.jar", "s2", str(tmp_path))

    assert result == {"success": True, "filename": "sodium-0.6.jar", "previous": "sodium-0.5.jar"}
    assert sorted(os.listdir(tmp_path / "mods")) == ["sodium-0.6.jar"]
    assert (tmp_path / "mods" / "sodium-0.6.jar").read_bytes() == new


def test_update_mod_keeps_old_jar_on_bad_checksum(tmp_path, server, monkeypatch, no_sleep):
    _install_jar(tmp_path, "sodium-0.5.jar", b"sodium-old")
    _serve(server, "/sodium-0.6.jar", b"tampered")
    version = {"files": [{"filename": "sodium-0.6.jar", "primary": True,
                          "url": _url(server, "/sodium-0.6.jar"),
                          "hashes": {"sha1": "0" * 40}}]}
    _fake_requests(monkeypatch, get=lambda url, **kw: _Resp(version))

    result = ModsManager().update_mod("sodium-0.5.jar", "s2", str(tmp_path))

    assert result["success"] is False
    assert sorted(os.listdir(tmp_path / "mods")) == ["sodium-0.5.jar"]


def test_update_mod_keeps_old_jar_when_download_fails(tmp_path, server, monkeypatch, no_sleep):
    _install_jar(tmp_path, "sodium-0.5.jar", b"sodium-old")
    version = {"files": [{"filename": "sodium-0.6.jar", "primary": True,
                          "url": _url(server, "/missing.jar")}]}
    _fake_requests(monkeypatch, get=lambda url, **kw: _Resp(version))

    result = ModsManager().update_mod("sodium-0.5.jar", "s2", str(tmp_path))

    assert result["success"] is False
    assert sorted(os.listdir(tmp_path / "mods")) == ["sodium-0.5.jar"]
