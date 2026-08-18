from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

result = session.search(
    query="Research Salesforce official API documentation, authentication methods, API capabilities, MCP availability, and developer access requirements"
)

print(result)