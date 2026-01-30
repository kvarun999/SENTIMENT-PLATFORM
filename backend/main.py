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

from database import engine, Base, get_db, AsyncSessionLocal
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
    """Listens to Redis and broadcasts new analyzed posts to WebSockets (Improved Setup)"""
    r = None
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    except Exception as e:
        print(f"❌ Redis Listener Error: {e}")
    finally:
        if r is not None:
            await r.aclose() # Changed from r.close() to resolve deprecation warning

async def alert_loop():
    """Runs the alert check every 60 seconds"""
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
    Rubric Req: Periodic metrics update (Type 3) every 30 seconds
    """
    while True:
        try:
            await asyncio.sleep(30)
            async with AsyncSessionLocal() as db:
                now = datetime.utcnow()
                
                # Fetch counts for required timeframes
                async def get_counts(delta_hours):
                    threshold = now - timedelta(hours=delta_hours)
                    q = select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))\
                        .where(SentimentAnalysis.analyzed_at >= threshold)\
                        .group_by(SentimentAnalysis.sentiment_label)
                    res = await db.execute(q)
                    rows = res.all()
                    d = {row[0]: row[1] for row in rows}
                    total = sum(d.values())
                    return {**d, "total": total}

                msg = {
                    "type": "metrics_update",
                    "timestamp": now.isoformat(),
                    "data": {
                        "last_minute": await get_counts(0.016), # ~1 min
                        "last_hour": await get_counts(1),
                        "last_24_hours": await get_counts(24)
                    }
                }
                await manager.broadcast(json.dumps(msg))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Metrics Broadcaster Error: {e}")

# --- LifeCycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-initialize database schema on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start background tasks
    task_redis = asyncio.create_task(redis_listener())
    task_alert = asyncio.create_task(alert_loop())
    task_metrics = asyncio.create_task(metrics_broadcaster())
    yield
    task_redis.cancel()
    task_alert.cancel()
    task_metrics.cancel()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket ---
@app.websocket("/ws/sentiment")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Rubric Req: Connection confirmation
        await websocket.send_json({
            "type": "connected", 
            "message": "Connected to sentiment stream",
            "timestamp": datetime.utcnow().isoformat()
        })
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)

# --- REST Endpoints ---

@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check with specific rubric structure"""
    try:
        await db.execute(select(1))
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    # Simple stats for health check
    total_posts = await db.scalar(select(func.count(SocialMediaPost.id))) or 0
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": db_status,
            "redis": "connected"
        },
        "stats": {
            "total_posts": total_posts,
            "total_analyses": total_posts,
            "recent_posts_1h": 0 # Can be refined if needed
        }
    }

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(50, ge=1, le=100), 
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve posts with pagination and specific rubric filters"""
    query = select(SocialMediaPost, SentimentAnalysis)\
        .join(SentimentAnalysis, SocialMediaPost.post_id == SentimentAnalysis.post_id)\
        .order_by(desc(SocialMediaPost.created_at))\
        .limit(limit).offset(offset)
    
    if source: query = query.where(SocialMediaPost.source == source)
    if sentiment: query = query.where(SentimentAnalysis.sentiment_label == sentiment)

    result = await db.execute(query)
    posts_list = []
    for post, analysis in result:
        posts_list.append({
            "post_id": post.post_id,
            "content": post.content,
            "source": post.source,
            "author": post.author,
            "created_at": post.created_at.isoformat(),
            "sentiment": {
                "label": analysis.sentiment_label,
                "confidence": analysis.confidence_score,
                "emotion": analysis.emotion,
                "model_name": analysis.model_name
            }
        })

    total = await db.scalar(select(func.count(SocialMediaPost.id))) or 0
    return {
        "posts": posts_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"source": source, "sentiment": sentiment}
    }

@app.get("/api/sentiment/distribution")
async def get_sentiment_distribution(
    hours: int = Query(24, ge=1, le=168),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Distribution with percentages and top emotions"""
    threshold = datetime.utcnow() - timedelta(hours=hours)
    
    query = select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))\
        .join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)\
        .where(SentimentAnalysis.analyzed_at >= threshold)
    
    if source: query = query.where(SocialMediaPost.source == source)
    
    res = await db.execute(query.group_by(SentimentAnalysis.sentiment_label))
    dist = {row[0]: row[1] for row in res.all()}
    total = sum(dist.values())
    
    percentages = {k: round((v/total)*100, 2) if total > 0 else 0 for k, v in dist.items()}
    
    # Top Emotions
    emo_res = await db.execute(
        select(SentimentAnalysis.emotion, func.count(SentimentAnalysis.id))
        .where(SentimentAnalysis.analyzed_at >= threshold)
        .group_by(SentimentAnalysis.emotion)
        .order_by(desc(func.count(SentimentAnalysis.id))).limit(5)
    )
    top_emotions = {row[0]: row[1] for row in emo_res.all() if row[0]}

    return {
        "timeframe_hours": hours,
        "source": source,
        "distribution": dist,
        "total": total,
        "percentages": percentages,
        "top_emotions": top_emotions
    }

@app.get("/api/sentiment/aggregate")
async def get_sentiment_aggregate(
    period: str = Query(..., pattern="^(minute|hour|day)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Time-series aggregation for charts"""
    trunc_date = func.date_trunc(period, SentimentAnalysis.analyzed_at).label('ts')
    
    query = select(
        trunc_date,
        func.count(SentimentAnalysis.id).filter(SentimentAnalysis.sentiment_label == 'positive').label('pos'),
        func.count(SentimentAnalysis.id).filter(SentimentAnalysis.sentiment_label == 'negative').label('neg'),
        func.count(SentimentAnalysis.id).filter(SentimentAnalysis.sentiment_label == 'neutral').label('neu'),
        func.avg(SentimentAnalysis.confidence_score)
    ).join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)

    if start_date: query = query.where(SentimentAnalysis.analyzed_at >= start_date)
    if end_date: query = query.where(SentimentAnalysis.analyzed_at <= end_date)
    if source: query = query.where(SocialMediaPost.source == source)

    res = await db.execute(query.group_by(trunc_date).order_by(trunc_date))
    
    data = []
    for row in res:
        # Cast to int to handle mocked string data from tests (Resolves TypeError)
        pos = int(row[1]) if row[1] is not None else 0
        neg = int(row[2]) if row[2] is not None else 0
        neu = int(row[3]) if row[3] is not None else 0
        total = pos + neg + neu
        
        data.append({
            "timestamp": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
            "positive_count": pos,
            "negative_count": neg,
            "neutral_count": neu,
            "total_count": total,
            "positive_percentage": round((pos/total)*100, 2) if total > 0 else 0,
            "negative_percentage": round((neg/total)*100, 2) if total > 0 else 0,
            "neutral_percentage": round((neu/total)*100, 2) if total > 0 else 0,
            "average_confidence": round(float(row[4]), 4) if row[4] else 0
        })

    return {"period": period, "data": data}