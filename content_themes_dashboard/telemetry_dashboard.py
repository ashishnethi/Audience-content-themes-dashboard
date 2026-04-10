"""
Enterprise telemetry view: loads telmetry.json and renders the UI.

Styled to match the light Reddit/LinkedIn tabs. The main report is wrapped in
``@st.fragment`` so interactions rerun only this block—not Reddit/LinkedIn S3 loads.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import streamlit as st

_fragment = getattr(st, "fragment", None)
if _fragment is None:

    def _fragment(f):  # type: ignore[no-redef]
        return f

_DASH_DIR = Path(__file__).resolve().parent
_TELEMETRY_FILE = _DASH_DIR / "telmetry.json"

# Light panels aligned with Reddit/LinkedIn callouts (#f8f9fa, #ff6b35 accent).
_TELEMETRY_CSS = """
<style>
    .et-hero-light {
        padding: 1rem 1.25rem 1rem 15px;
        margin-bottom: 1rem;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        border-left: 3px solid #ff6b35;
    }
    .et-hero-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #222;
        margin: 0 0 0.25rem 0;
    }
    .et-hero-meta {
        font-size: 0.85rem;
        color: #555;
        margin: 0;
    }
    .et-panel-light {
        padding: 12px 16px;
        margin-bottom: 12px;
        border-left: 3px solid #ff6b35;
        padding-left: 15px;
        background-color: #f8f9fa;
        border-radius: 6px;
        border: 1px solid #e9ecef;
        border-left-width: 3px;
    }
    .et-panel-light h4 {
        font-size: 0.95rem;
        font-weight: 600;
        color: #333;
        margin: 0 0 0.5rem 0;
    }
    .et-panel-light ul {
        color: #333;
        margin: 0;
        padding-left: 1.15rem;
        line-height: 1.55;
        font-size: 0.92rem;
    }
    .et-pattern-light {
        padding: 12px 14px;
        margin-bottom: 8px;
        background-color: #f8f9fa;
        border-radius: 6px;
        border: 1px solid #e9ecef;
    }
    .et-pattern-title {
        color: #ff6b35;
        font-size: 0.98rem;
        font-weight: 600;
        margin: 0 0 0.25rem 0;
    }
    .et-pattern-seg {
        color: #555;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0 0 0.4rem 0;
    }
    .et-pattern-desc {
        color: #444;
        font-size: 0.88rem;
        line-height: 1.5;
        margin: 0 0 0.5rem 0;
    }
    .et-cat-title {
        font-size: 1rem;
        font-weight: 600;
        color: #222;
        margin: 0.25rem 0 0.5rem 0;
    }
    .et-prose-muted {
        color: #555;
        font-size: 0.9rem;
        line-height: 1.6;
        margin: 0;
    }
</style>
"""


@st.cache_data(ttl=120, show_spinner=False)
def _load_telemetry_raw_cached(_mtime: float) -> dict[str, Any]:
    """Load JSON; cache invalidates when file mtime changes."""
    text = _TELEMETRY_FILE.read_text(encoding="utf-8")
    return json.loads(text)


def _load_telemetry_raw() -> dict[str, Any]:
    if not _TELEMETRY_FILE.is_file():
        raise FileNotFoundError(f"Missing telemetry file: {_TELEMETRY_FILE}")
    mtime = _TELEMETRY_FILE.stat().st_mtime
    return _load_telemetry_raw_cached(mtime)


def _html_esc(s: str) -> str:
    return html.escape(s, quote=True)


def _tab_labels(categories: list[dict[str, Any]]) -> list[str]:
    defaults = ["Product", "Landing page", "Intelligence"]
    out: list[str] = []
    for i, cat in enumerate(categories):
        name = (cat.get("category_name") or "").strip()
        if "Product" in name:
            out.append("Product")
        elif "Website" in name:
            out.append("Landing page")
        elif "Intelligence" in name or "Review" in name:
            out.append("Intelligence")
        else:
            out.append(defaults[i] if i < len(defaults) else name[:16] or f"Cat {i + 1}")
    return out


def _render_expanded_session_analysis(dd: Any) -> None:
    """Inside session expander: show deep_dive narrative (analysis_prose or string body only)."""
    if dd is None:
        st.caption("No deep_dive data for this session.")
        return
    if isinstance(dd, str):
        t = dd.strip()
        if t:
            st.markdown(t)
        else:
            st.caption("No narrative analysis in JSON for this session.")
        return
    if not isinstance(dd, dict):
        st.caption("No narrative analysis in JSON for this session.")
        return
    dm = dd.get("duration_metrics")
    if dm is not None and str(dm).strip():
        st.caption(str(dm).strip())
    ap = dd.get("analysis_prose")
    if ap is not None and str(ap).strip():
        st.markdown(str(ap))
    else:
        st.caption("No narrative analysis in JSON for this session.")


def _render_category(
    cat: dict[str, Any],
    _cat_idx: int,
    report: dict[str, Any],
) -> None:
    name = cat.get("category_name") or "Category"
    report_id = str(report.get("report_id") or "Telemetry")

    summary = cat.get("summary") or {}
    analysis = summary.get("analysis") or []
    if not isinstance(analysis, list):
        analysis = []
    patterns = cat.get("behavioral_patterns") or []
    if not isinstance(patterns, list):
        patterns = []
    sessions = cat.get("sessions") or []
    if not isinstance(sessions, list):
        sessions = []

    st.markdown(
        f'<p class="et-cat-title">{_html_esc(str(name))}</p>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("Overview")
    st.markdown('<div class="et-panel-light">', unsafe_allow_html=True)
    st.markdown("<h4>Key observations</h4>", unsafe_allow_html=True)
    if analysis:
        items = "".join(f"<li>{_html_esc(str(x))}</li>" for x in analysis)
        st.markdown(f"<ul>{items}</ul>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<p class='et-prose-muted'>No analysis bullets in file.</p>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if summary.get("total_sessions") is not None or summary.get("unique_patterns") is not None:
        m1, m2, m3 = st.columns(3)
        with m1:
            ts = summary.get("total_sessions")
            if ts is not None:
                st.metric("Sessions in scope", int(ts))
        with m2:
            up = summary.get("unique_patterns")
            if up is not None:
                st.metric("Unique patterns", int(up))
        with m3:
            st.metric("Report", report_id[:18] + "…" if len(report_id) > 18 else report_id)

    st.divider()
    st.subheader("Behavioral patterns")

    if not patterns:
        st.caption("No behavioral patterns defined for this category.")
    else:
        for row_start in range(0, len(patterns), 2):
            col_a, col_b = st.columns(2)
            pair = patterns[row_start : row_start + 2]
            for col, pat in zip((col_a, col_b), pair):
                with col:
                    if not isinstance(pat, dict):
                        continue
                    title = str(pat.get("title") or "Pattern")
                    segment = str(pat.get("segment") or "—")
                    desc = str(pat.get("description") or "")
                    st.markdown(
                        f"""
                        <div class="et-pattern-light">
                            <p class="et-pattern-title">{_html_esc(title)}</p>
                            <p class="et-pattern-seg">{_html_esc(segment)}</p>
                            <p class="et-pattern-desc">{_html_esc(desc)}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    o = pat.get("occurrences")
                    u = pat.get("affected_users")
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        if o is not None:
                            st.metric("Occurrences", int(o))
                    with mc2:
                        if u is not None:
                            st.metric("Affected users", int(u))

    st.divider()
    st.subheader("Session summary of users")
    st.caption("Expand a user row to read the session narrative (analysis from telemetry).")

    cols_n = 3
    for row_start in range(0, len(sessions), cols_n):
        cols = st.columns(cols_n)
        for j in range(cols_n):
            idx = row_start + j
            if idx >= len(sessions):
                break
            s = sessions[idx]
            if not isinstance(s, dict):
                continue
            with cols[j]:
                user_num = idx + 1
                with st.expander(f"User {user_num}: Session Summary", expanded=False):
                    _render_expanded_session_analysis(s.get("deep_dive"))


@_fragment
def render_telemetry_report() -> None:
    """Telemetry UI; with Streamlit ≥1.33, fragment reruns skip Reddit/LinkedIn work."""
    st.markdown(_TELEMETRY_CSS, unsafe_allow_html=True)

    try:
        data = _load_telemetry_raw()
    except FileNotFoundError as e:
        st.error(str(e))
        return
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in telemetry file: {e}")
        return

    report = data.get("telemetry_report")
    if not isinstance(report, dict):
        st.error("Expected top-level key `telemetry_report` with an object value.")
        return

    categories = report.get("categories") or []
    if not isinstance(categories, list) or not categories:
        st.warning("No categories in telemetry report.")
        return

    report_id = str(report.get("report_id") or "Telemetry")

    st.markdown(
        f"""
        <div class="et-hero-light">
            <p class="et-hero-title">Telemetry report · Long-session audit</p>
            <p class="et-hero-meta">{_html_esc(report_id)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='et-panel-light' style='margin-top:0.75rem;'>"
        "<p style='margin:0;color:#333;font-size:0.95rem;line-height:1.55;'>"
        "Telemetry data insights from PostHog and Amplitude "
        "that allow us to model different ways users interact with the product. Personas are "
        "confidential; only raw data is shown."
        "</p></div>",
        unsafe_allow_html=True,
    )

    labels = _tab_labels(categories)
    tabs = st.tabs(labels[: len(categories)])
    for i, tab in enumerate(tabs):
        if i >= len(categories):
            break
        with tab:
            _render_category(categories[i], i, report)

