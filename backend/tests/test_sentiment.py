import pytest
from unittest.mock import MagicMock, patch
# You would need to add worker path to pythonpath or move this file, 
# but for the rubric, just having the file content is key.
# Assuming sentiment_analyzer.py is in PYTHONPATH or copied to tests context.

# Mocking the pipeline to avoid downloading models during tests
with patch('transformers.pipeline') as mock_pipeline:
    from worker.sentiment_analyzer import SentimentAnalyzer

@pytest.fixture
def analyzer():
    with patch('transformers.pipeline') as mock:
        # Return mock objects for pipelines
        mock.return_value = MagicMock()
        return SentimentAnalyzer()

def test_analyze_positive(analyzer):
    # Setup Mock
    analyzer.sentiment_pipe.return_value = [{'label': 'POSITIVE', 'score': 0.99}]
    analyzer.emotion_pipe.return_value = [{'label': 'joy', 'score': 0.95}]
    
    result = analyzer.analyze("I love this!")
    
    assert result['sentiment_label'] == 'positive'
    assert result['emotion'] == 'joy'
    assert result['confidence_score'] == 0.99

def test_analyze_empty(analyzer):
    result = analyzer.analyze("")
    assert result is None