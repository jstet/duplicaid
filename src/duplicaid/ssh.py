"""SSH remote execution utilities for DuplicAid."""

from typing import Optional, Tuple

import paramiko
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from .config import Config
from .executor import BaseExecutor, ExecutorError

console = Console()


class SSHError(ExecutorError):
    pass


class RemoteExecutor(BaseExecutor):
    """SSH client wrapper for executing commands on remote server."""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def connect(self) -> None:
        """Establish SSH connection to remote server."""
        if not self.config.validate():
            raise SSHError("Invalid configuration")

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            with Live(
                Spinner("dots", text=f"Connecting to {self.config.remote_host}..."),
                console=console,
                transient=True,
            ):
                self.client.connect(
                    hostname=self.config.remote_host,
                    port=self.config.remote_port,
                    username=self.config.remote_user,
                    key_filename=self.config.ssh_key_path,
                    timeout=10,
                )

            console.print(f"[green]✓ Connected to {self.config.remote_host}[/green]")

        except Exception as e:
            raise SSHError(f"Failed to connect to {self.config.remote_host}: {e}")

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self.client = None

    def execute(self, command: str, show_command: bool = True) -> Tuple[str, str, int]:
        """
        Execute command on remote server.

        Args:
            command: Command to execute
            show_command: Whether to display the command being executed

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        if not self.client:
            raise SSHError("Not connected to remote server")

        if show_command:
            console.print(f"[dim]$ {command}[/dim]")

        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()

            stdout_text = stdout.read().decode("utf-8").strip()
            stderr_text = stderr.read().decode("utf-8").strip()

            if exit_code != 0:
                console.print(f"[red]Command failed with exit code {exit_code}[/red]")
                if stderr_text:
                    console.print(f"[red]Error: {stderr_text}[/red]")

            return stdout_text, stderr_text, exit_code

        except Exception as e:
            raise SSHError(f"Failed to execute command: {e}")

    def docker_exec(
        self, container: str, command: str, user: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """
        Execute command in Docker container.

        Args:
            container: Container name
            command: Command to execute in container
            user: User to run command as

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        docker_command = "docker exec"
        if user:
            docker_command += f" -u {user}"
        docker_command += f" {container} {command}"

        return self.execute(docker_command)

    def docker_exec_interactive(
        self, container: str, command: str, stdin_data: str = None
    ) -> Tuple[str, str, int]:
        """
        Execute interactive command in Docker container (e.g., for piping data).

        Args:
            container: Container name
            command: Command to execute in container
            stdin_data: Data to pipe to stdin

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        docker_command = f"docker exec -i {container} {command}"

        if stdin_data:
            # For commands that need stdin, we'll use a different approach
            full_command = f"echo '{stdin_data}' | {docker_command}"
            return self.execute(full_command)
        else:
            return self.execute(docker_command)

    def check_container_running(self, container: str) -> bool:
        """
        Check if a Docker container is running.

        Args:
            container: Container name

        Returns:
            True if container is running, False otherwise
        """
        stdout, stderr, exit_code = self.execute(
            f"docker ps --filter name={container} --filter status=running --format '{{{{.Names}}}}'",
            show_command=False,
        )

        return container in stdout.split("\n")

    def get_container_status(self, container: str) -> Optional[str]:
        """
        Get container status.

        Args:
            container: Container name

        Returns:
            Container status or None if not found
        """
        stdout, stderr, exit_code = self.execute(
            f"docker ps -a --filter name={container} --format '{{{{.Status}}}}'",
            show_command=False,
        )

        if stdout:
            return stdout.strip()
        return None

    def file_exists(self, path: str) -> bool:
        """
        Check if file exists on remote server.

        Args:
            path: File path to check

        Returns:
            True if file exists, False otherwise
        """
        stdout, stderr, exit_code = self.execute(f"test -f {path}", show_command=False)
        return exit_code == 0
