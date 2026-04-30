from __future__ import annotations

from realestate_finder.models import BuyerPreferenceState
from realestate_finder.ui_helpers import (
    QUICK_FEEDBACK_COMMENTS,
    checkpoint_tables_for_reset,
    preference_drift_rows,
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


def test_quick_feedback_comments_cover_common_buyer_reasons():
    labels = set(QUICK_FEEDBACK_COMMENTS)

    assert {"Too dark", "Great location", "Too expensive", "Loved amenities"}.issubset(labels)


def test_checkpoint_tables_for_reset_are_limited_to_langgraph_checkpoint_tables():
    tables = checkpoint_tables_for_reset()

    assert set(tables) == {"checkpoints", "checkpoint_blobs", "checkpoint_writes"}
