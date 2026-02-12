# -*- coding: utf-8 -*-
"""
观澜量化 - 项目资源模块

资源目录结构：
- js/      - JavaScript 库
- css/     - CSS 样式文件
- fonts/   - 字体文件
- sounds/  - 音频文件
- data/    - 数据文件

Author: 海山观澜
"""

from pathlib import Path

# 资源根目录
RESOURCES_DIR = Path(__file__).parent

# 各类资源子目录
JS_DIR = RESOURCES_DIR / "js"
CSS_DIR = RESOURCES_DIR / "css"
FONTS_DIR = RESOURCES_DIR / "fonts"
SOUNDS_DIR = RESOURCES_DIR / "sounds"
DATA_DIR = RESOURCES_DIR / "data"


def get_resource_path(resource_type: str, filename: str) -> Path:
    """
    获取资源文件路径

    Parameters
    ----------
    resource_type : str
        资源类型：'js', 'css', 'fonts', 'sounds', 'data'
    filename : str
        资源文件名

    Returns
    -------
    Path
        资源文件的完整路径

    Examples
    --------
    >>> get_resource_path('js', 'lightweight-charts.min.js')
    PosixPath('.../resources/js/lightweight-charts.min.js')
    """
    type_dirs = {
        'js': JS_DIR,
        'css': CSS_DIR,
        'fonts': FONTS_DIR,
        'sounds': SOUNDS_DIR,
        'data': DATA_DIR,
    }

    if resource_type not in type_dirs:
        raise ValueError(f"Unknown resource type: {resource_type}. "
                         f"Must be one of {list(type_dirs.keys())}")

    return type_dirs[resource_type] / filename


__all__ = [
    'RESOURCES_DIR',
    'JS_DIR',
    'CSS_DIR',
    'FONTS_DIR',
    'SOUNDS_DIR',
    'DATA_DIR',
    'get_resource_path',
]
