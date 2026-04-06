"""Settings API — edit LLM providers config (admin only)."""
import os
import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from mcp_manager.api.routers.auth import require_admin
from mcp_manager.llm.config import load_config, save_config

router = APIRouter(tags=["settings"])

DOCKERS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "dockers")


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
    from mcp_manager.summarizer.ollama_client import get_llm_manager
    manager = get_llm_manager()
    manager.load()
    return {"status": "saved"}


@router.get("/settings/docker-images")
async def list_docker_images(request: Request, admin: dict = Depends(require_admin)):
    """List available Docker images from dockers/Dockerfile.* and their default args from run.*.md."""
    dockers_path = os.path.abspath(DOCKERS_DIR)
    images = []

    if not os.path.isdir(dockers_path):
        return images

    for filename in os.listdir(dockers_path):
        if not filename.startswith("Dockerfile."):
            continue
        image_name = filename.replace("Dockerfile.", "")

        # Read default args from run.{image}.md
        default_args = {}
        run_file = os.path.join(dockers_path, f"run.{image_name}.md")
        if os.path.isfile(run_file):
            with open(run_file, encoding="utf-8") as f:
                content = f.read()
            # Extract <default> block
            match = re.search(r"<default>(.*?)</default>", content, re.DOTALL)
            if match:
                for line in match.group(1).strip().split("\n"):
                    line = line.strip()
                    if "=" in line:
                        key, val = line.split("=", 1)
                        default_args[key.strip()] = val.strip()

        images.append({
            "name": image_name,
            "default_args": default_args,
        })

    return images
