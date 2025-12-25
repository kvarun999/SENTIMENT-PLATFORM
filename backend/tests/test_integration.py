import pytest
import json
from unittest.mock import AsyncMock, patch
from main import app

@pytest.mark.asyncio
async def test_full_flow(client, db_session):
    """
    Tests the full flow:
    1. Ingestion (Simulated via API for simplicity or direct DB insert)
    2. Retrieval via API
    3. Aggregation
    """
    
    # 1. Simulate Worker Saving Data (Direct DB Insert)
    from models import SocialMediaPost, SentimentAnalysis
    from datetime import datetime
    
    post = SocialMediaPost(
        post_id="integration_test_1",
        source="twitter",
        content="Integration test content",
        author="tester",
        created_at=datetime.utcnow()
    )
    db_session.add(post)
    
    analysis = SentimentAnalysis(
        post_id="integration_test_1",
        model_name="test_model",
        sentiment_label="positive",
        confidence_score=0.95,
        emotion="joy",
        analyzed_at=datetime.utcnow()
    )
    db_session.add(analysis)
    await db_session.commit()
    
    # 2. Test Posts API
    response = await client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert len(data['posts']) >= 1
    assert data['posts'][0]['post_id'] == "integration_test_1"
    
    # 3. Test Distribution API
    dist_response = await client.get("/api/sentiment/distribution?hours=24")
    assert dist_response.status_code == 200
    dist_data = dist_response.json()
    assert dist_data['distribution']['positive'] >= 1