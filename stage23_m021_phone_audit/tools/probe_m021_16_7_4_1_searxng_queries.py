from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8081"

queries = [
    "OpenAI",
    "380632874404",
    "+380632874404",
    '"380632874404"',
    '"+380632874404"',
    '"063 287 4404"',
]

with httpx.Client(timeout=30) as client:
    for query in queries:
        print()
        print("=" * 76)
        print("QUERY:", query)
        print("=" * 76)

        response = client.get(
            f"{BASE}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",
                "safesearch": 0,
            },
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        unresponsive = data.get(
            "unresponsive_engines",
            [],
        )

        print("results:", len(results))
        print(
            "unresponsive_engines:",
            unresponsive,
        )

        for item in results[:5]:
            print(
                "-",
                item.get("engine"),
                "|",
                item.get("url"),
            )

print()
print("DIAGNOSTIC COMPLETE")
