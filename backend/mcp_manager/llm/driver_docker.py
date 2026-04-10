"""Docker LLM driver — launches a container, communicates via stdin/stdout JSON."""
import asyncio
import json
import logging
import os
import subprocess
import time
import uuid

logger = logging.getLogger(__name__)


def _resolve_env_var(value: str) -> str:
    """Resolve ${VAR} and ${VAR:-default} patterns from environment."""
    if not value.startswith("${"):
        return value
    # ${VAR:-default}
    inner = value[2:-1]
    if ":-" in inner:
        var_name, default = inner.split(":-", 1)
        return os.environ.get(var_name, default)
    return os.environ.get(inner, "")


_IMAGE_ENV_KEY = {
    "claude-code": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "codex": None,  # Auth via mounted auth.json, no API key env var
}

_IMAGE_MODEL_ENV = {
    "claude-code": "CLAUDE_MODEL",
    "openai": "OPENAI_MODEL",
    "mistral": "MISTRAL_MODEL",
    "codex": "CODEX_MODEL",
}


class DockerDriver:
    def __init__(self, provider_id: int, args: dict, image: str = "claude", batch_id: str = ""):
        self.provider_id = provider_id
        self.image = image
        self._args = args
        suffix = f"-{batch_id}" if batch_id else ""
        self.container_name = f"mcp-llm-worker-{provider_id}{suffix}"
        self.api_key = _resolve_env_var(args.get("API_KEY", ""))
        self.workspace = _resolve_env_var(args.get("WORKSPACE_PATH", "./workspace"))
        self.codex_auth_path = _resolve_env_var(args.get("CODEX_AUTH_PATH", "/root/.codex/auth.json"))
        self._process = None
        self._rate_limit = 1.0  # seconds between calls
        self._last_call = 0.0
        self.request_count = 0

    def set_rate_limit(self, rps: float):
        self._rate_limit = 1.0 / rps if rps > 0 else 1.0

    def start(self):
        """Build and start the Docker container."""
        logger.info("Starting Docker LLM container: %s", self.container_name)

        # Stop if already running
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
        )

        # Build docker run command based on image type
        cmd = [
            "docker", "run",
            "--name", self.container_name,
            "--rm",
            "-i",
            "--network", "host",
            "-e", "AGENT_ROLE=indexer",
            "-e", "AGENT_MAX_TURNS=5",
            "-v", f"{os.path.abspath(self.workspace)}:/workspace",
            "-w", "/workspace",
        ]

        # Inject API key env var (image-specific) or auth volume
        env_key = _IMAGE_ENV_KEY.get(self.image, "ANTHROPIC_API_KEY")
        if env_key and self.api_key:
            cmd.extend(["-e", f"{env_key}={self.api_key}"])
        if self.image == "codex":
            cmd.extend(["-v", f"{self.codex_auth_path}:/home/agent/.codex/auth.json:ro"])

        # Inject extra args as env vars (MODEL, AGENT_MAX_TOKENS, etc.)
        _skip_keys = {"API_KEY", "WORKSPACE_PATH", "CODEX_AUTH_PATH"}
        for key, val in self._args.items():
            if key in _skip_keys:
                continue
            resolved = _resolve_env_var(str(val))
            if key == "MODEL":
                model_env = _IMAGE_MODEL_ENV.get(self.image, "MODEL")
                cmd.extend(["-e", f"{model_env}={resolved}"])
            else:
                cmd.extend(["-e", f"{key}={resolved}"])

        # Find the built image: agent-{image}:{hash} or fallback to mcp-manager-{image}
        import subprocess as _sp
        result = _sp.run(
            ["docker", "images", f"agent-{self.image}", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True,
        )
        built_image = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        cmd.append(built_image if built_image else f"agent-{self.image}")

        # Start container in background with stdin open
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info("Container %s started (PID %d)", self.container_name, self._process.pid)

    def stop(self):
        """Stop and remove the container."""
        logger.info("Stopping Docker LLM container: %s", self.container_name)
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
        )
        if self._process:
            self._process.kill()
            self._process = None

    async def generate(self, prompt: str) -> str:
        """Send a task to the container via docker exec and get result."""
        self.request_count += 1
        # Rate limit
        now = time.monotonic()
        wait = self._rate_limit - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()

        task_id = str(uuid.uuid4())[:8]
        task_json = json.dumps({
            "task_id": task_id,
            "payload": {"instruction": prompt},
            "timeout_seconds": 120,
        })

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", self.container_name,
                "/usr/local/bin/entrypoint.claude-code.sh",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=task_json.encode()),
                timeout=180,
            )

            # Parse events from stdout, extract result
            result_text = ""
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "progress" and isinstance(event.get("data"), str):
                        result_text = event["data"]
                    elif event.get("type") == "result":
                        break
                except json.JSONDecodeError:
                    continue

            return result_text.strip().strip('"')

        except asyncio.TimeoutError:
            logger.warning("Docker generate timed out for task %s", task_id)
            return ""
        except Exception:
            logger.exception("Docker generate failed for task %s", task_id)
            return ""

    async def embed(self, text: str) -> list[float] | None:
        """Docker/Claude doesn't do embeddings — fallback to None."""
        return None
