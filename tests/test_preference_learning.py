from __future__ import annotations

import builtins

from realestate_finder.listings import DATASET_SOURCE_URL, SYNTHETIC_LISTINGS, load_dataset_listings
from realestate_finder.models import (
    BuyerPreferenceState,
    CoupleProfile,
    FeedbackEvent,
    ListingScore,
    PREFERENCE_DIMENSIONS,
    PreferenceDelta,
)
from realestate_finder import nodes
from realestate_finder.nodes import matcher, preference_updater, ranker, state_saver
from realestate_finder.ui_helpers import buyer_profile_for, buyer_selector_options


def test_initial_state_has_required_preference_dimensions():
    state = BuyerPreferenceState()
    assert set(state.preference_weights) == set(PREFERENCE_DIMENSIONS)
    assert state.session_count == 0


def test_public_dataset_loads_into_listing_model():
    listings = load_dataset_listings()
    assert DATASET_SOURCE_URL.startswith("https://github.com/")
    assert len(listings) > 100
    assert listings[0].city == "Bengaluru"
    assert listings[0].price > 1_000_000
    assert {"price", "size", "location", "light", "age", "amenities"} == set(listings[0].feature_scores)


def test_matcher_prioritises_light_when_light_weight_is_high():
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:4],
        preference_weights={"price": 0.5, "size": 0.5, "location": 0.5, "light": 3.0, "age": 0.5, "amenities": 0.5},
    )
    matched = matcher(state)
    matched_state = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matched})
    result = ranker(matched_state)
    updated = BuyerPreferenceState.model_validate({**matched_state.model_dump(mode="python"), **result})
    assert updated.ranked_listings[0].listing.feature_scores["light"] >= 0.95


def test_ranker_returns_top_five_and_marks_seen():
    state = BuyerPreferenceState(current_listings=SYNTHETIC_LISTINGS[:7])
    result = ranker(state)
    updated = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **result})
    assert len(updated.ranked_listings) == 5
    assert len(result["seen_listings"]) == 5


def test_ranker_avoids_seen_listings_while_unseen_options_remain():
    seen_ids = [listing.listing_id for listing in SYNTHETIC_LISTINGS[:5]]
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:12],
        seen_listings=seen_ids,
    )

    result = ranker(state)
    ranked_ids = [item["listing"]["listing_id"] for item in result["ranked_listings"]]

    assert len(ranked_ids) == 5
    assert set(ranked_ids).isdisjoint(seen_ids)


def test_buyer_selector_exposes_multiple_named_profiles():
    options = buyer_selector_options()

    assert len(options) >= 3
    assert "demo-buyer" in options
    assert buyer_profile_for("budget-buyer").budget < buyer_profile_for("premium-family").budget


def test_buyer_memory_parameters_differ_by_preset_persona():
    budget = buyer_profile_for("budget-buyer").memory
    premium = buyer_profile_for("premium-family").memory
    commute = buyer_profile_for("commute-first").memory
    assert budget.preference_delta_cap < premium.preference_delta_cap
    assert budget.feedback_history_window > premium.feedback_history_window
    assert commute.feedback_history_window not in (budget.feedback_history_window, premium.feedback_history_window)


def test_clamp_delta_uses_per_buyer_cap():
    delta = PreferenceDelta(deltas={"light": 0.5, "price": -0.6}, rationale="test")
    budget_cap = buyer_profile_for("budget-buyer").memory.preference_delta_cap
    clamped = nodes._clamp_delta(delta, budget_cap)
    assert clamped.deltas["light"] == budget_cap
    assert clamped.deltas["price"] == -budget_cap


def test_feedback_requires_gemini_key_without_keyword_learning(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    listing = SYNTHETIC_LISTINGS[1]
    state = BuyerPreferenceState(
        ranked_listings=[ListingScore(listing=listing, score=0.5, explanation="test")],
        incoming_feedback=[
            FeedbackEvent(
                listing_id=listing.listing_id,
                rating="down",
                comment="This felt too dark and had limited windows.",
            )
        ],
    )
    result = preference_updater(state)
    assert "GOOGLE_API_KEY" in result["learning_error"]
    assert "preference_weights" not in result


def test_feedback_reports_missing_gemini_dependency_with_setup_guidance(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langchain_google_genai":
            raise ModuleNotFoundError("No module named 'langchain_google_genai'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    state = BuyerPreferenceState(
        incoming_feedback=[
            FeedbackEvent(
                listing_id="BLR-001",
                rating="down",
                comment="Too dark.",
            )
        ],
    )

    result = preference_updater(state)

    assert "langchain-google-genai" in result["learning_error"]
    assert "python -m streamlit run app.py" in result["learning_error"]


def test_feedback_updates_weights_with_injected_llm_delta(monkeypatch):
    listing = SYNTHETIC_LISTINGS[1]
    state = BuyerPreferenceState(
        ranked_listings=[],
        incoming_feedback=[
            FeedbackEvent(
                listing_id=listing.listing_id,
                rating="down",
                comment="This felt too dark and had limited windows.",
            )
        ],
    )

    def fake_delta(*args, **kwargs):
        return PreferenceDelta(deltas={"light": 0.25}, rationale="Buyer disliked dark homes.")

    monkeypatch.setattr(nodes, "_infer_preference_delta_with_llm", fake_delta)
    result = nodes.preference_updater(state)
    assert result["preference_weights"]["light"] > state.preference_weights["light"]


def test_state_saver_increments_only_recommendation_sessions():
    recommend_state = BuyerPreferenceState(graph_action="recommend", session_count=2)
    feedback_state = BuyerPreferenceState(graph_action="feedback", session_count=2)
    assert state_saver(recommend_state)["session_count"] == 3
    assert "session_count" not in state_saver(feedback_state)


def test_couple_mode_ranking_does_not_overwrite_saved_conflict_notes():
    baseline = {dim: 1.0 for dim in PREFERENCE_DIMENSIONS}
    coupled = CoupleProfile(
        enabled=True,
        partner_a_weights={**baseline, "light": 2.5},
        partner_b_weights={**baseline, "light": 1.0},
        conflict_notes=["Saved from UI: light sliders disagree"],
    )
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:10],
        couple_profile=coupled,
    )
    ranker(state)
    assert state.couple_profile.conflict_notes == ["Saved from UI: light sliders disagree"]

