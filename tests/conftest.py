import subprocess
import time
from pathlib import Path

import pytest

from duplicaid.config import Config
from duplicaid.local import LocalExecutor


@pytest.fixture(scope="session")
def docker_compose_file():
    return Path(__file__).parent.parent / "docker-compose.test.yml"


@pytest.fixture(scope="session")
def test_services(docker_compose_file):
    subprocess.run(
        ["docker", "compose", "-f", str(docker_compose_file), "down", "-v"],
        capture_output=True,
    )

    result = subprocess.run(
        ["docker", "compose", "-f", str(docker_compose_file), "up", "-d"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to start test services: {result.stderr}")

    time.sleep(30)

    yield

    subprocess.run(
        ["docker", "compose", "-f", str(docker_compose_file), "down", "-v"],
        capture_output=True,
    )


@pytest.fixture
def test_config(docker_compose_file):
    config = Config()
    config._data = {
        "execution_mode": "local",
        "containers": {"postgres": "postgres", "backup": "db-backup"},
        "paths": {"docker_compose": str(docker_compose_file)},
        "databases": ["testdb1", "testdb2"],
        "postgres": {"user": "postgres", "password": "testpassword"},
        "s3": {
            "endpoint": "http://localhost:9000",
            "bucket": "test-bucket",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "path": "test/logical",
        },
    }
    return config


@pytest.fixture
def local_executor(test_config):
    return LocalExecutor(test_config)


@pytest.fixture
def postgres_ready(test_services, local_executor):
    max_retries = 30
    for i in range(max_retries):
        if local_executor.check_container_running("postgres"):
            stdout, stderr, exit_code = local_executor.docker_exec(
                "postgres", "pg_isready -U postgres -d postgres"
            )
            if exit_code == 0:
                break
        time.sleep(1)
    else:
        pytest.fail("PostgreSQL not ready after 30 seconds")

    stdout, stderr, exit_code = local_executor.docker_exec(
        "postgres", 'psql -U postgres -c "CREATE DATABASE testdb1;" || true'
    )
    stdout, stderr, exit_code = local_executor.docker_exec(
        "postgres", 'psql -U postgres -c "CREATE DATABASE testdb2;" || true'
    )
