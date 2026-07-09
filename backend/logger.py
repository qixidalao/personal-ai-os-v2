"""
日志系统 — 基于 loguru
"""
import sys
from pathlib import Path
from loguru import logger as _logger
from typing import Dict, Any


def setup_logger(config: Dict[str, Any] = None):
    """初始化日志系统"""
    # 移除默认 handler
    _logger.remove()

    # 控制台输出
    _logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if config and config.get("dev", {}).get("enabled") else "INFO",
        colorize=True,
    )

    # 文件输出
    log_dir = Path("storage/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    _logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="gz",
    )

    _logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="90 days",
        compression="gz",
    )

    return _logger
