import os

from dotenv import load_dotenv
from parallel import Parallel


load_dotenv()


def parallel_search(
    objective: str,
    search_queries: list[str],
) -> dict:
    """
    Search the live web through Parallel for
    production-relevant information.
    """

    api_key = os.getenv("PARALLEL_API_KEY")

    if not api_key:
        raise RuntimeError(
            "PARALLEL_API_KEY is not configured."
        )

    client = Parallel(
        api_key=api_key
    )

    response = client.search(
        objective=objective,
        search_queries=search_queries,
    )

    results = []

    for item in response.results:

        excerpts = getattr(
            item,
            "excerpts",
            [],
        )

        if isinstance(
            excerpts,
            str,
        ):
            excerpts = [excerpts]

        results.append(
            {
                "title": getattr(
                    item,
                    "title",
                    None,
                ),
                "url": getattr(
                    item,
                    "url",
                    None,
                ),
                "excerpts": excerpts,
            }
        )

    return {
        "result_count": len(results),
        "results": results,
    }