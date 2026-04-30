from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


PREFERENCE_DIMENSIONS = ("price", "size", "location", "light", "age", "amenities")


class BuyerProfile(BaseModel):
    budget: int = Field(default=18_000_000, description="Maximum purchase budget in INR")
    city: str = Field(default="Bengaluru")
    hard_requirements: list[str] = Field(
        default_factory=lambda: ["2+ bedrooms", "covered parking", "safe neighborhood"]
    )


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

    current_listings: list[Listing] = Field(default_factory=list)
    ranked_listings: list[ListingScore] = Field(default_factory=list)
    presentation_markdown: str = ""
    incoming_feedback: list[FeedbackEvent] = Field(default_factory=list)
    graph_action: Literal["recommend", "feedback"] = "recommend"
    last_update_rationale: str = ""


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    cleaned = {dimension: max(0.1, min(3.0, weights.get(dimension, 1.0))) for dimension in PREFERENCE_DIMENSIONS}
    total = sum(cleaned.values())
    target_total = float(len(PREFERENCE_DIMENSIONS))
    return {key: round((value / total) * target_total, 3) for key, value in cleaned.items()}

