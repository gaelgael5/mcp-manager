"""Generate installation recipes by matching service runtime to target modes."""


def generate_from_modes(
    modes: list[dict],
    runtime_hint: str | None,
    package_identifier: str | None,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str] | None:
    """Match a service's runtime_hint against target modes and render the template.

    Template placeholders:
      {name}    — service name
      {package} — package identifier (e.g., @playwright/mcp)
      {runtime} — runtime hint (e.g., npx, uvx)
      {env_flags} — -e KEY1 -e KEY2 for docker
    """
    if not modes:
        return None

    rh = runtime_hint or "npx"
    pkg = package_identifier or service_name

    # Find matching mode
    matched = None
    for mode in modes:
        if mode.get("runtime") == rh:
            matched = mode
            break

    # Fallback: first mode if no exact match
    if not matched:
        matched = modes[0]
        rh = matched.get("runtime", rh)

    template = matched.get("template", "")
    action_type = matched.get("action_type", "cmd")

    if not template:
        return None

    env_flags = " ".join(f"-e {k}" for k in env_vars)

    rendered = (
        template
        .replace("{name}", service_name)
        .replace("{package}", pkg)
        .replace("{runtime}", rh)
        .replace("{env_flags}", env_flags)
    )

    return {"action_type": action_type, "data": rendered.strip()}


# Legacy function for backward compatibility (used by CLI export)
def generate_installation_data(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    target_name: str,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str] | None:
    """Legacy wrapper — uses hardcoded defaults if no modes in DB."""
    default_modes = _get_default_modes(target_name)
    if not default_modes:
        return None
    return generate_from_modes(
        modes=default_modes,
        runtime_hint=runtime_hint,
        package_identifier=package_identifier,
        service_name=service_name,
        env_vars=env_vars,
    )


def _get_default_modes(target_name: str) -> list[dict] | None:
    """Hardcoded defaults for targets that don't have modes in DB yet."""
    defaults = {
        "claude_code": [
            {"runtime": "npx", "action_type": "cmd", "template": "claude mcp add {name} -- npx {package}"},
            {"runtime": "uvx", "action_type": "cmd", "template": "claude mcp add {name} -- uvx {package}"},
            {"runtime": "docker", "action_type": "cmd", "template": "claude mcp add {name} -- docker run -i {package}"},
        ],
        "claude_desktop": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": "{\"mcpServers\": {\"{name}\": {\"command\": \"npx\", \"args\": [\"-y\", \"{package}\"]}}}"},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": "{\"mcpServers\": {\"{name}\": {\"command\": \"uvx\", \"args\": [\"{package}\"]}}}"},
        ],
        "langgraph": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": "{\"command\": \"npx\", \"args\": [\"-y\", \"{package}\"], \"transport\": \"stdio\", \"name\": \"{name}\", \"enabled\": true}"},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": "{\"command\": \"uvx\", \"args\": [\"{package}\"], \"transport\": \"stdio\", \"name\": \"{name}\", \"enabled\": true}"},
        ],
        "docker_stdio": [
            {"runtime": "docker", "action_type": "docker_run", "template": "docker run -i --rm {env_flags} {package}"},
        ],
    }
    return defaults.get(target_name)
