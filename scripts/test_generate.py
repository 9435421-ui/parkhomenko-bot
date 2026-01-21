import os
os.environ['YANDEX_API_KEY'] = 'dummy'
os.environ['FOLDER_ID'] = 'dummy'
from content_agent import ContentAgent

# Create agent with dummy values
agent = ContentAgent(api_key='dummy', model_uri='dummy')

# Generate posts for testing
posts = agent.generate_posts(count=3, post_types={'seasonal': 1, 'fact': 1, 'case': 1})

for i, post in enumerate(posts, 1):
    print(f"Post {i} - Type: {post['type']}")
    print(f"Title: {post.get('title', 'No title')}")
    print(f"Body: {post['body']}")
    print(f"CTA: {post['cta']}")
    print(f"Image Prompt: {post.get('image_prompt', 'None')}")
    print("=" * 50)
