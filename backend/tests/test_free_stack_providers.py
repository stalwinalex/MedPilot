import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.config import settings
from app.agent.llm_provider import (
    get_llm_provider,
    is_gemini_configured,
    is_groq_configured,
    is_openai_configured,
    GeminiProvider,
    GroqProvider,
    OpenAIProvider,
    FallbackAcademicProvider
)
from app.agent.agent_tools_registry import AgentToolsRegistry
from app.agent.diagram_generator import MedicalDiagramGenerator


def test_diagram_generator_free_svg_and_mermaid():
    """Verify diagram generator outputs both Base64 SVG and structured Mermaid code with zero paid APIs"""
    res = MedicalDiagramGenerator.generate_diagram("Brachial Plexus", "roots trunks cords")
    assert res["image_url"].startswith("data:image/svg+xml;base64,")
    assert "mermaid_code" in res
    assert "graph TD" in res["mermaid_code"] or "graph LR" in res["mermaid_code"]
    assert "Roots" in res["mermaid_code"] or "C5" in res["mermaid_code"]

    res_nephron = MedicalDiagramGenerator.generate_diagram("Nephron", "tubule")
    assert res_nephron["image_url"].startswith("data:image/svg+xml;base64,")
    assert "Glomerulus" in res_nephron["mermaid_code"]


def test_provider_priority_hierarchy():
    """
    Verify provider priority:
    1. Gemini (primary)
    2. Groq (fallback)
    3. OpenAI (preserved / optional)
    4. FallbackAcademicProvider (offline)
    """
    # 1. Gemini primary
    with patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch.object(settings, "GROQ_API_KEY", "test-groq-key"), \
         patch.object(settings, "OPENAI_API_KEY", "test-openai-key"):
        with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel"):
            provider = get_llm_provider()
            assert isinstance(provider, GeminiProvider)

    # 2. Groq fallback (when Gemini unconfigured)
    with patch.object(settings, "GEMINI_API_KEY", None), \
         patch.object(settings, "GROQ_API_KEY", "gsk-test-groq-key"), \
         patch.object(settings, "OPENAI_API_KEY", "test-openai-key"):
        provider = get_llm_provider()
        assert isinstance(provider, GroqProvider)
        assert provider.model_name == "llama-3.3-70b-versatile"

    # 3. OpenAI preserved (when Gemini & Groq unconfigured)
    with patch.object(settings, "GEMINI_API_KEY", None), \
         patch.object(settings, "GROQ_API_KEY", None), \
         patch.object(settings, "OPENAI_API_KEY", "sk-test-openai-key"):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)

    # 4. Offline mode (when none configured)
    with patch.object(settings, "GEMINI_API_KEY", None), \
         patch.object(settings, "GROQ_API_KEY", None), \
         patch.object(settings, "OPENAI_API_KEY", None):
        provider = get_llm_provider()
        assert isinstance(provider, FallbackAcademicProvider)


@pytest.mark.asyncio
async def test_groq_provider_chat_mock():
    """Test GroqProvider formatting and chat call"""
    provider = GroqProvider(api_key="gsk-mock-key", model_name="llama-3.3-70b-versatile")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Brachial plexus originates from C5-T1."}}]
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        reply = await provider.generate_response("You are a medical assistant", "Explain brachial plexus")
        assert "Brachial plexus originates" in reply


@pytest.mark.asyncio
async def test_tavily_and_youtube_search_dispatch():
    """Test Tavily and YouTube integration in execute_web_search"""
    # 1. Unconfigured -> returns curated verified links
    with patch.object(settings, "TAVILY_API_KEY", None), \
         patch.object(settings, "YOUTUBE_API_KEY", None):
        res = await AgentToolsRegistry.execute_web_search("upper limb")
        assert len(res["web_sources"]) > 0
        assert any(s["source_type"] == "youtube" for s in res["web_sources"])
        assert any("youtube.com" in s["url"] for s in res["web_sources"])

    # 2. Configured Tavily -> calls Tavily API
    mock_tavily_resp = MagicMock()
    mock_tavily_resp.status_code = 200
    mock_tavily_resp.json.return_value = {
        "results": [
            {"title": "PubMed - Glycolysis Regulation", "url": "https://pubmed.ncbi.nlm.nih.gov/12345/", "content": "Detailed enzymatic steps."}
        ]
    }

    with patch.object(settings, "TAVILY_API_KEY", "tvly-test-key"), \
         patch.object(settings, "YOUTUBE_API_KEY", None), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_tavily_resp)):
        res = await AgentToolsRegistry.execute_web_search("glycolysis")
        assert any("pubmed.ncbi.nlm.nih.gov/12345" in s["url"] for s in res["web_sources"])

    # 3. Configured YouTube Data API -> calls YouTube API
    mock_yt_resp = MagicMock()
    mock_yt_resp.status_code = 200
    mock_yt_resp.json.return_value = {
        "items": [
            {
                "id": {"videoId": "realVideo123"},
                "snippet": {
                    "title": "Nephron Physiology in Depth",
                    "channelTitle": "Ninja Nerd",
                    "description": "Countercurrent multiplier breakdown."
                }
            }
        ]
    }

    with patch.object(settings, "TAVILY_API_KEY", None), \
         patch.object(settings, "YOUTUBE_API_KEY", "AIzaSyTestKey"), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_yt_resp)):
        res = await AgentToolsRegistry.execute_web_search("nephron physiology")
        assert any(s["url"] == "https://www.youtube.com/watch?v=realVideo123" for s in res["web_sources"])
