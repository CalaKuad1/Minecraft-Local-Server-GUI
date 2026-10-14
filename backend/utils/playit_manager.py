"""playit.gg integration: permanent public addresses without port forwarding.

The user never touches playit's installer, service or terminal UI. MLSG drives
the same HTTP API the official agent uses (https://api.playit.gg):

1. Link (once): generate a claim code, the user approves it in the browser at
   playit.gg/claim/<code> (guest accounts allowed), and we exchange the code
   for the agent's secret key, stored in MLSG's app-data folder.
2. Tunnel: read the agent's tunnels (/v1/agents/rundata) and create a
   Minecraft tunnel for the server's local port if none exists yet. The
   address is stable, so friends keep the same IP between sessions.
3. Run: start the headless daemon (playitd) with that secret as a hidden
   child process; it carries the traffic.

Responses are wrapped as {"status": "success"|"fail"|"error", "data": ...}.
"""

import hashlib
import logging
import os
import secrets
import sys
import time

import requests

PLAYIT_API = "https://api.playit.gg"
CLIENT_VERSION = "mlsg-playit 1.0"

# playitd = the headless agent. Official releases of playit-cloud/playit-agent;
# a downloaded binary only runs when it matches its pinned size + SHA-256.
PLAYIT_AGENT_VERSION = "v1.0.10"
PLAYIT_AGENT_ASSETS = {
    "playit-windows-x86_64-signed.exe": (
        4822072,
        "2dbdaad119844cbbc062cc9774b8b462afa5f1b4b7832a9fc5ef4676cae887cf",
    ),
    "playit-windows-x86-signed.exe": (
        3603512,
        "9cec088fa4ee9ad4d59acd27512cf914078bdb31742e9abc946b81ea705f9d35",
    ),
    "playit-linux-amd64": (
        5894088,
        "2df7d9f10227ab312b1ad341853db4e8a8243df5cfcdbae58713a4271711c339",
    ),
    "playit-linux-aarch64": (
        6194872,
        "4c0db3e7b3a8158e249441c2f0b73f54e83429395890c7b1ca45fd7a6303d763",
    ),
}

TUNNEL_JAVA = "minecraft-java"
TUNNEL_BEDROCK = "minecraft-bedrock"


class PlayitError(Exception):
    """A playit API failure. `code` is playit's error name (e.g. "CodeExpired")."""

    def __init__(self, code, message=None):
        super().__init__(message or code)
        self.code = code


# --- HTTP API ---


def api_call(path, body=None, secret=None, timeout=15):
    """POST to the playit API and return `data`, raising PlayitError otherwise."""
    headers = {"Content-Type": "application/json", "User-Agent": CLIENT_VERSION}
    if secret:
        headers["Authorization"] = f"Agent-Key {secret.strip()}"
    try:
        r = requests.post(
            f"{PLAYIT_API}{path}", json=body or {}, headers=headers, timeout=timeout
        )
    except requests.RequestException as e:
        raise PlayitError("NetworkError", f"Could not reach playit.gg: {e}")
    if r.status_code == 429:
        raise PlayitError("TooManyRequests", "playit.gg rate limit, retry shortly")
    try:
        payload = r.json()
    except ValueError:
        raise PlayitError("BadResponse", f"HTTP {r.status_code} from playit.gg")

    status = payload.get("status")
    data = payload.get("data")
    if status == "success":
        return data
    if status == "fail":
        # Fail payloads are an error-name string (or an object for a few calls).
        code = data if isinstance(data, str) else str(data)
        raise PlayitError(code)
    # "error": auth / internal problems, e.g. {"type": "auth", "message": "..."}
    if isinstance(data, dict):
        raise PlayitError(
            data.get("message") or data.get("type") or "ApiError", str(data)
        )
    raise PlayitError("ApiError", str(payload))


# --- Linking (claim flow) ---


def generate_claim_code():
    return secrets.token_hex(5)


def claim_url(code):
    return f"https://playit.gg/claim/{code}"


def claim_setup(code):
    """Registers/polls the claim. Returns WaitingForUserVisit, WaitingForUser,
    UserAccepted or UserRejected."""
    return api_call(
        "/claim/setup",
        {"code": code, "agent_type": "self-managed", "version": CLIENT_VERSION},
    )


def claim_exchange(code):
    return api_call("/claim/exchange", {"code": code})["secret_key"]


def wait_for_claim(code, should_cancel=None, timeout=900, interval=2.0):
    """Polls until the user approves the claim in the browser; returns the
    secret key. Raises PlayitError("UserRejected"/"Timeout"/"Cancelled")."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if should_cancel and should_cancel():
            raise PlayitError("Cancelled")
        try:
            status = claim_setup(code)
        except PlayitError as e:
            if e.code not in ("NetworkError", "TooManyRequests"):
                raise
            status = None
        if status == "UserAccepted":
            return claim_exchange(code)
        if status == "UserRejected":
            raise PlayitError("UserRejected", "The link was rejected on playit.gg")
        time.sleep(interval)
    raise PlayitError("Timeout", "The playit.gg link was not approved in time")


# --- Secret storage ---


def secret_path(app_data_dir):
    return os.path.join(app_data_dir, "playit", "agent.secret")


def load_secret(app_data_dir):
    try:
        with open(secret_path(app_data_dir), "r", encoding="utf-8") as f:
            value = f.read().strip()
        return value or None
    except OSError:
        return None


def save_secret(app_data_dir, secret):
    path = secret_path(app_data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(secret.strip())
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def delete_secret(app_data_dir):
    try:
        os.remove(secret_path(app_data_dir))
    except OSError:
        pass


# --- Tunnels ---


def get_run_data(secret):
    """Agent id, tunnels, pending tunnels, notices and permissions."""
    return api_call("/v1/agents/rundata", secret=secret)


def _config_value(tunnel, name):
    for field in (tunnel.get("agent_config") or {}).get("fields") or []:
        if field.get("name") == name:
            return field.get("value")
    return None


def find_tunnel(run_data, local_port, tunnel_type=TUNNEL_JAVA):
    """The agent's allocated tunnel of this type pointing at local_port."""
    port = str(local_port)
    for t in run_data.get("tunnels") or []:
        if t.get("tunnel_type") == tunnel_type and _config_value(t, "local_port") == port:
            return t
    return None


def tunnel_name(local_port, tunnel_type=TUNNEL_JAVA):
    return f"MLSG {'Bedrock' if tunnel_type == TUNNEL_BEDROCK else 'Java'} {local_port}"


def create_tunnel(secret, local_port, agent_id, tunnel_type=TUNNEL_JAVA, name=None):
    """Creates a tunnel for this agent; returns the new tunnel id.

    Uses /tunnels/create: /v1/tunnels/create rejects every body with "failed
    to parse body" (verified 2026-10). The agent must be online, otherwise
    playit answers AgentVersionTooOld.
    """
    body = {
        "name": (name or tunnel_name(local_port, tunnel_type))[:30],
        "tunnel_type": tunnel_type,
        "port_type": "udp" if tunnel_type == TUNNEL_BEDROCK else "tcp",
        "port_count": 1,
        "origin": {
            "type": "agent",
            "data": {
                "agent_id": agent_id,
                "local_ip": "127.0.0.1",
                "local_port": int(local_port),
            },
        },
        "enabled": True,
        "alloc": None,
        "firewall_id": None,
        "proxy_protocol": None,
    }
    result = api_call("/tunnels/create", body, secret=secret)
    return result.get("id") if isinstance(result, dict) else result


def ensure_tunnel(secret, local_port, tunnel_type=TUNNEL_JAVA, name=None,
                  should_cancel=None, timeout=90, interval=3.0):
    """Returns the active tunnel for local_port, creating it if needed and
    waiting until playit has allocated its public address. Start the agent
    first: playit may keep a tunnel pending until its agent is online."""
    name = name or tunnel_name(local_port, tunnel_type)
    created = False
    deadline = time.monotonic() + timeout
    while True:
        if should_cancel and should_cancel():
            raise PlayitError("Cancelled")
        run_data = get_run_data(secret)
        tunnel = find_tunnel(run_data, local_port, tunnel_type)
        if tunnel:
            if tunnel.get("disabled_reason"):
                raise PlayitError("TunnelDisabled", str(tunnel["disabled_reason"]))
            return tunnel
        # A tunnel we created on a previous run may still be pending.
        if not created and any(
            p.get("tunnel_type") == tunnel_type and p.get("name") == name
            for p in run_data.get("pending") or []
        ):
            created = True
        if not created:
            # Not allocated yet: create it once, then wait for the address.
            try:
                create_tunnel(secret, local_port, run_data.get("agent_id"), tunnel_type, name)
                created = True
                continue
            except PlayitError as e:
                # The agent we just started has not registered yet; retry.
                if e.code != "AgentVersionTooOld":
                    raise
        if time.monotonic() >= deadline:
            raise PlayitError("Timeout", "playit.gg did not allocate an address in time")
        time.sleep(interval)


def account_notices(run_data):
    """Human-readable notices playit wants the user to see (e.g. limits)."""
    return [
        n.get("message")
        for n in (run_data.get("notices") or [])
        if n.get("message") and n.get("priority") in ("Critical", "High")
    ]


# --- Agent binary ---


def pick_agent_asset():
    import platform

    machine = platform.machine().lower()
    if sys.platform == "win32":
        is_64 = machine in ("amd64", "x86_64", "arm64", "aarch64")
        return "playit-windows-x86_64-signed.exe" if is_64 else "playit-windows-x86-signed.exe"
    if sys.platform.startswith("linux"):
        return "playit-linux-aarch64" if machine in ("arm64", "aarch64") else "playit-linux-amd64"
    return None  # playit publishes no standalone macOS daemon


def verify_binary(path, expected_size, expected_sha256):
    try:
        if not os.path.isfile(path) or os.path.getsize(path) != expected_size:
            return False
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected_sha256
    except OSError:
        return False


def get_agent_path(app_data_dir, should_cancel=None, log=None):
    """Path to the verified playitd binary, downloading it (~5 MB) if needed."""
    asset = pick_agent_asset()
    if not asset:
        raise PlayitError("UnsupportedPlatform", "playit.gg is not available on this OS")
    expected_size, expected_sha256 = PLAYIT_AGENT_ASSETS[asset]

    bin_dir = os.path.join(app_data_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    target = os.path.join(bin_dir, "playitd.exe" if sys.platform == "win32" else "playitd")
    if verify_binary(target, expected_size, expected_sha256):
        return target

    url = (
        "https://github.com/playit-cloud/playit-agent/releases/download/"
        f"{PLAYIT_AGENT_VERSION}/{asset}"
    )
    part = target + ".part"
    if log:
        log("📥 Downloading playit.gg agent (~5 MB)...", "info")
    try:
        res = requests.get(url, stream=True, timeout=(10, 120))
        res.raise_for_status()
        with open(part, "wb") as f:
            for chunk in res.iter_content(chunk_size=256 * 1024):
                if should_cancel and should_cancel():
                    raise PlayitError("Cancelled")
                if chunk:
                    f.write(chunk)
        if not verify_binary(part, expected_size, expected_sha256):
            raise PlayitError("ChecksumMismatch", "playit agent failed SHA-256 verification")
        os.replace(part, target)
        if sys.platform != "win32":
            os.chmod(target, 0o755)
        return target
    except requests.RequestException as e:
        raise PlayitError("DownloadFailed", f"Could not download playit agent: {e}")
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass


def agent_command(agent_path, app_data_dir):
    """Command line for a private, headless playitd instance.

    A dedicated IPC endpoint keeps it from clashing with a playit service the
    user may have installed separately (and /run/playit needs root on Linux).
    """
    base = os.path.join(app_data_dir, "playit")
    os.makedirs(base, exist_ok=True)
    socket = (
        r"\\.\pipe\mlsg-playitd"
        if sys.platform == "win32"
        else os.path.join(base, "playitd.sock")
    )
    return [
        agent_path,
        "--secret-path", secret_path(app_data_dir),
        "--socket-path", socket,
        "--log-path", os.path.join(base, "playitd.log"),
    ]


# --- Agent failures that make waiting pointless ---

AGENTS_URL = "https://playit.gg/account/agents"
# playitd log marker -> our error code
_FATAL_AGENT_ERRORS = {"AgentDisabledOverLimit": "AgentOverLimit"}


def agent_log_path(app_data_dir):
    return os.path.join(app_data_dir, "playit", "playitd.log")


def agent_fatal_error(app_data_dir, since):
    """Error code if the agent logged a fatal error after `since` (epoch secs).

    playitd keeps retrying forever on e.g. "account over the agent limit",
    so without this we'd wait for an address that will never come.
    """
    from datetime import datetime

    try:
        with open(agent_log_path(app_data_dir), "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 32768))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        stamp = line.split(" ", 1)[0]
        try:
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ts < since:
            break
        for marker, code in _FATAL_AGENT_ERRORS.items():
            if marker in line:
                return code
    return None
