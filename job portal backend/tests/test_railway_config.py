from pathlib import Path
import tomllib


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_api_deployment_teardown_values_are_numeric():
    with (BACKEND_ROOT / "railway.api.toml").open("rb") as config_file:
        config = tomllib.load(config_file)

    deploy = config["deploy"]

    assert deploy["overlapSeconds"] == 30
    assert deploy["drainingSeconds"] == 30
    assert isinstance(deploy["overlapSeconds"], int)
    assert isinstance(deploy["drainingSeconds"], int)
