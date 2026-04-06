"""API key management — admin only."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import ApiKey

router = APIRouter(tags=["api_keys"])

KEY_PREFIX = "mcp_"


def _generate_key() -> tuple[str, str, str]:
    """Generate API key. Returns (raw_key, key_hash, key_prefix)."""
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:12] + "..."
    return raw, key_hash, prefix


class KeyCreate(BaseModel):
    name: str


@router.get("/api-keys")
async def list_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    keys = result.scalars().all()
    return [_serialize(k) for k in keys]


@router.post("/api-keys")
async def create_key(
    body: KeyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    raw_key, key_hash, prefix = _generate_key()

    key = ApiKey(
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
        owner_email=admin.get("email", ""),
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)

    # Return the raw key only once
    return {
        **_serialize(key),
        "raw_key": raw_key,
    }


@router.delete("/api-keys/{key_id}")
async def revoke_key(
    key_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await db.commit()
    return {"status": "revoked"}


def _serialize(k: ApiKey) -> dict:
    return {
        "id": str(k.id),
        "name": k.name,
        "key_prefix": k.key_prefix,
        "owner_email": k.owner_email,
        "is_active": k.is_active,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


async def validate_api_key(key: str, db: AsyncSession) -> dict | None:
    """Validate an API key, return key info or None."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None
    return {
        "email": api_key.owner_email,
        "name": api_key.name,
        "is_admin": False,
        "is_api_key": True,
    }
