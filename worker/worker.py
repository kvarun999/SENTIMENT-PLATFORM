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
        """Create Consumer Group if not exists"""
        try:
            await self.redis.xgroup_create(REDIS_STREAM, REDIS_GROUP, mkstream=True)
            print(f"✅ Created Consumer Group: {REDIS_GROUP}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"ℹ️ Consumer Group {REDIS_GROUP} already exists.")
            else:
                raise e

    async def save_result(self, post_data, analysis_result):
        """Saves Post + Analysis to DB transactionally [Fixes FK Error]"""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Parse Date (Fixes potential timestamp errors)
                created_at_str = post_data.get('created_at')
                if isinstance(created_at_str, str):
                    try:
                        # Handle ISO format '2025-01-15T10:30:00'
                        created_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except ValueError:
                        created_dt = datetime.utcnow()
                else:
                    created_dt = datetime.utcnow()

                # 2. Check if Post Exists (Upsert Logic)
                # We cannot use merge() because post_id is not the Primary Key
                stmt = select(SocialMediaPost).where(SocialMediaPost.post_id == post_data['post_id'])
                result = await session.execute(stmt)
                existing_post = result.scalar_one_or_none()

                if not existing_post:
                    # Create New Post
                    new_post = SocialMediaPost(
                        post_id=post_data['post_id'],
                        source=post_data['source'],
                        content=post_data['content'],
                        author=post_data['author'],
                        created_at=created_dt
                    )
                    session.add(new_post)
                    await session.flush() # Force ID generation and save to DB
                
                # 3. Save Analysis (Now safe because Post is guaranteed to exist)
                analysis = SentimentAnalysis(
                    post_id=post_data['post_id'],
                    model_name=analysis_result['model_name'],
                    sentiment_label=analysis_result['sentiment_label'],
                    confidence_score=analysis_result['confidence_score'],
                    emotion=analysis_result['emotion']
                )
                session.add(analysis)
            # Commit happens automatically here

    async def process_message(self, msg_id, data):
        """Process a single message"""
        try:
            # 1. Run AI Analysis
            result = self.analyzer.analyze(data['content'])
            if not result:
                # Skip invalid empty posts but ack them so we don't loop forever
                await self.redis.xack(REDIS_STREAM, REDIS_GROUP, msg_id)
                return

            # 2. Save to DB
            await self.save_result(data, result)
            
            # 3. Acknowledge Message
            await self.redis.xack(REDIS_STREAM, REDIS_GROUP, msg_id)
            
            # 4. Publish Update
            update_msg = {
                "type": "new_post",
                "data": {**data, "sentiment": result}
            }
            # Publish stringified JSON
            await self.redis.publish("sentiment_updates", json.dumps(update_msg))
            
            print(f"✅ Processed: {data['post_id']} -> {result['sentiment_label']}")

        except Exception as e:
            print(f"❌ Error processing {msg_id}: {e}")
            # Do NOT ack, so another worker can retry later

    async def run(self):
        """Main Loop"""
        await self.setup_redis()
        print("👷 Worker Started. Waiting for posts...")
        
        while True:
            try:
                entries = await self.redis.xreadgroup(
                    REDIS_GROUP, 
                    self.consumer_name, 
                    {REDIS_STREAM: ">"}, 
                    count=1, 
                    block=5000
                )
                
                if not entries:
                    continue

                for stream, messages in entries:
                    for msg_id, data in messages:
                        await self.process_message(msg_id, data)

            except Exception as e:
                print(f"Critical Worker Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        worker = SentimentWorker()
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("Worker stopping...")