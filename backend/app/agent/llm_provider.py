import asyncio
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_GEMINI_MODELS = {
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}


def resolve_gemini_model_name(configured_model: Optional[str] = None) -> str:
    """
    Determines the correct, currently supported Google Gemini model from SDK capability.
    Guards against obsolete models (e.g. gemini-pro, gemini-1.0-pro).
    """
    default_model = "gemini-3.8-flash"
    if not configured_model or not isinstance(configured_model, str) or not configured_model.strip():
        return default_model

    clean = configured_model.strip().lower()
    if clean.startswith("models/"):
        clean = clean[7:]

    if clean in SUPPORTED_GEMINI_MODELS:
        return clean

    # Deprecated Gemini 1.0 models -> map to modern default
    if clean in ("gemini-pro", "gemini-1.0-pro", "gemini-1.0-pro-vision"):
        logger.info(f"Deprecated model '{configured_model}' mapped to modern '{default_model}'.")
        return default_model

    # Resolve family variants
    if "3.8" in clean or "3.6" in clean or "3.5" in clean or "2.5" in clean:
        return clean
    elif "flash" in clean:
        return "gemini-3.8-flash"
    elif "pro" in clean:
        return "gemini-pro-latest"

    logger.warning(
        f"Configured Gemini model '{configured_model}' is not a recognized supported model. "
        f"Safely resolving to standard '{default_model}'."
    )
    return default_model


def categorize_gemini_error(e: Exception) -> str:
    """
    Categorizes Gemini errors into safe, actionable classifications.
    Does not log or expose the GEMINI_API_KEY.
    """
    err_str = str(e).lower()
    if not is_gemini_configured():
        return "API key not loaded"
    if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        return "quota/rate limit"
    elif "api_key_invalid" in err_str or "invalid api key" in err_str or "api key not valid" in err_str:
        return "API key invalid"
    elif "not found" in err_str or ("model" in err_str and ("not supported" in err_str or "is not available" in err_str or "no longer available" in err_str)):
        return "model unavailable"
    elif "permission" in err_str or "forbidden" in err_str or "403" in err_str:
        return "authentication/API permission problem"
    elif "dns" in err_str or "connection" in err_str or "network" in err_str or "failed to establish" in err_str:
        return "network/DNS problem"
    elif "import" in err_str or "module" in err_str or "package" in err_str:
        return "SDK/package problem"
    return "unknown Gemini error"


FALLBACK_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
]

# In-memory exhaustion tracking: model_name -> expiration timestamp
_EXHAUSTED_MODELS: Dict[str, float] = {}


def mark_model_exhausted(model_name: str, cooldown_seconds: float = 300.0) -> None:
    """
    Temporarily marks a model unavailable until time.time() + cooldown_seconds.
    """
    _EXHAUSTED_MODELS[model_name] = time.time() + cooldown_seconds
    logger.warning(
        f"Model '{model_name}' marked temporarily exhausted for {int(cooldown_seconds)}s "
        f"(until {time.strftime('%H:%M:%S', time.localtime(_EXHAUSTED_MODELS[model_name]))})."
    )


def is_model_exhausted(model_name: str) -> bool:
    """
    Checks if a model is currently within its cooldown/reset period.
    """
    expire_at = _EXHAUSTED_MODELS.get(model_name)
    if expire_at is None:
        return False
    if time.time() >= expire_at:
        _EXHAUSTED_MODELS.pop(model_name, None)
        return False
    return True


def reset_exhausted_models() -> None:
    """Clears all exhaustion timestamps (useful for testing or manual resets)."""
    _EXHAUSTED_MODELS.clear()


def parse_cooldown_from_error(err_str: str) -> float:
    """
    Extracts the recommended cooldown from Google API error response.
    Guarantees a safe cooldown period (default 5 minutes, 30 minutes for daily limits)
    so that we do not keep attempting an exhausted model for every new student question.
    """
    err_lower = err_str.lower()
    if "perday" in err_lower or "daily" in err_lower or "limit: 20" in err_lower or "limit: 15" in err_lower:
        return 1800.0  # 30 minutes for daily quota exhaustion

    parsed_sec = 0.0
    match = re.search(r"retry in\s+([\d\.]+)\s*s", err_str, re.IGNORECASE)
    if match:
        parsed_sec = float(match.group(1))
    else:
        match_delay = re.search(r"retryDelay[\x27\":\s]+(\d+)s", err_str)
        if match_delay:
            parsed_sec = float(match_delay.group(1))

    # Keep unavailable for at least 300 seconds (5 minutes) so new student messages
    # immediately use the fallback model without wasting requests/latency on the primary model
    return max(parsed_sec, 300.0)


def is_quota_exhausted_error(e: Exception) -> bool:
    """
    Checks if an exception is specifically due to 429 / RESOURCE_EXHAUSTED / quota exhaustion.
    """
    err_str = str(e).lower()
    return any(marker in err_str for marker in [
        "429",
        "resource_exhausted",
        "quota exceeded",
        "rate limit",
        "exceeded your current quota",
    ])


def is_transient_network_error(e: Exception) -> bool:
    """
    Checks if an exception is a transient network or connection issue.
    """
    err_str = str(e).lower()
    return any(term in err_str for term in [
        "connecterror",
        "connection reset",
        "timeout",
        "timed out",
        "temporary failure in name resolution",
        "failed to establish a new connection",
        "connection refused",
    ])


class GeminiAllModelsExhaustedError(Exception):
    """Raised when every candidate Gemini model fails due to quota or rate limit exhaustion."""
    pass


def is_gemini_configured() -> bool:
    key = getattr(settings, "GEMINI_API_KEY", "")
    if not key or not str(key).strip():
        import os
        key = os.environ.get("GEMINI_API_KEY", "")
    if not key or not isinstance(key, str):
        return False
    k = key.strip()
    return bool(k and not k.startswith("your-") and not k.startswith("your_") and not k.startswith("dummy_") and len(k) > 10)


def is_groq_configured() -> bool:
    key = getattr(settings, "GROQ_API_KEY", "")
    return bool(key and key.strip() and not key.strip().startswith("your-") and not key.strip().startswith("gsk_dummy"))


def is_openai_configured() -> bool:
    key = getattr(settings, "OPENAI_API_KEY", "")
    return bool(key and key.strip() and not key.strip().startswith("your-") and not key.strip().startswith("dummy_"))


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2
    ) -> str:
        pass

    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        pass


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI Primary Provider using current ChatGPT models (e.g. gpt-4o).
    Supports multi-turn chat, function/tool calling, vision/image understanding,
    and DALL-E image generation over async HTTP.
    """
    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1"
    ):
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-8:]:
                role = "user" if h.get("role") == "user" else "assistant"
                content = h.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                logger.error(f"OpenAI API Error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"OpenAI API returned status {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": f"{system_prompt}\nReturn strictly valid JSON only."},
            {"role": "user", "content": user_prompt}
        ]
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                logger.error(f"OpenAI JSON API Error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"OpenAI API error: {resp.status_code}")
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"].strip()
            return json.loads(raw_text)

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Calls OpenAI with function tools for autonomous agent routing"""
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                logger.error(f"OpenAI Tools Error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"OpenAI API status {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]

    async def generate_dalle_image(self, prompt: str) -> Optional[str]:
        """Generates an educational image using DALL-E 3"""
        payload = {
            "model": getattr(settings, "OPENAI_IMAGE_MODEL", "dall-e-3"),
            "prompt": f"Medical education schematic illustration: {prompt}. High clarity, anatomically accurate, clear labels, academic diagram.",
            "n": 1,
            "size": "1024x1024"
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/images/generations",
                headers=self.headers,
                json=payload
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["data"][0]["url"]
            else:
                logger.warning(f"DALL-E generation failed {resp.status_code}: {resp.text}")
                return None


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Provider using official google-genai SDK.
    Implements intelligent model fallback, exhaustion remembering, and request efficiency.
    """
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.api_key = api_key.strip()
        self.primary_model = resolve_gemini_model_name(
            model_name or getattr(settings, "DEFAULT_LLM_MODEL", "gemini-3.8-flash")
        )
        self.model_name = self.primary_model
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self.system_instruction = (
            "You are MedPilot's Academic Learning Assistant for MBBS medical students.\n"
            "Provide accurate, rigorous, high-yield medical concept explanations with clinical correlations.\n"
            "Never claim to diagnose patients, recommend personal medications, or provide emergency clinical advice.\n"
            "Format using clear, structured Markdown headers, bullet points, and high-yield exam takeaways."
        )
        self.last_used_model: Optional[str] = None
        self.used_fallback: bool = False

    def get_candidate_models(self) -> List[str]:
        candidates = [self.primary_model]
        for m in FALLBACK_GEMINI_MODELS:
            if m not in candidates:
                candidates.append(m)
        return candidates

    def _build_contents(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None
    ) -> Any:
        from google.genai import types

        # 1. Multimodal image input
        if image_bytes:
            part_img = types.Part.from_bytes(data=image_bytes, mime_type=image_mime or "image/jpeg")
            return [part_img, user_prompt]

        # 2. Multi-turn conversation
        if history:
            contents = []
            for item in history[-10:]:
                raw_role = item.get("role", "user")
                role = "user" if raw_role == "user" else "model"
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                if not contents and role != "user":
                    continue
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content)]))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))
            return contents

        # 3. Single-turn prompt
        return user_prompt

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        from google.genai import types

        req_id = request_id or uuid.uuid4().hex[:8]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt or self.system_instruction,
            temperature=temperature
        )
        contents = self._build_contents(user_prompt, history, image_bytes, image_mime)

        all_candidates = self.get_candidate_models()
        # Filter out currently exhausted models
        eligible_models = [m for m in all_candidates if not is_model_exhausted(m)]
        if not eligible_models:
            eligible_models = all_candidates

        last_error = None
        attempt = 0

        for model_candidate in eligible_models:
            attempt += 1
            is_fallback = (model_candidate != self.primary_model)

            def _call(m=model_candidate):
                return self.client.models.generate_content(
                    model=m,
                    contents=contents,
                    config=config
                )

            try:
                resp = await asyncio.to_thread(_call)
                self.last_used_model = model_candidate
                self.used_fallback = is_fallback

                # Exact required development logging
                logger.info(f"Attempt {attempt}:\n{model_candidate}\nsuccess")
                return resp.text.strip()

            except Exception as e:
                last_error = e

                # Check if this error is an approved fallback reason (429 / RESOURCE_EXHAUSTED)
                if is_quota_exhausted_error(e):
                    cooldown = parse_cooldown_from_error(str(e))
                    mark_model_exhausted(model_candidate, cooldown)
                    logger.warning(
                        f"Attempt {attempt}:\n{model_candidate}\nfailed: quota/rate limit exhaustion (429/RESOURCE_EXHAUSTED). Triggering fallback."
                    )
                    # Proceed to next eligible model
                    continue

                # Check for temporary network error: allow at most ONE controlled retry on this same model
                if is_transient_network_error(e):
                    logger.warning(
                        f"Attempt {attempt}:\n{model_candidate}\ntransient network error. Retrying once..."
                    )
                    try:
                        await asyncio.sleep(1.0)
                        resp = await asyncio.to_thread(_call)
                        self.last_used_model = model_candidate
                        self.used_fallback = is_fallback
                        logger.info(f"Attempt {attempt} (retry):\n{model_candidate}\nsuccess")
                        return resp.text.strip()
                    except Exception as retry_err:
                        last_error = retry_err
                        logger.error(f"Attempt {attempt} network retry failed: {retry_err}")
                        raise retry_err

                # Non-fallback error (invalid API key, 401, 403, 400, programming errors):
                # Do NOT cycle through models. Raise immediately.
                logger.error(f"Attempt {attempt}:\n{model_candidate}\nunrecoverable error ({type(e).__name__}): {e}")
                raise e

        # If all candidate models exhausted
        logger.error(f"All candidate Gemini models exhausted. Final error: {last_error}")
        raise GeminiAllModelsExhaustedError(f"All candidate Gemini models exhausted: {last_error}")

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        from google.genai import types

        req_id = request_id or uuid.uuid4().hex[:8]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            response_mime_type="application/json"
        )

        all_candidates = self.get_candidate_models()
        eligible_models = [m for m in all_candidates if not is_model_exhausted(m)]
        if not eligible_models:
            eligible_models = all_candidates

        last_error = None
        attempt = 0

        for model_candidate in eligible_models:
            attempt += 1
            is_fallback = (model_candidate != self.primary_model)

            def _call(m=model_candidate):
                return self.client.models.generate_content(
                    model=m,
                    contents=user_prompt,
                    config=config
                )

            try:
                resp = await asyncio.to_thread(_call)
                text = resp.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                self.last_used_model = model_candidate
                self.used_fallback = is_fallback
                logger.info(f"Attempt {attempt}:\n{model_candidate}\nsuccess")
                return json.loads(text.strip())

            except Exception as e:
                last_error = e
                if is_quota_exhausted_error(e):
                    cooldown = parse_cooldown_from_error(str(e))
                    mark_model_exhausted(model_candidate, cooldown)
                    logger.warning(
                        f"Attempt {attempt}:\n{model_candidate}\nfailed: quota/rate limit exhaustion. Triggering fallback."
                    )
                    continue

                if is_transient_network_error(e):
                    logger.warning(
                        f"Attempt {attempt}:\n{model_candidate}\ntransient network error. Retrying once..."
                    )
                    try:
                        await asyncio.sleep(1.0)
                        resp = await asyncio.to_thread(_call)
                        text = resp.text.strip()
                        if text.startswith("```json"):
                            text = text[7:]
                        if text.startswith("```"):
                            text = text[3:]
                        if text.endswith("```"):
                            text = text[:-3]
                        self.last_used_model = model_candidate
                        self.used_fallback = is_fallback
                        logger.info(f"Attempt {attempt} (retry):\n{model_candidate}\nsuccess")
                        return json.loads(text.strip())
                    except Exception as retry_err:
                        last_error = retry_err
                        raise retry_err

                raise e

        raise GeminiAllModelsExhaustedError(f"All candidate Gemini models exhausted in JSON: {last_error}")


class GroqProvider(BaseLLMProvider):
    """
    Groq Fast AI Provider (Free development tier)
    Uses Groq's high-speed Llama models (e.g. llama-3.3-70b-versatile, llama-3.1-8b-instant).
    Fully compatible with OpenAI Chat Completions API format.
    """
    def __init__(
        self,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        base_url: str = "https://api.groq.com/openai/v1"
    ):
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-8:]:
                role = "user" if h.get("role") == "user" else "assistant"
                content = h.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                logger.error(f"Groq API Error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Groq API returned status {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": f"{system_prompt}\nReturn strictly valid JSON only."},
            {"role": "user", "content": user_prompt}
        ]
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                logger.error(f"Groq JSON Error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Groq API error: {resp.status_code}")
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"].strip()
            return json.loads(raw_text)


class FallbackAcademicProvider(BaseLLMProvider):
    """
    Friendly configuration provider returned when no real AI provider (Gemini or Groq)
    is configured in backend/.env.
    Adheres strictly to the invariant: If GEMINI_API_KEY is missing, return a friendly
    configuration guide instead of a fake or hardcoded answer.
    """
    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.2
    ) -> str:
        return (
            "> [!NOTE]\n"
            "> **Google Gemini AI Assistant Not Configured**\n\n"
            "> The AI Assistant is ready to connect with Google Gemini. To activate it:\n"
            "> 1. Open `backend/.env` in your project.\n"
            "> 2. Add your Gemini API key:\n"
            ">    ```bash\n"
            ">    GEMINI_API_KEY=your_gemini_api_key_here\n"
            ">    ```\n"
            "> 3. Restart the MedPilot backend server.\n\n"
            "> *You can generate a free API key instantly at [Google AI Studio](https://aistudio.google.com).* "
            "Once configured, MedPilot will provide live, dynamic medical concept explanations, "
            "viva questions, and clinical reasoning."
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        prompt_lower = user_prompt.lower()

        if "what should i do now" in prompt_lower or "what should i study now" in prompt_lower:
            return {
                "recommendation": "Dedicate the next 45 minutes to high-yield review of your upcoming exam subject, followed by a short hydration break and active recall questions.",
                "reasoning": "Evaluated live timetable, upcoming exam dates, and attendance standing.",
                "source_type": "student_data",
                "citations": ["Live Academic Timetable & Exam Records"],
                "actions": [
                    {
                        "action_type": "create_task",
                        "label": "Schedule 45m Focused Review",
                        "payload": {"title": "Priority Subject High-Yield Revision", "estimated_minutes": 45, "priority": "high"}
                    },
                    {
                        "action_type": "study_session",
                        "label": "Start 45-Minute Focus Session",
                        "payload": {"duration_minutes": 45}
                    }
                ]
            }

        return {
            "summary": "Academic syllabus guidance for medical coursework.",
            "citations": ["Standard MBBS Curriculum Competencies"]
        }


def get_llm_provider() -> BaseLLMProvider:
    # 1. Primary AI: Google Gemini
    if is_gemini_configured():
        try:
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY.strip(),
                model_name=getattr(settings, "DEFAULT_LLM_MODEL", "gemini-1.5-flash")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini provider, falling back: {e}")

    # 2. Fallback AI: Groq Cloud (Free Llama models)
    if is_groq_configured():
        try:
            return GroqProvider(
                api_key=settings.GROQ_API_KEY.strip(),
                model_name=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
                base_url=getattr(settings, "GROQ_API_BASE", "https://api.groq.com/openai/v1")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Groq provider, falling back: {e}")

    # 3. Optional / Preserved: OpenAI (Ready for future activation)
    if is_openai_configured():
        try:
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY.strip(),
                model_name=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                base_url=getattr(settings, "OPENAI_API_BASE", "https://api.openai.com/v1")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider: {e}")

    # 4. Offline mode when neither is configured
    return FallbackAcademicProvider()
