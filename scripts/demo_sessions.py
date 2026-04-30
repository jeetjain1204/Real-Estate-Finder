from __future__ import annotations

from realestate_finder.graph import compile_graph, run_recommendation_session, save_feedback
from realestate_finder.models import FeedbackEvent


BUYER_ID = "demo-buyer"


def print_state(label: str, state) -> None:
    print(f"\n=== {label} ===")
    print(f"Session count  : {state.session_count}")
    print(f"Loaded from DB : {state.loaded_from_checkpoint}")
    print(f"Weights        : { {k: round(v, 3) for k, v in state.preference_weights.items()} }")
    print("Top recommendations:")
    for item in state.ranked_listings:
        listing = item.listing
        print(f"  - {listing.listing_id}: {listing.title} | score={item.score:.3f} | light={listing.feature_scores['light']:.2f}")


def feedback_for_session(state, session_number: int) -> list[FeedbackEvent]:
    top_ids = [item.listing.listing_id for item in state.ranked_listings[:5]]
    if session_number == 1:
        return [
            FeedbackEvent(listing_id=top_ids[0], rating="down", comment="Still not bright enough for us."),
            FeedbackEvent(listing_id=top_ids[1], rating="down", comment="The apartment feels too dark and closed in."),
            FeedbackEvent(listing_id=top_ids[2], rating="down", comment="Limited windows — we really care about natural light."),
        ]
    if session_number == 2:
        return [
            FeedbackEvent(listing_id=top_ids[0], rating="up", comment="Loved the big windows and natural light."),
            FeedbackEvent(listing_id=top_ids[1], rating="up", comment="Good sunlight and the location works well."),
            FeedbackEvent(listing_id=top_ids[2], rating="down", comment="Nice amenities but the commute is too far."),
        ]
    return [
        FeedbackEvent(listing_id=listing_id, rating="up", comment="Great fit — bright, practical, and well located.")
        for listing_id in top_ids[:4]
    ]


def main() -> None:
    """
    Run ONE session per script invocation.

    To demonstrate SQLite persistence across process restarts:
      1. python scripts/demo_sessions.py   → session 1 (cold start)
      2. Stop the process (Ctrl-C or let it finish).
      3. python scripts/demo_sessions.py   → session 2 (loaded_from_checkpoint=True, light weight drifted up)
      4. python scripts/demo_sessions.py   → session 3 (preferences further refined)
    """
    graph = compile_graph()

    state = run_recommendation_session(graph, BUYER_ID)
    session_number = state.session_count  # 1 after first run, 2 after second, …
    print_state(f"Recommendation — session {session_number}", state)

    feedback = feedback_for_session(state, min(session_number, 3))
    state = save_feedback(graph, BUYER_ID, feedback)
    print_state(f"After feedback  — session {session_number}", state)

    print(f"\n→ Restart this script to continue from session {state.session_count}.")
    print("  The weights above will persist in data/checkpoints.sqlite.\n")


if __name__ == "__main__":
    main()
