import json
import os
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "data" / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "hand_history_path": "",
    "hand_history_save_path": str(PROJECT_ROOT / "data" / "hand_histories"),
    "hero_seat": 6,
    "table_size": 6,
    "badge_positions": {
        "1": {"x": 100, "y": 100},
        "2": {"x": 300, "y": 100},
        "3": {"x": 500, "y": 300},
        "4": {"x": 300, "y": 500},
        "5": {"x": 100, "y": 500},
        "6": {"x": 50, "y": 300},
        "7": {"x": 100, "y": 150},
        "8": {"x": 300, "y": 50},
        "9": {"x": 500, "y": 150},
        "hero": {"x": 300, "y": 300}
    }
}

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    user_config = json.load(f)
                    self.config.update(user_config)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        os.makedirs(CONFIG_FILE.parent, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()
