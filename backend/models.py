from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.sql import func
from database import Base

class SocialMediaPost(Base):
    __tablename__ = "social_media_posts"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Core Fields
    post_id = Column(String(255), unique=True, index=True, nullable=False)
    source = Column(String(50), index=True, nullable=False) # e.g., twitter, reddit
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False) # When user posted
    ingested_at = Column(DateTime(timezone=True), server_default=func.now()) # When we saw it

class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationship to Post
    post_id = Column(String(255), ForeignKey("social_media_posts.post_id"), nullable=False)
    
    # AI Results
    model_name = Column(String(100), nullable=False)
    sentiment_label = Column(String(20), nullable=False) # positive, negative, neutral
    confidence_score = Column(Float, nullable=False)
    emotion = Column(String(50), nullable=True) # joy, anger, etc.
    
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class SentimentAlert(Base):
    __tablename__ = "sentiment_alerts"

    id = Column(Integer, primary_key=True, index=True)
    
    alert_type = Column(String(50), nullable=False) # e.g., high_negative_ratio
    threshold_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    post_count = Column(Integer, nullable=False)
    
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    details = Column(JSON, nullable=True) # Extra context