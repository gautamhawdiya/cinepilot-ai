import re

from schemas.parallel import (
    ParallelResearch,
    ParallelResult,
)
from tools.parallel_search import parallel_search


def _extract_location(text: str) -> str | None:
    locations = [
        "Mumbai",
        "Pune",
        "Delhi",
        "Bengaluru",
        "Hyderabad",
        "Chennai",
    ]

    for location in locations:
        if location.lower() in text.lower():
            return location

    return None


def _extract_price(text: str) -> str | None:
    patterns = [
        r"₹\s?[\d,]+(?:\.\d+)?",
        r"INR\s?[\d,]+(?:\.\d+)?",
        r"[\d,]+\s?INR",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(0)

    return None


def research_production_resources(
    screenplay,
) -> ParallelResearch:

    queries = []

    # ------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------

    for location in screenplay.locations:
        queries.append(
            f"film shooting location rental {location}"
        )

    # ------------------------------------------------------------
    # Equipment
    # ------------------------------------------------------------

    for prop in screenplay.props:
        prop_lower = prop.lower()

        if any(
            keyword in prop_lower
            for keyword in [
                "camera",
                "monitor",
                "laptop",
            ]
        ):
            queries.append(
                f"{prop} film equipment rental Mumbai Pune"
            )

    # ------------------------------------------------------------
    # VFX
    # ------------------------------------------------------------

    for vfx in screenplay.vfx_requirements[:3]:
        queries.append(
            f"VFX studio India {vfx}"
        )

    # Keep the initial search bounded.
    queries = queries[:8]

    objective = (
        "Find real-world production resources for the "
        f"screenplay '{screenplay.title}'. "
        "Focus on filming locations, production equipment, "
        "and VFX resources in India, especially Mumbai and Pune. "
        "Return factual information from available sources. "
        "Do not invent prices."
    )

    raw = parallel_search(
        objective=objective,
        search_queries=queries,
        max_results=8,
    )

    results = []

    for item in raw.get("results", []):

        excerpts = item.get("excerpts", [])

        if isinstance(excerpts, list):
            snippet = "\n".join(
                str(x) for x in excerpts
            )
        else:
            snippet = str(excerpts or "")

        results.append(
            ParallelResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet[:5000],
                relevance="Production resource found by Parallel",
                price=_extract_price(snippet),
                location=_extract_location(
                    f"{item.get('title', '')} {snippet}"
                ),
            )
        )

    return ParallelResearch(
        objective=objective,
        queries=queries,
        results=results,
    )