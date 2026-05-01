from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from realestate_finder.listings import SYNTHETIC_LISTINGS, fetch_broad_listings
from realestate_finder.models import (
    BuyerMemoryParameters,
    BuyerPreferenceState,
    FeedbackEvent,
    Listing,
    ListingScore,
    PREFERENCE_DIMENSIONS,
    PreferenceDelta,
    normalise_weights,
)

try:
    from langsmith import traceable as _traceable
except ImportError:
    def _traceable(**_kw):  # no-op when langsmith is not installed
        def _wrap(fn): return fn
        return _wrap


def state_loader(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    return {
        "last_updated": datetime.now(timezone.utc),
        "loaded_from_checkpoint": state.session_count > 0 or bool(state.feedback_log),
        "learning_error": "",
    }


def listing_fetcher(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    listings = fetch_broad_listings(
        city=state.buyer_profile.city,
        budget=state.buyer_profile.budget,
        seen_listing_ids=state.seen_listings,
    )
    kpis = state.kpis.model_copy()
    if state.session_count == 0 and not kpis.cold_start_listing_count:
        kpis.cold_start_listing_count = len(listings)
    return {"current_listings": [_dump_model(listing) for listing in listings], "kpis": _dump_model(kpis)}


def matcher(state: BuyerPreferenceState | dict) -> dict:
    """Score every eligible listing against the current preference weights."""
    state = _as_state(state)
    eligible = []
    for listing in state.current_listings:
        notes = _hard_requirement_notes(listing, state)
        if not notes:
            eligible.append(listing)

    kpis = state.kpis.model_copy()
    total = len(state.current_listings)
    filtered_count = total - len(eligible)
    kpis.listings_filtered_out_pct = round((filtered_count / total) * 100, 2) if total else 0.0

    effective_weights, conflict_notes = _reconciled_weights(state.preference_weights, state)

    scored = [
        ListingScore(
            listing=listing,
            score=_score_listing(listing, state.preference_weights, state),
            explanation=_explain_match(listing, state, effective_weights),
            eligibility_notes=[],
            fair_price_estimate=_estimate_fair_price(listing),
            fair_price_note=_fair_price_note(listing),
        )
        for listing in eligible
    ]

    result: dict = {
        "ranked_listings": [_dump_model(item) for item in scored],
        "kpis": _dump_model(kpis),
    }
    if conflict_notes != state.couple_profile.conflict_notes:
        updated_couple = state.couple_profile.model_copy(update={"conflict_notes": conflict_notes})
        result["couple_profile"] = _dump_model(updated_couple)
    return result


def ranker(state: BuyerPreferenceState | dict) -> dict:
    """Sort the scored listings and pick the top 5."""
    state = _as_state(state)
    effective_weights, _ = _reconciled_weights(state.preference_weights, state)
    seen_ids = set(state.seen_listings)
    listing_pool = [listing for listing in state.current_listings if listing.listing_id not in seen_ids]
    if len(listing_pool) < 5:
        listing_pool = state.current_listings

    ranked = [
        ListingScore(
            listing=listing,
            score=_score_listing(listing, state.preference_weights, state),
            explanation=_explain_match(listing, state, effective_weights),
            eligibility_notes=[],
            fair_price_estimate=_estimate_fair_price(listing),
            fair_price_note=_fair_price_note(listing),
        )
        for listing in listing_pool
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    top_five = ranked[:5]
    updated_seen = list(dict.fromkeys([*state.seen_listings, *[item.listing.listing_id for item in top_five]]))
    return {
        "ranked_listings": [_dump_model(item) for item in top_five],
        "seen_listings": updated_seen,
    }


def presenter(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    if not state.ranked_listings:
        return {"tour_intent_summary": "", "tour_calendar_ics": ""}

    top = state.ranked_listings[0].listing
    return {
        "tour_intent_summary": (
            f"Tour request: {top.title}, {top.neighborhood}, "
            f"{top.bedrooms} BHK, INR {top.price / 10_000_000:.2f} Cr."
        ),
        "tour_calendar_ics": _build_tour_ics(top),
    }


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

    mem = state.buyer_profile.memory
    try:
        delta = _infer_preference_delta_with_llm(
            feedback=state.incoming_feedback,
            listings=[item.listing for item in state.ranked_listings],
            current_weights=state.preference_weights,
            memory=mem,
        )
    except RuntimeError as exc:
        return {
            "feedback_log": [_dump_model(event) for event in [*state.feedback_log, *state.incoming_feedback]],
            "incoming_feedback": [],
            "learning_error": str(exc),
            "last_update_rationale": "Feedback saved, but preference learning did not run.",
        }

    updated_weights = dict(state.preference_weights)
    for dimension, adjustment in delta.deltas.items():
        if dimension in PREFERENCE_DIMENSIONS:
            updated_weights[dimension] = updated_weights.get(dimension, 1.0) + adjustment
    kpis = _update_feedback_kpis(state)

    return {
        "preference_weights": normalise_weights(
            updated_weights, floor=mem.weight_floor, ceiling=mem.weight_ceiling
        ),
        "feedback_log": [_dump_model(event) for event in [*state.feedback_log, *state.incoming_feedback]],
        "incoming_feedback": [],
        "last_update_rationale": delta.rationale,
        "learning_error": "",
        "kpis": _dump_model(kpis),
    }


def state_saver(state: BuyerPreferenceState | dict) -> dict:
    state = _as_state(state)
    now = datetime.now(timezone.utc)
    update: dict = {
        "last_updated": now,
        "graph_action": "recommend",
    }
    if state.graph_action == "recommend":
        new_count = state.session_count + 1
        update["session_count"] = new_count
        kpis = state.kpis.model_copy()
        if kpis.first_session_at is None:
            kpis.first_session_at = now
        elapsed_days = max(1.0, (now - kpis.first_session_at).total_seconds() / 86400.0)
        kpis.buyer_engagement_sessions_per_week = round(new_count / (elapsed_days / 7.0), 2)
        update["kpis"] = _dump_model(kpis)
    return update


def _as_state(state: BuyerPreferenceState | dict) -> BuyerPreferenceState:
    if isinstance(state, BuyerPreferenceState):
        return state
    return BuyerPreferenceState.model_validate(state)


def _dump_model(model) -> dict:
    return model.model_dump(mode="python") if hasattr(model, "model_dump") else model


def _hard_requirement_notes(listing: Listing, state: BuyerPreferenceState) -> list[str]:
    notes = []
    profile = state.buyer_profile
    if listing.bedrooms < profile.min_bedrooms:
        notes.append(f"below {profile.min_bedrooms} bedrooms")
    amenity_set = {item.lower() for item in listing.amenities}
    missing = [a for a in profile.required_amenities if a.lower() not in amenity_set]
    if missing:
        notes.append(f"missing {', '.join(missing)}")
    return notes


def _score_listing(listing: Listing, weights: dict[str, float], state: BuyerPreferenceState | None = None) -> float:
    effective_weights, _ = _reconciled_weights(weights, state)
    weighted_total = 0.0
    weight_sum = 0.0
    for dimension in PREFERENCE_DIMENSIONS:
        floor = state.buyer_profile.memory.weight_floor if state else 0.1
        weight = max(floor, effective_weights.get(dimension, 1.0))
        weighted_total += weight * listing.feature_scores.get(dimension, 0.5)
        weight_sum += weight
    return round(weighted_total / weight_sum, 3)


def _explain_match(listing: Listing, state: BuyerPreferenceState, effective_weights: dict[str, float]) -> str:
    strongest = sorted(PREFERENCE_DIMENSIONS, key=lambda dim: effective_weights.get(dim, 1.0), reverse=True)[:2]
    history = _history_reason(state.feedback_log, state.buyer_profile.memory.feedback_history_window)
    evidence = ", ".join(
        f"{dimension} {listing.feature_scores.get(dimension, 0.5):.0%}" for dimension in strongest
    )
    if history:
        return f"Shown because {history}; this home scores strongly on {evidence}."
    return f"Best match for current emphasis on {', '.join(strongest)} ({evidence})."


@_traceable(name="infer_preference_delta", run_type="chain")
def _infer_preference_delta_with_llm(
    feedback: list[FeedbackEvent],
    listings: list[Listing],
    current_weights: dict[str, float],
    memory: BuyerMemoryParameters,
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
            return _invoke_structured_preference_parser(llm, feedback, listings, current_weights, memory)
        except ModuleNotFoundError as exc:
            if exc.name == "langchain_google_genai" or "langchain_google_genai" in str(exc):
                raise RuntimeError(
                    "Gemini preference parsing failed because `langchain-google-genai` is not installed "
                    "in the Python environment running Streamlit. Activate the project venv and run "
                    "`python -m streamlit run app.py`, or install dependencies with "
                    "`python -m pip install -r requirements.txt`."
                ) from exc
            raise
        except Exception as exc:
            raise RuntimeError(f"Gemini preference parsing failed: {exc}") from exc

    raise RuntimeError("GOOGLE_API_KEY is not configured; feedback was saved without preference learning.")


def _invoke_structured_preference_parser(
    llm,
    feedback: list[FeedbackEvent],
    listings: list[Listing],
    current_weights: dict[str, float],
    memory: BuyerMemoryParameters,
) -> PreferenceDelta:
    cap = memory.preference_delta_cap
    structured_llm = llm.with_structured_output(PreferenceDelta)
    response = structured_llm.invoke(
        [
            SystemMessage(
                content=(
                    "You update real-estate buyer preference weights from feedback. "
                    f"Return small deltas between -{cap} and {cap} only for these dimensions: "
                    f"{', '.join(PREFERENCE_DIMENSIONS)}. Positive means the buyer values it more. "
                    "If a buyer downvotes a listing because it lacks a quality, increase that quality. "
                    "For example, 'too dark' should increase light because the buyer wants brighter homes. "
                    "Do not invent new dimensions."
                )
            ),
            HumanMessage(content=_feedback_prompt(feedback, listings, current_weights)),
        ]
    )
    if not isinstance(response, PreferenceDelta):
        raise RuntimeError("Gemini preference parsing returned an unexpected structured output.")
    return _clamp_delta(response, cap)


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


def _clamp_delta(delta: PreferenceDelta, cap: float) -> PreferenceDelta:
    clamped = {
        dimension: round(max(-cap, min(cap, float(delta.deltas.get(dimension, 0.0)))), 3)
        for dimension in PREFERENCE_DIMENSIONS
    }
    return PreferenceDelta(deltas=clamped, rationale=delta.rationale)


def _history_reason(feedback_log: list[FeedbackEvent], window: int) -> str:
    if not feedback_log:
        return ""
    window = max(1, min(window, len(feedback_log)))
    recent = feedback_log[-window:]
    comments = " ".join(event.comment.lower() for event in recent)
    if "dark" in comments or "light" in comments or "window" in comments:
        return "you reacted to natural light in earlier feedback"
    if "commute" in comments or "far" in comments or "location" in comments:
        return "you commented on commute and location fit"
    if "amenities" in comments or "gym" in comments or "pool" in comments:
        return "you responded to amenities in previous homes"
    positive = [event for event in recent if event.rating == "up"]
    if positive:
        return "you liked similar homes in earlier sessions"
    return "your recent feedback shifted the preference weights"


def _update_feedback_kpis(state: BuyerPreferenceState):
    kpis = state.kpis.model_copy()
    if kpis.sessions_to_first_strong_yes is None:
        if any(event.rating == "up" for event in state.incoming_feedback):
            kpis.sessions_to_first_strong_yes = max(1, state.session_count)
    if kpis.final_stated_preferences:
        learned = set(sorted(PREFERENCE_DIMENSIONS, key=lambda dim: state.preference_weights.get(dim, 1.0), reverse=True)[:3])
        stated = set(kpis.final_stated_preferences)
        kpis.preference_inference_accuracy = round((len(learned & stated) / len(stated)) * 100, 2) if stated else None
    return kpis


def _estimate_fair_price(listing: Listing) -> int | None:
    if listing.area_sqft <= 0:
        return None
    comparables = [
        item
        for item in SYNTHETIC_LISTINGS
        if item.listing_id != listing.listing_id
        and item.city == listing.city
        and item.bedrooms == listing.bedrooms
        and item.area_sqft > 0
        and abs(item.area_sqft - listing.area_sqft) <= 250
    ]
    if not comparables:
        return None
    avg_price_per_sqft = sum(item.price / item.area_sqft for item in comparables) / len(comparables)
    return int(avg_price_per_sqft * listing.area_sqft)


def _fair_price_note(listing: Listing) -> str:
    estimate = _estimate_fair_price(listing)
    if not estimate:
        return "Not enough comparable listings for a fair-price estimate."
    delta_pct = ((listing.price - estimate) / estimate) * 100
    if delta_pct > 5:
        return f"Listed about {delta_pct:.1f}% above comparable estimate."
    if delta_pct < -5:
        return f"Listed about {abs(delta_pct):.1f}% below comparable estimate."
    return "Listed close to comparable estimate."


def _build_tour_ics(listing: Listing) -> str:
    """Build a minimal iCalendar VEVENT for a property tour, importable into Google Calendar."""
    now = datetime.now(timezone.utc)
    tour_start = (now + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    tour_end = tour_start + timedelta(hours=1)
    fmt = "%Y%m%dT%H%M%SZ"
    description = (
        f"{listing.bedrooms} BHK, {listing.area_sqft} sqft, "
        f"INR {listing.price / 10_000_000:.2f} Cr, "
        f"{listing.neighborhood}, {listing.city}"
    )
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RealEstateFinder//Tour//EN",
            "BEGIN:VEVENT",
            f"UID:tour-{listing.listing_id}-{int(now.timestamp())}@realestatefinder",
            f"DTSTAMP:{now.strftime(fmt)}",
            f"DTSTART:{tour_start.strftime(fmt)}",
            f"DTEND:{tour_end.strftime(fmt)}",
            f"SUMMARY:Property tour - {listing.title}",
            f"LOCATION:{listing.neighborhood}, {listing.city}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def _reconciled_weights(weights: dict[str, float], state: BuyerPreferenceState | None) -> tuple[dict[str, float], list[str]]:
    if not state or not state.couple_profile.enabled:
        return weights, []
    profile = state.couple_profile
    combined: dict[str, float] = {}
    notes: list[str] = []
    for dimension in PREFERENCE_DIMENSIONS:
        a_weight = profile.partner_a_weights.get(dimension, weights.get(dimension, 1.0))
        b_weight = profile.partner_b_weights.get(dimension, weights.get(dimension, 1.0))
        combined[dimension] = round((a_weight + b_weight) / 2, 3)
        if abs(a_weight - b_weight) >= 0.7:
            notes.append(f"{dimension}: buyer A {a_weight:.1f}, buyer B {b_weight:.1f}")
    return combined, notes

