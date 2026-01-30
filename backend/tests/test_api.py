import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app, manager, redis_listener, metrics_broadcaster
from models import SocialMediaPost, SentimentAnalysis, SentimentAlert
from services.alerting import AlertService, check_alerts

# --- 1. HEALTH & FILTERS ---

@pytest.mark.asyncio
async def test_health_check_stats(client, db_session):
    """Covers dynamic health stats and DB disconnect logic (main.py:158, 165)"""
    # Success Path
    response = await client.get("/api/health")
    assert response.status_code == 200
    
    # Error Path: Force a database failure to cover line 161 (db_status = 'disconnected')
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=Exception("DB Down")):
        response = await client.get("/api/health")
        assert response.json()["services"]["database"] == "disconnected"

@pytest.mark.asyncio
async def test_get_posts_filters(client, db_session):
    """Covers all filtering branches in get_posts (main.py:197-214)"""
    now = datetime.utcnow()
    p = SocialMediaPost(post_id="f1", source="reddit", content="c", author="a", created_at=now)
    db_session.add(p)
    a = SentimentAnalysis(post_id="f1", model_name="m", sentiment_label="positive", confidence_score=0.9, analyzed_at=now)
    db_session.add(a)
    await db_session.commit()

    response = await client.get("/api/posts?source=reddit&sentiment=positive")
    assert response.status_code == 200
    assert len(response.json()["posts"]) >= 1

# --- 2. AGGREGATION (Fixed: Mocked to avoid date_trunc error) ---

@pytest.mark.asyncio
async def test_aggregate_endpoint_full_hit(client):
    """
    FIX: Mocks DB execution to avoid 'date_trunc' error on SQLite.
    Covers the aggregation JSON loop (main.py:286-306).
    """
    # Mock row simulating PostgreSQL return: [timestamp, pos, neg, neu, avg_conf]
    mock_row = [datetime.utcnow(), 10, 5, 2, 0.95]
    
    mock_result = MagicMock()
    mock_result.__iter__.return_value = [mock_row]
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", return_value=mock_result):
        response = await client.get("/api/sentiment/aggregate?period=hour&source=reddit")
        
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "hour"
    assert data["data"][0]["positive_count"] == 10

# --- 3. ALERTING & BACKGROUND TASKS ---

@pytest.mark.asyncio
async def test_alert_logic_full_cycle(db_session):
    """Covers AlertService trigger and save logic (alerting.py:51, 77)"""
    now = datetime.utcnow()
    # Add data to trigger alert (> 0.5 ratio)
    for i in range(1): # 1 positive
        db_session.add(SocialMediaPost(post_id=f"p{i}", source="t", content="g", author="u", created_at=now))
        db_session.add(SentimentAnalysis(post_id=f"p{i}", model_name="m", sentiment_label="positive", confidence_score=0.9))
    for i in range(6): # 6 negative
        db_session.add(SocialMediaPost(post_id=f"n{i}", source="t", content="b", author="u", created_at=now))
        db_session.add(SentimentAnalysis(post_id=f"n{i}", model_name="m", sentiment_label="negative", confidence_score=0.9))
    await db_session.commit()

    service = AlertService(db_session_maker=lambda: db_session)
    alert_data = await service.check_thresholds()
    assert alert_data is not None
    
    alert_id = await service.save_alert(alert_data)
    assert alert_id is not None

@pytest.mark.asyncio
async def test_check_alerts_wrapper():
    """Covers the check_alerts wrapper function (alerting.py:103-107)"""
    with patch("services.alerting.AlertService") as MockService:
        instance = MockService.return_value
        instance.check_thresholds = AsyncMock(return_value={"actual_ratio": 0.9, "timestamp": datetime.utcnow().isoformat(), "alert_type": "test", "threshold": 0.5, "window_start": datetime.utcnow(), "window_end": datetime.utcnow(), "metrics": {"total_count": 10}})
        instance.save_alert = AsyncMock()
        await check_alerts()
        assert instance.check_thresholds.called

@pytest.mark.asyncio
async def test_redis_listener_error_handling():
    """Covers redis listener exception path (main.py:52-54)"""
    with patch("redis.asyncio.Redis.pubsub", side_effect=Exception("Connection Failed")):
        await redis_listener() # Should catch exception and log it

@pytest.mark.asyncio
async def test_websocket_connection():
    """Standard WebSocket Test"""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/sentiment") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"

@pytest.mark.asyncio
async def test_get_posts_comprehensive_filters_new(client): # Removed db_session, as new test doesn't use it
    """Covers line 197-214: Hits all filtering branches in get_posts"""
    response = await client.get("/api/posts?source=twitter&sentiment=positive&limit=10&offset=0")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_aggregate_mock_hit(client):
    """Covers line 270-306: Hits the aggregate JSON processing loop"""
    mock_row = [datetime.utcnow(), 10, 5, 2, 0.95] # ts, pos, neg, neu, avg_conf
    mock_res = MagicMock()
    mock_res.__iter__.return_value = [mock_row]
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", return_value=mock_res):
        response = await client.get("/api/sentiment/aggregate?period=hour")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_alert_wrapper_hit():
    """Covers alerting.py: 103-107: Hits the check_alerts wrapper"""
    from services.alerting import check_alerts
    from unittest.mock import patch, AsyncMock
    with patch("services.alerting.AlertService") as MockService:
        MockService.return_value.check_thresholds = AsyncMock(return_value=None)
        await check_alerts()