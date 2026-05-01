from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


PREFERENCE_DIMENSIONS = ("price", "size", "location", "light", "age", "amenities")


class BuyerMemoryParameters(BaseModel):
    """How strongly this buyer updates preferences from feedback and how much history informs copy."""

    feedback_history_window: int = Field(default=5, ge=1, le=40)
    preference_delta_cap: float = Field(default=0.35, ge=0.05, le=0.5)
    weight_floor: float = Field(default=0.1, ge=0.05, le=0.5)
    weight_ceiling: float = Field(default=3.0, ge=1.0, le=5.0)


class BuyerProfile(BaseModel):
    budget: int = Field(default=18_000_000, description="Maximum purchase budget in INR")
    city: str = Field(default="Bengaluru")
    min_bedrooms: int = 2
    required_amenities: list[str] = Field(default_factory=lambda: ["covered parking"])
    hard_requirements: list[str] = Field(
        default_factory=lambda: ["2+ bedrooms", "covered parking", "safe neighborhood"]
    )
    memory: BuyerMemoryParameters = Field(default_factory=BuyerMemoryParameters)


class Listing(BaseModel):
    listing_id: str
    title: str
    city: str
    neighborhood: str
    price: int
    bedrooms: int
    area_sqft: int
    property_age_years: int
    amenities: list[str]
    description: str
    feature_scores: dict[str, float]


class ListingScore(BaseModel):
    listing: Listing
    score: float
    explanation: str
    eligibility_notes: list[str] = Field(default_factory=list)
    fair_price_estimate: int | None = None
    fair_price_note: str = ""


class FeedbackEvent(BaseModel):
    listing_id: str
    rating: Literal["up", "down"]
    comment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreferenceDelta(BaseModel):
    deltas: dict[str, float] = Field(
        description="Preference weight adjustments for price, size, location, light, age, amenities"
    )
    rationale: str


class KPIMetrics(BaseModel):
    preference_inference_accuracy: float | None = None
    sessions_to_first_strong_yes: int | None = None
    listings_filtered_out_pct: float = 0.0
    buyer_engagement_sessions_per_week: float = 0.0
    cold_start_listing_count: int = 0
    final_stated_preferences: list[str] = Field(default_factory=list)
    first_session_at: datetime | None = None


class CoupleProfile(BaseModel):
    enabled: bool = False
    partner_a_weights: dict[str, float] = Field(default_factory=dict)
    partner_b_weights: dict[str, float] = Field(default_factory=dict)
    conflict_notes: list[str] = Field(default_factory=list)


class BuyerPreferenceState(BaseModel):
    buyer_profile: BuyerProfile = Field(default_factory=BuyerProfile)
    preference_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "price": 1.0,
            "size": 1.0,
            "location": 1.0,
            "light": 1.0,
            "age": 1.0,
            "amenities": 1.0,
        }
    )
    seen_listings: list[str] = Field(default_factory=list)
    feedback_log: list[FeedbackEvent] = Field(default_factory=list)
    session_count: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    loaded_from_checkpoint: bool = False

    current_listings: list[Listing] = Field(default_factory=list)
    ranked_listings: list[ListingScore] = Field(default_factory=list)
    incoming_feedback: list[FeedbackEvent] = Field(default_factory=list)
    graph_action: Literal["recommend", "feedback"] = "recommend"
    last_update_rationale: str = ""
    learning_error: str = ""
    kpis: KPIMetrics = Field(default_factory=KPIMetrics)
    couple_profile: CoupleProfile = Field(default_factory=CoupleProfile)
    tour_intent_summary: str = ""
    tour_calendar_ics: str = ""


def normalise_weights(
    weights: dict[str, float],
    *,
    floor: float = 0.1,
    ceiling: float = 3.0,
) -> dict[str, float]:
    return {
        dimension: round(max(floor, min(ceiling, weights.get(dimension, 1.0))), 3)
        for dimension in PREFERENCE_DIMENSIONS
    }


def clamp_weights(weights: dict[str, float]) -> dict[str, float]:
    """Clamp each weight to [0.1, 3.0] so no dimension is silenced or dominates entirely."""
    return normalise_weights(weights, floor=0.1, ceiling=3.0)


def json_safe_state(state: BuyerPreferenceState) -> dict:
    return state.model_dump(mode="json")

