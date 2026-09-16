import pytest
from unittest.mock import MagicMock, patch
from google.genai.errors import ClientError

from app.agent.llm_provider import (
    GeminiProvider,
    FALLBACK_GEMINI_MODELS,
    mark_model_exhausted,
    is_model_exhausted,
    reset_exhausted_models,
    is_quota_exhausted_error,
    is_transient_network_error,
    categorize_gemini_error
)


@pytest.fixture(autouse=True)
def clean_exhaustion_state():
    reset_exhausted_models()
    yield
    reset_exhausted_models()


@pytest.mark.asyncio
async def test_a_primary_model_succeeds_exactly_one_request():
    """
    Requirement A: Primary model succeeds -> exactly ONE Gemini request.
    """
    provider = GeminiProvider(api_key="AIzaSyTestKey_12345", model_name="gemini-3.8-flash")
    mock_resp = MagicMock()
    mock_resp.text = "Normal response from primary 3.8."
    provider.client.models.generate_content = MagicMock(return_value=mock_resp)

    res = await provider.generate_response(
        system_prompt="System",
        user_prompt="Explain cardiac cycle"
    )

    assert res == "Normal response from primary 3.8."
    assert provider.client.models.generate_content.call_count == 1
    assert provider.client.models.generate_content.call_args[1]["model"] == "gemini-3.8-flash"
    assert provider.last_used_model == "gemini-3.8-flash"
    assert provider.used_fallback is False


@pytest.mark.asyncio
async def test_b_and_c_simulated_primary_429_triggers_fallback_and_stops():
    """
    Requirement B & C:
    Simulated primary 429 -> exactly one primary attempt + one fallback attempt.
    Fallback succeeds -> no additional models called.
    """
    provider = GeminiProvider(api_key="AIzaSyTestKey_12345", model_name="gemini-3.8-flash")
    
    mock_fallback_resp = MagicMock()
    mock_fallback_resp.text = "Response from fallback 3.6."

    def side_effect(*args, **kwargs):
        model = kwargs.get("model")
        if model == "gemini-3.8-flash":
            # Simulate Google 429 RESOURCE_EXHAUSTED
            raise ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED: quota exceeded, retry in 30s"}}, None)
        elif model == "gemini-3.6-flash":
            return mock_fallback_resp
        raise RuntimeError("Unexpected model called")

    provider.client.models.generate_content = MagicMock(side_effect=side_effect)

    res = await provider.generate_response(
        system_prompt="System",
        user_prompt="Explain cardiac cycle"
    )

    assert res == "Response from fallback 3.6."
    # Exactly 2 calls: primary 3.8 -> fallback 3.6 (no 3rd model called)
    assert provider.client.models.generate_content.call_count == 2
    calls = provider.client.models.generate_content.call_args_list
    assert calls[0][1]["model"] == "gemini-3.8-flash"
    assert calls[1][1]["model"] == "gemini-3.6-flash"
    assert provider.last_used_model == "gemini-3.6-flash"
    assert provider.used_fallback is True


@pytest.mark.asyncio
async def test_d_primary_known_exhausted_uses_fallback_without_wasting_request():
    """
    Requirement D: Primary already known to be exhausted -> use fallback without
    wasting another request on primary.
    """
    provider = GeminiProvider(api_key="AIzaSyTestKey_12345", model_name="gemini-3.8-flash")
    
    # Mark primary model exhausted
    mark_model_exhausted("gemini-3.8-flash", cooldown_seconds=300.0)
    assert is_model_exhausted("gemini-3.8-flash") is True

    mock_resp = MagicMock()
    mock_resp.text = "Direct fallback response."
    provider.client.models.generate_content = MagicMock(return_value=mock_resp)

    res = await provider.generate_response(
        system_prompt="System",
        user_prompt="Explain nephron physiology"
    )

    assert res == "Direct fallback response."
    # Exactly 1 request made, directly to gemini-3.6-flash!
    assert provider.client.models.generate_content.call_count == 1
    assert provider.client.models.generate_content.call_args[1]["model"] == "gemini-3.6-flash"
    assert provider.last_used_model == "gemini-3.6-flash"
    assert provider.used_fallback is True


@pytest.mark.asyncio
async def test_e_invalid_api_key_does_not_cycle_through_models():
    """
    Requirement E: Invalid API key -> do not cycle through every model.
    """
    provider = GeminiProvider(api_key="AIzaSyTestKey_12345", model_name="gemini-3.8-flash")
    
    # Simulate 401 Unauthorized / Invalid API Key
    provider.client.models.generate_content = MagicMock(
        side_effect=ClientError(401, {"error": {"code": 401, "message": "API_KEY_INVALID"}}, None)
    )

    with pytest.raises(ClientError) as exc_info:
        await provider.generate_response(
            system_prompt="System",
            user_prompt="Explain cardiac cycle"
        )

    # Exactly 1 call was made; did NOT try 3.6 or 2.5!
    assert provider.client.models.generate_content.call_count == 1
    assert "API_KEY_INVALID" in str(exc_info.value)


def test_f_error_categorization_and_transient_network_check():
    """
    Requirement F: Check categorization accuracy for non-429 errors.
    """
    auth_err = Exception("401 Client Error: API_KEY_INVALID")
    assert categorize_gemini_error(auth_err) == "API key invalid"
    assert is_quota_exhausted_error(auth_err) is False

    quota_err = Exception("429 RESOURCE_EXHAUSTED quota exceeded")
    assert categorize_gemini_error(quota_err) == "quota/rate limit"
    assert is_quota_exhausted_error(quota_err) is True

    net_err = Exception("ConnectError: Failed to establish a new connection")
    assert is_transient_network_error(net_err) is True
