import os
import time
import json
import random
import uuid
import redis
from datetime import datetime
from faker import Faker

# 1. Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
STREAM_NAME = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")

# 2. Initialize Faker and Redis
fake = Faker()
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    # Test connection
    r.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
    exit(1)

# 3. Data Templates (to make it look real)
PRODUCTS = ["iPhone 16", "Tesla Model 3", "Netflix", "ChatGPT", "Pixel 8", "AWS"]
POSITIVE_ADJECTIVES = ["amazing", "love", "great", "excellent", "superb"]
NEGATIVE_ADJECTIVES = ["terrible", "hate", "awful", "worst", "disappointed"]

def generate_post():
    """Generates a realistic fake social media post"""
    product = random.choice(PRODUCTS)
    
    # Simple logic to generate sentiment-biased text
    sentiment_type = random.choice(["positive", "negative", "neutral"])
    
    if sentiment_type == "positive":
        adj = random.choice(POSITIVE_ADJECTIVES)
        content = f"I just got the new {product} and it is {adj}! Highly recommend."
    elif sentiment_type == "negative":
        adj = random.choice(NEGATIVE_ADJECTIVES)
        content = f"My experience with {product} has been {adj}. Do not buy."
    else:
        content = f"Just saw an ad for {product}. wondering if it's any good."

    return {
        "post_id": str(uuid.uuid4()),
        "source": random.choice(["twitter", "reddit", "facebook"]),
        "author": fake.user_name(),
        "content": content,
        "created_at": datetime.utcnow().isoformat()
    }

def start_ingestion():
    """Main loop to publish posts"""
    print(f"Starting ingestion to stream: {STREAM_NAME}...")
    
    while True:
        try:
            # Generate a post
            post_data = generate_post()
            
            # Publish to Redis Stream
            # maxlen=1000 prevents Redis from filling up memory forever
            r.xadd(STREAM_NAME, post_data, maxlen=10000)
            
            print(f"Published post: {post_data['post_id']} ({post_data['source']})")
            
            # Rate limiting: 1 post every 0.5 to 2 seconds
            time.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            print(f"Error publishing post: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Wait for Redis to be ready (simple retry)
    time.sleep(5) 
    start_ingestion()