import json
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc
from database import AsyncSessionLocal
from models import SocialMediaPost, SentimentAnalysis, SentimentAlert

# Rubric Configuration
# Trigger alert if negative/positive ratio > 0.5 (Strict for testing)
ALERT_NEGATIVE_RATIO_THRESHOLD = 0.5 
ALERT_WINDOW_MINUTES = 5
ALERT_MIN_POSTS = 5

async def check_alerts():
    """
    Background job: Checks last 5 minutes of data. 
    If negative sentiment is too high, saves an Alert to the DB.
    """
    print("🔍 Running background alert check...")
    
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=ALERT_WINDOW_MINUTES)

        # 1. Aggregation Query: Count sentiments in the last window
        # "SELECT sentiment_label, COUNT(*) FROM ... WHERE created_at > window_start GROUP BY label"
        query = (
            select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))
            .join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)
            .where(SocialMediaPost.created_at >= window_start)
            .group_by(SentimentAnalysis.sentiment_label)
        )
        
        result = await db.execute(query)
        # Convert result to dict: {'positive': 10, 'negative': 5, 'neutral': 2}
        stats = {row[0]: row[1] for row in result.all()}
        
        positive = stats.get('positive', 0)
        negative = stats.get('negative', 0)
        neutral = stats.get('neutral', 0)
        total = positive + negative + neutral

        # 2. Threshold Logic
        if total < ALERT_MIN_POSTS:
            return # Not enough data to judge

        # Prevent division by zero
        if positive == 0:
            ratio = float(negative) 
        else:
            ratio = negative / positive

        # 3. Trigger Alert
        if ratio > ALERT_NEGATIVE_RATIO_THRESHOLD:
            print(f"⚠️ ALERT: Negative Ratio {ratio:.2f} > {ALERT_NEGATIVE_RATIO_THRESHOLD}")
            
            new_alert = SentimentAlert(
                alert_type="high_negative_ratio",
                threshold_value=ALERT_NEGATIVE_RATIO_THRESHOLD,
                actual_value=ratio,
                window_start=window_start,
                window_end=now,
                post_count=total,
                triggered_at=now,
                details=stats # Saves as JSON
            )
            db.add(new_alert)
            await db.commit()