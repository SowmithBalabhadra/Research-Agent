from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

result = session.execute(
    "COMPOSIO_SEARCH_WEB",
    arguments={
        "query": "Salesforce official developer documentation OAuth 2.0 REST API authentication"
    }
)

print(result)