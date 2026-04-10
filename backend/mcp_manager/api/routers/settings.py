"""Settings API — edit LLM providers config (admin only)."""
import hashlib
import json
import os
import re
import subprocess

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import (
    Language,
    McpSummary,
    SkillSourceTranslation,
    SkillTranslation,
)
from mcp_manager.llm.config import load_config, save_config
from mcp_manager.prompts import (
    PROMPT_KINDS,
    PromptNotFound,
    load_prompt,
    prompt_path,
    write_prompt,
)

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

    # System keys (always shown)
    for var_name in ("ANTHROPIC_API_KEY",):
        keys[var_name] = {
            "name": var_name,
            "default": "",
            "current": os.environ.get(var_name, ""),
            "pattern": f"${{{var_name}}}",
        }

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


# --- Auth files (e.g. Codex auth.json) ---

_AUTH_FILES = {
    "codex": {"path": "/root/.codex/auth.json", "label": "Codex auth.json"},
}


@router.get("/settings/auth-files")
async def list_auth_files(request: Request, admin: dict = Depends(require_admin)):
    """List available auth files and whether they exist on disk."""
    result = []
    for key, info in _AUTH_FILES.items():
        path = info["path"]
        content = ""
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                content = f.read()
        result.append({
            "key": key,
            "label": info["label"],
            "path": path,
            "exists": os.path.isfile(path),
            "content": content,
        })
    return result


class AuthFileUpdate(BaseModel):
    key: str
    content: str


@router.put("/settings/auth-files")
async def update_auth_file(
    body: AuthFileUpdate,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Save auth file content to disk."""
    if body.key not in _AUTH_FILES:
        return {"status": "error", "message": f"Unknown auth file: {body.key}"}

    info = _AUTH_FILES[body.key]
    path = info["path"]

    # Validate JSON
    try:
        json.loads(body.content)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)

    return {"status": "saved", "path": path}


# --- API Tokens (domain-based rate-limited pool) ---


class ApiTokenCreate(BaseModel):
    domain: str
    token: str
    rate_limit_per_min: int = 60


@router.get("/settings/api-tokens")
async def list_api_tokens(request: Request, admin: dict = Depends(require_admin)):
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import ApiToken
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(ApiToken).order_by(ApiToken.domain, ApiToken.created_at))
        tokens = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "domain": t.domain,
            "token_prefix": t.token[:8] + "..." if len(t.token) > 8 else t.token,
            "rate_limit_per_min": t.rate_limit_per_min,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


@router.post("/settings/api-tokens")
async def create_api_token(
    body: ApiTokenCreate,
    request: Request,
    admin: dict = Depends(require_admin),
):
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import ApiToken

    async with SessionLocal() as db:
        t = ApiToken(domain=body.domain, token=body.token, rate_limit_per_min=body.rate_limit_per_min)
        db.add(t)
        await db.commit()

    from mcp_manager.connectors.token_pool import invalidate_cache
    invalidate_cache()
    return {"status": "created", "id": str(t.id)}


@router.delete("/settings/api-tokens/{token_id}")
async def delete_api_token(
    token_id: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    import uuid
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import ApiToken
    from sqlalchemy import delete

    async with SessionLocal() as db:
        await db.execute(delete(ApiToken).where(ApiToken.id == uuid.UUID(token_id)))
        await db.commit()

    from mcp_manager.connectors.token_pool import invalidate_cache
    invalidate_cache()
    return {"status": "deleted"}


@router.get("/settings/api-tokens/stats")
async def api_tokens_stats(request: Request, admin: dict = Depends(require_admin)):
    from mcp_manager.connectors.token_pool import get_pool_stats
    return get_pool_stats()


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


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


class LanguageIn(BaseModel):
    code: str
    name: str
    is_active: bool = False
    display_order: int = 100


class LanguageUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


def _language_to_dict(lang: Language) -> dict:
    return {
        "code": lang.code,
        "name": lang.name,
        "is_active": lang.is_active,
        "display_order": lang.display_order,
    }


def _check_prompts_exist(code: str) -> None:
    missing = [k for k in PROMPT_KINDS if not prompt_path(k, code).exists()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"missing prompts for {code}: {', '.join(missing)}",
        )


@router.get("/settings/languages")
async def list_languages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Language).order_by(Language.display_order))
    return [_language_to_dict(l) for l in result.scalars().all()]


@router.post("/settings/languages", status_code=201)
async def create_language(
    body: LanguageIn,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    if body.is_active:
        _check_prompts_exist(body.code)
    lang = Language(**body.model_dump())
    db.add(lang)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="language code already exists")
    await db.refresh(lang)
    return _language_to_dict(lang)


@router.patch("/settings/languages/{code}")
async def update_language(
    code: str,
    body: LanguageUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Language).where(Language.code == code))
    lang = result.scalar_one_or_none()
    if not lang:
        raise HTTPException(status_code=404, detail="language not found")
    if body.is_active is True and not lang.is_active:
        _check_prompts_exist(code)
    if body.name is not None:
        lang.name = body.name
    if body.is_active is not None:
        lang.is_active = body.is_active
    if body.display_order is not None:
        lang.display_order = body.display_order
    await db.commit()
    await db.refresh(lang)
    return _language_to_dict(lang)


@router.delete("/settings/languages/{code}")
async def delete_language(
    code: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    for model in (McpSummary, SkillSourceTranslation, SkillTranslation):
        n = (await db.execute(
            select(func.count()).select_from(model).where(model.culture == code)
        )).scalar() or 0
        if n:
            raise HTTPException(
                status_code=409,
                detail=f"{n} translation(s) exist for {code}; remove them first",
            )
    await db.execute(sa_delete(Language).where(Language.code == code))
    await db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class PromptIn(BaseModel):
    content: str


@router.get("/settings/prompts")
async def list_prompts(db: AsyncSession = Depends(get_db)):
    """List (kind, language) combinations with their file status."""
    result = await db.execute(select(Language).order_by(Language.display_order))
    langs = result.scalars().all()
    items = []
    for lang in langs:
        for kind in PROMPT_KINDS:
            p = prompt_path(kind, lang.code)
            items.append({
                "kind": kind,
                "language": lang.code,
                "language_name": lang.name,
                "is_active": lang.is_active,
                "exists": p.exists(),
                "size": p.stat().st_size if p.exists() else 0,
            })
    return items


@router.get("/settings/prompts/{kind}/{language}")
async def get_prompt(kind: str, language: str):
    if kind not in PROMPT_KINDS:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")
    try:
        content = load_prompt(kind, language)
    except PromptNotFound:
        raise HTTPException(
            status_code=404, detail=f"prompt not found: {kind}/{language}"
        )
    return {"kind": kind, "language": language, "content": content}


@router.put("/settings/prompts/{kind}/{language}")
async def update_prompt(
    kind: str,
    language: str,
    body: PromptIn,
    admin: dict = Depends(require_admin),
):
    if kind not in PROMPT_KINDS:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")
    if "{content}" not in body.content:
        raise HTTPException(
            status_code=400,
            detail="prompt template must contain the {content} placeholder",
        )
    write_prompt(kind, language, body.content)
    return {
        "status": "written",
        "kind": kind,
        "language": language,
        "size": len(body.content),
    }
