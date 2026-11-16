"""Load and manage LLM providers config from llm_providers.json."""
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config"))
CONFIG_PATH = os.path.join(CONFIG_DIR, "llm_providers.json")
EXAMPLE_PATH = os.path.join(CONFIG_DIR, "llm_providers.example.json")


def _bootstrap_from_example(path: str) -> bool:
    """Recopie l'exemple en configuration si celle-ci manque.

    `llm_providers.json` n'est volontairement pas suivi par git : il est monte
    en bind-mount et modifie depuis /settings, alors que `deploy-mcp.sh` fait un
    `git reset --hard`. Tant que le fichier etait suivi, chaque livraison
    reinstallait les valeurs du depot (llama3.1:8b) par-dessus la configuration
    saisie dans l'interface, sans rien dire — on testait donc un fournisseur
    different de celui qu'affichait l'ecran.

    Contrepartie : sur une machine neuve le fichier n'existe pas. Le creer ici
    plutot que renvoyer une liste vide, un referentiel sans fournisseur ne
    produisant aucun message d'erreur exploitable.
    """
    if not os.path.exists(EXAMPLE_PATH):
        return False
    try:
        shutil.copyfile(EXAMPLE_PATH, path)
    except OSError:
        logger.exception("Impossible d'initialiser %s depuis l'exemple", path)
        return False
    logger.warning("LLM config absente, initialisee depuis %s", EXAMPLE_PATH)
    return True


def load_config() -> dict:
    path = os.path.abspath(CONFIG_PATH)
    if not os.path.exists(path):
        _bootstrap_from_example(path)
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
