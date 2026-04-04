from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawMcpService:
    name: str
    source_url: str
    source_type: str
    doc_url: str | None = None
    doc_hash: str | None = None
    branch_hash: str | None = None
    transport: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    is_deprecated: bool = False
    registry_type: str | None = None
    package_identifier: str | None = None
    runtime_hint: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)


class AbstractConnector(ABC):
    @abstractmethod
    async def fetch_services(self) -> list[RawMcpService]:
        ...

    @abstractmethod
    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        ...

    @abstractmethod
    def source_type(self) -> str:
        ...
