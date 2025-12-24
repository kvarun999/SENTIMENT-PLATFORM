# Real-Time AI Sentiment Analysis Platform

A full-stack event-driven platform that ingests social media posts, analyzes sentiment using AI (DistilBERT), and visualizes results in real-time.

## Features

- **Real-Time Dashboard**: Live feed and charts updated via WebSockets.
- **AI Processing**: Local inference using Hugging Face Transformers.
- **Event-Driven**: Uses Redis Streams for reliable message processing.
- **Alerting**: Automatically detects high negative sentiment ratios.

## Quick Start

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd sentiment-platform
    ```

2.  **Setup Environment:**

    ```bash
    cp .env.example .env
    ```

3.  **Start Services:**

    ```bash
    docker compose up -d --build
    ```

4.  **Access Application:**

    - **Dashboard:** http://localhost:3000
    - **API Docs:** http://localhost:8000/docs

5.  **Run Tests:**
    ```bash
    docker compose exec backend python -m pytest --cov=.
    ```
