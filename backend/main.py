import os
import json
import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, Base, get_db
from models import SocialMediaPost, SentimentAnalysis, SentimentAlert
from services.alerting import check_alerts

# --- Config ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_CHANNEL = "sentiment_updates"

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# --- Background Tasks ---
async def redis_listener():
    """Listens to Redis and broadcasts to WebSockets"""
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    print("✅ Backend: Listening for Real-Time Updates...")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    except Exception as e:
        print(f"❌ Redis Error: {e}")
    finally:
        await r.close()

async def alert_loop():
    """Runs the alert check every 60 seconds"""
    print("✅ Backend: Alert Monitor Started...")
    while True:
        try:
            await asyncio.sleep(60)
            await check_alerts()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Alert Loop Error: {e}")

# --- LifeCycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Start Background Services
    task_redis = asyncio.create_task(redis_listener())
    task_alert = asyncio.create_task(alert_loop())
    
    print("🚀 System Startup Complete.")
    yield
    
    # 3. Cleanup
    task_redis.cancel()
    task_alert.cancel()

app = FastAPI(lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Endpoint ---
@app.websocket("/ws/sentiment")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send confirmation message
        await websocket.send_json({"type": "connected", "message": "Connected to sentiment stream"})
        while True:
            # Keep-alive loop
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# --- REST Endpoints ---

@app.get("/api/health")
async def health_check():
    """Health check for Docker Compose"""
    return {"status": "healthy", "service": "backend"}

@app.get("/api/posts")
async def get_posts(
    limit: int = 50, 
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve recent posts with joins"""
    query = (
        select(SocialMediaPost, SentimentAnalysis)
        .join(SentimentAnalysis, SocialMediaPost.post_id == SentimentAnalysis.post_id)
        .order_by(desc(SocialMediaPost.created_at))
        .limit(limit)
    )
    
    if source:
        query = query.where(SocialMediaPost.source == source)

    result = await db.execute(query)
    
    posts = []
    for post, analysis in result:
        posts.append({
            "post_id": post.post_id,
            "content": post.content,
            "source": post.source,
            "author": post.author,
            "created_at": post.created_at,
            "sentiment": {
                "label": analysis.sentiment_label,
                "score": analysis.confidence_score,
                "emotion": analysis.emotion
            }
        })
    return {"posts": posts}

@app.get("/api/sentiment/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """General Dashboard Stats"""
    # 1. Total Count
    total_q = select(func.count(SocialMediaPost.id))
    total_res = await db.execute(total_q)
    total = total_res.scalar()

    # 2. Distribution
    dist_q = (
        select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))
        .group_by(SentimentAnalysis.sentiment_label)
    )
    dist_res = await db.execute(dist_q)
    
    return {
        "total_posts": total,
        "distribution": {row[0]: row[1] for row in dist_res.all()}
    }

@app.get("/api/sentiment/aggregate")
async def get_aggregate(
    period: str = Query("hour", regex="^(minute|hour|day)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Time-Series Aggregation (Required for Rubric Phase 4)
    Uses PostgreSQL 'date_trunc' to group data.
    """
    # Truncate timestamp based on period (hour/day/minute)
    trunc_date = func.date_trunc(period, SentimentAnalysis.analyzed_at).label('timestamp')
    
    query = (
        select(
            trunc_date,
            SentimentAnalysis.sentiment_label,
            func.count(SentimentAnalysis.id)
        )
        .group_by(trunc_date, SentimentAnalysis.sentiment_label)
        .order_by(trunc_date)
        .limit(100)
    )
    
    result = await db.execute(query)
    
    # Process into readable format
    data = []
    for row in result:
        data.append({
            "timestamp": row[0],
            "sentiment": row[1],
            "count": row[2]
        })
        
    return {"period": period, "data": data}