# Real-Time AI Sentiment Analysis Platform

A full-stack event-driven platform that ingests social media posts, analyzes sentiment using AI (DistilBERT/RoBERTa), and visualizes results in real-time. This project demonstrates microservices architecture, Redis Streams, and WebSocket integration.

---

## 🚀 Features

- **Real-Time Dashboard**: Live feed and charts updated via WebSockets.
- **AI Processing**: Local inference using Hugging Face Transformers with external LLM fallback.
- **Event-Driven Architecture**: Redis Streams with consumer groups for reliable message processing.
- **Alerting System**: Automatically detects high negative sentiment ratios.
- **Historic Analysis**: Time-series aggregation and sentiment distribution statistics.

---

## 🏗️ Architecture

The system consists of **6 containerized services**:

- Frontend (Web Dashboard)
- Backend API
- AI Worker
- Data Ingester
- Redis (Streams)
- PostgreSQL (Persistence)

For detailed design decisions and diagrams, see **ARCHITECTURE.md**.

---

## ⚙️ Prerequisites

- **Docker**: v20.10+
- **Docker Compose**: v2.0+
- **RAM**: 4GB minimum recommended
- **Ports**:
  - `3000` → Frontend
  - `8000` → Backend API
- **API Keys** (Optional):
  - Groq / OpenAI (for external LLM fallback)

---

## ⚡ Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd sentiment-platform
```

### 2. Setup Environment

```bash
cp .env.example .env
# Edit .env to add EXTERNAL_LLM_API_KEY if needed
```

### 3. Start Services

```bash
docker-compose up -d --build
```

> ⏳ Wait ~30 seconds for the AI worker to download models.

### 4. Access the Application

- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### 5. Run Tests

```bash
docker-compose exec backend pytest --cov=.
```

---

## 🔧 Configuration

The application is configured using environment variables in `.env`.

| Variable                       | Description               | Default             |
| ------------------------------ | ------------------------- | ------------------- |
| POSTGRES_USER                  | Database user             | sentiment_user      |
| POSTGRES_PASSWORD              | Database password         | secure_password_123 |
| REDIS_HOST                     | Redis hostname            | redis               |
| EXTERNAL_LLM_API_KEY           | External LLM fallback key | -                   |
| ALERT_NEGATIVE_RATIO_THRESHOLD | Alert trigger ratio       | 0.5                 |

---

## 📡 API Documentation

### REST Endpoints

- `GET /api/health` — System health status
- `GET /api/posts` — List recent posts (pagination supported)
- `GET /api/sentiment/distribution` — Sentiment distribution over time
- `GET /api/sentiment/aggregate` — Time-series data for charts

### WebSocket

- `WS /ws/sentiment` — Live sentiment stream

---

## ✅ Notes

- Designed for horizontal scalability
- Fault-tolerant message processing using Redis Streams
- Suitable for real-time analytics and monitoring use cases
