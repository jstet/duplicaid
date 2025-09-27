"""CLI interface for DuplicAid."""

from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from .backup import LogicalBackupManager, WALGBackupManager
from .config import Config
from .discovery import DatabaseDiscovery
from .executor import ExecutorError
from .local import LocalExecutor
from .ssh import RemoteExecutor

console = Console()
app = typer.Typer(
    name="duplicaid",
    help="PostgreSQL backup management CLI tool",
    rich_markup_mode="rich",
)

# Subcommands
config_app = typer.Typer(name="config", help="Configuration management")
backup_app = typer.Typer(name="backup", help="Create backups")
restore_app = typer.Typer(name="restore", help="Restore from backups")
list_app = typer.Typer(name="list", help="List available backups")

app.add_typer(config_app)
app.add_typer(backup_app)
app.add_typer(restore_app)
app.add_typer(list_app)

# Global configuration instance
config = Config()


def get_executor():
    """Get the appropriate executor based on configuration."""
    if config.execution_mode == "local":
        return LocalExecutor(config)
    else:
        return RemoteExecutor(config)


def check_config() -> bool:
    """Check if configuration is valid."""
    if not config.is_configured():
        console.print("[red]Configuration not found or incomplete.[/red]")
        console.print("Run [bold]duplicaid config init[/bold] to set up configuration.")
        raise typer.Exit(1)

    if not config.validate():
        console.print("[red]Configuration validation failed.[/red]")
        raise typer.Exit(1)

    return True


# Configuration commands
@config_app.command("init")
def config_init():
    """Initialize DuplicAid configuration."""
    config.init_config()


@config_app.command("show")
def config_show():
    """Show current configuration."""
    if not config.is_configured():
        console.print(
            "[yellow]No configuration found. Run 'duplicaid config init' to set up.[/yellow]"
        )
        return

    table = Table(title="DuplicAid Configuration", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Execution Mode", config.execution_mode)

    if config.execution_mode == "remote":
        table.add_row("Remote Host", config.remote_host or "Not set")
        table.add_row("Remote User", config.remote_user or "Not set")
        table.add_row("Remote Port", str(config.remote_port))
        table.add_row("SSH Key Path", config.ssh_key_path or "Not set")

    table.add_row("PostgreSQL Container", config.postgres_container)
    table.add_row("Backup Container", config.backup_container)
    table.add_row("Docker Compose Path", config.docker_compose_path)
    table.add_row(
        "Databases", ", ".join(config.databases) if config.databases else "None"
    )

    console.print(table)


# Backup commands
@backup_app.command("walg")
def backup_walg():
    """Create a WAL-G backup (point-in-time)."""
    check_config()

    try:
        with get_executor() as executor:
            walg_manager = WALGBackupManager(config)
            success = walg_manager.create_backup(executor)

            if not success:
                raise typer.Exit(1)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


@backup_app.command("logical")
def backup_logical(
    database: Optional[str] = typer.Option(
        None, "--db", help="Specific database to backup"
    ),
):
    """Create a logical backup."""
    check_config()

    if database and database not in config.databases:
        console.print(f"[red]Database '{database}' not found in configuration.[/red]")
        console.print("Available databases:", ", ".join(config.databases))
        raise typer.Exit(1)

    try:
        with get_executor() as executor:
            logical_manager = LogicalBackupManager(config)
            success = logical_manager.create_backup(executor, database)

            if not success:
                raise typer.Exit(1)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


# Restore commands
@restore_app.command("walg")
def restore_walg(
    backup_name: str = typer.Option(
        "LATEST", "--backup", help="Backup name to restore"
    ),
    target_time: Optional[str] = typer.Option(
        None,
        "--to",
        help="Target time for point-in-time recovery (YYYY-MM-DD HH:MM:SS)",
    ),
):
    """Restore from WAL-G backup."""
    check_config()

    # Confirm destructive operation
    if not typer.confirm("This will destroy current data. Are you sure?"):
        console.print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit()

    try:
        with get_executor() as executor:
            walg_manager = WALGBackupManager(config)
            success = walg_manager.restore_backup(executor, backup_name, target_time)

            if not success:
                raise typer.Exit(1)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


@restore_app.command("logical")
def restore_logical(
    database: str = typer.Argument(..., help="Database name to restore"),
    backup_file: str = typer.Argument(..., help="Path to backup file on remote server"),
):
    """Restore from logical backup."""
    check_config()

    if database not in config.databases:
        console.print(f"[red]Database '{database}' not found in configuration.[/red]")
        console.print("Available databases:", ", ".join(config.databases))
        raise typer.Exit(1)

    # Confirm destructive operation
    if not typer.confirm(f"This will overwrite database '{database}'. Are you sure?"):
        console.print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit()

    try:
        with get_executor() as executor:
            logical_manager = LogicalBackupManager(config)
            success = logical_manager.restore_backup(executor, database, backup_file)

            if not success:
                raise typer.Exit(1)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


# List commands
@list_app.command("walg")
def list_walg():
    """List available WAL-G backups."""
    check_config()

    try:
        with get_executor() as executor:
            walg_manager = WALGBackupManager(config)
            backups = walg_manager.list_backups(executor)

            if not backups:
                console.print("[yellow]No WAL-G backups found.[/yellow]")
                return

            table = Table(title="WAL-G Backups", box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("Timestamp", style="green")
            table.add_column("Size", style="yellow")

            for backup in backups:
                table.add_row(
                    backup.name,
                    backup.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    backup.size or "Unknown",
                )

            console.print(table)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


@list_app.command("logical")
def list_logical():
    """List available logical backups."""
    check_config()

    try:
        with get_executor() as executor:
            logical_manager = LogicalBackupManager(config)
            backups = logical_manager.list_backups(executor)

            if not backups:
                console.print("[yellow]No logical backups found.[/yellow]")
                return

            table = Table(title="Logical Backups", box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("Database", style="blue")
            table.add_column("Timestamp", style="green")

            for backup in backups:
                table.add_row(
                    backup.name,
                    backup.database or "Unknown",
                    backup.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                )

            console.print(table)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


# Status command
@app.command("status")
def status():
    """Show system status."""
    check_config()

    try:
        with get_executor() as executor:
            console.print("[bold blue]DuplicAid Status[/bold blue]\n")

            # Check container status
            postgres_running = executor.check_container_running(
                config.postgres_container
            )
            backup_running = executor.check_container_running(config.backup_container)

            table = Table(title="Container Status", box=box.ROUNDED)
            table.add_column("Container", style="cyan")
            table.add_column("Status", style="green")

            postgres_status = (
                "[green]Running[/green]" if postgres_running else "[red]Stopped[/red]"
            )
            backup_status = (
                "[green]Running[/green]" if backup_running else "[red]Stopped[/red]"
            )

            table.add_row(config.postgres_container, postgres_status)
            table.add_row(config.backup_container, backup_status)

            console.print(table)

            # Show database status if postgres is running
            if postgres_running:
                discovery = DatabaseDiscovery(config)
                databases = discovery.get_databases(executor)

                if databases:
                    console.print("\n")
                    db_table = Table(title="Database Status", box=box.ROUNDED)
                    db_table.add_column("Database", style="cyan")
                    db_table.add_column("Size", style="green")

                    for db_info in databases:
                        db_table.add_row(
                            db_info["name"], db_info.get("size", "Unknown")
                        )

                    console.print(db_table)

    except ExecutorError as e:
        console.print(f"[red]Executor Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
