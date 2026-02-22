import json
import os
from typing import Dict, Set


STATE_PATH = "data/state.json"


def load_state(path: str = STATE_PATH) -> Dict[str, Set[str]]:
    if not os.path.exists(path):
        return {"seen_urls": set(), "seen_fingerprints": set()}

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return {
        "seen_urls": set(raw.get("seen_urls", [])),
        "seen_fingerprints": set(raw.get("seen_fingerprints", [])),
    }


def save_state(seen_urls: Set[str], seen_fingerprints: Set[str], path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "seen_urls": sorted(seen_urls),
        "seen_fingerprints": sorted(seen_fingerprints),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
