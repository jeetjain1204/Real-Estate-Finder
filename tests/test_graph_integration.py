from __future__ import annotations

from realestate_finder.graph import compile_graph, load_checkpoint_state, reset_buyer_checkpoint, run_recommendation_session, save_feedback
from realestate_finder.models import BuyerPreferenceState, FeedbackEvent
from realestate_finder.nodes import matcher, ranker


def test_sqlite_checkpoint_survives_graph_recompile(tmp_path):
    db_path = tmp_path / "checkpoint.sqlite"
    graph = compile_graph(db_path)
    state = run_recommendation_session(graph, "restart-buyer")

    recompiled_graph = compile_graph(db_path)
    restored = load_checkpoint_state(recompiled_graph, "restart-buyer")

    assert restored.session_count == state.session_count
    assert len(restored.ranked_listings) == 5
    assert restored.last_updated is not None


def test_recommendation_path_returns_five_listings_for_four_sessions(tmp_path):
    graph = compile_graph(tmp_path / "checkpoint.sqlite")
    buyer_id = "long-demo-buyer"
    reset_buyer_checkpoint(buyer_id, tmp_path / "checkpoint.sqlite")

    counts = []
    for _ in range(4):
        state = run_recommendation_session(graph, buyer_id)
        counts.append(len(state.ranked_listings))

    assert counts == [5, 5, 5, 5]


def test_hard_requirements_remove_ineligible_listings():
    state = BuyerPreferenceState(current_listings=[])
    state.current_listings = [
        listing.model_copy(update={"listing_id": f"copy-{index}"})
        for index, listing in enumerate([])
    ]

    from realestate_finder.listings import SYNTHETIC_LISTINGS

    state.current_listings = SYNTHETIC_LISTINGS[:12]
    matched = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matcher(state)})

    assert all(listing.bedrooms >= state.buyer_profile.min_bedrooms for listing in matched.current_listings)
    assert all("covered parking" in [amenity.lower() for amenity in listing.amenities] for listing in matched.current_listings)


def test_feedback_path_does_not_increment_session_without_gemini(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    graph = compile_graph(tmp_path / "checkpoint.sqlite")
    state = run_recommendation_session(graph, "feedback-route")
    listing_id = state.ranked_listings[0].listing.listing_id

    updated = save_feedback(
        graph,
        "feedback-route",
        [FeedbackEvent(listing_id=listing_id, rating="down", comment="Too dark")],
    )

    assert updated.session_count == 1
    assert updated.learning_error
    assert len(updated.feedback_log) == 1


def test_explanations_reference_feedback_history():
    from realestate_finder.listings import SYNTHETIC_LISTINGS

    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:10],
        feedback_log=[
            FeedbackEvent(listing_id="BLR-002", rating="down", comment="Too dark and closed in"),
        ],
    )
    matched = BuyerPreferenceState.model_validate({**state.model_dump(mode="python"), **matcher(state)})
    ranked = BuyerPreferenceState.model_validate({**matched.model_dump(mode="python"), **ranker(matched)})

    assert "natural light" in ranked.ranked_listings[0].explanation
    assert ranked.ranked_listings[0].fair_price_estimate is not None
