import re
import sqlite3
from typing import Optional

from vending_machine.database import serialize_supplement
from vending_machine.schemas import RecommendationRequest

ACTIVITY_TERMS = {
    "walking": ("walk", "walking", "hike", "hiking"),
    "running": ("run", "running", "jog", "jogging"),
    "gym": ("gym", "workout", "weight", "weights", "lifting", "strength training"),
    "cycling": ("cycle", "cycling", "bike", "biking"),
    "endurance": ("endurance", "long distance", "marathon"),
}
GOAL_TERMS = {
    "muscle_gain": ("muscle", "muscle gain", "build muscle", "bulk"),
    "strength": ("strength", "stronger", "power"),
    "recovery": ("recover", "recovery", "sore"),
    "hydration": ("hydrate", "hydration", "sweat", "electrolyte"),
    "endurance": ("endurance", "stamina", "long distance"),
    "general_health": ("health", "vitamin", "general wellness"),
}


def _normalize(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").casefold()).strip()


def _infer_tags(message: str, terms: dict[str, tuple[str, ...]]) -> set[str]:
    normalized = _normalize(message)
    return {
        tag
        for tag, phrases in terms.items()
        if any(re.search(rf"\b{re.escape(_normalize(phrase))}\b", normalized) for phrase in phrases)
    }


def _parse_tags(value: Optional[str], terms: dict[str, tuple[str, ...]]) -> set[str]:
    normalized = _normalize(value)
    if normalized in terms:
        return {normalized}
    return _infer_tags(normalized, terms)


def retrieve_recommendations(
    connection: sqlite3.Connection,
    request: RecommendationRequest,
    input_mode: str,
    extra_context: str = "",
) -> dict:
    message = f"{request.message} {extra_context}".strip()
    activities = _parse_tags(request.activity, ACTIVITY_TERMS) | _infer_tags(message, ACTIVITY_TERMS)
    goals = _parse_tags(request.goal, GOAL_TERMS) | _infer_tags(message, GOAL_TERMS)
    if not activities:
        activities = {"general"}

    dietary_preference = _normalize(request.dietary_preference)
    excluded_allergens = {_normalize(item) for item in request.allergies if item.strip()}
    candidates = connection.execute(
        "SELECT * FROM supplements WHERE stock > 0 ORDER BY name"
    ).fetchall()
    ranked = []
    for row in candidates:
        item = serialize_supplement(row)
        item_allergens = {_normalize(item) for item in item["allergens"]}
        if excluded_allergens & item_allergens:
            continue
        dietary_tags = {_normalize(tag) for tag in item["dietary_tags"]}
        if dietary_preference and dietary_preference not in dietary_tags:
            continue
        if request.caffeine_sensitive and item["caffeine_mg"] > 0:
            continue

        activity_tags = {_normalize(tag) for tag in item["activity_tags"]}
        goal_tags = {_normalize(tag) for tag in item["goal_tags"]}
        activity_matches = activities & activity_tags
        goal_matches = goals & goal_tags
        score = 2 * len(activity_matches) + 3 * len(goal_matches)
        reasons = []
        if "muscle_gain" in goals and item["protein_g"] > 0:
            score += 4
            reasons.append(f"provides {item['protein_g']:g} g protein per listed serving")
        if dietary_preference:
            score += 1
        if activity_matches:
            reasons.append(f"tagged for {', '.join(sorted(activity_matches))}")
        if goal_matches:
            reasons.append(f"matches your {', '.join(sorted(goal_matches)).replace('_', ' ')} goal")
        if dietary_preference:
            reasons.append(f"matches your {dietary_preference} preference")
        if not reasons:
            reasons.append("a general sports-nutrition option from the catalog")

        item["match_reasons"] = reasons
        item["match_score"] = score
        ranked.append(item)

    ranked.sort(key=lambda item: (-item["match_score"], item["name"]))
    recommendations = ranked[:3]
    activity_label = ", ".join(sorted(activities)).replace("_", " ")
    goal_label = ", ".join(sorted(goals)).replace("_", " ") or "general fitness"
    if recommendations:
        summary = (
            f"For {activity_label} and your {goal_label} goal, "
            f"these catalog options may be relevant: "
            + ", ".join(item["name"] for item in recommendations)
            + "."
        )
    else:
        summary = (
            "No in-stock supplements match the provided allergy and dietary filters. "
            "Try changing the filters or ask staff for help."
        )

    connection.execute(
        """
        INSERT INTO recommendation_history
            (input_mode, activity, goal, recommendation_names)
        VALUES (?, ?, ?, ?)
        """,
        (
            input_mode,
            ", ".join(sorted(activities)),
            ", ".join(sorted(goals)) or None,
            ", ".join(item["name"] for item in recommendations),
        ),
    )
    return {
        "input_mode": input_mode,
        "activity": sorted(activities),
        "goal": sorted(goals),
        "summary": summary,
        "recommendations": recommendations,
        "safety_notice": (
            "General product information only, not medical or dietary advice. "
            "Follow each product label. Ask a qualified healthcare professional "
            "before using supplements if you have a medical condition, take medication, "
            "are pregnant, or are unsure what is suitable for you."
        ),
    }
