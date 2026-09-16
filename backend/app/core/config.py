import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILES = [
    ".env",
    "backend/.env",
    os.path.join(_BASE_DIR, ".env"),
    os.path.join(os.path.dirname(_BASE_DIR), ".env")
]


class Settings(BaseSettings):
    PROJECT_NAME: str = "MedPilot"
    TAGLINE: str = "Your AI Academic Companion"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = True
    
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, set)):
            return list(v)
        return ["*"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./medpilot.db"

    # Supabase Configuration
    SUPABASE_URL: str = "http://127.0.0.1:54321"
    SUPABASE_ANON_KEY: str = "dummy_anon_key"
    SUPABASE_SERVICE_KEY: str = "dummy_service_key"
    SUPABASE_JWT_SECRET: str = "medpilot-academic-companion-jwt-secret-key"
    STORAGE_BUCKET: str = "medpilot-resources"

    # AI Configuration (Free Development Stack: Gemini Primary, Groq Fallback, OpenAI Preserved)
    GEMINI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini-1.5-flash"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"

    # Search & Media APIs (Free Tier)
    TAVILY_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""

    # OpenAI (Preserved for optional/future use)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"

    # Security
    SECRET_KEY: str = "medpilot-academic-companion-secret-key-32-chars-min"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
