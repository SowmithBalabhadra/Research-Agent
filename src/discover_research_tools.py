from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

tools = session.tools()

search_tool = next(
    tool for tool in tools
    if tool["function"]["name"] == "COMPOSIO_SEARCH_TOOLS"
)

result = composio.execute(
    search_tool["function"]["name"],
    {
        "queries": [
            {
                "use_case": "Research Salesforce official API documentation, authentication methods, API capabilities, MCP availability, and developer access requirements"
            }
        ],
        "session": {
            "generate_id": True
        }
    }
)

print(result)