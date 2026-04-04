from mcp_manager.connectors.base import AbstractConnector

_connectors: dict[str, type[AbstractConnector]] = {}


def register_connector(cls: type[AbstractConnector]) -> type[AbstractConnector]:
    instance = cls.__new__(cls)
    _connectors[instance.source_type()] = cls
    return cls


def get_all_connectors() -> list[AbstractConnector]:
    return [cls() for cls in _connectors.values()]


def get_connector(source_type: str) -> AbstractConnector | None:
    cls = _connectors.get(source_type)
    return cls() if cls else None
