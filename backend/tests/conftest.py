import pytest
import json

@pytest.fixture(autouse=True)
def mock_gemini_network_calls(monkeypatch):
    """
    Prevents external Google Gemini network calls during test suite execution.
    Returns simulated medical content or JSON based on prompt requests.
    """
    class MockContentResponse:
        def __init__(self, prompt=""):
            self._prompt = str(prompt)

        @property
        def text(self):
            if "JSON" in self._prompt or "json" in self._prompt or "{" in self._prompt:
                return json.dumps({
                    "title": "Simulated Medical Study Guide",
                    "summary": "High-yield MBBS review generated for testing.",
                    "key_points": ["Key concept 1", "Key concept 2"],
                    "citations": ["Standard Medical Reference"],
                    "cards": [{"front": "Concept A", "back": "Explanation A"}],
                    "questions": [{
                        "question": "What is the primary function?",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "correct_answer": "Option A",
                        "explanation": "High-yield explanation."
                    }]
                })
            return "This is a simulated Google Gemini response for MBBS learning."

    def fake_generate_content(self, contents, *args, **kwargs):
        return MockContentResponse(contents)

    def fake_send_message(self, contents, *args, **kwargs):
        return MockContentResponse(contents)

    try:
        import google.generativeai as genai
        monkeypatch.setattr(genai.GenerativeModel, "generate_content", fake_generate_content, raising=False)
        monkeypatch.setattr(genai.ChatSession, "send_message", fake_send_message, raising=False)
    except ImportError:
        pass
