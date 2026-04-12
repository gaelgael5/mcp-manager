"""Docker LLM driver — long-running container acting as a task daemon.

Protocol: one JSON task per line written to the container's stdin, one JSON
response per line read from its stdout. Responses carry the original task_id so
the driver can correlate concurrent requests to their futures.

Task shape:
    {"task_id": "abc123",
     "payload": {"instruction": "..."},
     "timeout_seconds": 120}

Response shape (success):
    {"task_id": "abc123", "status": "success", "data": "<model output>"}

Response shape (failure):
    {"task_id": "abc123", "status": "failure", "exit_code": <int>}
"""
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
    inner = value[2:-1]
    if ":-" in inner:
        var_name, default = inner.split(":-", 1)
        return os.environ.get(var_name, default)
    return os.environ.get(inner, "")


_IMAGE_ENV_KEY = {
    "claude-code": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "codex": None,  # Auth via mounted auth.json
}

_IMAGE_MODEL_ENV = {
    "claude-code": "CLAUDE_MODEL",
    "openai": "OPENAI_MODEL",
    "mistral": "MISTRAL_MODEL",
    "codex": "CODEX_MODEL",
}


class LLMProviderDead(Exception):
    """Raised when a Docker LLM provider has failed too many times in a row —
    signals that the entire pipeline should abort (e.g. expired auth token)."""


FAILURE_THRESHOLD = 5  # consecutive failures before a driver is declared dead


class DockerDriver:
    def __init__(
        self,
        provider_id: int,
        args: dict,
        image: str = "claude",
        batch_id: str = "",
        instance_idx: int = 0,
    ):
        self.provider_id = provider_id
        self.instance_idx = instance_idx
        self.image = image
        self._args = args
        suffix = f"-{batch_id}" if batch_id else ""
        self.container_name = f"mcp-llm-worker-{provider_id}-{instance_idx}{suffix}"
        self.api_key = _resolve_env_var(args.get("API_KEY", ""))
        self.workspace = _resolve_env_var(args.get("WORKSPACE_PATH", "./workspace"))
        self.codex_auth_path = _resolve_env_var(args.get("CODEX_AUTH_PATH", "/root/.codex/auth.json"))
        self._process: asyncio.subprocess.Process | None = None
        self._stdin_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._closed = False
        self._rate_limit = 1.0  # seconds between calls
        self._last_call = 0.0
        self.request_count = 0
        self._consecutive_failures = 0

    def _build_run_cmd(self) -> list[str]:
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

        env_key = _IMAGE_ENV_KEY.get(self.image, "ANTHROPIC_API_KEY")
        if env_key and self.api_key:
            cmd.extend(["-e", f"{env_key}={self.api_key}"])
        if self.image == "codex":
            cmd.extend(["-v", f"{self.codex_auth_path}:/home/agent/.codex/auth.json:ro"])

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

        result = subprocess.run(
            ["docker", "images", f"agent-{self.image}", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True,
        )
        built_image = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        cmd.append(built_image if built_image else f"agent-{self.image}")
        return cmd

    async def start(self):
        """Start the container as a long-running daemon reading tasks on stdin."""
        logger.info("Starting Docker LLM container: %s", self.container_name)

        rm = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", self.container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await rm.wait()

        cmd = self._build_run_cmd()
        self._closed = False
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info("Container %s started (PID %d)", self.container_name, self._process.pid)

    async def _read_loop(self):
        """Read JSON lines from the container stdout and dispatch to pending futures."""
        assert self._process is not None
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break  # container stdout closed
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # ignore non-protocol chatter
                task_id = event.get("task_id", "")
                future = self._pending.pop(task_id, None)
                if future and not future.done():
                    future.set_result(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reader loop crashed for %s", self.container_name)
        finally:
            # Fail any pending futures so callers don't hang forever.
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_result({"status": "failure", "exit_code": -1})
            self._pending.clear()

    async def generate(self, prompt: str) -> str:
        """Send a task to the daemon, await the response, return its text output."""
        self.request_count += 1
        if self._process is None or self._closed:
            return ""

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

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[task_id] = future

        try:
            async with self._stdin_lock:
                try:
                    self._process.stdin.write(task_json.encode() + b"\n")
                    await self._process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    logger.warning("Docker stdin broken on %s", self.container_name)
                    self._pending.pop(task_id, None)
                    return ""

            try:
                event = await asyncio.wait_for(future, timeout=180)
            except asyncio.TimeoutError:
                self._pending.pop(task_id, None)
                logger.warning("Docker generate timeout task %s on %s", task_id, self.container_name)
                return ""
        except Exception:
            self._pending.pop(task_id, None)
            logger.exception("Docker generate failed task %s", task_id)
            return ""

        if event.get("status") == "success":
            self._consecutive_failures = 0
            return event.get("data", "") or ""

        self._consecutive_failures += 1
        if self._consecutive_failures >= FAILURE_THRESHOLD:
            raise LLMProviderDead(
                f"{self.container_name} failed {self._consecutive_failures} "
                f"consecutive tasks — aborting pipeline (check auth token / logs)"
            )
        return ""

    async def embed(self, text: str) -> list[float] | None:
        """Docker drivers don't embed."""
        return None

    async def stop(self):
        """Close the daemon cleanly: close stdin, cancel reader, remove container."""
        logger.info("Stopping Docker LLM container: %s", self.container_name)
        self._closed = True

        if self._process and self._process.stdin and not self._process.stdin.is_closing():
            try:
                self._process.stdin.close()
            except Exception:
                pass

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None

        rm = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", self.container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await rm.wait()

        if self._process:
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
