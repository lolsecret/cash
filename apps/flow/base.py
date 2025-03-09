from typing import Any
from abc import ABC, abstractmethod


class InterfaceError(Exception):
    pass


class ServiceInterface(ABC):
    @abstractmethod
    def run_service(self) -> Any:
        raise InterfaceError("This method should be overload")


class Service:
    def __init__(self, integration: ServiceInterface):
        if not isinstance(integration, ServiceInterface):
            raise InterfaceError("Class should be extends from IntegrationInterface")
        self.integration = integration

    def run_service(self):
        return self.integration.run_service()
