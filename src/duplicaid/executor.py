from abc import ABC, abstractmethod
from typing import Optional, Tuple


class ExecutorError(Exception):
    pass


class BaseExecutor(ABC):
    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def execute(self, command: str, show_command: bool = True) -> Tuple[str, str, int]:
        pass

    @abstractmethod
    def docker_exec(
        self, container: str, command: str, user: Optional[str] = None
    ) -> Tuple[str, str, int]:
        pass

    @abstractmethod
    def docker_exec_interactive(
        self, container: str, command: str, stdin_data: str = None
    ) -> Tuple[str, str, int]:
        pass

    @abstractmethod
    def check_container_running(self, container: str) -> bool:
        pass

    @abstractmethod
    def get_container_status(self, container: str) -> Optional[str]:
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        pass
