"""Load room list from YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from constants import Platform


def _config_path() -> Path:
    env = os.getenv("CONTENT_THEMES_ROOMS_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent / "rooms.yaml"


def load_rooms_config() -> list[dict[str, Any]]:
    path = _config_path()
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    rooms = data.get("rooms")
    if not isinstance(rooms, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rooms:
        if not isinstance(row, dict):
            continue
        rid = row.get("room_id")
        plat = row.get("platform")
        if not rid or plat not in ("reddit", "linkedin"):
            continue
        entry: dict[str, Any] = {"room_id": str(rid).strip(), "platform": plat}
        lbl = row.get("label")
        if isinstance(lbl, str) and lbl.strip():
            entry["label"] = lbl.strip()
        out.append(entry)
    return out


def rooms_for_platform(rooms: list[dict[str, Any]], platform: Platform) -> list[dict[str, Any]]:
    return [r for r in rooms if r["platform"] == platform]
