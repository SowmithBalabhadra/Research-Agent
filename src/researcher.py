from dotenv import load_dotenv
from composio import Composio
from ollama import chat
import json

load_dotenv()

MODEL = "qwen2.5:3b"

VALID_BREADTH = {"broad", "moderate", "limited", "unknown"}
VALID_VERDICT = {"easy", "moderate", "difficult", "not_feasible", "unknown"}
VALID_MCP = {True, False, "unknown"}


def call_qwen(prompt, schema):
    response = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        format=schema,
        options={"temperature": 0, "num_ctx": 8192}
    )
    content = response.message.content.strip()
    if not content:
        raise RuntimeError("Empty model response.")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1:
            raise RuntimeError(f"No JSON object in response:\n{content}")
        return json.loads(content[start:end + 1])


def evidence_text(sources):
    if not sources:
        return "No evidence found for this topic."
    parts = []
    for i, s in enumerate(sources, start=1):
        parts.append(
            f"SOURCE {i}\nTITLE: {s.get('title', '')}\nURL: {s.get('url', '')}\n"
            f"CONTENT:\n{s.get('content', '')}\n"
        )
    return "\n".join(parts)


EVIDENCE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["claim", "url"],
        "properties": {
            "claim": {"type": "string"},
            "url": {"type": "string"}
        }
    }
}


def extract_auth(app_name, sources):
    prompt = f"""
Extract ONLY explicitly stated authentication facts about {app_name} from the
excerpts below. Do not guess or use prior knowledge.

methods: authentication mechanisms (OAuth 2.0, API Key, Basic Auth, Bearer Token, JWT, Other)
flows: auth flows (Authorization Code, Client Credentials, Device Authorization, PKCE, Refresh Token)
token_types: credential/token forms (access token, bearer token, API key, JWT)
evidence: list of {{claim, url}}, url must be one of the URLs below

If nothing is stated for a field, return an empty list. Return only the JSON object.

SOURCES:
{evidence_text(sources)}
"""
    schema = {
        "type": "object",
        "required": ["methods", "flows", "token_types", "evidence"],
        "properties": {
            "methods": {"type": "array", "items": {"type": "string"}},
            "flows": {"type": "array", "items": {"type": "string"}},
            "token_types": {"type": "array", "items": {"type": "string"}},
            "evidence": EVIDENCE_SCHEMA
        }
    }
    return call_qwen(prompt, schema)


def extract_api(app_name, sources):
    prompt = f"""
Extract ONLY explicitly stated API facts about {app_name} from the excerpts below.

available: true if a documented public API exists, false otherwise
types: API types explicitly mentioned (REST, GraphQL, SOAP, RPC, Webhooks, Other). SDKs are not API types.
evidence: list of {{claim, url}}, url must be one of the URLs below

Return only the JSON object.

SOURCES:
{evidence_text(sources)}
"""
    schema = {
        "type": "object",
        "required": ["available", "types", "evidence"],
        "properties": {
            "available": {"type": "boolean"},
            "types": {"type": "array", "items": {"type": "string"}},
            "evidence": EVIDENCE_SCHEMA
        }
    }
    return call_qwen(prompt, schema)


def extract_access(app_name, sources):
    prompt = f"""
Extract developer-access facts about {app_name} from the excerpts below.

If a source mentions a free trial, free developer account, free signup, or a
"get started for free" style page, that counts as explicit evidence for
developer_signup. Do not require the word "unknown" to appear before using it;
use "unknown" ONLY when nothing at all is said about that field.

developer_signup: how a developer gets an account (short phrase, e.g. "free developer account", "paid account required", "contact sales")
credential_access: how the actual API key/token is obtained (short phrase)
plan_requirement: "none" or "paid plan required"
admin_requirement: "none" or "admin approval required"
partner_requirement: "none" or "partnership required"
evidence: list of {{claim, url}}, url must be one of the URLs below

Example: if a source says "Start building on Salesforce for free with a
development environment", the correct output includes:
developer_signup: "free developer account"
evidence: [{{"claim": "Free development environment available", "url": "<that source's URL>"}}]

Return only the JSON object.

SOURCES:
{evidence_text(sources)}
"""
    schema = {
        "type": "object",
        "required": [
            "developer_signup", "credential_access", "plan_requirement",
            "admin_requirement", "partner_requirement", "evidence"
        ],
        "properties": {
            "developer_signup": {"type": "string"},
            "credential_access": {"type": "string"},
            "plan_requirement": {"type": "string"},
            "admin_requirement": {"type": "string"},
            "partner_requirement": {"type": "string"},
            "evidence": EVIDENCE_SCHEMA
        }
    }
    result = call_qwen(prompt, schema)
    for field in ["developer_signup", "credential_access", "plan_requirement",
                  "admin_requirement", "partner_requirement"]:
        value = str(result.get(field, "")).strip()
        if value.lower().startswith("http") or len(value.split()) > 8:
            result[field] = "unknown"
    return result


def extract_mcp(app_name, sources):
    prompt = f"""
Extract ONLY explicitly stated MCP (Model Context Protocol) facts about
{app_name} from the excerpts below.

available: true ONLY if the sources explicitly mention an MCP server, MCP
support, or Model Context Protocol integration for {app_name}. false if the
sources discuss {app_name} but no MCP is mentioned. "unknown" if the sources
say nothing relevant to MCP at all.
details: ONE concise sentence summarizing how the MCP integration works, in your own words. Do not copy setup steps, callback URLs, or client-configuration tables from the source.
auth: how the MCP server authenticates, if documented, else ""
evidence: list of {{claim, url}}. Each claim must be a factual sentence, not a client name, product name, or a bare URL.

Do NOT infer MCP support merely because a REST API exists.
Do NOT list individual client apps (Claude, ChatGPT, Cursor, Postman, etc.) or their callback URLs as evidence.
Return only the JSON object.

SOURCES:
{evidence_text(sources)}
"""
    schema = {
        "type": "object",
        "required": ["available", "details", "auth", "evidence"],
        "properties": {
            "available": {},
            "details": {"type": "string"},
            "auth": {"type": "string"},
            "evidence": EVIDENCE_SCHEMA
        }
    }
    result = call_qwen(prompt, schema)
    result["available"] = normalize_mcp_available(result.get("available"))
    return result


def normalize_mcp_available(raw):
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("available", raw.get("mcp", "unknown")))
    if isinstance(raw, list):
        raw = raw[0] if raw else "unknown"
    if isinstance(raw, bool):
        return raw
    val = str(raw).strip().lower()
    if val in ("true", "yes", "available"):
        return True
    if val in ("false", "no", "not available", "none"):
        return False
    return "unknown"


def enforce_auth_grounding(auth):
    if not auth.get("evidence"):
        auth["methods"] = []
        auth["flows"] = []
        auth["token_types"] = []
    return auth


def enforce_access_grounding(access):
    if not access.get("evidence"):
        for field in ["developer_signup", "credential_access", "plan_requirement",
                      "admin_requirement", "partner_requirement"]:
            access[field] = "unknown"
    return access


def reconcile_mcp_available(mcp):
    if mcp.get("available") == "unknown":
        signal = (mcp.get("details", "") + " " + mcp.get("auth", "")).strip()
        if signal and mcp.get("evidence"):
            mcp["available"] = True
    return mcp


def extract_description(app_name, evidence_pack):
    combined = []
    for topic in ["api", "access"]:
        sources = evidence_pack.get(topic, [])
        if sources:
            combined.append(sources[0])
    prompt = f"""
Write exactly one concise sentence describing what {app_name} is and does,
based only on the excerpts below. Do not mention authentication or API details.

SOURCES:
{evidence_text(combined)}
"""
    schema = {
        "type": "object",
        "required": ["description"],
        "properties": {"description": {"type": "string"}}
    }
    return call_qwen(prompt, schema).get("description", "").strip()


def classify_breadth(api_result):
    if not api_result.get("available"):
        return "unknown"
    types = api_result.get("types", [])
    evidence_count = len(api_result.get("evidence", []))
    if len(types) >= 2 and evidence_count >= 2:
        return "broad"
    if len(types) >= 1:
        return "moderate"
    return "limited"


def classify_buildability(auth, api, access, mcp):
    if not api.get("available"):
        return "not_feasible", "No documented public API found."

    partner = str(access.get("partner_requirement", "unknown")).lower()
    admin = str(access.get("admin_requirement", "unknown")).lower()
    plan = str(access.get("plan_requirement", "unknown")).lower()

    if "required" in partner or "partner" in partner:
        return "difficult", "Requires partnership / contact-sales approval."
    if "required" in admin:
        return "moderate", "Requires admin approval to obtain credentials."
    if "required" in plan:
        return "moderate", "Requires a paid plan for API access."
    if mcp.get("available") is True or auth.get("methods"):
        return "easy", ""
    return "unknown", "Insufficient evidence to classify buildability."


def compute_confidence(auth, api, access, mcp):
    topics = [auth, api, access, mcp]
    topics_with_evidence = sum(1 for t in topics if t.get("evidence"))
    coverage = topics_with_evidence / 4
    total_evidence = sum(len(t.get("evidence", [])) for t in topics)
    density = min(1.0, total_evidence / 8)
    return round(0.5 * coverage + 0.5 * density, 2)


def build_record(app_name, category, evidence_pack):
    auth = enforce_auth_grounding(extract_auth(app_name, evidence_pack.get("authentication", [])))
    api = extract_api(app_name, evidence_pack.get("api", []))
    access = enforce_access_grounding(extract_access(app_name, evidence_pack.get("access", [])))
    mcp = reconcile_mcp_available(extract_mcp(app_name, evidence_pack.get("mcp", [])))
    description = extract_description(app_name, evidence_pack)

    breadth = classify_breadth(api)
    verdict, blocker = classify_buildability(auth, api, access, mcp)
    confidence = compute_confidence(auth, api, access, mcp)

    all_evidence = []
    for field_prefix, part in [
        ("authentication", auth), ("api", api),
        ("access", access), ("mcp", mcp)
    ]:
        for item in part.get("evidence", []):
            all_evidence.append({
                "field": field_prefix,
                "claim": item.get("claim", ""),
                "url": item.get("url", "")
            })

    record = {
        "app": app_name,
        "category": category,
        "description": description,
        "authentication": {
            "methods": auth.get("methods", []),
            "flows": auth.get("flows", []),
            "token_types": auth.get("token_types", [])
        },
        "access": {
            "developer_signup": access.get("developer_signup", "unknown"),
            "credential_access": access.get("credential_access", "unknown"),
            "plan_requirement": access.get("plan_requirement", "unknown"),
            "admin_requirement": access.get("admin_requirement", "unknown"),
            "partner_requirement": access.get("partner_requirement", "unknown")
        },
        "api": {
            "available": bool(api.get("available", False)),
            "types": api.get("types", []),
            "breadth": breadth if breadth in VALID_BREADTH else "unknown"
        },
        "mcp": {
            "available": mcp.get("available", "unknown"),
            "details": mcp.get("details", ""),
            "auth": mcp.get("auth", "")
        },
        "buildability": {
            "verdict": verdict if verdict in VALID_VERDICT else "unknown",
            "blocker": blocker
        },
        "evidence": all_evidence,
        "confidence": confidence,
        "notes": ""
    }
    validate_result(record)
    return record


def validate_result(result):
    required_fields = [
        "app", "category", "description", "authentication", "access",
        "api", "mcp", "buildability", "evidence", "confidence", "notes"
    ]
    missing = [f for f in required_fields if f not in result]
    if missing:
        raise RuntimeError("Result missing required fields: " + ", ".join(missing))

    if not result.get("app"):
        raise RuntimeError("Empty app field.")
    if not result.get("description"):
        raise RuntimeError("Empty description.")

    api = result["api"]
    if api.get("breadth") not in VALID_BREADTH:
        raise RuntimeError("Invalid API breadth: " + str(api.get("breadth")))

    mcp = result["mcp"]
    if mcp.get("available") not in VALID_MCP:
        raise RuntimeError("Invalid MCP availability: " + str(mcp.get("available")))

    buildability = result["buildability"]
    if buildability.get("verdict") not in VALID_VERDICT:
        raise RuntimeError("Invalid buildability verdict: " + str(buildability.get("verdict")))

    for item in result["evidence"]:
        if not item.get("field") or not item.get("claim") or not item.get("url"):
            raise RuntimeError("Evidence item missing field/claim/url.")

    confidence = result["confidence"]
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        raise RuntimeError("confidence must be a number between 0.0 and 1.0.")

    print("Validation passed.")


class AppResearcher:

    def __init__(self):
        self.composio = Composio()
        self.session = self.composio.create(user_id="researcher")

    def search(self, query):
        result = self.session.execute("COMPOSIO_SEARCH_WEB", arguments={"query": query})
        if result.error:
            raise RuntimeError(result.error)
        return result.data

    def fetch(self, urls):
        if not urls:
            return []
        result = self.session.execute(
            "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
            arguments={"urls": urls, "text": True, "max_characters": 3500}
        )
        if result.error:
            raise RuntimeError(result.error)
        return result.data

    def clean_evidence(self, fetched_data):
        cleaned = []
        if not fetched_data:
            return cleaned
        results = fetched_data.get("results", [])
        if not isinstance(results, list):
            return cleaned
        seen_urls = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            text = str(item.get("text", "")).strip()
            if not url or not text or url in seen_urls:
                continue
            seen_urls.add(url)
            junk_markers = [
                "Skip Navigation", "Select An Org", "Loading",
                "Ask me product support and troubleshooting questions",
                "Ask Agentforce", "close  Help shape the future"
            ]
            for marker in junk_markers:
                text = text.replace(marker, " ")
            text = " ".join(text.split())

            cleaned.append({"url": url, "title": title, "content": text[:2500]})
        return cleaned

    def build_evidence_pack(self, fetched_sources):
        evidence_pack = {}
        for topic, fetched_data in fetched_sources.items():
            cleaned = self.clean_evidence(fetched_data)
            evidence_pack[topic] = cleaned[:3]
        return evidence_pack

    def research_app(self, app_name):
        queries = {
            "authentication": f"{app_name} official developer documentation API authentication OAuth API key bearer token",
            "api": f"{app_name} official developer documentation REST API GraphQL SOAP API endpoints",
            "access": f"{app_name} official developer documentation API access developer account credentials free trial paid plan admin permissions",
            "mcp": f"{app_name} official developer documentation MCP Model Context Protocol server integration authentication"
        }

        raw_research = {}
        fetched_sources = {}
        all_urls = set()

        for topic, query in queries.items():
            print(f"Searching {app_name}: {topic}")
            result = self.search(query)
            if not isinstance(result, dict):
                result = {}
            raw_research[topic] = result

            topic_urls = []
            seen_topic_urls = set()
            for citation in result.get("citations", []):
                if not isinstance(citation, dict):
                    continue
                url = citation.get("url")
                if not url:
                    continue
                url = str(url).strip()
                if url in seen_topic_urls:
                    continue
                seen_topic_urls.add(url)
                topic_urls.append(url)
                all_urls.add(url)

            selected_urls = topic_urls[:3]
            raw_research[topic]["selected_urls"] = selected_urls
            for url in selected_urls:
                print(f"  {topic} -> {url}")

        print(f"Found {len(all_urls)} unique sources.")

        for topic, result in raw_research.items():
            urls = result.get("selected_urls", [])
            if not urls:
                print(f"No sources found for {topic}")
                fetched_sources[topic] = []
                continue
            print(f"Fetching {topic}: {len(urls)} sources")
            fetched_sources[topic] = self.fetch(urls)

        evidence_pack = self.build_evidence_pack(fetched_sources)
        for topic, sources in evidence_pack.items():
            print(f"{topic}: {len(sources)} cleaned sources")
            for s in sources:
                preview = s.get("content", "")[:200].replace("\n", " ")
                print(f"    [{s.get('url')}] {preview!r}")

        return evidence_pack


if __name__ == "__main__":
    researcher = AppResearcher()
    evidence_pack = researcher.research_app("Salesforce")
    result = build_record("Salesforce", "CRM and Sales", evidence_pack)

    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    with open("results.json", "w") as f:
        json.dump([result], f, indent=2, ensure_ascii=False)