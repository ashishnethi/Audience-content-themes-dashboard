"""Shared labels and S3 key helpers for the content themes dashboard."""

from __future__ import annotations

import os
from typing import Literal

Platform = Literal["reddit", "linkedin"]

S3_BUCKET = os.getenv("S3_BUCKET", "audience-room-uploads")

REDDIT_CATEGORY_LABELS: dict[str, str] = {
    "problems_rants": "Problems & rants",
    "solutions_fixes": "Solutions & fixes",
    "experiences": "Experiences",
    "opinions": "Opinions",
    "questions_help": "Questions & help",
}

LINKEDIN_CATEGORY_LABELS: dict[str, str] = {
    "pain_points": "Pain points",
    "solutions_learnings": "Solutions & learnings",
    "workflows_how_to": "Workflows & how-to",
    "new_tech_trends": "New tech & trends Adaption",
    "opinions_insights": "Opinions & insights",
}

REDDIT_CATEGORY_ORDER = tuple(REDDIT_CATEGORY_LABELS.keys())
LINKEDIN_CATEGORY_ORDER = tuple(LINKEDIN_CATEGORY_LABELS.keys())


def base_prefix(platform: Platform, room_id: str) -> str:
    return f"beta/{platform}-audience/{room_id}"


def description_key(platform: Platform, room_id: str) -> str:
    return f"{base_prefix(platform, room_id)}/description.json"


def content_themes_key(platform: Platform, room_id: str) -> str:
    return f"{base_prefix(platform, room_id)}/content_themes.json"


def content_themes_highlights_key(platform: Platform, room_id: str) -> str:
    return f"{base_prefix(platform, room_id)}/content_themes_highlights.json"


def signals_breakdown_key(platform: Platform, room_id: str) -> str:
    return f"{base_prefix(platform, room_id)}/signals_breakdown.json"


# How many posts/comments to render per category (highlights file may hold up to 20 each).
UI_POSTS_PER_CATEGORY = 10
UI_COMMENTS_PER_CATEGORY = 10


def category_labels_for_platform(platform: Platform) -> dict[str, str]:
    return REDDIT_CATEGORY_LABELS if platform == "reddit" else LINKEDIN_CATEGORY_LABELS


def category_order_for_platform(platform: Platform) -> tuple[str, ...]:
    return REDDIT_CATEGORY_ORDER if platform == "reddit" else LINKEDIN_CATEGORY_ORDER
