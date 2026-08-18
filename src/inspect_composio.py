from dotenv import load_dotenv
from composio import Composio
import inspect

load_dotenv()

composio = Composio()

print("Composio methods:")
for name in dir(composio):
    if not name.startswith("_"):
        print(name)

print("\nSession methods:")
session = composio.create(user_id="researcher")

for name in dir(session):
    if not name.startswith("_"):
        print(name)

import inspect

print("\nsearch() signature:")
print(inspect.signature(session.search))

print("\nsearch() documentation:")
print(inspect.getdoc(session.search))
print("\nexecute() signature:")
print(inspect.signature(session.execute))

print("\nexecute() documentation:")
print(inspect.getdoc(session.execute))