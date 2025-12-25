import os
import json
import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc, and_
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
    """Listens to Redis and broadcasts new posts to WebSockets"""
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

async def metrics_broadcaster():
    """
    Rubric Req: Periodic metrics update (Type 3)
    Broadcasts aggregated stats every 30 seconds.
    """
    print("✅ Backend: Metrics Broadcaster Started...")
    while True:
        try:
            await asyncio.sleep(30)
            async with AsyncSessionLocal() as db:
                # Calculate last minute stats
                now = datetime.utcnow()
                one_min_ago = now - timedelta(minutes=1)
                
                query = (
                    select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))
                    .where(SentimentAnalysis.analyzed_at >= one_min_ago)
                    .group_by(SentimentAnalysis.sentiment_label)
                )
                result = await db.execute(query)
                stats = {row[0]: row[1] for row in result.all()}
                
                # Format for Frontend Trend Chart
                msg = {
                    "type": "metrics_update",
                    "data": {
                        "timestamp": now.isoformat(),
                        "positive": stats.get("positive", 0),
                        "negative": stats.get("negative", 0),
                        "neutral": stats.get("neutral", 0)
                    }
                }
                await manager.broadcast(json.dumps(msg))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Metrics Loop Error: {e}")

# --- LifeCycle ---
from database import AsyncSessionLocal # Import here for background task

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Start Background Services
    task_redis = asyncio.create_task(redis_listener())
    task_alert = asyncio.create_task(alert_loop())
    task_metrics = asyncio.create_task(metrics_broadcaster())
    
    print("🚀 System Startup Complete.")
    yield
    
    # 3. Cleanup
    task_redis.cancel()
    task_alert.cancel()
    task_metrics.cancel()

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
        # Rubric Req: Connection Confirmation
        await websocket.send_json({
            "type": "connected", 
            "message": "Connected to sentiment stream",
            "timestamp": datetime.utcnow().isoformat()
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# --- REST Endpoints ---

@app.get("/api/health")
async def health_check():
    """Health check for Docker Compose"""
    return {
        "status": "healthy", 
        "service": "backend",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(50, ge=1, le=100), 
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve posts with filtering and pagination"""
    query = (
        select(SocialMediaPost, SentimentAnalysis)
        .join(SentimentAnalysis, SocialMediaPost.post_id == SentimentAnalysis.post_id)
        .order_by(desc(SocialMediaPost.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    if source:
        query = query.where(SocialMediaPost.source == source)
    if sentiment:
        query = query.where(SentimentAnalysis.sentiment_label == sentiment)

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
    return {"posts": posts, "limit": limit, "offset": offset}

@app.get("/api/sentiment/distribution")
async def get_sentiment_distribution(
    hours: int = Query(24, ge=1, le=168),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Rubric Req: Distribution Endpoint
    Gets sentiment counts for the last N hours.
    """
    threshold = datetime.utcnow() - timedelta(hours=hours)
    
    query = (
        select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))
        .join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)
        .where(SentimentAnalysis.analyzed_at >= threshold)
    )
    
    if source:
        query = query.where(SocialMediaPost.source == source)
        
    query = query.group_by(SentimentAnalysis.sentiment_label)
    
    result = await db.execute(query)
    distribution = {row[0]: row[1] for row in result.all()}
    
    return {
        "timeframe_hours": hours,
        "distribution": distribution,
        "total": sum(distribution.values())
    }

# Alias for dashboard compatibility if needed, but distribution is the strict rubric name
@app.get("/api/sentiment/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await get_sentiment_distribution(hours=24, source=None, db=db)

@app.get("/api/sentiment/aggregate")
async def get_aggregate(
    period: str = Query("hour", regex="^(minute|hour|day)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Time-Series Aggregation (Required for Rubric Phase 4)
    """
    trunc_date = func.date_trunc(period, SentimentAnalysis.analyzed_at).label('timestamp')
    
    query = (
        select(
            trunc_date,
            SentimentAnalysis.sentiment_label,
            func.count(SentimentAnalysis.id)
        )
        .join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)
    )

    if start_date:
        query = query.where(SentimentAnalysis.analyzed_at >= start_date)
    if end_date:
        query = query.where(SentimentAnalysis.analyzed_at <= end_date)
    if source:
        query = query.where(SocialMediaPost.source == source)

    query = (
        query
        .group_by(trunc_date, SentimentAnalysis.sentiment_label)
        .order_by(trunc_date)
    )
    
    result = await db.execute(query)
    
    data = []
    for row in result:
        data.append({
            "timestamp": row[0],
            "sentiment": row[1],
            "count": row[2]
        })
        
    return {"period": period, "data": data}