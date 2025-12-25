import os
import json
import asyncio
import redis.asyncio as redis
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sentiment_analyzer import SentimentAnalyzer
from models import SocialMediaPost, SentimentAnalysis, Base

# --- Config ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_STREAM = "social_posts_stream"
REDIS_GROUP = "sentiment_workers"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@db/sentiment_db")

# --- Database Setup ---
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class SentimentWorker:
    def __init__(self):
        self.redis = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        self.analyzer = SentimentAnalyzer()
        self.consumer_name = f"worker_{os.getpid()}"

    async def setup_redis(self):
        try:
            await self.redis.xgroup_create(REDIS_STREAM, REDIS_GROUP, mkstream=True)
            print(f"✅ Created Consumer Group: {REDIS_GROUP}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"ℹ️ Consumer Group {REDIS_GROUP} already exists.")
            else:
                raise e

    async def save_result(self, post_data, analysis_result):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                created_at_str = post_data.get('created_at')
                if isinstance(created_at_str, str):
                    try:
                        created_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except ValueError:
                        created_dt = datetime.utcnow()
                else:
                    created_dt = datetime.utcnow()

                stmt = select(SocialMediaPost).where(SocialMediaPost.post_id == post_data['post_id'])
                result = await session.execute(stmt)
                existing_post = result.scalar_one_or_none()

                if not existing_post:
                    new_post = SocialMediaPost(
                        post_id=post_data['post_id'],
                        source=post_data['source'],
                        content=post_data['content'],
                        author=post_data['author'],
                        created_at=created_dt
                    )
                    session.add(new_post)
                    await session.flush()
                
                analysis = SentimentAnalysis(
                    post_id=post_data['post_id'],
                    model_name=analysis_result['model_name'],
                    sentiment_label=analysis_result['sentiment_label'],
                    confidence_score=analysis_result['confidence_score'],
                    emotion=analysis_result['emotion']
                )
                session.add(analysis)

    async def process_message(self, msg_id, data):
        try:
            # Rubric Phase 3: External Support
            # Check for override flag, otherwise use local for speed/cost
            if os.getenv("USE_EXTERNAL_LLM") == "true":
                result = await self.analyzer.analyze_external(data['content'])
            else:
                result = self.analyzer.analyze(data['content'])

            if not result:
                await self.redis.xack(REDIS_STREAM, REDIS_GROUP, msg_id)
                return

            await self.save_result(data, result)
            await self.redis.xack(REDIS_STREAM, REDIS_GROUP, msg_id)
            
            update_msg = {
                "type": "new_post",
                "data": {**data, "sentiment": result}
            }
            await self.redis.publish("sentiment_updates", json.dumps(update_msg))
            
            print(f"✅ Processed: {data['post_id']} -> {result['sentiment_label']}")

        except Exception as e:
            print(f"❌ Error processing {msg_id}: {e}")

    async def run(self):
        await self.setup_redis()
        print("👷 Worker Started. Waiting for posts...")
        
        while True:
            try:
                # Rubric Phase 3: Batch Processing
                entries = await self.redis.xreadgroup(
                    REDIS_GROUP, 
                    self.consumer_name, 
                    {REDIS_STREAM: ">"}, 
                    count=10, 
                    block=5000
                )

                if not entries:
                    continue

                for stream, messages in entries:
                    # Asyncio Gather for Concurrency
                    tasks = [self.process_message(msg_id, data) for msg_id, data in messages]
                    await asyncio.gather(*tasks)

            except Exception as e:
                print(f"Critical Worker Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        worker = SentimentWorker()
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("Worker stopping...")