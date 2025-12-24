import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get DB URL from .env
# We use standard os.getenv because Pydantic settings are loaded later
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

# 2. Create the Async Engine
# echo=True prints SQL queries to console (good for debugging)
engine = create_async_engine(DATABASE_URL, echo=True)

# 3. Create Session Factory
# This is what generates new database sessions for each request
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 4. Create Base Class
# All our models will inherit from this
Base = declarative_base()

# 5. Dependency for FastAPI
# We will use this later in our API routes to get a DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session