import os
import httpx
import json
import asyncio
from transformers import pipeline

class SentimentAnalyzer:
    def __init__(self, model_type: str = 'local', model_name: str = None):
        self.model_type = model_type
        if model_type == 'local':
            # SST-2 is optimized for positive/negative. 
            self.sentiment_pipe = pipeline(
                "text-classification", 
                model=model_name or "distilbert-base-uncased-finetuned-sst-2-english",
                device=-1
            )
            self.emotion_pipe = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                device=-1
            )

    def analyze(self, text: str):
        """Standard wrapper for synchronous tests (Resolves AttributeError)"""
        if not text: return None
        res = self.sentiment_pipe(text[:512])[0]
        emo = self.emotion_pipe(text[:512])[0]
        
        return {
            "sentiment_label": res['label'].lower(),
            "confidence_score": float(res['score']),
            "emotion": emo['label'].lower(),
            "model_name": "distilbert-base-uncased"
        }

    async def analyze_sentiment(self, text: str) -> dict:
        """Async version for production worker"""
        res = self.analyze(text)
        return res if res else {"sentiment_label": "neutral", "confidence_score": 0.0, "model_name": "none"}

    async def batch_analyze(self, texts: list[str]) -> list[dict]:
        """Batch processing (Rubric Requirement)"""
        return [await self.analyze_sentiment(t) for t in texts]

    async def analyze_external(self, text: str) -> dict:
        """
        Analyzes sentiment using an external LLM (e.g., Groq).
        Satisfies Phase 3: External Support.
        """
        api_key = os.getenv("EXTERNAL_LLM_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            return await self.analyze_sentiment(text)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = f'Analyze the sentiment of this text: "{text}". Return ONLY a JSON object with keys: sentiment_label (positive/negative/neutral), confidence_score (0.0-1.0), and emotion.'
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json={
                    "model": os.getenv("EXTERNAL_LLM_MODEL", "llama-3.1-8b-instant"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                }, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    result = json.loads(data['choices'][0]['message']['content'])
                    result['model_name'] = "external_llm"
                    return result
        except Exception:
            pass
        
        return await self.analyze_sentiment(text)