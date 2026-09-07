import httpx

BASE = "http://127.0.0.1:8081"

engines = [
    "bing",
    "google",
    "google cse",
    "mojeek",
    "qwant",
    "yahoo",
]

queries = [
    "380632874404",
    "+380632874404",
    "0632874404",
    "063 287 4404",
    "063-287-4404",
    "+380 63 287 44 04",
]

with httpx.Client(timeout=45) as client:
    for engine in engines:
        print()
        print("#" * 76)
        print("ENGINE:", engine)
        print("#" * 76)

        for query in queries:
            response = client.get(
                f"{BASE}/search",
                params={
                    "q": f"!{engine} {query}",
                    "format": "json",
                    "safesearch": 0,
                },
            )

            try:
                data = response.json()
            except Exception:
                print(
                    query,
                    "| HTTP",
                    response.status_code,
                    "| invalid JSON",
                )
                continue

            results = data.get("results", [])

            print(
                query,
                "| HTTP",
                response.status_code,
                "| results:",
                len(results),
            )

            for item in results[:3]:
                print(
                    "   ",
                    item.get("engine"),
                    "|",
                    item.get("url"),
                )

            unresponsive = data.get(
                "unresponsive_engines",
                [],
            )

            if unresponsive:
                print(
                    "   unresponsive:",
                    unresponsive,
                )
