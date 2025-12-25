import os
import torch
import httpx # Needs to be in requirements.txt
import json
from transformers import pipeline

class SentimentAnalyzer:
    """
    Unified interface for sentiment analysis.
    Supports 'local' (Hugging Face) and 'external' (LLM).
    """
    def __init__(self):
        print("🧠 Loading AI Models... (This may take a moment)")
        
        # 1. Sentiment Model (DistilBERT)
        self.sentiment_pipe = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1 # Use CPU
        )

        # 2. Emotion Model (RobertA)
        self.emotion_pipe = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            device=-1
        )
        print("✅ Models Loaded.")

    def analyze(self, text: str) -> dict:
        """
        Default analysis method.
        """
        if not text:
            return None

        # --- A. Sentiment Analysis ---
        sent_result = self.sentiment_pipe(text[:512])[0]
        label = sent_result['label'].lower()
        score = sent_result['score']

        # --- B. Emotion Detection ---
        emo_result = self.emotion_pipe(text[:512])[0]
        emotion = emo_result['label'].lower()

        return {
            "sentiment_label": label,   # positive, negative
            "confidence_score": score,
            "emotion": emotion,
            "model_name": "distilbert-base-uncased"
        }

    async def analyze_external(self, text: str) -> dict:
        """
        Analyzes sentiment using an external LLM (e.g., Groq/OpenAI).
        Required for Rubric Phase 3.
        """
        api_key = os.getenv("EXTERNAL_LLM_API_KEY")
        if not api_key:
            # Fallback to local if no key provided
            return self.analyze(text)

        # Example structure for OpenAI-compatible API (Groq/OpenAI)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Strict JSON prompt
        prompt = f"""Analyze the sentiment of this text: "{text}". 
        Return ONLY a JSON object with keys: sentiment_label (positive/negative/neutral), confidence_score (0.0-1.0), and emotion."""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json={
                    "model": os.getenv("EXTERNAL_LLM_MODEL", "llama3-8b-8192"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                }, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data['choices'][0]['message']['content']
                    result = json.loads(content)
                    result['model_name'] = "external_llm"
                    return result
        except Exception as e:
            print(f"❌ External LLM Failed: {e}")
        
        # Fallback to local on error
        return self.analyze(text)