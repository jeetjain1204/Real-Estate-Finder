from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from realestate_finder.graph import (
    checkpoint_path,
    compile_graph,
    load_checkpoint_state,
    reset_buyer_checkpoint,
    run_recommendation_session,
    save_feedback,
)
from realestate_finder.models import FeedbackEvent, PREFERENCE_DIMENSIONS
from realestate_finder.ui_helpers import (
    QUICK_FEEDBACK_COMMENTS,
    preference_drift_rows,
    preference_summary_sentence,
)


st.set_page_config(page_title="RealEstateFinder", layout="wide")

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    }
    .block-container {
        padding-top: 2.4rem;
        max-width: 1060px;
    }
    h1, h2, h3 {
        letter-spacing: -0.03em;
        color: #1f1f1f;
    }
    .hero-eyebrow {
        color: #787774;
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .hero-title {
        color: #1f1f1f;
        font-size: 2.1rem;
        font-weight: 760;
        line-height: 1.04;
        letter-spacing: -0.055em;
        margin-bottom: 0.35rem;
    }
    .hero-copy {
        color: #6b6b66;
        max-width: 560px;
        line-height: 1.65;
        margin-bottom: 1rem;
    }
    .metric-card {
        border: 1px solid #e7e4dc;
        background: #ffffff;
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 86px;
    }
    .metric-label {
        color: #787774;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .metric-value {
        color: #1f1f1f;
        font-size: 1.28rem;
        line-height: 1.1;
        font-weight: 720;
    }
    .metric-note {
        color: #787774;
        font-size: 0.82rem;
        margin-top: 6px;
    }
    .listing-title {
        font-size: 1.08rem;
        font-weight: 720;
        color: #1f1f1f;
        letter-spacing: -0.02em;
    }
    .muted {
        color: #787774;
        font-size: 0.9rem;
        line-height: 1.55;
    }
    .score-tag {
        display: inline-block;
        border-radius: 999px;
        padding: 4px 10px;
        background: #e1f3fe;
        color: #1f6c9f;
        font-size: 0.74rem;
        font-weight: 720;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .amenity-tag {
        display: inline-block;
        border-radius: 999px;
        padding: 3px 9px;
        margin: 0 4px 4px 0;
        background: #f7f6f3;
        color: #6b6b66;
        border: 1px solid #e7e4dc;
        font-size: 0.76rem;
    }
    .why-box {
        border-left: 2px solid #d8d3c8;
        padding-left: 12px;
        color: #3f3f3b;
        font-size: 0.9rem;
        line-height: 1.55;
        margin: 10px 0 12px 0;
    }
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        border: 1px solid #d8d3c8;
        box-shadow: none;
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #111111;
        border-color: #111111;
        color: #ffffff;
    }
    section[data-testid="stSidebar"] {
        background: #f1efe9;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #e7e4dc;
        border-radius: 10px;
        background: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_graph():
    return compile_graph()


graph = get_graph()

with st.sidebar:
    st.header("Buyer")
    buyer_id = st.text_input("Thread", value="demo-buyer", label_visibility="collapsed")
    with st.expander("Demo", expanded=False):
        if st.button("Fresh start", use_container_width=True):
            reset_buyer_checkpoint(buyer_id)
            st.cache_resource.clear()
            st.rerun()
        if st.button("Run session", use_container_width=True):
            current_state = load_checkpoint_state(graph, buyer_id)
            current_state = run_recommendation_session(graph, buyer_id, current_state)
            st.rerun()
        if st.button("Apply too-dark feedback", use_container_width=True):
            current_state = load_checkpoint_state(graph, buyer_id)
            if current_state.ranked_listings:
                feedback = [
                    FeedbackEvent(
                        listing_id=item.listing.listing_id,
                        rating="down",
                        comment="This felt too dark and did not have enough natural light.",
                    )
                    for item in current_state.ranked_listings[:3]
                ]
                save_feedback(graph, buyer_id, feedback)
                st.rerun()
        if st.button("Apply strong yes", use_container_width=True):
            current_state = load_checkpoint_state(graph, buyer_id)
            if current_state.ranked_listings:
                feedback = [
                    FeedbackEvent(
                        listing_id=item.listing.listing_id,
                        rating="up",
                        comment="Strong yes: bright, practical, and a good fit.",
                    )
                    for item in current_state.ranked_listings[:4]
                ]
                save_feedback(graph, buyer_id, feedback)
                st.rerun()
    if st.button("Reset buyer", use_container_width=True):
        reset_buyer_checkpoint(buyer_id)
        st.cache_resource.clear()
        st.rerun()

state = load_checkpoint_state(graph, buyer_id)

drift_rows = preference_drift_rows(state)
strongest_drift = drift_rows[0] if drift_rows else {"Dimension": "None", "Change": 0.0}

st.markdown(
    """
    <div class="hero-eyebrow">Persistent buyer memory</div>
    <div class="hero-title">RealEstateFinder</div>
    <div class="hero-copy">
        Remembers buyer taste across sessions and ranks the next shortlist from learned preferences.
    </div>
    """,
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
metrics = [
    ("Session", str(state.session_count), "SQLite checkpoint"),
    ("Shortlist", f"{len(state.ranked_listings[:5])}", "Current homes"),
    ("Feedback", str(len(state.feedback_log)), "Saved reactions"),
    (
        "Strongest drift",
        f"{strongest_drift['Dimension']} {float(strongest_drift['Change']):+.2f}",
        preference_summary_sentence(state),
    ),
]
for column, (label, value, note) in zip(metric_cols, metrics):
    with column:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-note">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")
action_col, proof_col = st.columns([1, 2])
with action_col:
    if st.button("Next session", type="primary", use_container_width=True):
        state = run_recommendation_session(graph, buyer_id, state)
        st.rerun()
with proof_col:
    st.caption(f"`{buyer_id}` | updated `{state.last_updated.strftime('%d %b, %I:%M %p')}`")

left, right = st.columns([1.75, 1], gap="large")

with right:
    st.subheader("Memory")
    max_weight = max(state.preference_weights.values()) if state.preference_weights else 1.0
    for dimension in PREFERENCE_DIMENSIONS:
        value = state.preference_weights.get(dimension, 1.0)
        st.progress(min(1.0, value / max_weight), text=f"{dimension.title()}: {value:.2f}")

    drift_df = pd.DataFrame(preference_drift_rows(state))
    with st.expander("Drift"):
        st.bar_chart(drift_df.set_index("Dimension")["Change"])
        st.dataframe(drift_df, hide_index=True, use_container_width=True)

    st.subheader("Profile")
    st.caption(f"{state.buyer_profile.city} | INR {state.buyer_profile.budget / 10_000_000:.2f} Cr")
    for requirement in state.buyer_profile.hard_requirements:
        st.write(f"- {requirement}")

    with st.expander("Log"):
        st.write(f"Feedback: **{len(state.feedback_log)}**")
        if state.last_update_rationale:
            st.info(state.last_update_rationale)

    with st.expander("Checkpoint"):
        st.write(f"Buyer thread id: `{buyer_id}`")
        st.write(f"Checkpoint DB: `{checkpoint_path()}`")
        st.write(f"Seen listings: `{len(state.seen_listings)}`")
        if state.seen_listings:
            st.caption(", ".join(state.seen_listings[-10:]))

with left:
    st.subheader("Homes")
    if not state.ranked_listings:
        st.info("Run a session to create the first shortlist.")
    else:
        for index, item in enumerate(state.ranked_listings[:5], start=1):
            listing = item.listing
            price_cr = listing.price / 10_000_000
            with st.container(border=True):
                header_left, header_right = st.columns([4.4, 1])
                with header_left:
                    st.markdown(f"<div class='listing-title'>{index}. {listing.title}</div>", unsafe_allow_html=True)
                    st.markdown(
                        f"<div class='muted'>{listing.neighborhood} | {listing.bedrooms} BHK | "
                        f"{listing.area_sqft} sqft | INR {price_cr:.2f} Cr</div>",
                        unsafe_allow_html=True,
                    )
                with header_right:
                    st.markdown(f"<span class='score-tag'>{item.score:.2f} match</span>", unsafe_allow_html=True)

                st.markdown(f"<div class='why-box'>{item.explanation}</div>", unsafe_allow_html=True)
                st.markdown(
                    " ".join(f"<span class='amenity-tag'>{amenity}</span>" for amenity in listing.amenities),
                    unsafe_allow_html=True,
                )

                with st.expander("Feedback"):
                    with st.form(f"feedback_{listing.listing_id}_{state.session_count}", clear_on_submit=False):
                        feedback_cols = st.columns([1.1, 1.25, 1.65])
                        with feedback_cols[0]:
                            rating = st.radio(
                                "Reaction",
                                options=["not rated", "up", "down"],
                                format_func=lambda value: {
                                    "not rated": "Skip",
                                    "up": "Like",
                                    "down": "Pass",
                                }[value],
                                horizontal=False,
                                key=f"rating_{listing.listing_id}_{state.session_count}",
                            )
                        with feedback_cols[1]:
                            quick_reason = st.selectbox(
                                "Reason",
                                options=["Custom", *QUICK_FEEDBACK_COMMENTS.keys()],
                                key=f"quick_{listing.listing_id}_{state.session_count}",
                            )
                        with feedback_cols[2]:
                            comment = st.text_area(
                                "Note",
                                placeholder="Optional",
                                height=80,
                                key=f"comment_{listing.listing_id}_{state.session_count}",
                            )
                        submitted = st.form_submit_button("Save")
                        if submitted:
                            selected_comment = comment.strip()
                            if not selected_comment and quick_reason != "Custom":
                                selected_comment = QUICK_FEEDBACK_COMMENTS[quick_reason]
                            if rating == "not rated":
                                st.error("Pick Like or Pass.")
                            elif not selected_comment:
                                st.error("Pick a reason or add a note.")
                            else:
                                state = save_feedback(
                                    graph,
                                    buyer_id,
                                    [
                                        FeedbackEvent(
                                            listing_id=listing.listing_id,
                                            rating=rating,
                                            comment=selected_comment,
                                        )
                                    ],
                                )
                                st.success("Saved.")
                                st.rerun()

