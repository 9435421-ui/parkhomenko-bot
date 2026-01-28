from llm_client import call_llm
print("Testing LLM Integration...")
resp = call_llm("You are a helpful assistant for TERION.", "Say hello.")
print(f"Response: {resp}")
