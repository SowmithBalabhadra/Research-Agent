from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio = Composio()

session = composio.create(
    user_id="researcher"
)

tools = session.tools()

print(f"Number of tools: {len(tools)}")

for tool in tools:
    print(tool)