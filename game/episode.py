import json
from pathlib import Path
from typing import Any, Dict

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "season_01_episode_01.json"


def load_episode() -> Dict[str, Any]:
    with CONTENT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def default_state() -> Dict[str, Any]:
    episode = load_episode()
    hero = dict(episode["hero_defaults"])
    hero["skills"] = dict(episode["hero_defaults"].get("skills", {}))
    hero["npc_memory"] = dict(episode["hero_defaults"].get("npc_memory", {}))
    hero["skill_log"] = list(episode["hero_defaults"].get("skill_log", []))
    return {
        "season": episode["season"],
        "episode": episode["episode"],
        "genre": episode.get("genre", ""),
        "turn": 0,
        "hero": hero,
        "last_scene": episode["opening_scene"],
        "case_status": "setup",
        "moral_style": {
            "careful": 0,
            "aggressive": 0,
            "diplomatic": 0,
            "deceptive": 0,
            "analytical": 0
        }
    }
