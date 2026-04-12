"""Google OAuth authentication + JWT session."""
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from mcp_manager.config import settings

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 180  # 6 mois


async def _upsert_user(email: str, name: str, picture: str) -> str:
    """Create or update user in DB. Returns user_id as string."""
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import User
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with SessionLocal() as db:
        stmt = pg_insert(User.__table__).values(
            email=email, name=name, picture=picture,
        ).on_conflict_do_update(
            index_elements=["email"],
            set_={"name": name, "picture": picture},
        ).returning(User.__table__.c.id)
        result = await db.execute(stmt)
        user_id = str(result.scalar_one())
        await db.commit()
        return user_id


def _get_callback_url(request: Request) -> str:
    """Build callback URL preserving the original host from the request."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost")
    scheme = request.headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{host}/api/v1/auth/callback"


@router.get("/auth/login")
async def login(request: Request):
    """Redirect to Google OAuth consent screen."""
    callback_url = _get_callback_url(request)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(code: str, request: Request):
    """Handle Google OAuth callback, issue JWT."""
    callback_url = _get_callback_url(request)

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": callback_url,
            "grant_type": "authorization_code",
        })
        if resp.status_code != 200:
            logger.error("Token exchange failed: %s", resp.text)
            raise HTTPException(status_code=400, detail="Token exchange failed")
        tokens = resp.json()

    # Get user info
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        user_info = resp.json()

    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")
    is_admin = email.lower() == settings.admin_email.lower()

    # Persist user in DB
    user_id = await _upsert_user(email, name, picture)

    # Create JWT
    payload = {
        "email": email,
        "name": name,
        "picture": picture,
        "is_admin": is_admin,
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)

    # Redirect to frontend — use the same origin as the request
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:3001")
    scheme = request.headers.get("x-forwarded-proto", "http")
    frontend_url = f"{scheme}://{host}"
    return RedirectResponse(f"{frontend_url}/?token={token}")


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user from JWT in Authorization header."""
    user = _get_user_from_request(request)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "is_admin": user.get("is_admin", False),
        "user_id": user.get("user_id"),
    }


def _get_user_from_request(request: Request) -> dict | None:
    """Extract user from JWT (Authorization: Bearer) or API key (X-API-Key)."""
    # Try JWT first
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and not auth[7:].startswith("mcp_"):
        token = auth[7:]
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    # Try API key (X-API-Key header or Bearer mcp_xxx)
    api_key = request.headers.get("X-API-Key", "")
    if not api_key and auth.startswith("Bearer mcp_"):
        api_key = auth[7:]
    if api_key:
        validated = getattr(request.state, "validated_api_user", None)
        if validated:
            return validated
        request.state.api_key = api_key
        return {"email": "api_key", "is_admin": False, "is_api_key": True, "pending_validation": True}

    return None


def require_authenticated(request: Request) -> dict:
    """Dependency: require any authenticated user."""
    user = _get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> dict:
    """Dependency: require authenticated admin user."""
    user = _get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
