from __future__ import annotations

from realestate_finder.models import BuyerPreferenceState, PREFERENCE_DIMENSIONS


QUICK_FEEDBACK_COMMENTS = {
    "Too dark": "This felt too dark and did not have enough natural light.",
    "Great location": "Great location and the commute works well for us.",
    "Too expensive": "This feels too expensive for the value on offer.",
    "Too small": "The home feels too small for our needs.",
    "Too old": "The property feels too old and may need too much upkeep.",
    "Loved amenities": "Loved the amenities and community facilities.",
}


def checkpoint_tables_for_reset() -> tuple[str, str, str]:
    return ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


def preference_drift_rows(state: BuyerPreferenceState) -> list[dict[str, float | str]]:
    rows = []
    for dimension in PREFERENCE_DIMENSIONS:
        current = round(state.preference_weights.get(dimension, 1.0), 3)
        baseline = 1.0
        rows.append(
            {
                "Dimension": dimension.title(),
                "Baseline": baseline,
                "Current": current,
                "Change": round(current - baseline, 3),
            }
        )
    return sorted(rows, key=lambda row: abs(float(row["Change"])), reverse=True)


def preference_summary_sentence(state: BuyerPreferenceState) -> str:
    rows = preference_drift_rows(state)
    strongest = rows[0]
    change = float(strongest["Change"])
    if abs(change) < 0.05:
        return "The buyer is still close to the cold-start preference profile."
    direction = "more" if change > 0 else "less"
    return f"The buyer now cares {direction} about {str(strongest['Dimension']).lower()} than at cold start."

