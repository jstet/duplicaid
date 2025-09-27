"""Local execution utilities for DuplicAid."""

import os
import subprocess
from typing import Optional, Tuple

from rich.console import Console

from .config import Config
from .executor import BaseExecutor, ExecutorError

console = Console()


class LocalError(ExecutorError):
    pass


class LocalExecutor(BaseExecutor):
    def __init__(self, config: Config):
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, command: str, show_command: bool = True) -> Tuple[str, str, int]:
        if show_command:
            console.print(f"[dim]$ {command}[/dim]")

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                console.print(
                    f"[red]Command failed with exit code {result.returncode}[/red]"
                )
                if result.stderr:
                    console.print(f"[red]Error: {result.stderr.strip()}[/red]")

            return result.stdout.strip(), result.stderr.strip(), result.returncode

        except subprocess.TimeoutExpired:
            raise LocalError("Command timed out")
        except Exception as e:
            raise LocalError(f"Failed to execute command: {e}")

    def docker_exec(
        self, container: str, command: str, user: Optional[str] = None
    ) -> Tuple[str, str, int]:
        actual_container_name = (
            self.config.postgres_container
            if container == "postgres"
            else self.config.backup_container
            if container == "backup"
            else container
        )
        docker_command = "docker exec"
        if user:
            docker_command += f" -u {user}"
        docker_command += f" {actual_container_name} {command}"

        return self.execute(docker_command)

    def docker_exec_interactive(
        self, container: str, command: str, stdin_data: str = None
    ) -> Tuple[str, str, int]:
        actual_container_name = (
            self.config.postgres_container
            if container == "postgres"
            else self.config.backup_container
            if container == "backup"
            else container
        )
        docker_command = f"docker exec -i {actual_container_name} {command}"

        if stdin_data:
            full_command = f"echo '{stdin_data}' | {docker_command}"
            return self.execute(full_command)
        else:
            return self.execute(docker_command)

    def check_container_running(self, container: str) -> bool:
        actual_container_name = (
            self.config.postgres_container
            if container == "postgres"
            else self.config.backup_container
            if container == "backup"
            else container
        )

        stdout, stderr, exit_code = self.execute(
            f"docker ps --filter name={actual_container_name} --filter status=running --format '{{{{.Names}}}}'",
            show_command=False,
        )

        return actual_container_name in stdout.split("\n")

    def get_container_status(self, container: str) -> Optional[str]:
        actual_container_name = (
            self.config.postgres_container
            if container == "postgres"
            else self.config.backup_container
            if container == "backup"
            else container
        )

        stdout, stderr, exit_code = self.execute(
            f"docker ps -a --filter name={actual_container_name} --format '{{{{.Status}}}}'",
            show_command=False,
        )

        if stdout:
            return stdout.strip()
        return None

    def file_exists(self, path: str) -> bool:
        return os.path.exists(path)
