"""Tests for the world backup helpers (including path-traversal/zip-slip)."""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

# Configure a throwaway AppData before importing api_server (it builds AppState
# and a log handler at import time).
_FAKE_APPDATA = os.path.join(tempfile.gettempdir(), "mlsg_test_appdata")
os.makedirs(_FAKE_APPDATA, exist_ok=True)
os.environ["APPDATA"] = _FAKE_APPDATA
os.environ.pop("MLSG_TOKEN", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_server  # noqa: E402


class WorldBackupHelperTests(unittest.TestCase):
    def setUp(self):
        self.server = tempfile.mkdtemp(prefix="mlsg_srv_")
        self.world = os.path.join(self.server, "world")
        os.makedirs(os.path.join(self.world, "region"))
        with open(os.path.join(self.world, "level.dat"), "wb") as f:
            f.write(b"LEVELDATA")
        with open(os.path.join(self.world, "region", "r.0.0.mca"), "wb") as f:
            f.write(b"A" * 256)

    def tearDown(self):
        shutil.rmtree(self.server, ignore_errors=True)

    def test_create_backup_unique_names(self):
        n1 = api_server._create_world_backup_sync(self.server, "world")
        n2 = api_server._create_world_backup_sync(self.server, "world")
        self.assertNotEqual(n1, n2)
        self.assertTrue(os.path.isfile(os.path.join(self.server, "world_backups", n2)))

    def test_create_backup_missing_world(self):
        with self.assertRaises(FileNotFoundError):
            api_server._create_world_backup_sync(self.server, "nope")

    def test_prune_keeps_newest(self):
        api_server._create_world_backup_sync(self.server, "world")
        newest = api_server._create_world_backup_sync(self.server, "world")
        removed = api_server._prune_backups(self.server, "world", 1)
        self.assertEqual(removed, 1)
        remaining = [f for f in os.listdir(os.path.join(self.server, "world_backups")) if f.endswith(".zip")]
        self.assertEqual(remaining, [newest])

    def test_safe_backup_path(self):
        self.assertIsNone(api_server._safe_backup_path(self.server, "../evil.zip"))
        self.assertIsNone(api_server._safe_backup_path(self.server, "evil.txt"))
        self.assertIsNone(api_server._safe_backup_path(self.server, ""))
        name = api_server._create_world_backup_sync(self.server, "world")
        self.assertIsNotNone(api_server._safe_backup_path(self.server, name))

    def test_zip_slip_rejected(self):
        evil = os.path.join(self.server, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../escaped.txt", "gotcha")
        dest = os.path.join(self.server, "extract_here")
        with self.assertRaises(ValueError):
            api_server._safe_extract_zip(evil, dest)
        self.assertFalse(os.path.exists(os.path.join(self.server, "escaped.txt")))

    def test_safe_extract_normal(self):
        good = os.path.join(self.server, "good.zip")
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("world/level.dat", b"X")
        dest = os.path.join(self.server, "extract_here")
        api_server._safe_extract_zip(good, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "world", "level.dat")))


if __name__ == "__main__":
    unittest.main()
