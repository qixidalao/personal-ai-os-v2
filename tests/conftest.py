import os

os.environ.setdefault("AIOS_DISABLE_AUTH", "1")

"""
Shared test fixtures for Personal AI OS V2
"""
# 中文：Personal AI OS V2 的共享测试固件
from pathlib import Path
import pytest


import tempfile

@pytest.fixture(autouse=True)
def _execution_test_roots():
    """P0：工具文件访问受工作区边界约束；测试临时目录需加入允许根。"""
    try:
        from runtime.execution import get_execution_manager
        manager = get_execution_manager()
        roots = list(manager.workspace.roots)
        for extra_root in (Path(tempfile.gettempdir()), Path("/tmp")):
            resolved = extra_root.resolve()
            if resolved not in roots:
                roots.append(resolved)
        manager.workspace.roots = roots
    except Exception:
        pass
    yield


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test file operations."""
    # 中文：返回用于测试文件操作的临时目录。
    return tmp_path


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Create a temporary YAML config file and return its path."""
    # 中文：创建临时 YAML 配置文件并返回其路径。
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
    # 中文：创建临时 settings.json 文件。
    settings_path = tmp_path / "storage" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        '{"agentParams": {"maxToolRounds": 6}}'
    )
    return settings_path
