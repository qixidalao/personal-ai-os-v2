"""
Shared test fixtures for Personal AI OS V2
"""
from pathlib import Path
import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test file operations."""
    return tmp_path


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Create a temporary YAML config file and return its path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_file = config_dir / "app.yaml"
    yaml_file.write_text(
        "app:\n"
        "  name: Personal AI OS\n"
        "  version: 2.0.0\n"
        "server:\n"
        "  host: 0.0.0.0\n"
        "  port: 8080\n"
        "  dev_mode: false\n"
        "  cors_origins:\n"
        "    - '*'\n"
    )
    return config_dir


@pytest.fixture
def sample_settings_json(tmp_path: Path) -> Path:
    """Create a temporary settings.json file."""
    settings_path = tmp_path / "storage" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        '{"agentParams": {"maxToolRounds": 6}}'
    )
    return settings_path
