from ollama import chat

response = chat(
    model="qwen2.5:3b",
    messages=[
        {
            "role": "user",
            "content": """
You are a research assistant.

Extract the authentication method from this evidence:

"Salesforce uses OAuth 2.0 to secure API access via Connected Apps.
Applications obtain an access token and use it as a Bearer token."

Return ONLY JSON:

{
  "auth_methods": [],
  "evidence_summary": ""
}
"""
        }
    ]
)

print(response.message.content)