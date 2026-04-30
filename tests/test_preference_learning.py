from __future__ import annotations

from realestate_finder.listings import SYNTHETIC_LISTINGS
from realestate_finder.models import (
    BuyerPreferenceState,
    CoupleProfile,
    FeedbackEvent,
    ListingScore,
    PREFERENCE_DIMENSIONS,
    PreferenceDelta,
)
from realestate_finder import nodes
from realestate_finder.nodes import (
    _estimate_fair_price,
    _fair_price_note,
    matcher,
    preference_updater,
    ranker,
    state_saver,
)


def test_initial_state_has_required_preference_dimensions():
    state = BuyerPreferenceState()
    assert set(state.preference_weights) == set(PREFERENCE_DIMENSIONS)
    assert state.session_count == 0


def test_matcher_prioritises_light_when_light_weight_is_high():
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:4],
        preference_weights={"price": 0.5, "size": 0.5, "location": 0.5, "light": 3.0, "age": 0.5, "amenities": 0.5},
    )
    matched = matcher(state)
    matched_state = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matched})
    result = ranker(matched_state)
    updated = BuyerPreferenceState.model_validate({**matched_state.model_dump(mode="python"), **result})
    top_light = updated.ranked_listings[0].listing.feature_scores["light"]
    best_available_light = max(item.listing.feature_scores["light"] for item in matched_state.ranked_listings)
    assert top_light == best_available_light


def test_ranker_returns_top_five_and_marks_seen():
    state = BuyerPreferenceState(current_listings=SYNTHETIC_LISTINGS[:7])
    matched = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matcher(state)})
    result = ranker(matched)
    updated = BuyerPreferenceState.model_validate({**matched.model_dump(mode="python"), **result})
    assert len(updated.ranked_listings) == 5
    assert len(result["seen_listings"]) == 5


def test_matcher_scores_listings_against_preference_weights():
    state = BuyerPreferenceState(current_listings=SYNTHETIC_LISTINGS[:4])
    matched = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matcher(state)})
    assert matched.ranked_listings, "matcher must produce scored ListingScore objects"
    assert all(0.0 <= item.score <= 1.0 for item in matched.ranked_listings)
    assert all(item.explanation for item in matched.ranked_listings)


def test_couple_mode_blends_partner_weights_and_flags_conflicts():
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:6],
        couple_profile=CoupleProfile(
            enabled=True,
            partner_a_weights={dim: 1.0 for dim in PREFERENCE_DIMENSIONS} | {"light": 3.0},
            partner_b_weights={dim: 1.0 for dim in PREFERENCE_DIMENSIONS} | {"light": 1.0},
        ),
    )
    matched = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matcher(state)})
    assert any("light" in note for note in matched.couple_profile.conflict_notes)


def test_fair_price_estimate_compares_against_synthetic_comparables():
    listing = SYNTHETIC_LISTINGS[0]
    estimate = _estimate_fair_price(listing)
    assert estimate is not None and estimate > 0
    note = _fair_price_note(listing)
    assert any(phrase in note for phrase in ("above", "below", "close to"))


def test_state_saver_tracks_first_session_and_sessions_per_week():
    state = BuyerPreferenceState(graph_action="recommend", session_count=0)
    update = state_saver(state)
    assert update["session_count"] == 1
    kpis = update["kpis"]
    assert kpis["first_session_at"] is not None
    assert kpis["buyer_engagement_sessions_per_week"] > 0


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

