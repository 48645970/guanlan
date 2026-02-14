# -*- coding: utf-8 -*-
"""
观澜量化 - 指标插件系统

自动发现并注册所有指标模块。

Author: 海山观澜
"""

import importlib.util
from glob import glob
from pathlib import Path

from .registry import get_indicator, get_all_indicators, register_indicator  # noqa: F401
from .base import BaseIndicator, BaseIndicatorParams  # noqa: F401


def _load_indicators() -> None:
    """从 indicators/ 目录自动加载所有指标模块"""
    from guanlan.core.constants import PROJECT_ROOT

    indicators_dir = PROJECT_ROOT / "indicators"
    if not indicators_dir.is_dir():
        return

    for filepath in sorted(Path(p) for p in glob(str(indicators_dir / "*.py"))):
        if filepath.stem.startswith("_"):
            continue

        module_name = f"indicators.{filepath.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(filepath))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            pass


_load_indicators()
