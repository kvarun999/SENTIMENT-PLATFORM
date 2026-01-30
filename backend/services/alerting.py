import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from database import AsyncSessionLocal
from models import SocialMediaPost, SentimentAnalysis, SentimentAlert

class AlertService:
    """
    Monitors sentiment metrics and triggers alerts on anomalies.
    """
    def __init__(self, db_session_maker=AsyncSessionLocal):
        """
        Initialize with configuration from environment variables.
        """
        self.db_session_maker = db_session_maker
        # Load environment variables with defaults
        self.threshold = float(os.getenv("ALERT_NEGATIVE_RATIO_THRESHOLD", 0.5))
        self.window_minutes = int(os.getenv("ALERT_WINDOW_MINUTES", 5))
        self.min_posts = int(os.getenv("ALERT_MIN_POSTS", 5))

    async def check_thresholds(self) -> Optional[dict]:
        """
        Check if current sentiment metrics exceed alert thresholds.
        """
        async with self.db_session_maker() as db:
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=self.window_minutes)

            # 1. Count positive/negative posts in the ALERT_WINDOW_MINUTES
            query = (
                select(SentimentAnalysis.sentiment_label, func.count(SentimentAnalysis.id))
                .join(SocialMediaPost, SentimentAnalysis.post_id == SocialMediaPost.post_id)
                .where(SocialMediaPost.created_at >= window_start)
                .group_by(SentimentAnalysis.sentiment_label)
            )
            
            result = await db.execute(query)
            stats = {row[0]: row[1] for row in result.all()}
            
            positive = stats.get('positive', 0)
            negative = stats.get('negative', 0)
            neutral = stats.get('neutral', 0)
            total = positive + negative + neutral

            # 2. If total posts < ALERT_MIN_POSTS, return None
            if total < self.min_posts:
                return None

            # 3. Calculate ratio = negative_count / positive_count
            # Handle division by zero: if positive is 0, ratio is the count of negative posts
            actual_ratio = negative / positive if positive > 0 else float(negative)

            # 4. If ratio > ALERT_NEGATIVE_RATIO_THRESHOLD, trigger alert
            if actual_ratio > self.threshold:
                alert_data = {
                    "alert_triggered": True,
                    "alert_type": "high_negative_ratio",
                    "threshold": self.threshold,
                    "actual_ratio": round(actual_ratio, 2),
                    "window_minutes": self.window_minutes,
                    "metrics": {
                        "positive_count": positive,
                        "negative_count": negative,
                        "neutral_count": neutral,
                        "total_count": total
                    },
                    "window_start": window_start,
                    "window_end": now,
                    "timestamp": now.isoformat()
                }
                return alert_data
            
            return None

    async def save_alert(self, alert_data: dict) -> int:
        """
        Save triggered alert to the sentiment_alerts table.
        """
        async with self.db_session_maker() as db:
            new_alert = SentimentAlert(
                alert_type=alert_data["alert_type"],
                threshold_value=alert_data["threshold"],
                actual_value=alert_data["actual_ratio"],
                window_start=alert_data["window_start"],
                window_end=alert_data["window_end"],
                post_count=alert_data["metrics"]["total_count"],
                triggered_at=datetime.fromisoformat(alert_data["timestamp"]),
                details=alert_data["metrics"]
            )
            db.add(new_alert)
            await db.commit()
            await db.refresh(new_alert)
            return new_alert.id

async def check_alerts():
    """
    Wrapper function used by the main backend loop.
    """
    service = AlertService()
    alert_data = await service.check_thresholds()
    if alert_data:
        print(f"⚠️ ALERT TRIGGERED: {alert_data['actual_ratio']} ratio detected.")
        await service.save_alert(alert_data)