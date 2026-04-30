from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from realestate_finder.listings import SYNTHETIC_LISTINGS, fetch_broad_listings
from realestate_finder.models import (
    BuyerPreferenceState,
    FeedbackEvent,
    Listing,
    ListingScore,
    PREFERENCE_DIMENSIONS,
    PreferenceDelta,
    normalise_weights,
)


def state_loader(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    return {"last_updated": datetime.now(timezone.utc)}


def listing_fetcher(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if state.graph_action == "feedback":
        return {"current_listings": [_dump_model(listing) for listing in state.current_listings]}

    listings = fetch_broad_listings(
        city=state.buyer_profile.city,
        budget=state.buyer_profile.budget,
        seen_listing_ids=state.seen_listings,
    )

    if len(listings) < 5:
        listings = [
            listing
            for listing in SYNTHETIC_LISTINGS
            if listing.city.lower() == state.buyer_profile.city.lower()
            and listing.listing_id not in state.seen_listings[-5:]
        ]

    return {"current_listings": [_dump_model(listing) for listing in listings]}


def matcher(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if state.graph_action == "feedback" and state.ranked_listings:
        return {"ranked_listings": [_dump_model(item) for item in state.ranked_listings]}

    ranked = [
        ListingScore(
            listing=listing,
            score=_score_listing(listing, state.preference_weights),
            explanation=_explain_match(listing, state.preference_weights),
        )
        for listing in state.current_listings
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return {"ranked_listings": [_dump_model(item) for item in ranked]}


def ranker(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if state.graph_action == "feedback":
        return {"ranked_listings": [_dump_model(item) for item in state.ranked_listings[:5]]}

    top_five = state.ranked_listings[:5]
    updated_seen = list(dict.fromkeys([*state.seen_listings, *[item.listing.listing_id for item in top_five]]))
    return {"ranked_listings": [_dump_model(item) for item in top_five], "seen_listings": updated_seen}


def presenter(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    lines = [f"### Session {state.session_count + 1} Recommendations"]
    for index, item in enumerate(state.ranked_listings[:5], start=1):
        listing = item.listing
        price_cr = listing.price / 10_000_000
        lines.extend(
            [
                f"**{index}. {listing.title}** (`{listing.listing_id}`)",
                f"- {listing.neighborhood} | {listing.bedrooms} BHK | {listing.area_sqft} sqft | INR {price_cr:.2f} Cr",
                f"- Match score: {item.score:.2f}/1.00",
                f"- Why shown: {item.explanation}",
                f"- {listing.description}",
                "",
            ]
        )
    return {"presentation_markdown": "\n".join(lines)}


def feedback_receiver(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if not state.incoming_feedback:
        return {"incoming_feedback": []}

    known_ids = {item.listing.listing_id for item in state.ranked_listings}
    accepted_feedback = [
        event for event in state.incoming_feedback if event.listing_id in known_ids and event.comment.strip()
    ]
    return {"incoming_feedback": [_dump_model(event) for event in accepted_feedback]}


def preference_updater(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if not state.incoming_feedback:
        return {"last_update_rationale": "No buyer feedback submitted in this graph turn."}

    delta = _infer_preference_delta_with_llm(
        feedback=state.incoming_feedback,
        listings=[item.listing for item in state.ranked_listings],
        current_weights=state.preference_weights,
    )
    updated_weights = dict(state.preference_weights)
    for dimension, adjustment in delta.deltas.items():
        if dimension in PREFERENCE_DIMENSIONS:
            updated_weights[dimension] = updated_weights.get(dimension, 1.0) + adjustment

    return {
        "preference_weights": normalise_weights(updated_weights),
        "feedback_log": [_dump_model(event) for event in [*state.feedback_log, *state.incoming_feedback]],
        "incoming_feedback": [],
        "last_update_rationale": delta.rationale,
    }


def state_saver(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    update = {
        "last_updated": datetime.now(timezone.utc),
        "graph_action": "recommend",
    }
    if state.graph_action == "recommend":
        update["session_count"] = state.session_count + 1
    return update


def _as_state(state: BuyerPreferenceState | dict) -> BuyerPreferenceState:
    if isinstance(state, BuyerPreferenceState):
        return state
    return BuyerPreferenceState.model_validate(state)


def _dump_model(model) -> dict:
    return model.model_dump(mode="python") if hasattr(model, "model_dump") else model


def _score_listing(listing: Listing, weights: dict[str, float]) -> float:
    weighted_total = 0.0
    weight_sum = 0.0
    for dimension in PREFERENCE_DIMENSIONS:
        weight = max(0.1, weights.get(dimension, 1.0))
        weighted_total += weight * listing.feature_scores.get(dimension, 0.5)
        weight_sum += weight
    return round(weighted_total / weight_sum, 3)


def _explain_match(listing: Listing, weights: dict[str, float]) -> str:
    strongest = sorted(PREFERENCE_DIMENSIONS, key=lambda dim: weights.get(dim, 1.0), reverse=True)[:2]
    evidence = ", ".join(
        f"{dimension} {listing.feature_scores.get(dimension, 0.5):.0%}" for dimension in strongest
    )
    return f"it best matches your current emphasis on {', '.join(strongest)} ({evidence})."


def _infer_preference_delta_with_llm(
    feedback: list[FeedbackEvent],
    listings: list[Listing],
    current_weights: dict[str, float],
) -> PreferenceDelta:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                google_api_key=google_api_key,
                temperature=0,
            )
            return _invoke_structured_preference_parser(llm, feedback, listings, current_weights)
        except Exception as exc:
            return _demo_fallback_delta(feedback, f"Google AI Studio parsing failed, used demo fallback: {exc}")

    return _demo_fallback_delta(
        feedback,
        "GOOGLE_API_KEY is not configured, so the demo fallback estimated conservative deltas.",
    )


def _invoke_structured_preference_parser(
    llm,
    feedback: list[FeedbackEvent],
    listings: list[Listing],
    current_weights: dict[str, float],
) -> PreferenceDelta:
    structured_llm = llm.with_structured_output(PreferenceDelta)
    response = structured_llm.invoke(
        [
            SystemMessage(
                content=(
                    "You update real-estate buyer preference weights from feedback. "
                    "Return small deltas between -0.35 and 0.35 only for these dimensions: "
                    f"{', '.join(PREFERENCE_DIMENSIONS)}. Positive means the buyer values it more. "
                    "Do not invent new dimensions."
                )
            ),
            HumanMessage(content=_feedback_prompt(feedback, listings, current_weights)),
        ]
    )
    return _clamp_delta(response)


def _feedback_prompt(
    feedback: list[FeedbackEvent],
    listings: list[Listing],
    current_weights: dict[str, float],
) -> str:
    listing_lookup = {listing.listing_id: listing.model_dump() for listing in listings}
    payload = {
        "current_weights": current_weights,
        "feedback": [event.model_dump(mode="json") for event in feedback],
        "listing_context": listing_lookup,
    }
    return json.dumps(payload, indent=2)


def _clamp_delta(delta: PreferenceDelta) -> PreferenceDelta:
    clamped = {
        dimension: round(max(-0.35, min(0.35, float(delta.deltas.get(dimension, 0.0)))), 3)
        for dimension in PREFERENCE_DIMENSIONS
    }
    return PreferenceDelta(deltas=clamped, rationale=delta.rationale)


def _demo_fallback_delta(feedback: list[FeedbackEvent], rationale_prefix: str) -> PreferenceDelta:
    deltas = {dimension: 0.0 for dimension in PREFERENCE_DIMENSIONS}
    for event in feedback:
        polarity = 1.0 if event.rating == "up" else -1.0
        text = event.comment.lower()
        if "dark" in text or "light" in text or "window" in text or "sun" in text:
            deltas["light"] += 0.22 * (-polarity if event.rating == "down" else polarity)
        if "small" in text or "space" in text or "sqft" in text:
            deltas["size"] += 0.18 * (-polarity if event.rating == "down" else polarity)
        if "far" in text or "commute" in text or "location" in text:
            deltas["location"] += 0.18 * (-polarity if event.rating == "down" else polarity)
        if "old" in text or "resale" in text:
            deltas["age"] += 0.16 * (-polarity if event.rating == "down" else polarity)
        if "expensive" in text or "budget" in text or "price" in text:
            deltas["price"] += 0.16 * (-polarity if event.rating == "down" else polarity)
        if "amenities" in text or "pool" in text or "gym" in text or "clubhouse" in text:
            deltas["amenities"] += 0.14 * (polarity if event.rating == "up" else -polarity)

    clamped = {dimension: round(max(-0.35, min(0.35, value)), 3) for dimension, value in deltas.items()}
    return PreferenceDelta(deltas=clamped, rationale=f"{rationale_prefix} Deltas: {clamped}")

