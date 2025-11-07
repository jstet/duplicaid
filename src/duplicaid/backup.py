"""Backup operations for PostgreSQL via WAL-G and logical dumps."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from minio import Minio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config
from .ssh import RemoteExecutor, SSHError

console = Console()


@dataclass
class BackupInfo:
    """Information about a backup."""

    name: str
    timestamp: datetime
    size: Optional[str] = None
    type: str = "unknown"
    database: Optional[str] = None


class WALGBackupManager:
    """Manager for WAL-G backup operations."""

    def __init__(self, config: Config):
        self.config = config

    def create_backup(self, executor: RemoteExecutor) -> bool:
        """
        Create a new WAL-G backup.

        Args:
            executor: SSH executor instance

        Returns:
            True if backup was successful, False otherwise
        """
        console.print("[blue]Creating WAL-G backup...[/blue]")

        if not executor.check_container_running(self.config.postgres_container):
            console.print(
                f"[red]PostgreSQL container '{self.config.postgres_container}' is not running[/red]"
            )
            return False

        command = (
            'su - postgres -c "WALG_DELTA_MAX_STEPS=0 '
            'envdir /etc/wal-g/env /usr/local/bin/wal-g backup-push /var/lib/postgresql/data"'
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Creating backup...", total=None)

                stdout, stderr, exit_code = executor.docker_exec(
                    self.config.postgres_container, command
                )

                if exit_code == 0:
                    console.print("[green]✓ WAL-G backup created successfully[/green]")
                    return True
                else:
                    console.print("[red]✗ WAL-G backup failed[/red]")
                    if stderr:
                        console.print(f"[red]Error: {stderr}[/red]")
                    return False

        except SSHError as e:
            console.print(f"[red]✗ WAL-G backup failed: {e}[/red]")
            return False

    def list_backups(self, executor: RemoteExecutor) -> List[BackupInfo]:
        """
        List available WAL-G backups.

        Args:
            executor: SSH executor instance

        Returns:
            List of BackupInfo objects
        """
        if not executor.check_container_running(self.config.postgres_container):
            console.print(
                f"[red]PostgreSQL container '{self.config.postgres_container}' is not running[/red]"
            )
            return []

        command = "envdir /etc/wal-g/env /usr/local/bin/wal-g backup-list"

        try:
            stdout, stderr, exit_code = executor.docker_exec(
                self.config.postgres_container, command
            )

            if exit_code != 0:
                console.print("[red]Failed to list WAL-G backups[/red]")
                if stderr:
                    console.print(f"[red]Error: {stderr}[/red]")
                return []

            return self._parse_walg_backup_list(stdout)

        except SSHError as e:
            console.print(f"[red]Failed to list WAL-G backups: {e}[/red]")
            return []

    def _parse_walg_backup_list(self, output: str) -> List[BackupInfo]:
        """Parse WAL-G backup list output."""
        backups = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("name") or line.startswith("---"):
                continue

            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                try:
                    timestamp = datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
                    size = parts[2] if len(parts) > 2 else None

                    backups.append(
                        BackupInfo(
                            name=name, timestamp=timestamp, size=size, type="walg"
                        )
                    )
                except ValueError:
                    continue

        return sorted(backups, key=lambda x: x.timestamp, reverse=True)

    def restore_backup(
        self,
        executor: RemoteExecutor,
        backup_name: str = "LATEST",
        target_time: Optional[str] = None,
    ) -> bool:
        """
        Restore from WAL-G backup.

        Args:
            executor: SSH executor instance
            backup_name: Name of backup to restore (default: LATEST)
            target_time: Target time for point-in-time recovery (format: YYYY-MM-DD HH:MM:SS)

        Returns:
            True if restore was successful, False otherwise
        """
        console.print(f"[blue]Restoring from WAL-G backup: {backup_name}[/blue]")

        try:
            # Stop PostgreSQL and remove existing data
            console.print("[yellow]Stopping PostgreSQL container...[/yellow]")
            stdout, stderr, exit_code = executor.execute(
                f"docker compose -f {self.config.docker_compose_path} down --volumes"
            )

            # Remove the volume
            console.print("[yellow]Removing existing data volume...[/yellow]")
            executor.execute("docker volume rm postgres_data", show_command=False)

            # Fetch backup
            console.print(f"[yellow]Fetching backup {backup_name}...[/yellow]")
            fetch_command = (
                f"docker run --rm "
                f"--env-file {self.config.docker_compose_path.replace('docker-compose.yml', '.env')} "
                f"--user postgres "
                f"-v postgres_data:/var/lib/postgresql/data "
                f"jstet/wald:latest "
                f"envdir /etc/wal-g/env /usr/local/bin/wal-g backup-fetch /var/lib/postgresql/data {backup_name}"
            )

            stdout, stderr, exit_code = executor.execute(fetch_command)
            if exit_code != 0:
                console.print("[red]Failed to fetch backup[/red]")
                return False

            # Configure point-in-time recovery if target_time is specified
            if target_time:
                console.print(
                    f"[yellow]Configuring point-in-time recovery to {target_time}...[/yellow]"
                )
                recovery_command = (
                    f"docker run --rm "
                    f"-v postgres_data:/var/lib/postgresql/data "
                    f"jstet/wald:latest "
                    f'bash -c "'
                    f"touch /var/lib/postgresql/data/recovery.signal && "
                    f"cat >> /var/lib/postgresql/data/postgresql.auto.conf << 'EOF'\\n"
                    f"restore_command = 'envdir /etc/wal-g/env /usr/local/bin/wal-g wal-fetch %f %p'\\n"
                    f"recovery_target_time = '{target_time}'\\n"
                    f'EOF"'
                )

                stdout, stderr, exit_code = executor.execute(recovery_command)
                if exit_code != 0:
                    console.print(
                        "[red]Failed to configure point-in-time recovery[/red]"
                    )
                    return False

            # Start PostgreSQL
            console.print("[yellow]Starting PostgreSQL container...[/yellow]")
            stdout, stderr, exit_code = executor.execute(
                f"docker compose -f {self.config.docker_compose_path} up -d"
            )

            if exit_code == 0:
                console.print("[green]✓ WAL-G restore completed successfully[/green]")
                return True
            else:
                console.print("[red]✗ Failed to start PostgreSQL after restore[/red]")
                return False

        except SSHError as e:
            console.print(f"[red]✗ WAL-G restore failed: {e}[/red]")
            return False


class LogicalBackupManager:
    """Manager for logical backup operations."""

    def __init__(self, config: Config):
        self.config = config

    def create_backup(
        self, executor: RemoteExecutor, database: Optional[str] = None
    ) -> bool:
        """
        Create a logical backup.

        Args:
            executor: SSH executor instance
            database: Specific database to backup (None for all)

        Returns:
            True if backup was successful, False otherwise
        """
        if database:
            console.print(
                f"[blue]Creating logical backup for database: {database}[/blue]"
            )
            return self._create_single_database_backup(executor, database)
        else:
            console.print("[blue]Creating logical backup for all databases[/blue]")
            return self._create_all_databases_backup(executor)

    def _create_single_database_backup(
        self, executor: RemoteExecutor, database: str
    ) -> bool:
        """Create backup for a single database."""
        if not executor.check_container_running(self.config.postgres_container):
            console.print(
                f"[red]PostgreSQL container '{self.config.postgres_container}' is not running[/red]"
            )
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/tmp/{database}_backup_{timestamp}.sql.gz"

        command = f"pg_dump -U postgres_{database} -d {database} | gzip > {backup_file}"

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(f"Backing up {database}...", total=None)

                stdout, stderr, exit_code = executor.docker_exec(
                    self.config.postgres_container, command
                )

                if exit_code == 0:
                    console.print(
                        f"[green]✓ Logical backup created: {backup_file}[/green]"
                    )
                    return True
                else:
                    console.print(f"[red]✗ Logical backup failed for {database}[/red]")
                    if stderr:
                        console.print(f"[red]Error: {stderr}[/red]")
                    return False

        except SSHError as e:
            console.print(f"[red]✗ Logical backup failed: {e}[/red]")
            return False

    def _create_all_databases_backup(self, executor: RemoteExecutor) -> bool:
        """Create backup for all databases using db-backup container."""
        if not executor.check_container_running(self.config.backup_container):
            console.print(
                f"[red]Backup container '{self.config.backup_container}' is not running[/red]"
            )
            return False

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Creating logical backup...", total=None)

                stdout, stderr, exit_code = executor.docker_exec(
                    self.config.backup_container, "backup-now"
                )

                if exit_code == 0:
                    console.print(
                        "[green]✓ Logical backup created successfully[/green]"
                    )
                    return True
                else:
                    console.print("[red]✗ Logical backup failed[/red]")
                    if stderr:
                        console.print(f"[red]Error: {stderr}[/red]")
                    return False

        except SSHError as e:
            console.print(f"[red]✗ Logical backup failed: {e}[/red]")
            return False

    def list_backups(self, executor: RemoteExecutor) -> List[BackupInfo]:
        """
        List available logical backups from S3.

        Args:
            executor: SSH executor instance

        Returns:
            List of BackupInfo objects
        """
        if not self.config.s3_endpoint or not self.config.s3_bucket:
            console.print(
                "[yellow]S3 not configured, listing local backups...[/yellow]"
            )
            return self._list_local_backups(executor)

        try:
            endpoint = self.config.s3_endpoint.replace("http://", "").replace(
                "https://", ""
            )
            secure = self.config.s3_endpoint.startswith("https://")

            client = Minio(
                endpoint,
                access_key=self.config.s3_access_key,
                secret_key=self.config.s3_secret_key,
                secure=secure,
            )

            backups = []
            objects = client.list_objects(
                self.config.s3_bucket, prefix=self.config.s3_path, recursive=True
            )

            for obj in objects:
                if any(ext in obj.object_name for ext in [".sql", ".bz2", ".gz"]):
                    filename = obj.object_name.split("/")[-1]
                    match = re.search(r"(\w+)_(\d{8}[_-]\d{6})", filename)
                    if match:
                        database = match.group(1)
                        timestamp_str = match.group(2).replace("-", "_")
                        try:
                            timestamp = datetime.strptime(
                                timestamp_str, "%Y%m%d_%H%M%S"
                            )
                            backups.append(
                                BackupInfo(
                                    name=filename,
                                    timestamp=timestamp,
                                    type="logical",
                                    database=database,
                                    size=obj.size,
                                )
                            )
                        except ValueError:
                            continue

            return sorted(backups, key=lambda x: x.timestamp, reverse=True)

        except Exception as e:
            console.print(f"[red]Failed to list S3 backups: {e}[/red]")
            return []

    def _list_local_backups(self, executor: RemoteExecutor) -> List[BackupInfo]:
        """List backups from local /backup directory."""
        if not executor.check_container_running(self.config.backup_container):
            console.print(
                f"[red]Backup container '{self.config.backup_container}' is not running[/red]"
            )
            return []

        try:
            stdout, stderr, exit_code = executor.docker_exec(
                self.config.backup_container, "ls -1 /backup"
            )

            if exit_code != 0:
                console.print("[red]Failed to list local backups[/red]")
                if stderr:
                    console.print(f"[red]Error: {stderr}[/red]")
                return []

            return self._parse_logical_backup_list(stdout)

        except SSHError as e:
            console.print(f"[red]Failed to list local backups: {e}[/red]")
            return []

    def _parse_logical_backup_list(self, output: str) -> List[BackupInfo]:
        """Parse logical backup list output."""
        backups = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # This is a simplified parser - you may need to adjust based on actual output format
            if ".sql" in line or ".bz2" in line:
                try:
                    # Extract timestamp and database name from filename
                    # Format might be like: database_20240101_120000.sql.bz2
                    match = re.search(r"(\w+)_(\d{8}_\d{6})", line)
                    if match:
                        database = match.group(1)
                        timestamp_str = match.group(2)
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                        backups.append(
                            BackupInfo(
                                name=line,
                                timestamp=timestamp,
                                type="logical",
                                database=database,
                            )
                        )
                except ValueError:
                    continue

        return sorted(backups, key=lambda x: x.timestamp, reverse=True)

    def restore_backup(
        self, executor: RemoteExecutor, database: str, backup_file: str
    ) -> bool:
        """
        Restore from logical backup.

        Args:
            executor: SSH executor instance
            database: Target database name
            backup_file: Path to backup file

        Returns:
            True if restore was successful, False otherwise
        """
        console.print(
            f"[blue]Restoring logical backup for {database} from {backup_file}[/blue]"
        )

        if not executor.check_container_running(self.config.postgres_container):
            console.print(
                f"[red]PostgreSQL container '{self.config.postgres_container}' is not running[/red]"
            )
            return False

        try:
            # Determine restore command based on file extension
            if backup_file.endswith(".gz"):
                restore_command = f"gunzip -c {backup_file} | psql -U {self.config.postgres_user} -d {database}"
            elif backup_file.endswith(".bz2"):
                restore_command = f"bunzip2 -c {backup_file} | psql -U {self.config.postgres_user} -d {database}"
            else:
                restore_command = (
                    f"psql -U {self.config.postgres_user} -d {database} < {backup_file}"
                )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(f"Restoring {database}...", total=None)

                stdout, stderr, exit_code = executor.docker_exec(
                    self.config.postgres_container, restore_command
                )

                if exit_code == 0:
                    console.print(
                        f"[green]✓ Logical restore completed for {database}[/green]"
                    )

                    # Reset database permissions
                    console.print("[yellow]Resetting database permissions...[/yellow]")
                    permission_commands = [
                        f"ALTER DATABASE {database} OWNER TO postgres_{database};",
                        f"GRANT ALL PRIVILEGES ON DATABASE {database} TO postgres_{database};",
                        f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres_{database};",
                        f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres_{database};",
                    ]

                    for cmd in permission_commands:
                        executor.docker_exec(
                            self.config.postgres_container,
                            f'psql -U {self.config.postgres_user} -c "{cmd}" {database}',
                        )

                    return True
                else:
                    console.print(f"[red]✗ Logical restore failed for {database}[/red]")
                    if stderr:
                        console.print(f"[red]Error: {stderr}[/red]")
                    return False

        except SSHError as e:
            console.print(f"[red]✗ Logical restore failed: {e}[/red]")
            return False
