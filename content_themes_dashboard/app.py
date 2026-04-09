"""
Streamlit dashboard: audience room content themes (Reddit / LinkedIn).

Run from repo root:
  streamlit run content_themes_dashboard/app.py

Loads content_themes.json + content_themes_highlights.json (schema v2), or falls back
to v1 content_themes.json with embedded samples.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config_loader import load_rooms_config, rooms_for_platform
from constants import (
    Platform,
    S3_BUCKET,
    UI_COMMENTS_PER_CATEGORY,
    UI_POSTS_PER_CATEGORY,
    category_labels_for_platform,
    category_order_for_platform,
    content_themes_key,
)
from s3_data import (
    load_content_themes,
    load_content_themes_highlights,
    load_description,
    load_signals_breakdown,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

st.set_page_config(
    page_title="Content themes",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Layout only — colors follow Streamlit light/dark theme.
_LAYOUT_CSS = """
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1100px !important;
    }
    /* Metric sizing */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }
    /* Custom header styling */
    .custom-header {
        display: flex;
        align-items: center;
        margin-bottom: 2rem;
        padding: 1rem 0;
    }
    .vectorial-icon {
        width: 40px;
        height: 40px;
        margin-right: 15px;
        position: relative;
    }
    .diamond {
        position: absolute;
        width: 16px;
        height: 16px;
        background-color: #ff6b35;
        transform: rotate(45deg);
    }
    .diamond-top-left {
        top: 0;
        left: 0;
    }
    .diamond-top-right {
        top: 0;
        right: 0;
    }
    .diamond-bottom-left {
        bottom: 0;
        left: 0;
    }
    .diamond-bottom-right {
        bottom: 0;
        right: 0;
    }
    .vectorial-text {
        font-size: 2rem;
        font-weight: 700;
        color: #ff6b35;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        margin: 0;
    }
    .dashboard-title {
        font-size: 1.2rem;
        font-weight: 400;
        color: #666;
        margin-top: 0.25rem;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    /* Hide Streamlit Cloud GitHub link */
    .stDeployButton {
        display: none !important;
    }
    [data-testid="stHeader"] {
        display: none !important;
    }
</style>
"""


def _css() -> None:
    st.markdown(_LAYOUT_CSS, unsafe_allow_html=True)


def _fmt_int(val: Any) -> str:
    try:
        return f"{int(val):,}"
    except (TypeError, ValueError):
        return "—"


def _render_room_header(
    name: str,
    desc: dict[str, Any] | None,
    platform: Platform,
    themes: dict[str, Any],
    signals: dict[str, Any] | None,
) -> None:
    st.subheader(name)

    sig = (signals or {}).get("summary")
    if not isinstance(sig, dict):
        sig = {}
    tp, tc, profiles = sig.get("total_posts"), sig.get("total_comments"), sig.get("total_profiles")

    # Calculate behavioral signals (posts + comments)
    total_signals = 0
    if tp is not None:
        total_signals += int(tp)
    if tc is not None:
        total_signals += int(tc)

    # Display both metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Behavioral Signals",
            _fmt_int(total_signals),
        )
    with col2:
        st.metric(
            "Profiles",
            _fmt_int(profiles) if profiles is not None else "0",
        )

    desc_summary = (desc or {}).get("summary") or (desc or {}).get("description")
    with st.expander("Room description", expanded=False):
        if desc_summary and str(desc_summary).strip():
            st.text(str(desc_summary))
        else:
            st.caption("No summary in description.json for this room.")

    # Display traits if available
    if desc and isinstance(desc, dict) and desc.get("traits"):
        traits = desc.get("traits")
        if isinstance(traits, list) and traits:
            st.subheader("Learned behaviour traits of Audience (From SAPIENS)")
            
            # Show traits in a single expander, one by one
            with st.expander("View Audience Traits", expanded=False):
                for i, trait in enumerate(traits):
                    if isinstance(trait, dict):
                        st.markdown(f"### {trait.get('title', f'Trait {i+1}')}")
                        
                        # Show only important keys in a clean layout
                        keywords = trait.get('keywordTags', [])
                        descriptions = trait.get('descriptions', [])
                        behavioral = trait.get('behavioralImplications', [])
                        biases = trait.get('decisionBiases', [])
                        tension = trait.get('tensionAxis', '')
                        position = trait.get('positionOnAxis', '')
                        confidence = trait.get('confidenceScore', 0)
                        
                        # Display key information in requested order
                        if descriptions:
                            st.markdown("**Description:**")
                            for desc in descriptions[:2]:  # Show first 2 descriptions
                                st.write(f"· {desc}")
                        
                        if keywords:
                            st.markdown("**Keywords:** " + ", ".join(keywords))
                        
                        if behavioral:
                            st.markdown("**Behavioral Implications:**")
                            for imp in behavioral[:2]:  # Show first 2 implications
                                st.write(f"· {imp}")
                        
                        if biases:
                            st.markdown("**Decision Biases:**")
                            for bias in biases[:2]:  # Show first 2 biases
                                st.write(f"· {bias}")
                        
                        if tension and position:
                            st.markdown(f"**Position:** {position} on {tension}")
                        
                        # Add separator between traits
                        if i < len(traits) - 1:
                            st.divider()


def _theme_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return
    xmax = float(df["Share"].max())
    x_domain_upper = min(100.0, max(xmax * 1.12, 1.0))
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "Share:Q",
                title="Share (%)",
                scale=alt.Scale(domain=[0, x_domain_upper]),
            ),
            y=alt.Y("Theme:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
            color=alt.value("#2563eb"),
            tooltip=["Theme", alt.Tooltip("Share:Q", format=".1f", title="Share %")],
        )
        .configure_axis(grid=True, labelFontSize=14, titleFontSize=12)
        .properties(height=60 * max(len(df), 1))
    )
    st.altair_chart(chart, use_container_width=True, theme="streamlit")


def _render_sample_block(item: dict[str, Any], platform: Platform) -> None:
    with st.container(border=True):
        kind = (item.get("kind") or "").strip().capitalize() or "Item"
        st.caption(kind)
        url = item.get("url")
        if url and isinstance(url, str):
            if platform == "reddit":
                st.markdown(f"🔗 [View on Reddit]({url})")
            elif platform == "linkedin":
                st.markdown(f"💼 [View on LinkedIn]({url})")
            else:
                st.markdown(f"🔗 [View on platform]({url})")
        body = item.get("text") or ""
        if body.strip():
            st.text(body)
        else:
            st.caption("(No text)")


def _norm_cat_key(s: str) -> str:
    s = s.strip()
    for z in ("\ufeff", "\u200b", "\u200c", "\u200d"):
        s = s.replace(z, "")
    return s.lower().replace("-", "_").replace(" ", "_")


def _get_category_bucket(
    by_category: dict[str, Any], slug: str, platform: Platform
) -> dict[str, Any]:
    """Resolve bucket by slug, display label, or normalized key (handles edited JSON)."""
    if not isinstance(by_category, dict):
        return {}
    if slug in by_category and isinstance(by_category[slug], dict):
        return by_category[slug]

    labels = category_labels_for_platform(platform)
    display = labels.get(slug)
    if display and display in by_category and isinstance(by_category[display], dict):
        return by_category[display]

    target = _norm_cat_key(slug)
    if display:
        dnorm = _norm_cat_key(display)
    else:
        dnorm = ""

    for k, v in by_category.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            continue
        kn = _norm_cat_key(k)
        if kn == target or (dnorm and kn == dnorm):
            return v
        if kn == target.replace("_", "") or kn == slug.lower().replace("_", ""):
            return v
    return {}


def _bucket_array_ci(bucket: dict[str, Any], logical: str) -> list[Any]:
    """Read posts/comments arrays using any casing (Posts, COMMENTS, etc.)."""
    want = logical.lower()
    aliases = {want}
    if want == "posts":
        aliases |= {"post"}
    if want == "comments":
        aliases |= {"comment"}
    for k, raw in bucket.items():
        if not isinstance(k, str):
            continue
        if k.strip().lower() not in aliases:
            continue
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and raw:
            return [raw]
    return []


def _dedupe_dict_items(items: list[dict], text_chars: int = 240) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for x in items:
        t = (x.get("text") or "")[:text_chars].strip().lower()
        u = (x.get("url") or "") or ""
        sig = f"{t}|{u}"
        if sig in seen:
            continue
        seen.add(sig)
        out.append(x)
    return out


def _slice_highlights(
    highlights: dict[str, Any], slug: str, platform: Platform
) -> tuple[list[dict], list[dict]]:
    bc = (
        highlights.get("by_category")
        or highlights.get("byCategory")
        or {}
    )
    bucket = _get_category_bucket(bc, slug, platform)
    if not bucket:
        root = highlights.get(slug)
        if isinstance(root, dict) and (
            _bucket_array_ci(root, "posts") or _bucket_array_ci(root, "comments")
        ):
            bucket = root
    if not bucket:
        return [], []

    posts_raw = _bucket_array_ci(bucket, "posts")
    comments_raw = _bucket_array_ci(bucket, "comments")

    post_items: list[dict] = []
    comment_items: list[dict] = []

    for x in posts_raw:
        if not isinstance(x, dict):
            continue
        if (x.get("kind") or "").strip().lower() == "comment":
            comment_items.append(x)
        else:
            post_items.append(x)

    for x in comments_raw:
        if isinstance(x, dict):
            comment_items.append(x)

    post_items = _dedupe_dict_items(post_items)[:UI_POSTS_PER_CATEGORY]
    comment_items = _dedupe_dict_items(comment_items)[:UI_COMMENTS_PER_CATEGORY]
    return post_items, comment_items


def _legacy_samples_v1(themes: dict[str, Any], slug: str) -> tuple[list[dict], list[dict]]:
    samples = themes.get("samples") or {}
    if not isinstance(samples, dict):
        return [], []
    raw = samples.get(slug) or []
    if not isinstance(raw, list):
        return [], []
    items = [x for x in raw if isinstance(x, dict)]
    posts = [x for x in items if (x.get("kind") or "").lower() == "post"][
        :UI_POSTS_PER_CATEGORY
    ]
    comments = [x for x in items if (x.get("kind") or "").lower() == "comment"][
        :UI_COMMENTS_PER_CATEGORY
    ]
    if not posts and not comments and items:
        posts = items[:UI_POSTS_PER_CATEGORY]
    return posts, comments


def _render_platform_tab(platform: Platform) -> None:
    all_rooms = load_rooms_config()
    subset = rooms_for_platform(all_rooms, platform)
    if not subset:
        st.info(
            f"No **{platform.title()}** rooms configured. Add entries to `rooms.yaml`."
        )
        return

    desc_data: dict[str, str] = {}
    for r in subset:
        rid = r["room_id"]
        desc = load_description(platform, rid)
        desc_data[rid] = (
            (desc or {}).get("audience_room_name")
            or (desc or {}).get("name")
            or rid
        )

    options = [r["room_id"] for r in subset]
    display = []
    for rid in options:
        name = desc_data[rid]
        if rid == "52f82e3d-65eb-43f9-bc52-b5baaa67e54f":
            name = f"Womens health {name}"
        display.append(name)

    idx = st.selectbox(
        "Audience room",
        range(len(options)),
        format_func=lambda i: display[i],
        key=f"room_pick_{platform}",
    )
    room_id = options[idx]

    desc = load_description(platform, room_id)
    themes = load_content_themes(platform, room_id)
    signals = load_signals_breakdown(platform, room_id)

    name = desc_data[room_id]
    # Add "Womens health" prefix for specific room
    if room_id == "52f82e3d-65eb-43f9-bc52-b5baaa67e54f":
        name = f"Womens health {name}"
    summary = (desc or {}).get("summary") or (desc or {}).get("description")

    if not themes:
        st.error("No theme summary found for this room.")
        st.caption(f"Expected: `s3://{S3_BUCKET}/{content_themes_key(platform, room_id)}`")
        return

    schema = int(themes.get("schema_version") or 1)
    hkey = themes.get("highlights_key")
    highlights = None
    if schema >= 2:
        highlights = load_content_themes_highlights(
            platform,
            room_id,
            key_override=hkey if isinstance(hkey, str) else None,
        )

    _render_room_header(name, desc, platform, themes, signals)

    cats = themes.get("categories") or {}
    order = category_order_for_platform(platform)
    pretty = category_labels_for_platform(platform)

    rows = []
    for slug in order:
        pct = cats.get(slug)
        if pct is None:
            pct = 0.0
        rows.append({"Theme": pretty.get(slug, slug), "Share": float(pct)})

    st.subheader("Theme distribution")
    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values("Share", ascending=False)
        _theme_chart(df)
    else:
        st.caption("No category percentages in file.")

    st.subheader("Examples by theme")

    if schema >= 2 and not highlights:
        st.warning(
            "Highlights file missing. Re-run `build_content_themes.py` to upload "
            "`content_themes_highlights.json`, or use a v1 `content_themes.json` with samples."
        )

    # Sort themes by percentage (highest to lowest) for examples
    sorted_themes = sorted(order, key=lambda slug: float(cats.get(slug) or 0), reverse=True)
    
    for slug in sorted_themes:
        pct = cats.get(slug)
        label = pretty.get(slug, slug)
        title = f"{label} — {pct}%" if pct is not None else label

        if highlights is not None:
            posts, comments = _slice_highlights(highlights, slug, platform)
        else:
            posts, comments = _legacy_samples_v1(themes, slug)

        with st.expander(title, expanded=False):
            if not posts and not comments:
                st.caption("No examples in this category.")
                continue

            if posts:
                st.markdown("**Posts**")
                for it in posts:
                    _render_sample_block(it, platform)

            if platform == "linkedin":
                if comments:
                    st.markdown("**Comments**")
                    st.caption("Pipeline stores posts only; unexpected comment entries below.")
                    for it in comments:
                        _render_sample_block(it, platform)
            elif platform != "reddit" and comments:
                st.markdown("**Comments**")
                for it in comments:
                    _render_sample_block(it, platform)


def main() -> None:
    _css()
    
    # Custom header with VECTORIAL icon and branding
    st.markdown("""
    <div class="custom-header">
        <div class="vectorial-icon">
            <div class="diamond diamond-top-left"></div>
            <div class="diamond diamond-top-right"></div>
            <div class="diamond diamond-bottom-left"></div>
            <div class="diamond diamond-bottom-right"></div>
        </div>
        <div>
            <div class="vectorial-text">VECTORIAL</div>
            <div class="dashboard-title">Audience Room Data Insights by sources</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_r, tab_l = st.tabs(["Reddit", "LinkedIn"])
    with tab_r:
        _render_platform_tab("reddit")
    with tab_l:
        _render_platform_tab("linkedin")


if __name__ == "__main__":
    main()
