import json
import os

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {}
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading config file: {e}. A new one will be created.")
            self.config = {}

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
