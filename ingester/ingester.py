import os
import time
import json
import asyncio
import uuid
import random
import redis.asyncio as redis
from datetime import datetime

class DataIngester:
    """
    Publishes simulated social media posts to Redis Stream
    """
    def __init__(self, redis_client, stream_name: str, posts_per_minute: int = 60):
        self.redis = redis_client
        self.stream_name = stream_name
        self.posts_per_minute = posts_per_minute
        self.products = ["iPhone 16", "Tesla Model 3", "ChatGPT", "Netflix", "Amazon Prime"]
        self.authors = ["alex_99", "tech_guru", "user_123", "morning_star", "pixel_fan"]

    def generate_post(self) -> dict:
        product = random.choice(self.products)
        roll = random.random()
        
        if roll < 0.4: # Positive
            content = f"I absolutely love the {product}! This is amazing and exceeded my expectations."
        elif roll < 0.7: # Neutral
            content = f"Just tried the {product}. It is what it is. Received it today."
        else: # Negative
            content = f"Very disappointed with the {product}. Terrible experience, would not recommend."

        return {
            'post_id': f"post_{uuid.uuid4().hex[:10]}",
            'source': random.choice(['reddit', 'twitter']),
            'content': content,
            'author': random.choice(self.authors),
            'created_at': datetime.utcnow().isoformat() + "Z"
        }

    async def publish_post(self, post_data: dict) -> bool:
        try:
            await self.redis.xadd(self.stream_name, post_data)
            return True
        except Exception as e:
            print(f"❌ Redis Error: {e}")
            return False

    async def start(self, duration_seconds: int = None):
        interval = 60.0 / self.posts_per_minute
        start_time = time.time()
        
        while True:
            if duration_seconds and (time.time() - start_time) > duration_seconds:
                break
            
            post = self.generate_post()
            await self.publish_post(post)
            await asyncio.sleep(interval)

async def main():
    host = os.getenv("REDIS_HOST", "redis")
    client = redis.Redis(host=host, port=6379, decode_responses=True)
    stream = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")
    ppm = int(os.getenv("INGESTION_RATE", 60))
    
    ingester = DataIngester(client, stream, posts_per_minute=ppm)
    await ingester.start()

if __name__ == "__main__":
    asyncio.run(main())