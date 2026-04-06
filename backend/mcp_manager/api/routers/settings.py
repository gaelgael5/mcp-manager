"""Settings API — edit LLM providers config (admin only)."""
import hashlib
import os
import re
import subprocess

from fastapi import APIRouter, BackgroundTasks, Depends, Request
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


def _extract_env_vars_from_pattern(pattern: str) -> tuple[str, str] | None:
    """Extract VAR_NAME and default from ${VAR} or ${VAR:-default} patterns."""
    if not isinstance(pattern, str):
        return None
    for match in re.finditer(r"\$\{([^}]+)\}", pattern):
        inner = match.group(1)
        if ":-" in inner:
            var_name, default = inner.split(":-", 1)
            return var_name, default
        return inner, ""
    return None


@router.get("/settings/env-keys")
async def get_env_keys(request: Request, admin: dict = Depends(require_admin)):
    """Get all environment variables referenced by providers and docker run files."""
    keys: dict[str, dict] = {}

    # Scan provider args
    config = load_config()
    for provider in config.get("llm", []):
        for arg_val in provider.get("args", {}).values():
            parsed = _extract_env_vars_from_pattern(str(arg_val))
            if parsed:
                var_name, default = parsed
                keys[var_name] = {
                    "name": var_name,
                    "default": default,
                    "current": os.environ.get(var_name, default),
                    "pattern": str(arg_val),
                }

    # Scan <default> blocks in run.*.md files
    dockers_path = os.path.abspath(DOCKERS_DIR)
    if os.path.isdir(dockers_path):
        for filename in os.listdir(dockers_path):
            if not filename.startswith("run.") or not filename.endswith(".md"):
                continue
            with open(os.path.join(dockers_path, filename), encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"<default>(.*?)</default>", content, re.DOTALL)
            if match:
                for line in match.group(1).strip().split("\n"):
                    line = line.strip()
                    if "=" in line:
                        _, val = line.split("=", 1)
                        parsed = _extract_env_vars_from_pattern(val.strip())
                        if parsed:
                            var_name, default = parsed
                            if var_name not in keys:
                                keys[var_name] = {
                                    "name": var_name,
                                    "default": default,
                                    "current": os.environ.get(var_name, default),
                                    "pattern": val.strip(),
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
    provider_id: int = 0,
    request: Request = None,
    admin: dict = Depends(require_admin),
):
    """Generate the docker run command for a provider.

    Step 1: Replace {KEY} (no $) with the value from <default> block (which may be ${VAR})
    Step 2: Replace {workflow_id} with provider_id, {phase} with 'worker'
    Step 3: Keep ${VAR} patterns as-is — they're resolved at runtime
    """
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

    # Parse <default> block: KEY = ${VAR} or ${VAR:-default}
    default_match = re.search(r"<default>(.*?)</default>", content, re.DOTALL)
    defaults = {}
    if default_match:
        for line in default_match.group(1).strip().split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                defaults[k.strip()] = v.strip()

    # Step 1: Replace {KEY} patterns (not ${KEY}) with default values
    # This turns {API_KEY} into ${ANTHROPIC_API_KEY}
    for key, val in defaults.items():
        cmd = cmd.replace(f"{{{key}}}", val)

    # Step 2: Replace special patterns
    cmd = cmd.replace("{workflow_id}", str(provider_id))
    cmd = cmd.replace("{phase}", "worker")

    return {"cmd": cmd}


@router.post("/settings/llm-test")
async def test_llm_providers(
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Test each configured LLM provider with a simple prompt."""
    from mcp_manager.summarizer.ollama_client import get_llm_manager
    import time

    manager = get_llm_manager()
    manager.load()

    results = []
    config = load_config()

    for i, provider in enumerate(config.get("llm", [])):
        pid = provider.get("id", i)
        ptype = provider.get("type", "?")

        if i >= len(manager.drivers):
            results.append({"id": pid, "type": ptype, "status": "error", "message": "No driver loaded"})
            continue

        driver = manager.drivers[i]
        start = time.monotonic()
        try:
            response = await driver.generate("Reply with exactly: OK")
            elapsed = round(time.monotonic() - start, 2)
            results.append({
                "id": pid,
                "type": ptype,
                "status": "ok",
                "response": response[:200],
                "elapsed_seconds": elapsed,
            })
        except Exception as e:
            elapsed = round(time.monotonic() - start, 2)
            results.append({
                "id": pid,
                "type": ptype,
                "status": "error",
                "message": str(e)[:200],
                "elapsed_seconds": elapsed,
            })

    return {"results": results}


def _compute_image_tag(image_name: str) -> tuple[str, str]:
    """Compute Docker image name and tag from Dockerfile + related files.

    Returns (full_image_name, hash_tag).
    Image name: agent-{image_name}
    Tag: short hash of Dockerfile + entrypoint content
    """
    dockers_path = os.path.abspath(DOCKERS_DIR)
    hasher = hashlib.sha256()

    # Hash Dockerfile
    dockerfile = os.path.join(dockers_path, f"Dockerfile.{image_name}")
    if os.path.isfile(dockerfile):
        with open(dockerfile, "rb") as f:
            hasher.update(f.read())

    # Hash entrypoint if exists
    for pattern in [f"entrypoint.{image_name}*", f"entrypoint.{image_name}-code*"]:
        import glob
        for path in glob.glob(os.path.join(dockers_path, pattern)):
            with open(path, "rb") as f:
                hasher.update(f.read())

    tag = hasher.hexdigest()[:12]
    return f"agent-{image_name}", tag


@router.get("/settings/docker-image-status/{image_name}")
async def docker_image_status(
    image_name: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Check if Docker image exists and return its expected name:tag."""
    full_name, tag = _compute_image_tag(image_name)
    image_ref = f"{full_name}:{tag}"

    # Check if image exists
    result = subprocess.run(
        ["docker", "image", "inspect", image_ref],
        capture_output=True,
    )
    exists = result.returncode == 0

    return {
        "image_name": full_name,
        "tag": tag,
        "image_ref": image_ref,
        "exists": exists,
    }


_build_state: dict[str, dict] = {}  # image_name -> {status, logs, image_ref}


@router.post("/settings/docker-build/{image_name}")
async def docker_build(
    image_name: str,
    background_tasks: BackgroundTasks,
    request: Request,
    admin: dict = Depends(require_admin),
):
    full_name, tag = _compute_image_tag(image_name)
    image_ref = f"{full_name}:{tag}"

    if _build_state.get(image_name, {}).get("status") == "building":
        return _build_state[image_name]

    _build_state[image_name] = {"status": "building", "logs": "", "image_ref": image_ref}
    background_tasks.add_task(_run_build, image_name, full_name, tag)
    return _build_state[image_name]


@router.get("/settings/docker-build-status/{image_name}")
async def docker_build_status(
    image_name: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    return _build_state.get(image_name, {"status": "idle", "logs": "", "image_ref": ""})


def _run_build(image_name: str, full_name: str, tag: str):
    import logging
    logger = logging.getLogger(__name__)
    dockers_path = os.path.abspath(DOCKERS_DIR)
    dockerfile = os.path.join(dockers_path, f"Dockerfile.{image_name}")
    image_ref = f"{full_name}:{tag}"

    try:
        logger.info("Building %s from %s", image_ref, dockerfile)
        proc = subprocess.Popen(
            ["docker", "build", "-t", image_ref, "-f", dockerfile, dockers_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        logs = ""
        for line in proc.stdout:
            logs += line
            _build_state[image_name]["logs"] = logs

        proc.wait(timeout=600)
        if proc.returncode == 0:
            _build_state[image_name]["status"] = "done"
            logger.info("Build %s succeeded", image_ref)
        else:
            _build_state[image_name]["status"] = "error"
            logger.error("Build %s failed", image_ref)
    except Exception:
        _build_state[image_name]["status"] = "error"
        logger.exception("Build %s crashed", image_ref)
