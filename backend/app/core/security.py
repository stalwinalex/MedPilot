from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    # Try encode with SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    # Try decoding with Supabase JWT secret first, then fall back to app secret key
    for secret in [settings.SUPABASE_JWT_SECRET, settings.SECRET_KEY]:
        if not secret:
            continue
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            return payload
        except jwt.PyJWTError:
            continue
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Profile

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Supabase uses 'sub' as user UUID; custom tokens might use 'user_id' or 'sub'
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user profile from DB
    result = await db.execute(select(Profile).filter(Profile.id == str(user_id)))
    profile = result.scalars().first()

    if not profile:
        # Auto-provision profile only for valid Supabase user if first time logging in
        email = payload.get("email")
        is_supabase = (payload.get("aud") == "authenticated" or "supabase" in str(payload.get("iss", ""))) and bool(email)
        if is_supabase:
            profile = Profile(
                id=str(user_id),
                email=email,
                full_name=payload.get("user_metadata", {}).get("full_name", email.split("@")[0] if email else "Medical Student"),
                college="Medical College",
                year_of_study="MBBS 1st Year",
                target_attendance_percentage=75.0,
                daily_study_target_minutes=180
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or has been deleted",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return profile
