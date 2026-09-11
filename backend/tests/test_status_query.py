"""Regression tests for the Server List Ping helpers.

These exist because a broken `pack_varint` (an infinite generator) caused the
backend to grow ~25-45 MB/s while a server was online. See v1.2.8 changelog.
"""

import json
import os
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.status_query import get_server_status, pack_varint  # noqa: E402


def unpack_varint(data):
    val = 0
    shift = 0
    for b in data:
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val
        shift += 7
    raise ValueError("malformed varint")


class PackVarintTests(unittest.TestCase):
    def test_roundtrip_boundaries(self):
        for d in [0, 1, 127, 128, 255, 300, 25565, 2_147_483_647, 4_294_967_295]:
            with self.subTest(d=d):
                self.assertEqual(unpack_varint(pack_varint(d)), d)

    def test_known_encodings(self):
        self.assertEqual(pack_varint(0).hex(), "00")
        self.assertEqual(pack_varint(1).hex(), "01")
        self.assertEqual(pack_varint(127).hex(), "7f")
        self.assertEqual(pack_varint(128).hex(), "8001")
        self.assertEqual(pack_varint(25565).hex(), "ddc701")

    def test_protocol_version_minus_one_terminates(self):
        # The old implementation looped forever here (value >= 128).
        encoded = pack_varint(-1 & 0xFFFFFFFF)
        self.assertEqual(len(encoded), 5)
        self.assertEqual(encoded.hex(), "ffffffff0f")

    def test_max_length(self):
        # A valid VarInt is at most 5 bytes.
        self.assertLessEqual(len(pack_varint(0xFFFFFFFF)), 5)


class GetServerStatusTests(unittest.TestCase):
    def _serve_once(self, payload):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def serve():
            try:
                srv.settimeout(5)
                conn, _ = srv.accept()
                conn.recv(4096)
                body = b"\x00" + pack_varint(len(payload)) + payload
                conn.sendall(pack_varint(len(body)) + body)
                time.sleep(0.3)  # let the client drain before closing
                conn.close()
            finally:
                srv.close()

        threading.Thread(target=serve, daemon=True).start()
        return port

    def test_parses_status_response(self):
        payload = json.dumps(
            {
                "players": {"online": 3, "max": 20, "sample": []},
                "version": {"name": "1.21"},
                "description": {"text": "hello"},
            }
        ).encode()
        port = self._serve_once(payload)
        start = time.time()
        result = get_server_status(port=port, timeout=2)
        # Must return promptly — the old code never returned at all.
        self.assertLess(time.time() - start, 2)
        self.assertTrue(result["online"])
        self.assertEqual(result["players"]["online"], 3)
        self.assertEqual(result["version"], "1.21")

    def test_offline_when_nothing_listens(self):
        # Grab a free port, then close it so the connection is refused.
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        result = get_server_status(port=port, timeout=0.5)
        self.assertFalse(result["online"])


if __name__ == "__main__":
    unittest.main()
