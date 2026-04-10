"""
Qualitative story analysis report: loads story.json (stories + citations).

Light UI aligned with other Enterprise tabs; uses a Streamlit fragment for snappy reruns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Replace [CLIENT_A], [CLIENT_B], etc. with plain "CLIENT" in displayed text.
_CLIENT_BRACKET_RE = re.compile(r"\[CLIENT_[A-Za-z0-9]+\]", re.IGNORECASE)

_fragment = getattr(st, "fragment", None)
if _fragment is None:

    def _fragment(f):  # type: ignore[no-redef]
        return f

_DASH_DIR = Path(__file__).resolve().parent
_STORY_FILE = _DASH_DIR / "story.json"

_CITATION_SEP = " <SEP> "
_CITATIONS_VISIBLE_MAX = 10

# Story types excluded from the qualitative report (case-insensitive match on trimmed value).
_EXCLUDED_STORY_TYPES = frozenset({"user research"})


def _visible_story_dicts(stories: list[Any]) -> list[dict[str, Any]]:
    """Stories shown in the UI (excludes e.g. User research)."""
    out: list[dict[str, Any]] = []
    for s in stories:
        if not isinstance(s, dict):
            continue
        raw = str(s.get("story_type") or "").strip()
        if raw.casefold() in {t.casefold() for t in _EXCLUDED_STORY_TYPES}:
            continue
        out.append(s)
    return out


@st.cache_data(ttl=120, show_spinner=False)
def _load_story_raw_cached(_mtime: float) -> dict[str, Any]:
    text = _STORY_FILE.read_text(encoding="utf-8")
    return json.loads(text)


def _load_story_raw() -> dict[str, Any]:
    if not _STORY_FILE.is_file():
        raise FileNotFoundError(f"Missing story file: {_STORY_FILE}")
    mtime = _STORY_FILE.stat().st_mtime
    return _load_story_raw_cached(mtime)


def _redact_clients(text: str) -> str:
    if not text:
        return text
    return _CLIENT_BRACKET_RE.sub("CLIENT", text)


def _mask_urls(text: str) -> str:
    """Replace URLs and URIs with a neutral placeholder for safe display."""
    if not text:
        return text
    out = text

    def _md_link_repl(m: re.Match[str]) -> str:
        label, uri = m.group(1), m.group(2).strip()
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|www\.)", uri, re.IGNORECASE):
            return f"[{label}]([URL])"
        return m.group(0)

    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _md_link_repl, out)

    out = re.sub(
        r"(?<![\w/])(?:https?|s3)://[^\s\)\]\}\"\'<>,]+",
        "[URL]",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"(?<![\w/])(?<!@)[a-z][a-z0-9+.-]*://[^\s\)\]\}\"\'<>,]+",
        "[URL]",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"(?<![\w/])www\.[^\s\)\]\}\"\'<>,]+",
        "[URL]",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _sanitize_display(text: str) -> str:
    """Client tokens + URL masking for any user-visible string."""
    return _mask_urls(_redact_clients(text))


def _clean_citation_reference(ref: str) -> str:
    t = ref.strip()
    if not t:
        return ""
    if t.lower() == "no chunk content available":
        return ""
    return t


def _clean_citation_summary(detail: str) -> str:
    """Drop placeholder-only summary lines; leave real excerpts unchanged."""
    t = detail.strip()
    if not t:
        return ""
    tl = t.lower()
    # Short pipeline placeholders only (avoid stripping long excerpts that mention the phrase).
    if len(t) <= 30 and "no summary available" in tl:
        return ""
    if tl == "no chunk content available":
        return ""
    return t


def _parse_citation(raw: str) -> dict[str, str]:
    """Split pipeline citation strings on `` <SEP> ``."""
    if _CITATION_SEP not in raw:
        return {
            "source": "",
            "reference": "",
            "url": "",
            "detail": raw.strip(),
        }
    parts = [p.strip() for p in raw.split(_CITATION_SEP)]
    source = parts[0] if parts else ""
    reference = parts[1] if len(parts) > 1 else ""
    url = ""
    for p in parts[2:]:
        if p.startswith("http://") or p.startswith("https://"):
            url = p
            break
    detail = parts[-1] if parts else raw
    return {
        "source": source,
        "reference": reference,
        "url": url,
        "detail": detail,
    }


def _citations_dataframe(citations: list[Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, c in enumerate(citations):
        s = str(c) if c is not None else ""
        p = _parse_citation(s)
        ref = _clean_citation_reference(p["reference"])
        if len(ref) > 180:
            ref = ref[:177] + "…"
        detail = _clean_citation_summary(p["detail"])
        if len(detail) > 500:
            detail = detail[:497] + "…"
        src = _sanitize_display(p["source"].strip())
        ref_d = _sanitize_display(ref)
        sum_d = _sanitize_display(detail)
        rows.append(
            {
                "#": i + 1,
                "Source": src,
                "Reference": ref_d,
                "Summary": sum_d,
            }
        )
    return pd.DataFrame(rows)


def _group_stories_by_type(
    stories: list[Any],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Preserve first-seen order of story_type values; each bucket is a list of story dicts."""
    order: list[str] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for s in stories:
        if not isinstance(s, dict):
            continue
        raw = str(s.get("story_type") or "").strip()
        key = raw if raw else "Other"
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(s)
    return [(k, buckets[k]) for k in order]


def _render_story_body(story: dict[str, Any]) -> None:
    """Inner drawer: body + citations (title lives inside ``story_full`` markdown)."""
    body = _sanitize_display(str(story.get("story_full") or "").strip())
    citations = story.get("story_citations")
    if not isinstance(citations, list):
        citations = []

    if body:
        st.markdown(body)
    else:
        st.caption("No story content.")
    st.divider()
    n_cit = len(citations)
    st.markdown(f"##### Citations ({n_cit})")
    if not citations:
        st.caption("No citations for this story.")
        return
    shown = citations[:_CITATIONS_VISIBLE_MAX]
    extra = n_cit - len(shown)
    df = _citations_dataframe(shown)
    st.dataframe(
        df,
        column_config={
            "#": st.column_config.NumberColumn("#", width="small", format="%d"),
            "Source": st.column_config.TextColumn("Source", width="small"),
            "Reference": st.column_config.TextColumn("Reference", width="medium"),
            "Summary": st.column_config.TextColumn("Summary / excerpt", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        height=min(480, 140 + len(shown) * 34),
    )
    if extra > 0:
        st.caption(f"+ {extra} citations")


@_fragment
def render_qualitative_story_report() -> None:
    try:
        data = _load_story_raw()
    except FileNotFoundError as e:
        st.error(str(e))
        return
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in story file: {e}")
        return

    stories = data.get("stories")
    if not isinstance(stories, list):
        st.error("Expected a `stories` array in story.json.")
        return

    st.subheader("Qualititative story analysis report")
    st.markdown(
        "<div style='margin-bottom:1rem;border-left:3px solid #ff6b35;"
        "padding:12px 16px 12px 15px;background-color:#f8f9fa;border-radius:6px;"
        "border:1px solid #e9ecef;'>"
        "<p style='margin:0;color:#333;font-size:0.95rem;line-height:1.55;'>"
        "Customer insights from enterprise data that allow us "
        "to model different personas. Personas are confidential; only raw data is shown."
        "</p></div>",
        unsafe_allow_html=True,
    )
    visible = _visible_story_dicts(stories)
    st.metric("Stories in this report", f"{len(visible):,}")

    st.divider()

    if not stories:
        st.info("No stories in file.")
        return
    if not visible:
        st.info("No stories to display after applying report filters.")
        return

    grouped = _group_stories_by_type(visible)
    for type_name, items in grouped:
        cat_label = _sanitize_display(type_name)
        if len(cat_label) > 88:
            cat_label = cat_label[:85] + "…"
        with st.expander(f"{cat_label} ({len(items)} stories)", expanded=False):
            for j, story in enumerate(items):
                if not isinstance(story, dict):
                    st.warning(f"Skipping non-object story in '{type_name}'.")
                    continue
                with st.expander(f"Story {j + 1}", expanded=False):
                    _render_story_body(story)
