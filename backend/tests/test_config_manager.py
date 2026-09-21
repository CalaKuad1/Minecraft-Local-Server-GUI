"""Tests for ConfigManager's server profile CRUD."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.config_manager import ConfigManager  # noqa: E402


class ConfigManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "gui_config.json")
        self.cm = ConfigManager(self.path)

    def test_add_get_update_delete(self):
        server = self.cm.add_server(
            {
                "name": "Survival",
                "path": self.tmp,
                "type": "paper",
                "version": "1.21",
                "ram_min": "2",
                "ram_max": "4",
                "ram_unit": "G",
            }
        )
        self.assertIn("id", server)

        self.assertEqual(len(self.cm.get_all_servers()), 1)
        self.assertEqual(self.cm.get_server(server["id"])["name"], "Survival")

        self.cm.update_server(server["id"], {"name": "Hardcore"})
        self.assertEqual(self.cm.get_server(server["id"])["name"], "Hardcore")

        self.cm.delete_server(server["id"])
        self.assertIsNone(self.cm.get_server(server["id"]))
        self.assertEqual(self.cm.get_all_servers(), [])

    def test_persists_to_disk(self):
        self.cm.add_server({"name": "A", "path": self.tmp, "type": "vanilla",
                            "ram_min": "1", "ram_max": "2", "ram_unit": "G"})
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["servers"]), 1)

        reloaded = ConfigManager(self.path)
        self.assertEqual(len(reloaded.get_all_servers()), 1)

    def test_migrates_legacy_single_server_config(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"server_path": self.tmp, "server_type": "vanilla"}, f)
        cm = ConfigManager(self.path)
        servers = cm.get_all_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["path"], self.tmp)

    def test_recovers_from_corrupt_config(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        cm = ConfigManager(self.path)
        self.assertEqual(cm.get_all_servers(), [])

    def test_update_server_ram_settings(self):
        server = self.cm.add_server(
            {
                "name": "Survival",
                "path": self.tmp,
                "type": "paper",
                "version": "1.21",
                "ram_min": "2",
                "ram_max": "4",
                "ram_unit": "G",
            }
        )
        self.cm.update_server(
            server["id"], {"ram_min": "4", "ram_max": "8", "ram_unit": "G"}
        )
        updated = self.cm.get_server(server["id"])
        self.assertEqual(updated["ram_min"], "4")
        self.assertEqual(updated["ram_max"], "8")


if __name__ == "__main__":
    unittest.main()
