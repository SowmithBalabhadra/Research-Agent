from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

url = "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/sforce_rest_api.htm"

result = session.execute(
    "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
    arguments={
        "urls": [url],
        "text": True,
        "max_characters": 15000
    }
)

print(result)