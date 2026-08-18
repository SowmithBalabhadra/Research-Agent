import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "apps.json"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "results.json"
ERRORS_FILE = RESULTS_DIR / "errors.json"


# ---------------------------------------------------------
# Import researcher
# ---------------------------------------------------------

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from researcher import AppResearcher, build_record


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Seconds between apps. Each app makes 5 LLM calls, and Groq's
# free tier is 8000 tokens/minute - keep this at 5-8s or the
# retry-backoff in call_groq will fire on nearly every app.
DELAY_BETWEEN_APPS = 40

# Set to True if you want to re-run apps that already have results.
FORCE_RERUN = False

# If this many apps in a row fail with the exact same error message,
# stop the whole run. That pattern means something systemic is broken
# (bad API key, Composio auth, etc) - not a per-app content issue -
# and continuing would just burn through all 100 apps' worth of
# Composio searches for nothing.
MAX_CONSECUTIVE_IDENTICAL_FAILURES = 3


# ---------------------------------------------------------
# Load apps
# ---------------------------------------------------------

def load_apps():
    """
    data/apps.json contains a JSON array:

    [
      {"id": 1, "name": "Salesforce", "category": "CRM and Sales"},
      ...
    ]
    """

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Could not find apps file:\n{DATA_FILE}"
        )

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        apps = json.load(f)

    if not isinstance(apps, list):
        raise ValueError(
            "data/apps.json must contain a JSON array."
        )

    return apps


# ---------------------------------------------------------
# Result helpers
# ---------------------------------------------------------

def load_existing_results():
    """
    Load previously completed results so the script can resume
    after a crash.
    """

    if not RESULTS_FILE.exists():
        return []

    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception as e:
        print(f"Warning: could not read existing results: {e}")

    return []


def save_results(results):
    """
    Save the complete accumulated dataset.
    """

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = RESULTS_DIR / "results.tmp.json"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    # Atomic-ish replacement so a crash during writing is less
    # likely to destroy the previous results file.
    os.replace(temp_file, RESULTS_FILE)


def save_app_result(app, result):
    """
    Save an individual app result as well.

    This gives us:
        results/001_Salesforce.json
        results/002_HubSpot.json
        etc.

    Useful for debugging and verification.
    """

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    app_id = app.get("id")
    app_name = app.get("name", "unknown")

    safe_name = "".join(
        c if c.isalnum() or c in ("-", "_")
        else "_"
        for c in app_name
    )

    if isinstance(app_id, int):
        filename = f"{app_id:03d}_{safe_name}.json"
    else:
        filename = f"{safe_name}.json"

    path = RESULTS_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )


def save_errors(errors):
    """
    Save failed apps separately.
    """

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(ERRORS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            errors,
            f,
            indent=2,
            ensure_ascii=False
        )


# ---------------------------------------------------------
# Main research pipeline
# ---------------------------------------------------------

def main():

    print("=" * 80)
    print("COMPOSIO 100-APP RESEARCH")
    print("=" * 80)

    apps = load_apps()

    print(f"\nLoaded {len(apps)} apps from:")
    print(DATA_FILE)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    existing_results = load_existing_results()

    # -----------------------------------------------------
    # Build lookup of completed apps
    # -----------------------------------------------------

    completed = {}

    for result in existing_results:

        app_name = result.get("app")

        if app_name:
            completed[app_name] = result

    print(f"Existing completed results: {len(completed)}")

    # -----------------------------------------------------
    # Initialize researcher
    # -----------------------------------------------------

    researcher = AppResearcher()

    results = list(completed.values())

    errors = []

    last_error_message = None
    consecutive_identical_failures = 0

    total = len(apps)

    # -----------------------------------------------------
    # Process apps
    # -----------------------------------------------------

    for index, app in enumerate(apps, start=1):

        app_id = app.get("id")
        app_name = app.get("name")
        category = app.get("category")

        if not app_name:
            print(
                f"\n[{index}/{total}] Skipping app with missing name."
            )
            continue

        print("\n")
        print("=" * 80)
        print(f"[{index}/{total}] {app_name}")
        print(f"Category: {category}")
        print("=" * 80)

        # -------------------------------------------------
        # Resume support
        # -------------------------------------------------

        if app_name in completed and not FORCE_RERUN:

            print(
                f"Already completed: {app_name} — skipping."
            )

            continue

        # -------------------------------------------------
        # Research
        # -------------------------------------------------

        try:

            start_time = time.time()

            print(f"Starting research for {app_name}...")

            evidence_pack = researcher.research_app(
                app_name
            )

            print(
                f"Building structured record for {app_name}..."
            )

            result = build_record(
                app_name,
                category,
                evidence_pack
            )

            elapsed = time.time() - start_time

            # -------------------------------------------------
            # Add pipeline metadata
            # -------------------------------------------------

            result["_meta"] = {
                "app_id": app_id,
                "research_time_seconds": round(elapsed, 2),
                "research_status": "success"
            }

            # -------------------------------------------------
            # Replace old result if rerunning
            # -------------------------------------------------

            results = [
                r for r in results
                if r.get("app") != app_name
            ]

            results.append(result)

            completed[app_name] = result

            # -------------------------------------------------
            # Reset the failure-streak tracker on any success
            # -------------------------------------------------

            consecutive_identical_failures = 0
            last_error_message = None

            # -------------------------------------------------
            # Save immediately
            # -------------------------------------------------

            save_app_result(
                app,
                result
            )

            save_results(results)

            print(
                f"\nSUCCESS: {app_name}"
            )

            print(
                f"Time: {elapsed:.1f}s"
            )

            print(
                f"Confidence: "
                f"{result.get('confidence')}"
            )

            print(
                f"Buildability: "
                f"{result.get('buildability', {}).get('verdict')}"
            )

            print(
                f"MCP: "
                f"{result.get('mcp', {}).get('available')}"
            )

            print(
                f"Progress: "
                f"{len(results)}/{total}"
            )

        except KeyboardInterrupt:

            print("\n")
            print("=" * 80)
            print("INTERRUPTED BY USER")
            print("=" * 80)

            print(
                f"Completed results have already been saved."
            )

            save_results(results)
            save_errors(errors)

            sys.exit(1)

        except Exception as e:

            error_message = f"{type(e).__name__}: {e}"

            print("\n")
            print(
                f"FAILED: {app_name}"
            )

            print(
                f"Error: {error_message}"
            )

            errors.append({
                "id": app_id,
                "name": app_name,
                "category": category,
                "error_type": type(e).__name__,
                "error": str(e)
            })

            save_errors(errors)
            save_results(results)

            # ---------------------------------------------
            # Circuit breaker: if the same error repeats
            # back-to-back, something systemic is broken
            # (bad key, dead Composio session, etc). Stop
            # instead of burning through the rest of the
            # apps' Composio search budget for nothing.
            # ---------------------------------------------

            if error_message == last_error_message:
                consecutive_identical_failures += 1
            else:
                consecutive_identical_failures = 1
                last_error_message = error_message

            if consecutive_identical_failures >= MAX_CONSECUTIVE_IDENTICAL_FAILURES:
                print("\n" + "=" * 80)
                print(
                    f"ABORTING: same error occurred "
                    f"{consecutive_identical_failures} times in a row:"
                )
                print(f"  {error_message}")
                print(
                    "This looks systemic (bad API key, dead session, etc), "
                    "not a per-app issue. Fix it and re-run - already "
                    "completed apps will be skipped automatically."
                )
                print("=" * 80)
                save_results(results)
                save_errors(errors)
                sys.exit(1)

            # Otherwise: do NOT kill the entire 100-app run.
            # Continue with the next app.

            continue

        # -------------------------------------------------
        # Delay
        # -------------------------------------------------

        if index < total:

            print(
                f"\nWaiting {DELAY_BETWEEN_APPS}s "
                f"before next app..."
            )

            time.sleep(DELAY_BETWEEN_APPS)

    # -----------------------------------------------------
    # Final save
    # -----------------------------------------------------

    save_results(results)
    save_errors(errors)

    # -----------------------------------------------------
    # Final summary
    # -----------------------------------------------------

    print("\n")
    print("=" * 80)
    print("RESEARCH COMPLETE")
    print("=" * 80)

    print(f"Apps in dataset:       {total}")
    print(f"Successful results:    {len(results)}")
    print(f"Failed apps:            {len(errors)}")

    print(f"\nResults:")
    print(RESULTS_FILE)

    print(f"\nIndividual results:")
    print(RESULTS_DIR)

    if errors:

        print("\nFailed apps:")

        for error in errors:
            print(
                f"  - {error['name']}: "
                f"{error['error']}"
            )

    else:

        print("\nNo failed apps.")

    print("\nDone.")


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()