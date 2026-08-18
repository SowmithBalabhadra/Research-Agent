from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

result = session.search(
    query="Search the web for official Salesforce developer documentation and fetch web pages so an agent can research API authentication, API capabilities, MCP availability, pricing, and developer access"
)

print(result)