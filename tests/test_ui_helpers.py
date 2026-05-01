from __future__ import annotations

from realestate_finder.models import PREFERENCE_DIMENSIONS, BuyerPreferenceState, ListingScore
from realestate_finder.listings import SYNTHETIC_LISTINGS
from realestate_finder.ui_helpers import (
    QUICK_FEEDBACK_COMMENTS,
    QUICK_FEEDBACK_COMMENTS_BY_REACTION,
    buyer_profile_for,
    checkpoint_tables_for_reset,
    preference_drift_rows,
    quick_feedback_comment_for,
    quick_feedback_options_for,
    repair_preset_buyer_profile_if_stale,
)


def test_preference_drift_rows_compare_baseline_to_current_weights():
    state = BuyerPreferenceState(
        preference_weights={
            "price": 0.8,
            "size": 1.0,
            "location": 1.1,
            "light": 1.4,
            "age": 0.8,
            "amenities": 0.9,
        }
    )

    rows = preference_drift_rows(state)

    assert rows[0]["Dimension"] == "Light"
    assert rows[0]["Change"] == 0.4
    assert {"Dimension": "Price", "Baseline": 1.0, "Current": 0.8, "Change": -0.2} in rows


def test_quick_feedback_labels_cover_all_preference_dimensions():
    labels = set(QUICK_FEEDBACK_COMMENTS)

    for dimension in PREFERENCE_DIMENSIONS:
        assert any(dimension in label.lower() for label in labels)


def test_quick_feedback_options_depend_on_reaction():
    assert quick_feedback_options_for(None) == []
    assert "Location — commute works" in quick_feedback_options_for("up")
    assert "Amenities — love facilities" in quick_feedback_options_for("up")
    assert "Price — too expensive" not in quick_feedback_options_for("up")

    assert "Price — too expensive" in quick_feedback_options_for("down")
    assert "Light — too dark" in quick_feedback_options_for("down")
    assert "Location — commute works" not in quick_feedback_options_for("down")


def test_quick_feedback_comment_requires_matching_reaction_reason():
    assert quick_feedback_comment_for("down", "Light — too dark") == (
        "This felt too dark and did not have enough natural light."
    )
    assert quick_feedback_comment_for("up", "Light — too dark") == ""
    assert quick_feedback_comment_for(None, "Light — too dark") == ""


def test_quick_feedback_like_and_pass_each_have_six_memory_criteria_groups():
    up_labels = {label.lower() for label in QUICK_FEEDBACK_COMMENTS_BY_REACTION["up"]}
    down_labels = {label.lower() for label in QUICK_FEEDBACK_COMMENTS_BY_REACTION["down"]}
    for dimension in PREFERENCE_DIMENSIONS:
        assert any(dimension in label for label in up_labels)
        assert any(dimension in label for label in down_labels)


def test_repair_preset_buyer_profile_clears_shortlist_when_checkpoint_profile_wrong():
    listing = SYNTHETIC_LISTINGS[0]
    state = BuyerPreferenceState(
        buyer_profile=buyer_profile_for("demo-buyer"),
        ranked_listings=[ListingScore(listing=listing, score=0.5, explanation="x")],
        session_count=3,
    )

    assert repair_preset_buyer_profile_if_stale(state, "budget-buyer") is True
    assert state.buyer_profile.budget == 12_500_000
    assert state.ranked_listings == []


def test_repair_preset_buyer_profile_noop_when_already_aligned():
    state = BuyerPreferenceState(buyer_profile=buyer_profile_for("budget-buyer"))

    assert repair_preset_buyer_profile_if_stale(state, "budget-buyer") is False


def test_checkpoint_tables_for_reset_are_limited_to_langgraph_checkpoint_tables():
    tables = checkpoint_tables_for_reset()

    assert set(tables) == {"checkpoints", "checkpoint_blobs", "checkpoint_writes"}
