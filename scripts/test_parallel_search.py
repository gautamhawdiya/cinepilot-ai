import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tools.parallel_search import parallel_search


def main():

    print()
    print("🎬 CinePilot AI")
    print("🔎 Parallel Production Research Test")
    print("=" * 60)

    objective = """
Find practical filming information for a production
planning a night shoot at a train station.

Focus on:
- filming permits
- filming restrictions
- access requirements
- safety considerations
- production logistics
"""

    queries = [
        "train station filming permit requirements",
        "train station filming restrictions production crew",
        "train station filming safety requirements",
    ]

    print()
    print("🔎 Searching Parallel...")
    print()

    results = parallel_search(
        objective=objective,
        search_queries=queries,
    )

    if not results:
        print("❌ No results returned.")
        return

    print(
        f"✅ Parallel returned {len(results)} results."
    )

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"========== RESULT {index} =========="
        )

        print(
            f"Title: {result['title']}"
        )

        print(
            f"URL: {result['url']}"
        )

        print(
            "Excerpts:"
        )

        excerpts = result.get(
            "excerpts"
        )

        if excerpts:

            if isinstance(
                excerpts,
                list,
            ):
                for excerpt in excerpts:
                    print(
                        f"  • {excerpt}"
                    )
            else:
                print(
                    f"  {excerpts}"
                )

    print()
    print("=" * 60)
    print("✅ PARALLEL SEARCH TEST COMPLETE")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()