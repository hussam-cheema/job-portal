from pathlib import Path
import subprocess
import tomllib


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_api_deployment_teardown_values_are_numeric():
    with (BACKEND_ROOT / "railway.api.toml").open("rb") as config_file:
        config = tomllib.load(config_file)

    deploy = config["deploy"]

    assert "railway.api.toml" in config["build"]["watchPatterns"]
    assert "startCommand" not in deploy
    assert deploy["overlapSeconds"] == 30
    assert deploy["drainingSeconds"] == 30
    assert isinstance(deploy["overlapSeconds"], int)
    assert isinstance(deploy["drainingSeconds"], int)


def test_railway_dockerfile_expands_the_injected_port_in_a_shell():
    dockerfile = (BACKEND_ROOT / "Dockerfile.railway").read_text()

    assert 'CMD ["sh", "-c"' in dockerfile
    assert "--port ${PORT:-8000}" in dockerfile


def test_database_migration_script_supports_verified_r2_backup():
    script_path = BACKEND_ROOT / "migration" / "migrate-postgres.sh"
    script = script_path.read_text()
    dockerfile = (BACKEND_ROOT / "migration" / "Dockerfile").read_text()

    subprocess.run(["sh", "-n", str(script_path)], check=True)
    assert 'MIGRATION_MODE:-copy' in script
    assert "BACKUP_DATABASE_URL" in script
    assert "pg_dump" in script
    assert "pg_restore --list" in script
    assert "sha256sum" in script
    assert "s3api head-object" in script
    assert "aws-cli" in dockerfile
