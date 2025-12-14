import json
import os
import uuid

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {
            "servers": [],
            "last_selected_id": None,
            "app_settings": {} 
        }
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    
                    # Migration: Check if old format (dict without 'servers' key)
                    if "servers" not in data and "server_path" in data:
                        print("Migrating config to multi-server format...")
                        new_server = {
                            "id": str(uuid.uuid4()),
                            "name": "My Server",
                            "path": data.get("server_path"),
                            "type": data.get("server_type", "vanilla"),
                            "version": data.get("minecraft_version"),
                            "ram_min": data.get("ram_min", "2"),
                            "ram_max": data.get("ram_max", "4"),
                            "ram_unit": data.get("ram_unit", "G")
                        }
                        self.config["servers"] = [new_server]
                        self.config["last_selected_id"] = new_server["id"]
                        self.save()
                    else:
                        self.config = data
                        
                    # Ensure basic structure exists
                    if "servers" not in self.config: self.config["servers"] = []
                    if "app_settings" not in self.config: self.config["app_settings"] = {}

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading config file: {e}. Starting fresh.")
            self.config = {"servers": [], "last_selected_id": None, "app_settings": {}}

    def get_all_servers(self):
        return self.config.get("servers", [])

    def get_server(self, server_id):
        for s in self.config.get("servers", []):
            if s["id"] == server_id:
                return s
        return None

    def add_server(self, server_data):
        if "id" not in server_data:
            server_data["id"] = str(uuid.uuid4())
        self.config["servers"].append(server_data)
        self.save()
        return server_data

    def update_server(self, server_id, updates):
        for s in self.config["servers"]:
            if s["id"] == server_id:
                s.update(updates)
                self.save()
                return s
        return None

    def delete_server(self, server_id):
        self.config["servers"] = [s for s in self.config["servers"] if s["id"] != server_id]
        if self.config.get("last_selected_id") == server_id:
            self.config["last_selected_id"] = None
        self.save()

    # Legacy/Global getters for app settings (themes, defaults, etc.)
    def get(self, key, default=None):
        return self.config.get("app_settings", {}).get(key, default)

    def set(self, key, value):
        if "app_settings" not in self.config:
            self.config["app_settings"] = {}
        self.config["app_settings"][key] = value
        self.save()

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

