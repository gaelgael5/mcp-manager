import json


def generate_installation_data(
    registry_type: str | None, package_identifier: str | None,
    runtime_hint: str | None, transport: str | None,
    target_name: str, service_name: str, env_vars: dict[str, str],
) -> dict[str, str] | None:
    generators = {
        "claude_code": _gen_claude_code,
        "claude_desktop": _gen_claude_desktop,
        "langgraph": _gen_langgraph,
        "docker_stdio": _gen_docker_stdio,
    }
    gen = generators.get(target_name)
    if not gen:
        return None
    return gen(registry_type=registry_type, package_identifier=package_identifier,
               runtime_hint=runtime_hint, transport=transport,
               service_name=service_name, env_vars=env_vars)


def _cmd_parts(runtime_hint: str | None, package_identifier: str | None) -> str:
    return f"{runtime_hint or 'npx'} {package_identifier or ''}"


def _gen_claude_code(registry_type, package_identifier, runtime_hint, transport, service_name, env_vars):
    cmd = _cmd_parts(runtime_hint, package_identifier)
    return {"action_type": "cmd", "data": f"claude mcp add {service_name} -- {cmd}"}


def _gen_claude_desktop(registry_type, package_identifier, runtime_hint, transport, service_name, env_vars):
    rh = runtime_hint or "npx"
    pkg = package_identifier or ""
    args = ["-y", pkg] if rh == "npx" else [pkg]
    entry = {service_name: {"command": rh, "args": args}}
    if env_vars:
        entry[service_name]["env"] = {k: f"${{{k}}}" for k in env_vars}
    return {"action_type": "insert_in_file", "data": json.dumps(entry, indent=2)}


def _gen_langgraph(registry_type, package_identifier, runtime_hint, transport, service_name, env_vars):
    rh = runtime_hint or "npx"
    pkg = package_identifier or ""
    args = ["-y", pkg] if rh == "npx" else [pkg]
    entry = {"command": rh, "args": args, "transport": transport or "stdio",
             "env": {k: k for k in env_vars}, "name": service_name, "enabled": True}
    return {"action_type": "insert_in_file", "data": json.dumps(entry, indent=2)}


def _gen_docker_stdio(registry_type, package_identifier, runtime_hint, transport, service_name, env_vars):
    image = package_identifier or f"mcp/{service_name}:latest"
    env_flags = " ".join(f"-e {k}" for k in env_vars)
    env_part = f" {env_flags}" if env_flags else ""
    return {"action_type": "docker_run", "data": f"docker run -i --rm{env_part} {image}"}
