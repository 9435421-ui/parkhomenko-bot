from llm_client import call_llm
print("Testing Claude 3.5 Sonnet...")
resp = call_llm("You are a helpful assistant.", "Say hello in Russian.")
print(f"Response: {resp}")
