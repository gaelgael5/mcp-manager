"""Load and manage LLM providers config from llm_providers.json."""
import json
import logging
import os

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "llm_providers.json")


def load_config() -> dict:
    path = os.path.abspath(CONFIG_PATH)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("LLM config not found at %s, using defaults", path)
        return {"llm": []}


def save_config(config: dict) -> None:
    path = os.path.abspath(CONFIG_PATH)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info("LLM config saved to %s", path)


def get_providers() -> list[dict]:
    return load_config().get("llm", [])


def get_provider(provider_id: int) -> dict | None:
    for p in get_providers():
        if p.get("id") == provider_id:
            return p
    return None


def get_setting(key: str, default=None):
    return load_config().get(key, default)


def set_setting(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)
