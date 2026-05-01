from __future__ import annotations

from realestate_finder.models import (
    BuyerMemoryParameters,
    BuyerPreferenceState,
    BuyerProfile,
    PREFERENCE_DIMENSIONS,
)


DEMO_BUYERS: dict[str, tuple[str, BuyerProfile]] = {
    "demo-buyer": (
        "Demo buyer - balanced 2 BHK",
        BuyerProfile(),
    ),
    "budget-buyer": (
        "Budget buyer - value focused",
        BuyerProfile(
            budget=12_500_000,
            min_bedrooms=2,
            required_amenities=["covered parking"],
            hard_requirements=["2+ bedrooms", "covered parking", "under 1.25 Cr"],
            memory=BuyerMemoryParameters(
                feedback_history_window=10,
                preference_delta_cap=0.2,
                weight_floor=0.12,
                weight_ceiling=2.6,
            ),
        ),
    ),
    "premium-family": (
        "Premium family - larger homes",
        BuyerProfile(
            budget=24_000_000,
            min_bedrooms=3,
            required_amenities=["covered parking"],
            hard_requirements=["3+ bedrooms", "covered parking", "premium family neighborhood"],
            memory=BuyerMemoryParameters(
                feedback_history_window=6,
                preference_delta_cap=0.4,
                weight_floor=0.08,
                weight_ceiling=3.5,
            ),
        ),
    ),
    "commute-first": (
        "Commute-first buyer - central locations",
        BuyerProfile(
            budget=18_500_000,
            min_bedrooms=2,
            required_amenities=["covered parking"],
            hard_requirements=["2+ bedrooms", "covered parking", "short central commute"],
            memory=BuyerMemoryParameters(
                feedback_history_window=9,
                preference_delta_cap=0.28,
                weight_floor=0.1,
                weight_ceiling=3.2,
            ),
        ),
    ),
}


# Short labels map to full comments sent to preference learning (aligned with PREFERENCE_DIMENSIONS).
QUICK_FEEDBACK_COMMENTS_BY_REACTION: dict[str, dict[str, str]] = {
    "up": {
        "Price — value feels right": "The price felt fair and we liked the value on offer.",
        "Size — fits our needs": "The size and layout feel right for how we live.",
        "Location — commute works": "Great location and the commute works well for us.",
        "Light — bright and airy": "We love how bright and airy the home felt.",
        "Age — modern, well kept": "The age and condition feel right and well maintained.",
        "Amenities — love facilities": "Loved the amenities and community facilities.",
    },
    "down": {
        "Price — too expensive": "This feels too expensive for the value on offer.",
        "Size — too small": "The home feels too small for our needs.",
        "Size — too large or impractical": "The home feels larger or more impractical than we want.",
        "Location — commute or area": "The location or commute does not work for us.",
        "Light — too dark": "This felt too dark and did not have enough natural light.",
        "Age — too old or heavy upkeep": "The property feels too old and may need too much upkeep.",
        "Amenities — missing what we need": "Amenities or facilities are missing what we need.",
    },
}

QUICK_FEEDBACK_COMMENTS = {
    label: comment
    for comments_by_reason in QUICK_FEEDBACK_COMMENTS_BY_REACTION.values()
    for label, comment in comments_by_reason.items()
}


def quick_feedback_options_for(reaction: str | None) -> list[str]:
    if reaction not in QUICK_FEEDBACK_COMMENTS_BY_REACTION:
        return []
    return ["Custom", *QUICK_FEEDBACK_COMMENTS_BY_REACTION[reaction]]


def quick_feedback_comment_for(reaction: str | None, reason: str) -> str:
    if reaction not in QUICK_FEEDBACK_COMMENTS_BY_REACTION:
        return ""
    return QUICK_FEEDBACK_COMMENTS_BY_REACTION[reaction].get(reason, "")


def buyer_selector_options() -> dict[str, str]:
    return {buyer_id: label for buyer_id, (label, _profile) in DEMO_BUYERS.items()}


def buyer_profile_for(buyer_id: str) -> BuyerProfile:
    _label, profile = DEMO_BUYERS.get(buyer_id, DEMO_BUYERS["demo-buyer"])
    return profile.model_copy(deep=True)


def repair_preset_buyer_profile_if_stale(state: BuyerPreferenceState, buyer_id: str) -> bool:
    """If checkpoint state does not match the sidebar preset, fix profile and clear the shortlist.

    Preset threads used to keep the default BuyerProfile after sessions started, so budget and
    bedroom filters never applied. Returns True when state was modified in place.
    """
    expected = buyer_profile_for(buyer_id)
    if state.buyer_profile.model_dump() == expected.model_dump():
        return False
    state.buyer_profile = expected
    state.ranked_listings = []
    return True


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

