from __future__ import annotations

from realestate_finder.graph import compile_graph, run_recommendation_session, save_feedback
from realestate_finder.models import FeedbackEvent


BUYER_ID = "demo-buyer"


def print_state(label, state):
    print(f"\n=== {label} ===")
    print(f"Session count: {state.session_count}")
    print(f"Preference weights: {state.preference_weights}")
    print("Top recommendations:")
    for item in state.ranked_listings:
        listing = item.listing
        print(f"- {listing.listing_id}: {listing.title} | score={item.score}")


def feedback_for_session(state, session_number: int) -> list[FeedbackEvent]:
    top_ids = [item.listing.listing_id for item in state.ranked_listings[:5]]
    if session_number == 1:
        return [
            FeedbackEvent(listing_id=top_ids[0], rating="down", comment="It is good but still not bright enough for us."),
            FeedbackEvent(listing_id=top_ids[1], rating="down", comment="The apartment feels too dark and closed in."),
            FeedbackEvent(listing_id=top_ids[2], rating="down", comment="Limited windows, we really care about natural light."),
        ]
    if session_number == 2:
        return [
            FeedbackEvent(listing_id=top_ids[0], rating="up", comment="Loved the big windows and natural light."),
            FeedbackEvent(listing_id=top_ids[1], rating="up", comment="Good sunlight and location works well."),
            FeedbackEvent(listing_id=top_ids[2], rating="down", comment="Nice amenities but commute is too far."),
        ]
    return [
        FeedbackEvent(listing_id=listing_id, rating="up", comment="Strong yes: bright, practical, and a good fit.")
        for listing_id in top_ids[:4]
    ]


def main():
    graph = compile_graph()
    print("This script uses the same local SQLite checkpointer as Streamlit.")
    print("Run it multiple times to show that session_count and weights persist after process restart.")

    for session_number in range(1, 4):
        state = run_recommendation_session(graph, BUYER_ID)
        print_state(f"Recommendation Session {session_number}", state)
        state = save_feedback(graph, BUYER_ID, feedback_for_session(state, session_number))
        print_state(f"After Feedback {session_number}", state)


if __name__ == "__main__":
    main()

