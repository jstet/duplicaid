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
    """SSH client wrapper for executing commands on a remote server."""

    def __init__(self, config: Config):
        super().__init__(config)
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

    def execute(
        self,
        command: str,
        show_command: bool = True,
        stdin: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """Execute command on remote server, now with stdin support."""
        if not self.client:
            raise SSHError("Not connected to remote server")

        if show_command:
            console.print(f"[dim]$ {command}[/dim]")

        try:
            # Get stdin, stdout, and stderr streams
            stdin_pipe, stdout_pipe, stderr_pipe = self.client.exec_command(command)

            # NEW: Handle stdin
            if stdin:
                stdin_pipe.write(stdin)
                stdin_pipe.channel.shutdown_write()  # Signal that we're done writing

            exit_code = stdout_pipe.channel.recv_exit_status()
            stdout_text = stdout_pipe.read().decode("utf-8").strip()
            stderr_text = stderr_pipe.read().decode("utf-8").strip()

            if exit_code != 0:
                console.print(f"[red]Command failed with exit code {exit_code}[/red]")
                if stderr_text:
                    console.print(f"[red]Error: {stderr_text}[/red]")

            return stdout_text, stderr_text, exit_code

        except Exception as e:
            raise SSHError(f"Failed to execute command: {e}")

    def file_exists(self, path: str) -> bool:
        """Check if file exists on remote server."""
        # The command exits with 0 if the file exists and is a regular file.
        _, _, exit_code = self.execute(f"test -f {path}", show_command=False)
        return exit_code == 0
