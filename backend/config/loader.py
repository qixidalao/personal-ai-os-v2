"""
配置加载器 — 万物皆配置的核心实现
支持热更新、Profile 联动、导入导出
"""
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass


class ConfigLoader:
    """配置加载器 — 热更新驱动"""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self._cache: Dict[str, Dict] = {}
        self._watchers: Dict[str, list] = {}

    def load_all(self) -> Dict[str, Any]:
        """加载所有 YAML 配置"""
        configs = {}
        for yaml_file in self.config_dir.glob("*.yaml"):
            name = yaml_file.stem
            configs[name] = self._load_file(yaml_file)
            self._cache[name] = configs[name]
        return configs

    def load(self, name: str) -> Optional[Dict]:
        """加载单个配置"""
        if name in self._cache:
            return self._cache[name]
        yaml_file = self.config_dir / f"{name}.yaml"
        if yaml_file.exists():
            config = self._load_file(yaml_file)
            self._cache[name] = config
            return config
        return None

    def reload(self, name: str) -> Optional[Dict]:
        """热重载单个配置"""
        yaml_file = self.config_dir / f"{name}.yaml"
        if yaml_file.exists():
            config = self._load_file(yaml_file)
            self._cache[name] = config
            # 通知 watchers
            if name in self._watchers:
                for callback in self._watchers[name]:
                    callback(name, config)
            return config
        return None

    def watch(self, name: str, callback):
        """注册配置变更监听"""
        if name not in self._watchers:
            self._watchers[name] = []
        self._watchers[name].append(callback)

    def get(self, name: str, key: str, default=None):
        """获取配置值（支持点号路径）"""
        config = self.load(name)
        if config is None:
            return default
        keys = key.split(".")
        value = config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def _load_file(self, path: Path) -> Dict:
        """加载 YAML 文件"""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def export_all(self) -> Dict[str, str]:
        """导出全部配置（用于备份）"""
        exports = {}
        for yaml_file in self.config_dir.glob("*.yaml"):
            name = yaml_file.stem
            with open(yaml_file, "r", encoding="utf-8") as f:
                exports[name] = f.read()
        return exports

    def import_config(self, name: str, content: str) -> bool:
        """导入配置"""
        try:
            data = yaml.safe_load(content)
            if data is None:
                return False
            path = self.config_dir / f"{name}.yaml"
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            self._cache[name] = data
            return True
        except Exception:
            return False
