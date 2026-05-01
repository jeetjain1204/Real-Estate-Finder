"""Evaluation framework: 5 representative buyer scenarios with expected behaviours.

Each test below corresponds to one realistic buyer scenario. Together they form
the evaluation suite referenced in the project deliverables.

Scenario index
--------------
1. Cold-start buyer sees five generic listings ordered by balanced weights.
2. Light-sensitive buyer (downvoted dark homes) is shown brighter homes next session.
3. Budget-constrained buyer has high-price listings filtered by hard requirements.
4. Couple with conflicting preferences sees blended scores with conflicts flagged.
5. Multi-session buyer shows measurable preference drift across three sessions.
"""
from __future__ import annotations

import pytest

from realestate_finder.graph import (
    compile_graph,
    load_checkpoint_state,
    reset_buyer_checkpoint,
    run_recommendation_session,
    save_feedback,
)
from realestate_finder.listings import SYNTHETIC_LISTINGS
from realestate_finder.models import (
    BuyerPreferenceState,
    CoupleProfile,
    FeedbackEvent,
    PREFERENCE_DIMENSIONS,
)
from realestate_finder.nodes import matcher, preference_updater, ranker


# ---------------------------------------------------------------------------
# Scenario 1: Cold-start buyer — expects 5 listings with equal initial weights
# ---------------------------------------------------------------------------

def test_scenario_cold_start_returns_five_balanced_listings(tmp_path):
    """A brand-new buyer with no history should receive exactly 5 listings.

    The initial preference weights are all 1.0, so the ranking reflects
    a balanced view of all dimensions, not a biased one.
    """
    graph = compile_graph(tmp_path / "eval1.sqlite")
    buyer_id = "eval-cold-start"

    state = run_recommendation_session(graph, buyer_id)

    assert len(state.ranked_listings) == 5, "Cold-start session must return exactly 5 listings"
    initial_weights = {d: 1.0 for d in PREFERENCE_DIMENSIONS}
    assert state.preference_weights == initial_weights, "Weights must be unchanged on cold start"
    assert state.session_count == 1


# ---------------------------------------------------------------------------
# Scenario 2: Light-sensitive buyer — dark-home downvotes raise light weight
# ---------------------------------------------------------------------------

def test_scenario_light_sensitive_buyer_shifts_light_weight(monkeypatch):
    """After downvoting dark homes, the light dimension weight must increase.

    This tests that feedback actually reaches the preference updater and
    changes the weights in the correct direction.
    """
    from realestate_finder import nodes
    from realestate_finder.models import ListingScore, PreferenceDelta

    dark_listing = next(l for l in SYNTHETIC_LISTINGS if l.feature_scores["light"] < 0.55)
    initial_state = BuyerPreferenceState(
        ranked_listings=[ListingScore(listing=dark_listing, score=0.5, explanation="test")],
        incoming_feedback=[
            FeedbackEvent(
                listing_id=dark_listing.listing_id,
                rating="down",
                comment="Way too dark — no natural light at all.",
            )
        ],
    )

    def fake_delta(*_args, **_kwargs):
        return PreferenceDelta(deltas={"light": 0.30}, rationale="Buyer consistently downvotes dark homes.")

    monkeypatch.setattr(nodes, "_infer_preference_delta_with_llm", fake_delta)
    result = nodes.preference_updater(initial_state)

    assert result["preference_weights"]["light"] > initial_state.preference_weights["light"], (
        "Light weight must increase after downvoting a dark listing"
    )


# ---------------------------------------------------------------------------
# Scenario 3: Budget-constrained buyer — expensive listings filtered out
# ---------------------------------------------------------------------------

def test_scenario_hard_budget_requirement_filters_overpriced_listings():
    """Listings priced above 1.25× the buyer's budget must never reach the shortlist.

    Hard requirements (budget band) are applied in listing_fetcher, not in
    the matcher, so this tests the full pipeline up to the matcher stage.
    """
    from realestate_finder.listings import fetch_broad_listings

    tight_budget = 12_000_000  # INR 1.2 Cr — filters most BASE_LISTINGS
    candidates = fetch_broad_listings(
        city="Bengaluru",
        budget=tight_budget,
        seen_listing_ids=[],
    )
    budget_limit = int(tight_budget * 1.25)
    assert all(listing.price <= budget_limit for listing in candidates), (
        "All candidates returned by fetch_broad_listings must be within 1.25× budget"
    )
    assert len(candidates) >= 5, "Must still return enough listings for a full shortlist"


# ---------------------------------------------------------------------------
# Scenario 4: Couple mode — conflicting preferences flagged correctly
# ---------------------------------------------------------------------------

def test_scenario_couple_mode_flags_conflicts_and_blends_weights():
    """When two partners disagree on a dimension by >= 0.7, a conflict must be logged.

    The blended weight should be the midpoint of the two partner weights.
    """
    state = BuyerPreferenceState(
        current_listings=SYNTHETIC_LISTINGS[:6],
        couple_profile=CoupleProfile(
            enabled=True,
            partner_a_weights={dim: 1.0 for dim in PREFERENCE_DIMENSIONS} | {"light": 3.0, "size": 2.5},
            partner_b_weights={dim: 1.0 for dim in PREFERENCE_DIMENSIONS} | {"light": 1.0, "size": 1.0},
        ),
    )
    matched = BuyerPreferenceState.model_validate(
        {**state.model_dump(mode="python"), **matcher(state)}
    )

    conflict_dims = {note.split(":")[0] for note in matched.couple_profile.conflict_notes}
    assert "light" in conflict_dims, "Conflict expected on 'light' (delta = 2.0 >= 0.7)"
    assert "size" in conflict_dims, "Conflict expected on 'size' (delta = 1.5 >= 0.7)"

    # Verify blended weight is midpoint
    from realestate_finder.nodes import _reconciled_weights
    blended, _ = _reconciled_weights(state.preference_weights, state)
    assert blended["light"] == pytest.approx((3.0 + 1.0) / 2, abs=0.01), (
        "Blended light weight must be the mean of partner A and partner B"
    )


# ---------------------------------------------------------------------------
# Scenario 5: Multi-session preference drift — three sessions show evolution
# ---------------------------------------------------------------------------

def test_scenario_three_sessions_show_measurable_preference_drift(tmp_path, monkeypatch):
    """After two rounds of 'too dark' feedback, the light weight must drift upward.

    This is the end-to-end proof of the persistent-state pattern: session 1
    sets baseline weights, two feedback rounds increase the light weight,
    session 2 should show a higher light weight than session 1.
    """
    from realestate_finder import nodes
    from realestate_finder.models import PreferenceDelta

    call_count = 0

    def fake_delta(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return PreferenceDelta(
            deltas={"light": 0.25},
            rationale=f"Buyer keeps downvoting dark homes (call {call_count}).",
        )

    monkeypatch.setattr(nodes, "_infer_preference_delta_with_llm", fake_delta)

    graph = compile_graph(tmp_path / "eval5.sqlite")
    buyer_id = "eval-drift"

    # Session 1 — cold start
    state_after_s1 = run_recommendation_session(graph, buyer_id)
    light_after_s1 = state_after_s1.preference_weights["light"]

    # Feedback round 1 — downvote dark listings
    fb1 = [
        FeedbackEvent(
            listing_id=item.listing.listing_id,
            rating="down",
            comment="Too dark, not enough windows.",
        )
        for item in state_after_s1.ranked_listings[:3]
    ]
    state_after_fb1 = save_feedback(graph, buyer_id, fb1)
    light_after_fb1 = state_after_fb1.preference_weights["light"]

    # Feedback round 2 — downvote again
    fb2 = [
        FeedbackEvent(
            listing_id=item.listing.listing_id,
            rating="down",
            comment="Still too dark.",
        )
        for item in state_after_s1.ranked_listings[:2]
    ]
    state_after_fb2 = save_feedback(graph, buyer_id, fb2)
    light_after_fb2 = state_after_fb2.preference_weights["light"]

    # Session 2 — should use drifted weights
    state_after_s2 = run_recommendation_session(graph, buyer_id)
    light_after_s2 = state_after_s2.preference_weights["light"]

    assert light_after_fb1 > light_after_s1, "Light weight must increase after first dark-home downvote"
    assert light_after_fb2 >= light_after_fb1, "Light weight must not decrease with repeated dark-home downvotes"
    assert light_after_s2 == light_after_fb2, "Session 2 must load drifted weights from SQLite checkpoint"
    assert state_after_s2.session_count == 2, "Session counter must be 2 after two recommendation sessions"
