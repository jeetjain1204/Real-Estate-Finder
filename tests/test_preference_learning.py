from __future__ import annotations

from realestate_finder.listings import SYNTHETIC_LISTINGS
from realestate_finder.models import BuyerPreferenceState, FeedbackEvent, ListingScore, PREFERENCE_DIMENSIONS
from realestate_finder.nodes import matcher, preference_updater, ranker, state_saver


def test_initial_state_has_required_preference_dimensions():
    state = BuyerPreferenceState()
    assert set(state.preference_weights) == set(PREFERENCE_DIMENSIONS)
    assert state.session_count == 0


def test_matcher_prioritises_light_when_light_weight_is_high():
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:4],
        preference_weights={"price": 0.5, "size": 0.5, "location": 0.5, "light": 3.0, "age": 0.5, "amenities": 0.5},
    )
    result = matcher(state)
    updated = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **result})
    assert updated.ranked_listings[0].listing.feature_scores["light"] >= 0.95


def test_ranker_returns_top_five_and_marks_seen():
    ranked = [ListingScore(listing=listing, score=1.0, explanation="test") for listing in SYNTHETIC_LISTINGS[:7]]
    state = BuyerPreferenceState(ranked_listings=ranked)
    result = ranker(state)
    updated = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **result})
    assert len(updated.ranked_listings) == 5
    assert len(result["seen_listings"]) == 5


def test_feedback_about_dark_homes_increases_light_weight(monkeypatch):
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
    assert result["preference_weights"]["light"] > state.preference_weights["light"]


def test_state_saver_increments_only_recommendation_sessions():
    recommend_state = BuyerPreferenceState(graph_action="recommend", session_count=2)
    feedback_state = BuyerPreferenceState(graph_action="feedback", session_count=2)
    assert state_saver(recommend_state)["session_count"] == 3
    assert "session_count" not in state_saver(feedback_state)

