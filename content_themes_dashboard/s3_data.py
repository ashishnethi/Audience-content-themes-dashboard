"""Load description.json, content_themes.json, and highlights from S3."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import streamlit as st
from botocore.config import Config
from botocore.exceptions import ClientError

from constants import (
    Platform,
    S3_BUCKET,
    content_themes_highlights_key,
    content_themes_key,
    description_key,
    signals_breakdown_key,
)

_s3_config = Config(read_timeout=90, connect_timeout=10, retries={"max_attempts": 3})


def _client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION"),
        config=_s3_config,
    )


def _object_etag(bucket: str, key: str) -> str | None:
    """Return ETag for cache key; None if object is missing."""
    try:
        r = _client().head_object(Bucket=bucket, Key=key)
        et = r.get("ETag")
        if et:
            return str(et)
        lm = r.get("LastModified")
        if lm is not None:
            return lm.isoformat()
        return "unknown"
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchKey"):
            return None
        raise


@st.cache_data(ttl=300, show_spinner=True)
def _fetch_s3_json_cached(bucket: str, key: str, etag: str) -> dict[str, Any] | None:
    try:
        obj = _client().get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise
    except json.JSONDecodeError:
        return None


def _load_json_key(bucket: str, key: str) -> dict[str, Any] | None:
    etag = _object_etag(bucket, key)
    if etag is None:
        return None
    return _fetch_s3_json_cached(bucket, key, etag)


def load_description(platform: Platform, room_id: str) -> dict[str, Any] | None:
    return _load_json_key(S3_BUCKET, description_key(platform, room_id))


def load_content_themes(platform: Platform, room_id: str) -> dict[str, Any] | None:
    return _load_json_key(S3_BUCKET, content_themes_key(platform, room_id))


def load_content_themes_highlights(
    platform: Platform,
    room_id: str,
    key_override: str | None = None,
) -> dict[str, Any] | None:
    key = key_override or content_themes_highlights_key(platform, room_id)
    return _load_json_key(S3_BUCKET, key)


def load_signals_breakdown(platform: Platform, room_id: str) -> dict[str, Any] | None:
    return _load_json_key(S3_BUCKET, signals_breakdown_key(platform, room_id))
