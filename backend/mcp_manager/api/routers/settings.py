"""Settings API — edit LLM providers config (admin only)."""
import os
import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from mcp_manager.api.routers.auth import require_admin
from mcp_manager.llm.config import load_config, save_config

router = APIRouter(tags=["settings"])

DOCKERS_DIR = os.environ.get("DOCKERS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "dockers"))


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

        # Extract <run type="cmd"> block for the docker run command template
        run_cmd = ""
        cmd_match = re.search(r'<run type="cmd">(.*?)</run>', content, re.DOTALL)
        if cmd_match:
            run_cmd = cmd_match.group(1).strip()

        images.append({
            "name": image_name,
            "default_args": default_args,
            "run_cmd": run_cmd,
        })

    return images


@router.get("/settings/env-keys")
async def get_env_keys(request: Request, admin: dict = Depends(require_admin)):
    """Get environment variable values referenced by providers (${VAR} patterns)."""
    config = load_config()
    keys: dict[str, dict] = {}

    for provider in config.get("llm", []):
        for arg_key, arg_val in provider.get("args", {}).items():
            if isinstance(arg_val, str) and arg_val.startswith("${"):
                inner = arg_val[2:-1]
                default = ""
                if ":-" in inner:
                    var_name, default = inner.split(":-", 1)
                else:
                    var_name = inner
                current = os.environ.get(var_name, default)
                keys[var_name] = {
                    "name": var_name,
                    "default": default,
                    "current": current,
                    "pattern": arg_val,
                }

    return list(keys.values())


class EnvKeyUpdate(BaseModel):
    keys: dict[str, str]  # {VAR_NAME: value}


@router.put("/settings/env-keys")
async def update_env_keys(
    body: EnvKeyUpdate,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Update environment variables in the .env file."""
    env_path = "/root/mcp-manager/.env"
    if not os.path.isfile(env_path):
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")

    # Read existing .env
    lines = []
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.readlines()

    # Update or append keys
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in body.keys:
                new_lines.append(f"{key}={body.keys[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append new keys
    for key, val in body.keys.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Update os.environ for immediate effect
    for key, val in body.keys.items():
        os.environ[key] = val

    return {"status": "saved"}


@router.get("/settings/docker-run-cmd/{image_name}")
async def get_docker_run_cmd(
    image_name: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Generate the docker run command for a provider, with resolved env vars."""
    dockers_path = os.path.abspath(DOCKERS_DIR)
    run_file = os.path.join(dockers_path, f"run.{image_name}.md")

    if not os.path.isfile(run_file):
        return {"cmd": ""}

    with open(run_file, encoding="utf-8") as f:
        content = f.read()

    # Extract <run type="cmd"> block
    cmd_match = re.search(r'<run type="cmd">(.*?)</run>', content, re.DOTALL)
    if not cmd_match:
        return {"cmd": ""}

    cmd = cmd_match.group(1).strip()

    # Resolve {VAR} patterns from defaults + env
    default_match = re.search(r"<default>(.*?)</default>", content, re.DOTALL)
    defaults = {}
    if default_match:
        for line in default_match.group(1).strip().split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                defaults[k.strip()] = v.strip()

    # Resolve defaults then env
    for key, pattern in defaults.items():
        resolved = pattern
        if pattern.startswith("${"):
            inner = pattern[2:-1]
            default = ""
            if ":-" in inner:
                var_name, default = inner.split(":-", 1)
            else:
                var_name = inner
            resolved = os.environ.get(var_name, default)
        cmd = cmd.replace(f"{{{key}}}", resolved)

    return {"cmd": cmd}
