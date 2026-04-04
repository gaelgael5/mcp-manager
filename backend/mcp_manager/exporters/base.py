from abc import ABC, abstractmethod


class AbstractExporter(ABC):
    @abstractmethod
    def target_name(self) -> str: ...

    @abstractmethod
    def generate(self, service_name: str, registry_type: str | None,
                 package_identifier: str | None, runtime_hint: str | None,
                 transport: str | None, env_vars: dict[str, str]) -> dict[str, str] | None: ...
