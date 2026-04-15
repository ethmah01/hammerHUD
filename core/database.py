import json
import os
from pathlib import Path
from core.models import PlayerStats

# Always resolve path relative to project root (or a specific config folder)
PROJECT_ROOT = Path(__file__).parent.parent
HERO_FILE = PROJECT_ROOT / "data" / "hero_stats.json"

def load_hero_stats() -> PlayerStats:
    """Loads Hero's lifetime stats from JSON. Returns empty stats if missing or corrupted."""
    if HERO_FILE.exists():
        try:
            with open(HERO_FILE, "r") as f:
                data = json.load(f)
            return PlayerStats(
                vpip_count=data.get("vpip_count", 0),
                pfr_count=data.get("pfr_count", 0),
                hands_played=data.get("hands_played", 0)
            )
        except Exception as e:
            print(f"Error loading hero stats: {e}")
            
    return PlayerStats()

def save_hero_stats(stats: PlayerStats) -> None:
    """Persists Hero's lifetime stats to JSON."""
    os.makedirs(HERO_FILE.parent, exist_ok=True)
    with open(HERO_FILE, "w") as f:
        json.dump({
            "vpip_count": stats.vpip_count,
            "pfr_count": stats.pfr_count,
            "hands_played": stats.hands_played
        }, f, indent=4)
