import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import playit_manager as pm


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def java_tunnel(port, address="demo.gl.joinmc.link", disabled=None):
    return {
        "id": "t1",
        "name": f"MLSG Java {port}",
        "display_address": address,
        "tunnel_type": "minecraft-java",
        "agent_config": {
            "fields": [
                {"name": "local_ip", "value": "127.0.0.1"},
                {"name": "local_port", "value": str(port)},
            ]
        },
        "disabled_reason": disabled,
    }


def test_api_call_unwraps_success_and_sends_agent_key(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        return FakeResponse({"status": "success", "data": {"ok": 1}})

    monkeypatch.setattr(pm.requests, "post", fake_post)
    assert pm.api_call("/v1/agents/rundata", secret=" abc \n") == {"ok": 1}
    assert seen["url"] == "https://api.playit.gg/v1/agents/rundata"
    assert seen["auth"] == "Agent-Key abc"


def test_api_call_raises_fail_code(monkeypatch):
    monkeypatch.setattr(
        pm.requests, "post",
        lambda *a, **k: FakeResponse({"status": "fail", "data": "CodeExpired"}),
    )
    with pytest.raises(pm.PlayitError) as e:
        pm.api_call("/claim/exchange", {"code": "x"})
    assert e.value.code == "CodeExpired"


def test_api_call_raises_auth_error(monkeypatch):
    monkeypatch.setattr(
        pm.requests, "post",
        lambda *a, **k: FakeResponse(
            {"status": "error", "data": {"type": "auth", "message": "AuthRequired"}}
        ),
    )
    with pytest.raises(pm.PlayitError) as e:
        pm.api_call("/v1/agents/rundata", secret="bad")
    assert e.value.code == "AuthRequired"


def test_wait_for_claim_exchanges_after_accept(monkeypatch):
    states = iter(["WaitingForUserVisit", "WaitingForUser", "UserAccepted"])
    monkeypatch.setattr(pm, "claim_setup", lambda code: next(states))
    monkeypatch.setattr(pm, "claim_exchange", lambda code: "secret-123")
    monkeypatch.setattr(pm.time, "sleep", lambda s: None)
    assert pm.wait_for_claim("abc") == "secret-123"


def test_wait_for_claim_rejected(monkeypatch):
    monkeypatch.setattr(pm, "claim_setup", lambda code: "UserRejected")
    with pytest.raises(pm.PlayitError) as e:
        pm.wait_for_claim("abc")
    assert e.value.code == "UserRejected"


def test_wait_for_claim_cancelled(monkeypatch):
    with pytest.raises(pm.PlayitError) as e:
        pm.wait_for_claim("abc", should_cancel=lambda: True)
    assert e.value.code == "Cancelled"


def test_find_tunnel_matches_type_and_port():
    run_data = {"tunnels": [java_tunnel(25566), java_tunnel(25565, "right.example")]}
    assert pm.find_tunnel(run_data, "25565")["display_address"] == "right.example"
    assert pm.find_tunnel(run_data, 25570) is None
    assert pm.find_tunnel(run_data, 25565, pm.TUNNEL_BEDROCK) is None


def test_ensure_tunnel_reuses_existing(monkeypatch):
    monkeypatch.setattr(pm, "get_run_data", lambda s: {"tunnels": [java_tunnel(25565)]})
    monkeypatch.setattr(pm, "create_tunnel", lambda *a, **k: pytest.fail("must not create"))
    assert pm.ensure_tunnel("s", 25565)["display_address"] == "demo.gl.joinmc.link"


def test_ensure_tunnel_creates_once_then_waits(monkeypatch):
    calls = {"create": 0, "rundata": 0}

    def run_data(secret):
        calls["rundata"] += 1
        if calls["create"] and calls["rundata"] >= 3:
            return {"tunnels": [java_tunnel(25565)]}
        return {"tunnels": [], "pending": []}

    def create(*a, **k):
        calls["create"] += 1
        return "new-id"

    monkeypatch.setattr(pm, "get_run_data", run_data)
    monkeypatch.setattr(pm, "create_tunnel", create)
    monkeypatch.setattr(pm.time, "sleep", lambda s: None)
    assert pm.ensure_tunnel("s", 25565)["id"] == "t1"
    assert calls["create"] == 1


def test_ensure_tunnel_does_not_duplicate_pending(monkeypatch):
    pending = {"tunnels": [], "pending": [
        {"name": "MLSG Java 25565", "tunnel_type": "minecraft-java"}
    ]}
    responses = iter([pending, pending, {"tunnels": [java_tunnel(25565)]}])
    monkeypatch.setattr(pm, "get_run_data", lambda s: next(responses))
    monkeypatch.setattr(pm, "create_tunnel", lambda *a, **k: pytest.fail("duplicate"))
    monkeypatch.setattr(pm.time, "sleep", lambda s: None)
    assert pm.ensure_tunnel("s", 25565)["id"] == "t1"


def test_ensure_tunnel_reports_disabled(monkeypatch):
    monkeypatch.setattr(
        pm, "get_run_data",
        lambda s: {"tunnels": [java_tunnel(25565, disabled="over-port-limit")]},
    )
    with pytest.raises(pm.PlayitError) as e:
        pm.ensure_tunnel("s", 25565)
    assert e.value.code == "TunnelDisabled"


def test_create_tunnel_body(monkeypatch):
    seen = {}

    def fake_call(path, body=None, secret=None, timeout=15):
        seen.update(path=path, body=body, secret=secret)
        return {"id": "abc"}

    monkeypatch.setattr(pm, "api_call", fake_call)
    assert pm.create_tunnel("sec", "25565", "agent-1") == "abc"
    assert seen["path"] == "/tunnels/create"
    body = seen["body"]
    assert (body["tunnel_type"], body["port_type"], body["port_count"]) == ("minecraft-java", "tcp", 1)
    assert body["origin"] == {
        "type": "agent",
        "data": {"agent_id": "agent-1", "local_ip": "127.0.0.1", "local_port": 25565},
    }


def test_ensure_tunnel_retries_until_agent_registers(monkeypatch):
    attempts = {"n": 0}
    state = {"created": False}

    def create(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise pm.PlayitError("AgentVersionTooOld")
        state["created"] = True

    monkeypatch.setattr(pm, "create_tunnel", create)
    monkeypatch.setattr(
        pm, "get_run_data",
        lambda s: {"agent_id": "a", "tunnels": [java_tunnel(25565)] if state["created"] else []},
    )
    monkeypatch.setattr(pm.time, "sleep", lambda s: None)
    assert pm.ensure_tunnel("s", 25565)["id"] == "t1"
    assert attempts["n"] == 3


def test_secret_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        assert pm.load_secret(d) is None
        pm.save_secret(d, "  key-1\n")
        assert pm.load_secret(d) == "key-1"
        pm.delete_secret(d)
        assert pm.load_secret(d) is None


def test_agent_command_uses_private_ipc_and_secret():
    with tempfile.TemporaryDirectory() as d:
        cmd = pm.agent_command("/bin/playitd", d)
        assert cmd[0] == "/bin/playitd"
        assert cmd[cmd.index("--secret-path") + 1] == pm.secret_path(d)
        socket = cmd[cmd.index("--socket-path") + 1]
        assert "mlsg" in socket or socket.startswith(d)


def test_verify_binary():
    import hashlib

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bin")
        with open(path, "wb") as f:
            f.write(b"playit")
        digest = hashlib.sha256(b"playit").hexdigest()
        assert pm.verify_binary(path, 6, digest)
        assert not pm.verify_binary(path, 7, digest)
        assert not pm.verify_binary(path, 6, "0" * 64)


def test_pinned_assets_cover_platform_picks():
    asset = pm.pick_agent_asset()
    assert asset is None or asset in pm.PLAYIT_AGENT_ASSETS


def test_agent_fatal_error_reads_recent_log_lines(tmp_path):
    import datetime as dt

    (tmp_path / "playit").mkdir()
    now = dt.datetime.now(dt.timezone.utc)
    old = (now - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    new = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    log = tmp_path / "playit" / "playitd.log"
    log.write_text(f'{old}  WARN playitd::daemon: agent disabled error=ApiFail("\\"AgentDisabledOverLimit\\"")\n', encoding="utf-8")
    since = now.timestamp() - 60
    assert pm.agent_fatal_error(str(tmp_path), since) is None  # only old lines
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{new}  INFO playitd::daemon: Starting playitd\n")
        f.write(f'{new}  WARN playitd::daemon: agent disabled error=ApiFail("\\"AgentDisabledOverLimit\\"")\n')
    assert pm.agent_fatal_error(str(tmp_path), since) == "AgentOverLimit"
    assert pm.agent_fatal_error(str(tmp_path / "missing"), since) is None
