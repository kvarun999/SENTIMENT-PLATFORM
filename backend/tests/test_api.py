import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from models import SocialMediaPost, SentimentAnalysis, SentimentAlert
from services.alerting import check_alerts

# --- TEST 1: Health Check ---
@pytest.mark.asyncio
async def test_health_check(client):
    """Test standard health check endpoint"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# --- TEST 2: Get Posts (Empty DB) ---
@pytest.mark.asyncio
async def test_get_posts_empty(client):
    """Test getting posts when DB is empty"""
    response = await client.get("/api/posts")
    assert response.status_code == 200
    assert response.json()["posts"] == []

# --- TEST 3: Get Posts (With Data) ---
@pytest.mark.asyncio
async def test_get_posts_with_data(client, db_session):
    """Test retrieving posts with joins"""
    post = SocialMediaPost(
        post_id="test_123", source="twitter", content="Hello", 
        author="user", created_at=datetime.utcnow()
    )
    db_session.add(post)
    
    analysis = SentimentAnalysis(
        post_id="test_123", model_name="bert", 
        sentiment_label="positive", confidence_score=0.99, emotion="joy"
    )
    db_session.add(analysis)
    await db_session.commit()

    response = await client.get("/api/posts")
    data = response.json()

    assert response.status_code == 200
    assert len(data["posts"]) == 1
    assert data["posts"][0]["sentiment"]["label"] == "positive"

# --- TEST 4: Aggregation Endpoint (MOCKED FIX) ---
@pytest.mark.asyncio
async def test_get_aggregate(client):
    """Test the Time-Series Aggregation Endpoint"""
    # SQLite doesn't support 'date_trunc', so we mock the DB response.
    # We trick the API into thinking the DB returned 1 row.
    
    class FakeRow:
        def __getitem__(self, idx):
            # Returns [timestamp, sentiment, count]
            return ["2025-01-01T12:00:00", "positive", 10][idx]

    mock_result = MagicMock()
    mock_result.__iter__.return_value = [FakeRow()]
    
    # We patch 'execute' to return our fake result instead of running real SQL
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", return_value=mock_result):
        response = await client.get("/api/sentiment/aggregate?period=hour")
        
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "hour"
    assert data["data"][0]["sentiment"] == "positive"
    assert data["data"][0]["count"] == 10

# --- TEST 5: Alerting Logic ---
@pytest.mark.asyncio
async def test_alert_logic_trigger(db_session):
    """Test that High Negative Ratio triggers an alert"""
    
    # 1. Setup Data: 6 negative posts, 0 positive
    for i in range(6):
        p = SocialMediaPost(
            post_id=f"bad_{i}", source="test", content="bad", author="test", 
            created_at=datetime.utcnow()
        )
        a = SentimentAnalysis(
            post_id=f"bad_{i}", model_name="test", sentiment_label="negative", 
            confidence_score=0.9, analyzed_at=datetime.utcnow()
        )
        db_session.add(p)
        db_session.add(a)
    await db_session.commit()

    # 2. Mock the Database Session
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = db_session
    mock_ctx.__aexit__.return_value = None

    with patch("services.alerting.AsyncSessionLocal", return_value=mock_ctx):
        # 3. Run the Alert Check
        await check_alerts()

    # 4. Verify Alert was Created
    from sqlalchemy import select
    result = await db_session.execute(select(SentimentAlert))
    alerts = result.scalars().all()
    
    assert len(alerts) >= 1
    assert alerts[0].alert_type == "high_negative_ratio"