import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import utils.api_client as api_client  # noqa: E402
from utils.api_client import (  # noqa: E402
    download_file_from_url,
    download_and_extract_zip,
    get_server_versions,
    download_server_jar,
)


class _RoutingHandler(BaseHTTPRequestHandler):
    """A minimal configurable HTTP server for download tests.

    Routes are stored on the *server* object (``server.routes`` /
    ``server.hits_map``), not on the handler class, so every server instance is
    isolated across tests.
    """

    def log_message(self, *args):
        pass

    def _route(self):
        routes = getattr(self.server, "routes", {})
        hits_map = getattr(self.server, "hits_map", {})
        # Consume-once entries take priority so a test can serve a flaky
        # response on the first hit and the real one afterwards.
        if self.path in hits_map:
            return hits_map.pop(self.path)
        if self.path in routes:
            return routes[self.path]
        return None

    def do_GET(self):
        self.server.hits.append(self.path)
        rule = self._route() or {"status": 500, "body": b"boom", "headers": {}}
        body = rule.get("body", b"")
        headers = dict(rule.get("headers", {}))
        self.send_response(rule.get("status", 200))
        for k, v in headers.items():
            self.send_header(k, v)
        if "Content-Length" not in headers:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        payload = rule.get("chunked_body")
        if payload:
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RoutingHandler)
    server.hits = []
    server.routes = {}
    server.hits_map = {}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(api_client.time, "sleep", lambda s: None)


def _url(server, path):
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def test_download_success_with_content_length(http_server, tmp_path, no_sleep):
    http_server.routes["/file.jar"] = {"body": b"PK\x03\x04payload-jar-data"}
    save = tmp_path / "server.jar"

    progress = []
    ok = download_file_from_url(_url(http_server, "/file.jar"), str(save), progress.append)

    assert ok is True
    assert save.read_bytes() == b"PK\x03\x04payload-jar-data"
    # progress never goes backwards and ends on 100
    assert progress == sorted(progress)
    assert progress[-1] == 100


def test_download_success_without_content_length(http_server, tmp_path, no_sleep):
    http_server.routes["/file.jar"] = {
        "body": b"data",
        "headers": {"Content-Type": "application/java-archive"},
    }
    save = tmp_path / "server.jar"
    assert download_file_from_url(_url(http_server, "/file.jar"), str(save), None) is True
    assert save.read_bytes() == b"data"


def test_download_follows_redirect(http_server, tmp_path, no_sleep):
    http_server.routes["/redirect"] = {
        "status": 302,
        "headers": {"Location": "/final.jar"},
        "body": b"",
    }
    http_server.routes["/final.jar"] = {"body": b"real-content"}
    save = tmp_path / "file.jar"
    assert download_file_from_url(_url(http_server, "/redirect"), str(save), None) is True
    assert save.read_bytes() == b"real-content"


def test_download_zero_byte_never_succeeds(http_server, tmp_path, no_sleep):
    http_server.routes["/empty.jar"] = {"body": b""}
    save = tmp_path / "server.jar"
    ok = download_file_from_url(_url(http_server, "/empty.jar"), str(save), None, retries=2)
    assert ok is False
    assert not save.exists(), "a zero-byte download must not leave a file behind"
    assert "empty response body" in download_file_from_url.last_error


def test_download_truncated_body_fails_and_cleans_up(http_server, tmp_path, no_sleep):
    # Declare a larger Content-Length than the body actually delivered: this
    # simulates a cut connection / CDN error page served with a 200.
    http_server.routes["/truncated.jar"] = {
        "body": b"partial",
        "headers": {"Content-Length": str(1024 * 1024 * 10)},
    }
    save = tmp_path / "server.jar"
    ok = download_file_from_url(_url(http_server, "/truncated.jar"), str(save), None, retries=2)
    assert ok is False
    assert not save.exists(), "a truncated download must not leave a partial file behind"
    # Either requests detects the short read itself (IncompleteRead) or our own
    # size check catches it; the error must surface the URL either way.
    assert "truncated.jar" in download_file_from_url.last_error


def test_download_permanent_404_fails_fast(http_server, tmp_path, no_sleep):
    http_server.routes["/missing.jar"] = {"status": 404, "body": b"nope"}
    save = tmp_path / "server.jar"
    ok = download_file_from_url(_url(http_server, "/missing.jar"), str(save), None, retries=3)
    assert ok is False
    assert http_server.hits.count("/missing.jar") == 1, "a permanent 4xx must not be retried"
    assert "Resource not found" in download_file_from_url.last_error
    assert not save.exists()


def test_download_retries_transient_then_succeeds(http_server, tmp_path, no_sleep):
    # First hit returns a transient 500, second succeeds.
    http_server.hits_map["/flaky.jar"] = {"status": 500, "body": b"internal error"}
    http_server.routes["/flaky.jar"] = {"body": b"final-content"}
    save = tmp_path / "server.jar"
    ok = download_file_from_url(_url(http_server, "/flaky.jar"), str(save), None, retries=3)
    assert ok is True
    assert save.read_bytes() == b"final-content"
    assert http_server.hits.count("/flaky.jar") == 2


def test_download_all_5xx_fails_and_cleans_up(http_server, tmp_path, no_sleep):
    http_server.routes["/down.jar"] = {"status": 503, "body": b"cdn unavailable"}
    save = tmp_path / "server.jar"
    ok = download_file_from_url(_url(http_server, "/down.jar"), str(save), None, retries=3)
    assert ok is False
    assert http_server.hits.count("/down.jar") == 3
    assert not save.exists()


def test_download_surfaces_last_error_for_callers(http_server, tmp_path, no_sleep):
    http_server.routes["/down.jar"] = {"status": 500, "body": b"x"}
    save = tmp_path / "server.jar"
    assert download_file_from_url(_url(http_server, "/down.jar"), str(save), None, retries=1) is False
    assert download_file_from_url.last_error
    assert _url(http_server, "/down.jar") in download_file_from_url.last_error


def test_download_complete_size_mismatch_retried(http_server, tmp_path, no_sleep):
    # Content-Length declares 6 bytes but only 3 are delivered wholesale: the
    # stream terminates early and must be detected.
    http_server.routes["/short.jar"] = {
        "body": b"abc",
        "headers": {"Content-Length": "6"},
    }
    save = tmp_path / "server.jar"
    assert download_file_from_url(_url(http_server, "/short.jar"), str(save), None, retries=2) is False


def test_download_server_jar_lowercases_type(http_server, monkeypatch):
    captured = {}

    def fake_download(url, save_path, cb):
        captured["url"] = url
        return True

    monkeypatch.setattr(api_client, "download_file_from_url", fake_download)
    ok = download_server_jar("Paper", "1.21.1", "/tmp/x/server.jar", None)
    assert ok is True
    assert captured["url"] == "https://mcutils.com/api/server-jars/paper/1.21.1/download"


def test_get_server_versions_rejects_non_list(http_server, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": "boom"}

    monkeypatch.setattr(api_client.requests, "get", lambda *a, **k: FakeResponse())
    assert get_server_versions("paper") == []


def test_get_server_versions_filters_malformed_entries(http_server, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"version": "1.21.1", "url": "/a"}, {"nope": 1}, "junk"]

    monkeypatch.setattr(api_client.requests, "get", lambda *a, **k: FakeResponse())
    versions = get_server_versions("paPer")
    assert [v["version"] for v in versions] == ["1.21.1"]


def _serve_zip(http_server, name, contents, content_type="application/java-archive"):
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for arcname, data in contents.items():
            zf.writestr(arcname, data)
    http_server.routes[name] = {"body": buf.getvalue(), "headers": {"Content-Type": content_type}}
    return _url(http_server, name)


def test_extract_zip_single_folder(http_server, tmp_path, no_sleep):
    zip_url = _serve_zip(
        http_server,
        "/pack.zip",
        {"inner-folder/content.txt": b"hello", "inner-folder/nested/deep.txt": b"deep"},
    )
    dest = tmp_path / "out"
    ok = download_and_extract_zip(zip_url, str(dest), None)
    assert ok is True
    assert (dest / "content.txt").read_text() == "hello"
    assert (dest / "nested" / "deep.txt").read_text() == "deep"
    assert not (dest / "temp.zip").exists()
    assert not (dest / "temp_extract").exists()


def test_extract_zip_bad_archive_cleans_up(http_server, tmp_path, no_sleep):
    http_server.routes["/bad.zip"] = {"body": b"this is not a zip archive"}
    dest = tmp_path / "out"
    ok = download_and_extract_zip(_url(http_server, "/bad.zip"), str(dest), None)
    assert ok is False
    assert not (dest / "temp.zip").exists()
    assert not (dest / "temp_extract").exists()