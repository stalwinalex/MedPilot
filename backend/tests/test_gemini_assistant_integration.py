import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.config import settings
from app.agent.llm_provider import (
    resolve_gemini_model_name,
    is_gemini_configured,
    GeminiProvider,
    FallbackAcademicProvider,
    get_llm_provider
)
from app.agent.orchestrator import MedPilotAgentOrchestrator
from app.schemas.schemas import AgentChatResponse


def test_resolve_gemini_model_name():
    """Verify supported model detection and safe fallback for invalid/obsolete models"""
    # 1. Obsolete models resolve safely to modern default (gemini-3.8-flash)
    assert resolve_gemini_model_name("gemini-pro") == "gemini-3.8-flash"
    assert resolve_gemini_model_name("gemini-1.0-pro") == "gemini-3.8-flash"
    assert resolve_gemini_model_name("") == "gemini-3.8-flash"
    assert resolve_gemini_model_name(None) == "gemini-3.8-flash"

    # 2. Known supported models are preserved
    assert resolve_gemini_model_name("gemini-flash-latest") == "gemini-flash-latest"
    assert resolve_gemini_model_name("models/gemini-flash-latest") == "gemini-flash-latest"
    assert resolve_gemini_model_name("gemini-3.6-flash") == "gemini-3.6-flash"
    assert resolve_gemini_model_name("gemini-3.8-flash") == "gemini-3.8-flash"
    assert resolve_gemini_model_name("gemini-2.5-flash") == "gemini-2.5-flash"


def test_is_gemini_configured_logic():
    """Verify is_gemini_configured correctly validates presence of valid non-dummy key"""
    with patch.object(settings, "GEMINI_API_KEY", ""):
        assert is_gemini_configured() is False

    with patch.object(settings, "GEMINI_API_KEY", "your_gemini_api_key_here"):
        assert is_gemini_configured() is False

    with patch.object(settings, "GEMINI_API_KEY", "dummy_key_123"):
        assert is_gemini_configured() is False

    with patch.object(settings, "GEMINI_API_KEY", "AIzaSyRealLookingApiKey123456789"):
        assert is_gemini_configured() is True


@pytest.mark.asyncio
async def test_unconfigured_gemini_returns_friendly_message_no_fake_answers():
    """
    Strict Requirement: If GEMINI_API_KEY is missing, return a friendly configuration message
    instead of a fake answer. No hardcoded medical answers pretending to be an AI.
    """
    provider = FallbackAcademicProvider()
    res_upper_limb = await provider.generate_response(
        system_prompt="sys",
        user_prompt="Explain upper limb anatomy and brachial plexus"
    )
    # Must NOT contain the old hardcoded fake syllabus outline
    assert "### High-Yield Syllabus Guide: Upper Limb Anatomy" not in res_upper_limb
    # Must contain the friendly configuration guide
    assert "Google Gemini AI Assistant Not Configured" in res_upper_limb
    assert "GEMINI_API_KEY" in res_upper_limb

    res_glycolysis = await provider.generate_response(
        system_prompt="sys",
        user_prompt="Explain glycolysis and rate limiting enzymes"
    )
    assert "### High-Yield Syllabus Guide: Glycolysis" not in res_glycolysis
    assert "Google Gemini AI Assistant Not Configured" in res_glycolysis


@pytest.mark.asyncio
async def test_gemini_multi_turn_history_preservation():
    """Verify GeminiProvider formats history into Content turns using google-genai"""
    provider = GeminiProvider(api_key="AIzaSyTestKey123456789", model_name="gemini-3.8-flash")
    mock_resp = MagicMock()
    mock_resp.text = "Here is the simplified explanation of the brachial plexus."
    provider.client.models.generate_content = MagicMock(return_value=mock_resp)

    history = [
        {"role": "user", "content": "Explain upper limb briefly."},
        {"role": "assistant", "content": "The upper limb consists of the arm and brachial plexus."}
    ]

    reply = await provider.generate_response(
        system_prompt="You are a medical assistant",
        user_prompt="Explain the second point more simply.",
        history=history
    )

    assert reply == "Here is the simplified explanation of the brachial plexus."
    assert provider.client.models.generate_content.call_count == 1
    call_args = provider.client.models.generate_content.call_args[1]
    contents = call_args["contents"]
    # User turn, assistant/model turn, and new user prompt
    assert len(contents) == 3
    assert contents[0].role == "user"
    assert contents[1].role == "model"
    assert contents[2].role == "user"


@pytest.mark.asyncio
async def test_gemini_error_handling_sanitizes_stack_traces_and_keys():
    """
    Strict Requirement: Do not expose environment variables, API keys, stack traces, or provider secrets.
    """
    with patch.object(settings, "GEMINI_API_KEY", "AIzaSyTestKey_Secret123"), \
         patch.object(settings, "GROQ_API_KEY", ""):
        
        # Simulate an exception in Gemini API call
        with patch("app.agent.llm_provider.GeminiProvider.generate_response", side_effect=RuntimeError("secret_key_internal: error 503")):
            mock_db = AsyncMock()
            response: AgentChatResponse = await MedPilotAgentOrchestrator.handle_learning_assistant(
                db=mock_db,
                user_id="test_user_id",
                message="Explain cardiac cycle"
            )
            
            # Must NOT expose raw secret key or stack trace
            assert "AIzaSyTestKey_Secret123" not in response.reply
            assert "Traceback" not in response.reply
