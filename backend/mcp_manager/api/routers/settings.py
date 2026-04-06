"""Settings API — edit LLM providers config (admin only)."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from mcp_manager.api.routers.auth import require_admin
from mcp_manager.llm.config import load_config, save_config

router = APIRouter(tags=["settings"])


@router.get("/settings/llm")
async def get_llm_config(request: Request, admin: dict = Depends(require_admin)):
    return load_config()


class LLMConfigUpdate(BaseModel):
    config: dict


@router.put("/settings/llm")
async def update_llm_config(
    body: LLMConfigUpdate,
    request: Request,
    admin: dict = Depends(require_admin),
):
    save_config(body.config)
    # Reload the global LLM manager
    from mcp_manager.summarizer.ollama_client import get_llm_manager
    manager = get_llm_manager()
    manager.load()
    return {"status": "saved"}
