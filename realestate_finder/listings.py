from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from realestate_finder.models import Listing


DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "bengaluru_house_data.csv"
DATASET_SOURCE_URL = "https://github.com/dphi-official/Datasets/blob/master/Bengaluru_House_Data.csv"


BASE_LISTINGS: list[Listing] = [
    Listing(
        listing_id="BLR-001",
        title="Sunlit corner apartment near Cubbon Park",
        city="Bengaluru",
        neighborhood="Lavelle Road",
        price=17_800_000,
        bedrooms=2,
        area_sqft=1320,
        property_age_years=4,
        amenities=["gym", "covered parking", "balcony", "power backup"],
        description="South-east corner unit with large windows, balcony, and morning light in every bedroom.",
        feature_scores={"price": 0.78, "size": 0.72, "location": 0.95, "light": 0.98, "age": 0.82, "amenities": 0.82},
    ),
    Listing(
        listing_id="BLR-002",
        title="Large family flat with clubhouse",
        city="Bengaluru",
        neighborhood="Whitefield",
        price=16_200_000,
        bedrooms=3,
        area_sqft=1720,
        property_age_years=9,
        amenities=["clubhouse", "pool", "gym", "kids play area", "covered parking"],
        description="Spacious gated-community apartment close to tech parks; lower-floor unit with moderate light.",
        feature_scores={"price": 0.86, "size": 0.95, "location": 0.72, "light": 0.48, "age": 0.58, "amenities": 0.94},
    ),
    Listing(
        listing_id="BLR-003",
        title="Quiet resale home near metro",
        city="Bengaluru",
        neighborhood="Jayanagar",
        price=14_900_000,
        bedrooms=2,
        area_sqft=1180,
        property_age_years=14,
        amenities=["covered parking", "security", "metro access"],
        description="Well-connected resale unit with practical layout, older interiors, and limited direct sunlight.",
        feature_scores={"price": 0.92, "size": 0.62, "location": 0.9, "light": 0.36, "age": 0.38, "amenities": 0.58},
    ),
    Listing(
        listing_id="BLR-004",
        title="Penthouse-style duplex with terrace",
        city="Bengaluru",
        neighborhood="Indiranagar",
        price=22_500_000,
        bedrooms=3,
        area_sqft=1880,
        property_age_years=3,
        amenities=["private terrace", "lift", "covered parking", "smart home"],
        description="Airy top-floor duplex with skylight, private terrace, and premium finishes.",
        feature_scores={"price": 0.42, "size": 0.98, "location": 0.93, "light": 1.0, "age": 0.9, "amenities": 0.86},
    ),
    Listing(
        listing_id="BLR-005",
        title="Budget starter apartment",
        city="Bengaluru",
        neighborhood="Electronic City",
        price=8_800_000,
        bedrooms=2,
        area_sqft=1040,
        property_age_years=6,
        amenities=["security", "covered parking"],
        description="Efficient apartment in a developing corridor with basic amenities and average daylight.",
        feature_scores={"price": 1.0, "size": 0.5, "location": 0.48, "light": 0.55, "age": 0.72, "amenities": 0.42},
    ),
    Listing(
        listing_id="BLR-006",
        title="Garden-facing apartment with big windows",
        city="Bengaluru",
        neighborhood="Koramangala",
        price=18_600_000,
        bedrooms=2,
        area_sqft=1260,
        property_age_years=2,
        amenities=["garden", "gym", "coworking lounge", "covered parking"],
        description="Bright garden-facing home with full-height windows and short commute to central offices.",
        feature_scores={"price": 0.68, "size": 0.68, "location": 0.91, "light": 0.96, "age": 0.96, "amenities": 0.84},
    ),
    Listing(
        listing_id="BLR-007",
        title="New launch smart apartment",
        city="Bengaluru",
        neighborhood="Hebbal",
        price=15_700_000,
        bedrooms=2,
        area_sqft=1210,
        property_age_years=1,
        amenities=["pool", "gym", "smart locks", "visitor parking"],
        description="Brand-new apartment with modern amenities, airport-road access, and decent afternoon light.",
        feature_scores={"price": 0.88, "size": 0.64, "location": 0.76, "light": 0.7, "age": 1.0, "amenities": 0.88},
    ),
    Listing(
        listing_id="BLR-008",
        title="Premium high-rise skyline view",
        city="Bengaluru",
        neighborhood="Rajajinagar",
        price=19_900_000,
        bedrooms=3,
        area_sqft=1610,
        property_age_years=5,
        amenities=["sky deck", "pool", "gym", "covered parking", "concierge"],
        description="Upper-floor apartment with skyline views, west-facing light, and extensive resident amenities.",
        feature_scores={"price": 0.58, "size": 0.88, "location": 0.82, "light": 0.9, "age": 0.78, "amenities": 0.98},
    ),
    Listing(
        listing_id="BLR-009",
        title="Compact central studio-plus",
        city="Bengaluru",
        neighborhood="MG Road",
        price=12_400_000,
        bedrooms=1,
        area_sqft=820,
        property_age_years=8,
        amenities=["security", "lift", "metro access"],
        description="Central compact home for commute-first buyers; small footprint but strong location.",
        feature_scores={"price": 0.96, "size": 0.28, "location": 0.98, "light": 0.62, "age": 0.64, "amenities": 0.52},
    ),
    Listing(
        listing_id="BLR-010",
        title="Leafy low-rise apartment",
        city="Bengaluru",
        neighborhood="Malleswaram",
        price=16_900_000,
        bedrooms=2,
        area_sqft=1350,
        property_age_years=11,
        amenities=["tree-lined street", "covered parking", "security"],
        description="Calm low-rise home in a mature neighborhood with filtered natural light and larger rooms.",
        feature_scores={"price": 0.82, "size": 0.76, "location": 0.88, "light": 0.76, "age": 0.48, "amenities": 0.6},
    ),
    Listing(
        listing_id="BLR-011",
        title="Resort-style gated community",
        city="Bengaluru",
        neighborhood="Sarjapur Road",
        price=15_100_000,
        bedrooms=3,
        area_sqft=1580,
        property_age_years=7,
        amenities=["pool", "tennis court", "gym", "supermarket", "covered parking"],
        description="Amenity-rich campus with practical layout; commute depends on office location.",
        feature_scores={"price": 0.9, "size": 0.86, "location": 0.58, "light": 0.64, "age": 0.68, "amenities": 1.0},
    ),
    Listing(
        listing_id="BLR-012",
        title="Minimal new-build near schools",
        city="Bengaluru",
        neighborhood="HSR Layout",
        price=18_200_000,
        bedrooms=2,
        area_sqft=1245,
        property_age_years=1,
        amenities=["covered parking", "ev charging", "security"],
        description="Freshly built apartment near schools and cafes with clean finishes and good cross-ventilation.",
        feature_scores={"price": 0.72, "size": 0.66, "location": 0.86, "light": 0.84, "age": 1.0, "amenities": 0.7},
    ),
]


def _generated_listing_variants() -> list[Listing]:
    neighborhoods = [
        ("Ulsoor", 17_400_000, 0.88, 0.92),
        ("Banashankari", 13_800_000, 0.76, 0.72),
        ("Yelahanka", 14_600_000, 0.68, 0.84),
        ("JP Nagar", 16_100_000, 0.82, 0.78),
        ("Bellandur", 15_600_000, 0.62, 0.66),
        ("Sadashivanagar", 21_200_000, 0.94, 0.9),
        ("Kalyan Nagar", 14_900_000, 0.72, 0.8),
        ("Basavanagudi", 16_800_000, 0.9, 0.74),
        ("Thanisandra", 13_900_000, 0.64, 0.82),
        ("Marathahalli", 12_900_000, 0.58, 0.62),
        ("Domlur", 17_100_000, 0.86, 0.78),
        ("Brookefield", 14_700_000, 0.66, 0.7),
        ("Cooke Town", 18_300_000, 0.9, 0.88),
        ("Vijayanagar", 13_600_000, 0.74, 0.68),
        ("Kanakapura Road", 11_900_000, 0.52, 0.76),
        ("Frazer Town", 17_900_000, 0.88, 0.86),
        ("RT Nagar", 15_300_000, 0.7, 0.74),
        ("Nagarbhavi", 12_600_000, 0.6, 0.7),
        ("Hennur", 14_300_000, 0.64, 0.82),
        ("Old Airport Road", 18_800_000, 0.86, 0.8),
        ("Yeshwanthpur", 15_800_000, 0.78, 0.72),
        ("Bannerghatta Road", 13_400_000, 0.56, 0.66),
        ("Richmond Town", 20_400_000, 0.92, 0.88),
        ("CV Raman Nagar", 14_800_000, 0.72, 0.76),
    ]
    variants: list[Listing] = []
    for index, (neighborhood, price, location_score, light_score) in enumerate(neighborhoods, start=13):
        bedrooms = 3 if index % 3 == 0 else 2
        area = 1180 + (index % 6) * 95 + (120 if bedrooms == 3 else 0)
        age = index % 12 + 1
        amenities = ["covered parking", "security"]
        if index % 2 == 0:
            amenities.append("gym")
        if index % 4 == 0:
            amenities.append("pool")
        if light_score >= 0.8:
            amenities.append("balcony")
        amenities_score = min(1.0, 0.42 + len(amenities) * 0.12)
        variants.append(
            Listing(
                listing_id=f"BLR-{index:03d}",
                title=f"{neighborhood} {bedrooms} BHK with balanced light",
                city="Bengaluru",
                neighborhood=neighborhood,
                price=price,
                bedrooms=bedrooms,
                area_sqft=area,
                property_age_years=age,
                amenities=amenities,
                description=f"{bedrooms} BHK home in {neighborhood} with covered parking and a practical family layout.",
                feature_scores={
                    "price": max(0.35, min(1.0, 1 - ((price - 11_000_000) / 18_000_000))),
                    "size": max(0.45, min(1.0, area / 1800)),
                    "location": location_score,
                    "light": light_score,
                    "age": max(0.35, min(1.0, 1 - age / 18)),
                    "amenities": amenities_score,
                },
            )
        )
    return variants


SYNTHETIC_LISTINGS: list[Listing] = [*BASE_LISTINGS, *_generated_listing_variants()]


def _parse_bhk(size: str) -> int | None:
    match = re.search(r"\d+", size or "")
    return int(match.group()) if match else None


def _parse_sqft(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None

    if "-" in text:
        try:
            bounds = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]
        except ValueError:
            bounds = []
        if len(bounds) >= 2:
            return round(sum(bounds[:2]) / 2)

    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        amount = float(match.group())
    except ValueError:
        return None
    lowered = text.lower()
    if "sq. meter" in lowered:
        amount *= 10.7639
    elif "sq. yard" in lowered:
        amount *= 9
    elif "perch" in lowered:
        amount *= 272.25
    elif "acre" in lowered:
        amount *= 43_560
    elif "cent" in lowered:
        amount *= 435.6
    elif "ground" in lowered:
        amount *= 2_400
    return round(amount)


def _availability_age_years(availability: str) -> int:
    return 5 if (availability or "").strip().lower() == "ready to move" else 0


def _amenities_from_row(row: dict[str, str]) -> list[str]:
    amenities = ["covered parking"]
    area_type = (row.get("area_type") or "").strip().lower()
    if "plot" in area_type:
        amenities.append("private land")
    elif area_type:
        amenities.append(area_type.replace("  ", " ").title())
    if (row.get("society") or "").strip():
        amenities.append("gated society")
    if (row.get("balcony") or "").strip() not in {"", "0"}:
        amenities.append("balcony")
    return amenities


def _location_score(location: str) -> float:
    premium_locations = {
        "Indira Nagar",
        "Koramangala",
        "Jayanagar",
        "Rajaji Nagar",
        "Malleshwaram",
        "Malleswaram",
        "Old Airport Road",
        "Whitefield",
        "HSR Layout",
        "Marathahalli",
        "Hebbal",
    }
    if location in premium_locations:
        return 0.9
    if len(location) <= 4 or location.lower() in {"other"}:
        return 0.55
    return 0.72


def _dataset_row_to_listing(index: int, row: dict[str, str]) -> Listing | None:
    location = (row.get("location") or "").strip()
    bedrooms = _parse_bhk(row.get("size", ""))
    area_sqft = _parse_sqft(row.get("total_sqft", ""))
    try:
        price = round(float(row.get("price", "")) * 100_000)
    except ValueError:
        return None

    if not location or not bedrooms or not area_sqft or price <= 0:
        return None

    age_years = _availability_age_years(row.get("availability", ""))
    amenities = _amenities_from_row(row)
    balcony_raw = (row.get("balcony") or "").strip()
    balcony_count = 0
    if balcony_raw.replace(".", "", 1).isdigit():
        try:
            balcony_count = int(float(balcony_raw))
        except ValueError:
            balcony_count = 0
    light_score = min(1.0, 0.5 + balcony_count * 0.12 + (0.08 if area_sqft >= 1_400 else 0))
    title = f"{location} {bedrooms} BHK from Bengaluru house price dataset"

    return Listing(
        listing_id=f"BHD-{index:05d}",
        title=title,
        city="Bengaluru",
        neighborhood=location,
        price=price,
        bedrooms=bedrooms,
        area_sqft=area_sqft,
        property_age_years=age_years,
        amenities=amenities,
        description=(
            f"{bedrooms} BHK {row.get('area_type', 'home').strip() or 'home'} in {location}, "
            f"{area_sqft} sqft, listed at INR {price / 10_000_000:.2f} Cr."
        ),
        feature_scores={
            "price": max(0.2, min(1.0, 1 - ((price - 6_000_000) / 24_000_000))),
            "size": max(0.25, min(1.0, area_sqft / 2_000)),
            "location": _location_score(location),
            "light": light_score,
            "age": max(0.45, min(1.0, 1 - age_years / 18)),
            "amenities": min(1.0, 0.4 + len(amenities) * 0.14),
        },
    )


@lru_cache(maxsize=1)
def load_dataset_listings() -> list[Listing]:
    if not DATASET_PATH.exists():
        return []

    listings: list[Listing] = []
    with DATASET_PATH.open(encoding="utf-8", newline="") as csv_file:
        for index, row in enumerate(csv.DictReader(csv_file), start=1):
            listing = _dataset_row_to_listing(index, row)
            if listing:
                listings.append(listing)
    return listings


def available_listings() -> list[Listing]:
    dataset_listings = load_dataset_listings()
    return dataset_listings if dataset_listings else SYNTHETIC_LISTINGS


def fetch_broad_listings(city: str, budget: int, seen_listing_ids: list[str]) -> list[Listing]:
    """Return broad listing candidates, preferring unseen homes while at least five remain."""
    broad_budget_limit = int(budget * 1.25)
    source_listings = available_listings()
    city_matches = [
        listing
        for listing in source_listings
        if listing.city.lower() == city.lower()
        and listing.price <= broad_budget_limit
    ]
    if not city_matches:
        city_matches = [listing for listing in source_listings if listing.price <= broad_budget_limit]

    seen = set(seen_listing_ids)
    preferred = [listing for listing in city_matches if listing.listing_id not in seen]
    return preferred if len(preferred) >= 5 else city_matches

