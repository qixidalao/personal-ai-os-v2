"""
单元测试 — ConfigLoader 配置加载器
"""

import os
import pytest
from pathlib import Path
from backend.config.loader import ConfigLoader


class TestConfigLoader:
    """ConfigLoader 核心功能测试"""

    def test_load_all_from_directory(self, sample_yaml_config: Path):
        """测试从目录加载所有 YAML 配置"""
        loader = ConfigLoader(sample_yaml_config)
        configs = loader.load_all()

        assert "app" in configs
        assert configs["app"]["app"]["name"] == "Personal AI OS"
        assert configs["app"]["server"]["port"] == 8080

    def test_load_single_config(self, sample_yaml_config: Path):
        """测试加载单个配置"""
        loader = ConfigLoader(sample_yaml_config)
        config = loader.load("app")

        assert config is not None
        assert config["app"]["version"] == "2.0.0"

    def test_load_nonexistent_config(self, sample_yaml_config: Path):
        """测试加载不存在的配置返回 None"""
        loader = ConfigLoader(sample_yaml_config)
        config = loader.load("nonexistent")

        assert config is None

    def test_load_empty_directory(self, tmp_path: Path):
        """测试空配置目录"""
        empty_dir = tmp_path / "empty_config"
        empty_dir.mkdir()

        loader = ConfigLoader(empty_dir)
        configs = loader.load_all()

        assert configs == {}

    def test_reload_updates_cache(self, sample_yaml_config: Path):
        """测试热重载更新缓存"""
        loader = ConfigLoader(sample_yaml_config)
        loader.load("app")

        # 修改 YAML 文件
        yaml_file = sample_yaml_config / "app.yaml"
        yaml_file.write_text(
            "app:\n"
            "  name: Personal AI OS Reloaded\n"
            "  version: 3.0.0\n"
        )

        config = loader.reload("app")
        assert config["app"]["name"] == "Personal AI OS Reloaded"
        assert config["app"]["version"] == "3.0.0"

    def test_reload_returns_none_for_missing(self, sample_yaml_config: Path):
        """测试重载不存在的配置返回 None"""
        loader = ConfigLoader(sample_yaml_config)
        result = loader.reload("ghost")
        assert result is None

    def test_get_simple_key(self, sample_yaml_config: Path):
        """测试获取简单配置值"""
        loader = ConfigLoader(sample_yaml_config)

        name = loader.get("app", "app.name")
        assert name == "Personal AI OS"

    def test_get_nested_key(self, sample_yaml_config: Path):
        """测试通过点号路径获取嵌套配置值"""
        loader = ConfigLoader(sample_yaml_config)

        host = loader.get("app", "server.host")
        assert host == "0.0.0.0"

        port = loader.get("app", "server.port")
        assert port == 8080

    def test_get_with_default(self, sample_yaml_config: Path):
        """测试获取不存在的键时返回默认值"""
        loader = ConfigLoader(sample_yaml_config)

        value = loader.get("app", "nonexistent.key", default="fallback")
        assert value == "fallback"

    def test_get_missing_config(self, sample_yaml_config: Path):
        """测试获取不存在的配置时返回默认值"""
        loader = ConfigLoader(sample_yaml_config)

        value = loader.get("ghost", "anything", default=42)
        assert value == 42

    def test_watch_callback_on_reload(self, sample_yaml_config: Path):
        """测试 watch 注册的回调在 reload 时被调用"""
        loader = ConfigLoader(sample_yaml_config)
        loader.load("app")

        callback_called = []

        def watcher(name, config):
            callback_called.append((name, config["app"]["name"]))

        loader.watch("app", watcher)

        # 修改文件并 reload
        yaml_file = sample_yaml_config / "app.yaml"
        yaml_file.write_text(
            "app:\n"
            "  name: Watched Update\n"
        )
        loader.reload("app")

        assert len(callback_called) == 1
        assert callback_called[0] == ("app", "Watched Update")

    def test_watch_multiple_callbacks(self, sample_yaml_config: Path):
        """测试同一个配置可以注册多个 watch 回调"""
        loader = ConfigLoader(sample_yaml_config)
        loader.load("app")

        calls = []

        def cb1(name, config):
            calls.append("cb1")

        def cb2(name, config):
            calls.append("cb2")

        loader.watch("app", cb1)
        loader.watch("app", cb2)

        yaml_file = sample_yaml_config / "app.yaml"
        yaml_file.write_text("app:\n  name: Multi\n")
        loader.reload("app")

        assert len(calls) == 2
        assert "cb1" in calls
        assert "cb2" in calls

    def test_export_all(self, sample_yaml_config: Path):
        """测试导出所有配置"""
        loader = ConfigLoader(sample_yaml_config)
        loader.load_all()

        exports = loader.export_all()
        assert "app" in exports
        assert "name: Personal AI OS" in exports["app"]

    def test_import_config(self, sample_yaml_config: Path):
        """测试导入配置"""
        loader = ConfigLoader(sample_yaml_config)

        yaml_content = (
            "database:\n"
            "  host: localhost\n"
            "  port: 5432\n"
        )
        success = loader.import_config("database", yaml_content)
        assert success is True

        # 验证导入成功
        config = loader.load("database")
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432

    def test_import_config_invalid_yaml(self, sample_yaml_config: Path):
        """测试导入无效 YAML 返回 False"""
        loader = ConfigLoader(sample_yaml_config)
        success = loader.import_config("bad", "{{invalid yaml:::}")
        assert success is False

    def test_import_config_empty(self, sample_yaml_config: Path):
        """测试导入空内容返回 False"""
        loader = ConfigLoader(sample_yaml_config)
        success = loader.import_config("empty", "   ")
        # yaml.safe_load("   ") returns None
        assert success is False

    def test_cache_works(self, sample_yaml_config: Path):
        """测试缓存机制：第二次 load 不重新读文件"""
        loader = ConfigLoader(sample_yaml_config)
        config1 = loader.load("app")

        # 修改文件（但不清缓存）
        yaml_file = sample_yaml_config / "app.yaml"
        yaml_file.write_text("app:\n  name: Modified\n")

        # 不 reload，再次 load 应返回缓存
        config2 = loader.load("app")
        assert config2["app"]["name"] == "Personal AI OS"  # 缓存中的旧值

        # reload 后更新
        config3 = loader.reload("app")
        assert config3["app"]["name"] == "Modified"

    def test_load_all_populates_cache(self, sample_yaml_config: Path):
        """测试 load_all 也会填充缓存"""
        loader = ConfigLoader(sample_yaml_config)
        loader.load_all()

        # 直接从缓存访问
        assert "app" in loader._cache
        assert loader._cache["app"]["app"]["name"] == "Personal AI OS"

    def test_multiple_config_files(self, sample_yaml_config: Path, tmp_path: Path):
        """测试多个配置文件"""
        # 添加第二个配置
        api_yaml = sample_yaml_config / "api.yaml"
        api_yaml.write_text(
            "api:\n"
            "  version: v1\n"
            "  rate_limit: 100\n"
        )

        loader = ConfigLoader(sample_yaml_config)
        configs = loader.load_all()

        assert len(configs) == 2
        assert "app" in configs
        assert "api" in configs
        assert configs["api"]["api"]["rate_limit"] == 100

    def test_get_returns_none_for_non_dict_path(self, sample_yaml_config: Path):
        """测试配置路径中的中间值不是字典时返回默认值"""
        loader = ConfigLoader(sample_yaml_config)

        # port 是 int，再往下取应该返回 default
        value = loader.get("app", "server.port.extra", default="nope")
        assert value == "nope"
