import json
from pathlib import Path
from urllib.parse import urlparse

from ddgs import DDGS


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

APPS_FILE = BASE_DIR / "data" / "apps.json"
RESULTS_DIR = BASE_DIR / "results"
OUTPUT_FILE = RESULTS_DIR / "research_links.json"


# ============================================================
# SEARCH CONFIG
# ============================================================

SEARCHES_PER_FIELD = 3


# ============================================================
# OFFICIAL-DOMAIN HELPERS
# ============================================================

def get_domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def get_official_domain(app):
    website = app.get("website", "")
    docs = app.get("documentation_hint", "")

    domain = get_domain(docs)

    if domain:
        return domain

    return get_domain(website)


def is_probably_official(url, official_domain):
    """
    Prefer official sources.

    We do NOT completely discard third-party sources because sometimes
    search engines return useful evidence there. Instead, official sources
    are ranked first.
    """
    domain = get_domain(url)

    if not domain:
        return False

    return (
        domain == official_domain
        or domain.endswith("." + official_domain)
    )


# ============================================================
# LOAD APPS
# ============================================================

def load_apps():
    if not APPS_FILE.exists():
        raise FileNotFoundError(
            f"Could not find apps file:\n{APPS_FILE}"
        )

    with open(APPS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("apps.json must contain a JSON array.")

    return data


# ============================================================
# FIND COMPLETED APPS
# ============================================================

def load_completed_apps():
    """
    Looks at:
      results/results.json
      results/*.json

    and collects app names that already have completed research.
    """

    completed = set()

    # --------------------------------------------------------
    # Combined results.json
    # --------------------------------------------------------

    combined = RESULTS_DIR / "results.json"

    if combined.exists():
        try:
            with open(combined, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                records = data

            elif isinstance(data, dict):
                records = data.get("results", [])

            else:
                records = []

            for record in records:
                if isinstance(record, dict):
                    app_name = record.get("app")

                    if app_name:
                        completed.add(app_name.strip())

        except Exception as e:
            print(f"Warning: could not read {combined}: {e}")

    # --------------------------------------------------------
    # Individual result files
    # --------------------------------------------------------

    if RESULTS_DIR.exists():

        for file in RESULTS_DIR.glob("*.json"):

            if file.name in {
                "results.json",
                "analysis.json",
                "research_links.json",
                "verification_inputs.json",
            }:
                continue

            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    app_name = data.get("app")

                    if app_name:
                        completed.add(app_name.strip())

            except Exception:
                # Ignore malformed/non-result JSON files.
                continue

    return completed


# ============================================================
# SEARCH
# ============================================================

def search_web(query, official_domain):
    """
    Search the web and return up to SEARCHES_PER_FIELD useful URLs.

    Official sources are ranked before third-party sources.
    """

    results = []

    try:
        with DDGS() as ddgs:

            search_results = ddgs.text(
                query,
                max_results=8
            )

            for item in search_results:

                url = item.get("href")

                if not url:
                    continue

                if url not in results:
                    results.append(url)

    except Exception as e:
        print(f"    Search error: {e}")
        return []

    # --------------------------------------------------------
    # Put official sources first
    # --------------------------------------------------------

    official = []
    third_party = []

    for url in results:

        if is_probably_official(url, official_domain):
            official.append(url)
        else:
            third_party.append(url)

    ordered = official + third_party

    return ordered[:SEARCHES_PER_FIELD]


# ============================================================
# SEARCH QUERY GENERATOR
# ============================================================

def build_queries(app):
    """
    Generate targeted searches.

    We intentionally search each research dimension separately.
    """

    name = app["name"]
    docs = app.get("documentation_hint", "")

    return {
        "authentication": [
            f'"{name}" API authentication OAuth API key token',
            f'"{name}" developer authentication OAuth 2.0',
            f'"{name}" API credentials authentication documentation',
        ],

        "api": [
            f'"{name}" API documentation REST GraphQL',
            f'"{name}" developer API reference',
            f'"{name}" API webhooks documentation',
        ],

        "access": [
            f'"{name}" developer signup API credentials',
            f'"{name}" API pricing developer access plan',
            f'"{name}" developer account API key OAuth',
        ],

        "mcp": [
            f'"{name}" official MCP Model Context Protocol',
            f'"{name}" MCP server documentation',
            f'"{name}" MCP authentication OAuth',
        ],
    }


# ============================================================
# COLLECT ONE APP
# ============================================================

def collect_app_links(app):

    name = app["name"]
    category = app.get("category", "")
    official_domain = get_official_domain(app)

    print()
    print("=" * 80)
    print(f"SEARCHING: {name}")
    print("=" * 80)

    print(f"Official domain: {official_domain}")

    queries = build_queries(app)

    sources = {
        "authentication": [],
        "api": [],
        "access": [],
        "mcp": [],
    }

    for field, field_queries in queries.items():

        print()
        print(f"[{field}]")

        field_urls = []

        for query in field_queries:

            print(f"  Query: {query}")

            urls = search_web(
                query,
                official_domain
            )

            for url in urls:

                if url not in field_urls:
                    field_urls.append(url)

        # Limit to useful links per field.
        sources[field] = field_urls[:SEARCHES_PER_FIELD]

        for url in sources[field]:
            print(f"  -> {url}")

    return {
        "app": name,
        "category": category,
        "website": app.get("website", ""),
        "documentation_hint": app.get(
            "documentation_hint",
            ""
        ),
        "sources": sources,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("COMPOSIO RESEARCH — LINK COLLECTION ONLY")
    print("=" * 80)

    apps = load_apps()

    completed = load_completed_apps()

    print()
    print(f"Total apps:        {len(apps)}")
    print(f"Completed apps:    {len(completed)}")

    remaining = [
        app
        for app in apps
        if app.get("name") not in completed
    ]

    print(f"Remaining apps:    {len(remaining)}")
    print()

    if not remaining:
        print("All apps already have results.")
        return

    all_results = []

    # ========================================================
    # PROCESS ONLY UNFINISHED APPS
    # ========================================================

    for index, app in enumerate(remaining, start=1):

        print()
        print(
            f"PROGRESS: "
            f"[{index}/{len(remaining)}] "
            f"{app['name']}"
        )

        result = collect_app_links(app)

        all_results.append(result)

        # Save after EVERY app.
        # This prevents losing progress if the process stops.
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                all_results,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(f"\nSaved progress to:")
        print(OUTPUT_FILE)

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 80)
    print("LINK COLLECTION COMPLETE")
    print("=" * 80)

    print(f"Apps processed: {len(all_results)}")
    print(f"Output file:    {OUTPUT_FILE}")

    print()
    print(
        "IMPORTANT: This script ONLY collected URLs."
    )
    print(
        "It did NOT fetch pages, extract content, "
        "call Qwen, or generate research conclusions."
    )


if __name__ == "__main__":
    main()