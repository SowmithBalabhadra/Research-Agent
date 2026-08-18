import json
import re
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

RESULTS_FILE = RESULTS_DIR / "results.json"
ANALYSIS_FILE = RESULTS_DIR / "analysis.json"
SUMMARY_FILE = RESULTS_DIR / "analysis_summary.md"


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_string(value):
    if not isinstance(value, str):
        return ""

    return value.strip().lower()


def normalize_list(value):
    """
    Converts a field into a list of strings.

    Handles malformed values such as:
        ["OAuth 2.0", "API Key"]

    and flags:
        [{"claim": "...", "url": "..."}]

    instead of silently treating malformed data as valid.
    """

    if not isinstance(value, list):
        return []

    output = []

    for item in value:

        if isinstance(item, str):
            text = item.strip()

            if text:
                output.append(text)

        elif isinstance(item, dict):
            # Do NOT treat evidence objects as classification values.
            continue

    return output


def normalize_yes_no_unknown(value):
    """
    Normalizes MCP availability.
    """

    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, str):

        value = normalize_string(value)

        if value in {
            "true",
            "yes",
            "available",
            "supported"
        }:
            return "yes"

        if value in {
            "false",
            "no",
            "unavailable",
            "not available"
        }:
            return "no"

        if value == "unknown":
            return "unknown"

    return "unknown"


def normalize_verdict(value):

    value = normalize_string(value)

    aliases = {
        "easy": "easy",
        "moderate": "moderate",
        "difficult": "difficult",
        "not_feasible": "not_feasible",
        "not feasible": "not_feasible",
        "unknown": "unknown"
    }

    return aliases.get(value, "unknown")


def normalize_breadth(value):

    value = normalize_string(value)

    aliases = {
        "broad": "broad",
        "moderate": "moderate",
        "limited": "limited",
        "unknown": "unknown"
    }

    return aliases.get(value, "unknown")


# ============================================================
# LOAD RESULTS
# ============================================================

def load_results():

    if not RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Could not find:\n{RESULTS_FILE}\n\n"
            "Run the research pipeline first."
        )

    with open(
        RESULTS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "results.json must contain a JSON array."
        )

    return data


# ============================================================
# DATA QUALITY CHECKS
# ============================================================

def check_data_quality(results):

    issues = []

    for result in results:

        app = result.get("app", "UNKNOWN")

        authentication = result.get(
            "authentication",
            {}
        )

        methods = authentication.get(
            "methods",
            []
        )

        flows = authentication.get(
            "flows",
            []
        )

        token_types = authentication.get(
            "token_types",
            []
        )

        # --------------------------------------------
        # Authentication schema
        # --------------------------------------------

        for field_name, values in [
            ("methods", methods),
            ("flows", flows),
            ("token_types", token_types)
        ]:

            if not isinstance(values, list):

                issues.append({
                    "app": app,
                    "field": f"authentication.{field_name}",
                    "issue": "not_a_list"
                })

                continue

            for item in values:

                if not isinstance(item, str):

                    issues.append({
                        "app": app,
                        "field": f"authentication.{field_name}",
                        "issue": "contains_non_string_value"
                    })

        # --------------------------------------------
        # API
        # --------------------------------------------

        api = result.get(
            "api",
            {}
        )

        api_types = api.get(
            "types",
            []
        )

        if not isinstance(api_types, list):

            issues.append({
                "app": app,
                "field": "api.types",
                "issue": "not_a_list"
            })

        else:

            for item in api_types:

                if not isinstance(item, str):

                    issues.append({
                        "app": app,
                        "field": "api.types",
                        "issue": "contains_non_string_value"
                    })

        # --------------------------------------------
        # MCP
        # --------------------------------------------

        mcp = result.get(
            "mcp",
            {}
        )

        mcp_value = mcp.get(
            "available"
        )

        if isinstance(mcp_value, dict):

            issues.append({
                "app": app,
                "field": "mcp.available",
                "issue": "contains_object_instead_of_boolean_or_unknown"
            })

        # --------------------------------------------
        # Evidence
        # --------------------------------------------

        evidence = result.get(
            "evidence",
            []
        )

        if not isinstance(evidence, list):

            issues.append({
                "app": app,
                "field": "evidence",
                "issue": "not_a_list"
            })

        else:

            for item in evidence:

                if not isinstance(item, dict):

                    issues.append({
                        "app": app,
                        "field": "evidence",
                        "issue": "evidence_item_not_object"
                    })

                    continue

                if not item.get("url"):

                    issues.append({
                        "app": app,
                        "field": "evidence",
                        "issue": "missing_url"
                    })

        # --------------------------------------------
        # Confidence
        # --------------------------------------------

        confidence = result.get(
            "confidence"
        )

        if not isinstance(
            confidence,
            (int, float)
        ):

            issues.append({
                "app": app,
                "field": "confidence",
                "issue": "not_numeric"
            })

        elif not 0 <= confidence <= 1:

            issues.append({
                "app": app,
                "field": "confidence",
                "issue": "outside_0_to_1_range"
            })

    return issues


# ============================================================
# COUNTER HELPERS
# ============================================================

def percentage(count, total):

    if total == 0:
        return 0.0

    return round(
        (count / total) * 100,
        1
    )


def counter_to_dict(counter, total):

    result = {}

    for key, count in counter.most_common():

        result[key] = {
            "count": count,
            "percentage": percentage(
                count,
                total
            )
        }

    return result


# ============================================================
# AUTHENTICATION ANALYSIS
# ============================================================

def analyze_authentication(results):

    method_counter = Counter()
    flow_counter = Counter()
    token_counter = Counter()

    apps_with_oauth = 0
    apps_with_api_key = 0
    apps_with_basic = 0
    apps_with_multiple_methods = 0

    for result in results:

        auth = result.get(
            "authentication",
            {}
        )

        methods = normalize_list(
            auth.get("methods", [])
        )

        flows = normalize_list(
            auth.get("flows", [])
        )

        token_types = normalize_list(
            auth.get("token_types", [])
        )

        for method in methods:
            method_counter[
                method
            ] += 1

        for flow in flows:
            flow_counter[
                flow
            ] += 1

        for token in token_types:
            token_counter[
                token
            ] += 1

        normalized_methods = {
            normalize_string(m)
            for m in methods
        }

        if "oauth 2.0" in normalized_methods:
            apps_with_oauth += 1

        if any(
            "api key" in m
            for m in normalized_methods
        ):
            apps_with_api_key += 1

        if any(
            "basic" in m
            for m in normalized_methods
        ):
            apps_with_basic += 1

        if len(methods) > 1:
            apps_with_multiple_methods += 1

    total = len(results)

    return {
        "methods": counter_to_dict(
            method_counter,
            total
        ),
        "flows": counter_to_dict(
            flow_counter,
            total
        ),
        "token_types": counter_to_dict(
            token_counter,
            total
        ),
        "apps_with_oauth": {
            "count": apps_with_oauth,
            "percentage": percentage(
                apps_with_oauth,
                total
            )
        },
        "apps_with_api_key": {
            "count": apps_with_api_key,
            "percentage": percentage(
                apps_with_api_key,
                total
            )
        },
        "apps_with_basic_auth": {
            "count": apps_with_basic,
            "percentage": percentage(
                apps_with_basic,
                total
            )
        },
        "apps_with_multiple_auth_methods": {
            "count": apps_with_multiple_methods,
            "percentage": percentage(
                apps_with_multiple_methods,
                total
            )
        }
    }


# ============================================================
# ACCESS ANALYSIS
# ============================================================

def analyze_access(results):

    developer_signup = Counter()
    plan_requirement = Counter()
    admin_requirement = Counter()
    partner_requirement = Counter()

    for result in results:

        access = result.get(
            "access",
            {}
        )

        developer_signup[
            normalize_string(
                access.get(
                    "developer_signup",
                    "unknown"
                )
            )
        ] += 1

        plan_requirement[
            normalize_string(
                access.get(
                    "plan_requirement",
                    "unknown"
                )
            )
        ] += 1

        admin_requirement[
            normalize_string(
                access.get(
                    "admin_requirement",
                    "unknown"
                )
            )
        ] += 1

        partner_requirement[
            normalize_string(
                access.get(
                    "partner_requirement",
                    "unknown"
                )
            )
        ] += 1

    total = len(results)

    return {
        "developer_signup": counter_to_dict(
            developer_signup,
            total
        ),
        "plan_requirement": counter_to_dict(
            plan_requirement,
            total
        ),
        "admin_requirement": counter_to_dict(
            admin_requirement,
            total
        ),
        "partner_requirement": counter_to_dict(
            partner_requirement,
            total
        )
    }


# ============================================================
# API ANALYSIS
# ============================================================

def analyze_api(results):

    type_counter = Counter()
    breadth_counter = Counter()

    apps_with_api = 0

    for result in results:

        api = result.get(
            "api",
            {}
        )

        available = api.get(
            "available",
            False
        )

        if available:
            apps_with_api += 1

        types = normalize_list(
            api.get(
                "types",
                []
            )
        )

        for api_type in types:

            type_counter[
                api_type
            ] += 1

        breadth = normalize_breadth(
            api.get(
                "breadth",
                "unknown"
            )
        )

        breadth_counter[
            breadth
        ] += 1

    total = len(results)

    return {
        "apps_with_api": {
            "count": apps_with_api,
            "percentage": percentage(
                apps_with_api,
                total
            )
        },
        "types": counter_to_dict(
            type_counter,
            total
        ),
        "breadth": counter_to_dict(
            breadth_counter,
            total
        )
    }


# ============================================================
# MCP ANALYSIS
# ============================================================

def analyze_mcp(results):

    availability = Counter()

    for result in results:

        mcp = result.get(
            "mcp",
            {}
        )

        value = normalize_yes_no_unknown(
            mcp.get(
                "available",
                "unknown"
            )
        )

        availability[value] += 1

    total = len(results)

    return {
        "availability": counter_to_dict(
            availability,
            total
        )
    }


# ============================================================
# BUILDABILITY ANALYSIS
# ============================================================

def analyze_buildability(results):

    verdict_counter = Counter()

    blockers = Counter()

    for result in results:

        buildability = result.get(
            "buildability",
            {}
        )

        verdict = normalize_verdict(
            buildability.get(
                "verdict",
                "unknown"
            )
        )

        verdict_counter[
            verdict
        ] += 1

        blocker = buildability.get(
            "blocker",
            ""
        )

        if isinstance(
            blocker,
            str
        ):

            blocker = blocker.strip()

            if blocker:

                blockers[
                    blocker
                ] += 1

    total = len(results)

    return {
        "verdicts": counter_to_dict(
            verdict_counter,
            total
        ),
        "blockers": [
            {
                "blocker": blocker,
                "count": count
            }
            for blocker, count
            in blockers.most_common(15)
        ]
    }


# ============================================================
# CATEGORY ANALYSIS
# ============================================================

def analyze_categories(results):

    categories = defaultdict(list)

    for result in results:

        category = result.get(
            "category",
            "Unknown"
        )

        categories[
            category
        ].append(result)

    output = {}

    for category, apps in sorted(
        categories.items()
    ):

        output[category] = {
            "app_count": len(apps),
            "apps": [
                app.get("app")
                for app in apps
            ],
            "buildability": analyze_buildability(
                apps
            )["verdicts"],
            "mcp": analyze_mcp(
                apps
            )["availability"],
            "api_breadth": analyze_api(
                apps
            )["breadth"]
        }

    return output


# ============================================================
# PRIORITY CLUSTERING
# ============================================================

def classify_priority(result):

    buildability = normalize_verdict(
        result.get(
            "buildability",
            {}
        ).get(
            "verdict",
            "unknown"
        )
    )

    mcp = normalize_yes_no_unknown(
        result.get(
            "mcp",
            {}
        ).get(
            "available",
            "unknown"
        )
    )

    api_available = bool(
        result.get(
            "api",
            {}
        ).get(
            "available",
            False
        )
    )

    access = result.get(
        "access",
        {}
    )

    plan = normalize_string(
        access.get(
            "plan_requirement",
            "unknown"
        )
    )

    admin = normalize_string(
        access.get(
            "admin_requirement",
            "unknown"
        )
    )

    partner = normalize_string(
        access.get(
            "partner_requirement",
            "unknown"
        )
    )

    # --------------------------------------------
    # Easy wins
    # --------------------------------------------

    if (
        buildability == "easy"
        and api_available
        and (
            mcp == "yes"
            or plan in {
                "none",
                "free",
                "free plan",
                "unknown"
            }
        )
    ):

        return "easy_win"

    # --------------------------------------------
    # MCP opportunities
    # --------------------------------------------

    if (
        mcp == "yes"
        and buildability in {
            "easy",
            "moderate"
        }
    ):

        return "mcp_opportunity"

    # --------------------------------------------
    # Gated
    # --------------------------------------------

    if (
        "paid" in plan
        or "required" in plan
        or "approval" in admin
        or "required" in partner
        or "contact" in partner
        or "partner" in partner
    ):

        return "gated"

    # --------------------------------------------
    # Needs investigation
    # --------------------------------------------

    if buildability == "unknown":

        return "needs_investigation"

    # --------------------------------------------
    # Difficult
    # --------------------------------------------

    if buildability in {
        "difficult",
        "not_feasible"
    }:

        return "difficult"

    return "standard"


def analyze_priority(results):

    clusters = defaultdict(list)

    for result in results:

        cluster = classify_priority(
            result
        )

        clusters[
            cluster
        ].append(
            result.get("app")
        )

    return {
        cluster: {
            "count": len(apps),
            "apps": apps
        }
        for cluster, apps
        in sorted(
            clusters.items(),
            key=lambda item: -len(item[1])
        )
    }


# ============================================================
# EVIDENCE ANALYSIS
# ============================================================

def analyze_evidence(results):

    total_evidence = 0

    evidence_per_app = []

    official_domains = Counter()

    for result in results:

        evidence = result.get(
            "evidence",
            []
        )

        if not isinstance(
            evidence,
            list
        ):
            continue

        count = 0

        for item in evidence:

            if not isinstance(
                item,
                dict
            ):
                continue

            url = item.get(
                "url",
                ""
            )

            if url:

                count += 1
                total_evidence += 1

                # Basic domain extraction
                match = re.search(
                    r"https?://([^/]+)",
                    url
                )

                if match:

                    domain = match.group(1).lower()

                    official_domains[
                        domain
                    ] += 1

        evidence_per_app.append({
            "app": result.get("app"),
            "evidence_count": count
        })

    total_apps = len(results)

    average = (
        total_evidence / total_apps
        if total_apps
        else 0
    )

    return {
        "total_evidence_items": total_evidence,
        "average_evidence_per_app": round(
            average,
            2
        ),
        "evidence_per_app": sorted(
            evidence_per_app,
            key=lambda x: x["evidence_count"]
        ),
        "top_source_domains": [
            {
                "domain": domain,
                "count": count
            }
            for domain, count
            in official_domains.most_common(20)
        ]
    }


# ============================================================
# CONFIDENCE ANALYSIS
# ============================================================

def analyze_confidence(results):

    values = []

    for result in results:

        confidence = result.get(
            "confidence"
        )

        if isinstance(
            confidence,
            (int, float)
        ):

            values.append(
                confidence
            )

    if not values:

        return {
            "average": None,
            "minimum": None,
            "maximum": None
        }

    return {
        "average": round(
            sum(values) / len(values),
            3
        ),
        "minimum": min(values),
        "maximum": max(values)
    }


# ============================================================
# INSIGHT GENERATION
# ============================================================

def generate_insights(
    results,
    authentication,
    access,
    api,
    mcp,
    buildability,
    priority
):

    insights = []

    total = len(results)

    if total == 0:
        return insights

    # --------------------------------------------
    # Authentication
    # --------------------------------------------

    oauth_pct = authentication[
        "apps_with_oauth"
    ]["percentage"]

    if oauth_pct >= 50:

        insights.append(
            f"OAuth 2.0 is the dominant authentication "
            f"pattern, appearing in {oauth_pct}% of the "
            f"researched apps."
        )

    # --------------------------------------------
    # MCP
    # --------------------------------------------

    mcp_yes = mcp[
        "availability"
    ].get(
        "yes",
        {}
    ).get(
        "percentage",
        0
    )

    if mcp_yes:

        insights.append(
            f"{mcp_yes}% of the current research set "
            f"has evidence of MCP availability."
        )

    # --------------------------------------------
    # Buildability
    # --------------------------------------------

    easy_pct = buildability[
        "verdicts"
    ].get(
        "easy",
        {}
    ).get(
        "percentage",
        0
    )

    moderate_pct = buildability[
        "verdicts"
    ].get(
        "moderate",
        {}
    ).get(
        "percentage",
        0
    )

    if easy_pct:

        insights.append(
            f"{easy_pct}% of apps are currently "
            f"classified as easy toolkit opportunities."
        )

    if moderate_pct:

        insights.append(
            f"{moderate_pct}% are classified as "
            f"moderate buildability opportunities."
        )

    # --------------------------------------------
    # Priority
    # --------------------------------------------

    easy_wins = priority.get(
        "easy_win",
        {}
    ).get(
        "count",
        0
    )

    if easy_wins:

        insights.append(
            f"{easy_wins} apps currently fall into "
            f"the preliminary easy-win cluster."
        )

    gated = priority.get(
        "gated",
        {}
    ).get(
        "count",
        0
    )

    if gated:

        insights.append(
            f"{gated} apps show preliminary signs "
            f"of access or commercial gating."
        )

    # --------------------------------------------
    # Data quality
    # --------------------------------------------

    quality_issues = check_data_quality(
        results
    )

    if quality_issues:

        insights.append(
            f"{len(quality_issues)} data-quality "
            f"issues were detected automatically; "
            f"these should be included in the "
            f"verification pass rather than silently "
            f"corrected."
        )

    return insights


# ============================================================
# MARKDOWN SUMMARY
# ============================================================

def generate_markdown(
    results,
    analysis
):

    total = len(results)

    lines = []

    lines.append(
        "# Composio App Research — Pattern Analysis"
    )

    lines.append("")

    lines.append(
        f"Research records analyzed: **{total}**"
    )

    lines.append("")

    lines.append(
        "## Preliminary Findings"
    )

    lines.append("")

    for insight in analysis[
        "insights"
    ]:

        lines.append(
            f"- {insight}"
        )

    lines.append("")

    # --------------------------------------------
    # Authentication
    # --------------------------------------------

    lines.append(
        "## Authentication"
    )

    lines.append("")

    auth = analysis[
        "authentication"
    ]

    lines.append(
        f"- OAuth 2.0: "
        f"{auth['apps_with_oauth']['percentage']}%"
    )

    lines.append(
        f"- API key: "
        f"{auth['apps_with_api_key']['percentage']}%"
    )

    lines.append(
        f"- Basic Auth: "
        f"{auth['apps_with_basic_auth']['percentage']}%"
    )

    lines.append("")

    # --------------------------------------------
    # API
    # --------------------------------------------

    lines.append(
        "## API Surface"
    )

    lines.append("")

    for name, data in analysis[
        "api"
    ]["types"].items():

        lines.append(
            f"- {name}: "
            f"{data['percentage']}%"
        )

    lines.append("")

    lines.append(
        "### API Breadth"
    )

    lines.append("")

    for name, data in analysis[
        "api"
    ]["breadth"].items():

        lines.append(
            f"- {name}: "
            f"{data['percentage']}%"
        )

    lines.append("")

    # --------------------------------------------
    # MCP
    # --------------------------------------------

    lines.append(
        "## MCP"
    )

    lines.append("")

    for name, data in analysis[
        "mcp"
    ]["availability"].items():

        lines.append(
            f"- {name}: "
            f"{data['percentage']}%"
        )

    lines.append("")

    # --------------------------------------------
    # Buildability
    # --------------------------------------------

    lines.append(
        "## Buildability"
    )

    lines.append("")

    for name, data in analysis[
        "buildability"
    ]["verdicts"].items():

        lines.append(
            f"- {name}: "
            f"{data['percentage']}%"
        )

    lines.append("")

    # --------------------------------------------
    # Priority
    # --------------------------------------------

    lines.append(
        "## Preliminary Priority Clusters"
    )

    lines.append("")

    for cluster, data in analysis[
        "priority_clusters"
    ].items():

        lines.append(
            f"### {cluster}"
        )

        lines.append("")

        lines.append(
            f"Count: **{data['count']}**"
        )

        lines.append("")

        lines.append(
            ", ".join(data["apps"])
        )

        lines.append("")

    # --------------------------------------------
    # Data quality
    # --------------------------------------------

    lines.append(
        "## Data Quality"
    )

    lines.append("")

    issues = analysis[
        "data_quality"
    ]

    if not issues:

        lines.append(
            "No automated schema/data-quality issues detected."
        )

    else:

        lines.append(
            f"Detected **{len(issues)}** issues."
        )

        lines.append("")

        for issue in issues[:30]:

            lines.append(
                f"- `{issue['app']}` — "
                f"`{issue['field']}` — "
                f"{issue['issue']}"
            )

    lines.append("")

    # --------------------------------------------
    # Evidence
    # --------------------------------------------

    evidence = analysis[
        "evidence"
    ]

    lines.append(
        "## Evidence Coverage"
    )

    lines.append("")

    lines.append(
        f"- Total evidence items: "
        f"{evidence['total_evidence_items']}"
    )

    lines.append(
        f"- Average evidence items/app: "
        f"{evidence['average_evidence_per_app']}"
    )

    lines.append("")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("COMPOSIO RESEARCH — PATTERN & CLUSTER ANALYSIS")
    print("=" * 80)

    results = load_results()

    print(
        f"\nLoaded {len(results)} research records."
    )

    # --------------------------------------------
    # Run analyses
    # --------------------------------------------

    print("\nAnalyzing authentication...")
    authentication = analyze_authentication(
        results
    )

    print("Analyzing access...")
    access = analyze_access(
        results
    )

    print("Analyzing API surface...")
    api = analyze_api(
        results
    )

    print("Analyzing MCP...")
    mcp = analyze_mcp(
        results
    )

    print("Analyzing buildability...")
    buildability = analyze_buildability(
        results
    )

    print("Analyzing categories...")
    categories = analyze_categories(
        results
    )

    print("Clustering priority...")
    priority = analyze_priority(
        results
    )

    print("Analyzing evidence...")
    evidence = analyze_evidence(
        results
    )

    print("Analyzing confidence...")
    confidence = analyze_confidence(
        results
    )

    print("Checking data quality...")
    data_quality = check_data_quality(
        results
    )

    # --------------------------------------------
    # Generate insights
    # --------------------------------------------

    insights = generate_insights(
        results,
        authentication,
        access,
        api,
        mcp,
        buildability,
        priority
    )

    # --------------------------------------------
    # Final analysis object
    # --------------------------------------------

    analysis = {

        "meta": {
            "records_analyzed": len(results),
            "analysis_type": "deterministic",
            "source": "results/*.json and results.json"
        },

        "authentication": authentication,

        "access": access,

        "api": api,

        "mcp": mcp,

        "buildability": buildability,

        "categories": categories,

        "priority_clusters": priority,

        "evidence": evidence,

        "confidence": confidence,

        "data_quality": data_quality,

        "insights": insights
    }

    # --------------------------------------------
    # Save JSON
    # --------------------------------------------

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        ANALYSIS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            analysis,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------
    # Save Markdown
    # --------------------------------------------

    markdown = generate_markdown(
        results,
        analysis
    )

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(markdown)

    # --------------------------------------------
    # Console summary
    # --------------------------------------------

    print("\n")
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    print(
        f"\nRecords analyzed: {len(results)}"
    )

    print(
        f"Average confidence: "
        f"{confidence['average']}"
    )

    print(
        f"Total evidence items: "
        f"{evidence['total_evidence_items']}"
    )

    print(
        f"Data-quality issues: "
        f"{len(data_quality)}"
    )

    print("\nKey findings:")

    for insight in insights:

        print(
            f"  • {insight}"
        )

    print("\nOutput files:")

    print(
        f"  {ANALYSIS_FILE}"
    )

    print(
        f"  {SUMMARY_FILE}"
    )

    print("\nDone.")


if __name__ == "__main__":
    main()