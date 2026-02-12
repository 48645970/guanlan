# -*- coding: utf-8 -*-
"""
观澜量化 - 系统工具演示

演示 core.utils.system 模块的各项功能

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import QApplication
from guanlan.core.utils.system import (
    get_system_info,
    is_windows,
    is_linux,
    is_macos,
    is_win11,
    desktop_size,
    screen_count,
    all_screen_sizes,
    dpi_scale,
    is_dark_mode,
)


def demo_system_info():
    """演示系统信息获取"""
    print("=" * 70)
    print("1. 系统信息")
    print("=" * 70)

    info = get_system_info()
    print(f"平台标识: {info.platform}")
    print(f"系统名称: {info.system}")
    print(f"系统版本: {info.release}")
    print(f"详细版本: {info.version}")
    print(f"机器类型: {info.machine}")
    print(f"Python 版本: {info.python_version}")

    print()


def demo_platform_detection():
    """演示平台检测"""
    print("=" * 70)
    print("2. 平台检测")
    print("=" * 70)

    print(f"是否为 Windows: {is_windows()}")
    print(f"是否为 Linux: {is_linux()}")
    print(f"是否为 macOS: {is_macos()}")
    print(f"是否为 Windows 11+: {is_win11()}")

    print()


def demo_screen_info():
    """演示屏幕信息获取"""
    print("=" * 70)
    print("3. 屏幕信息")
    print("=" * 70)

    # 主屏幕尺寸
    width, height = desktop_size()
    print(f"主屏幕分辨率: {width}x{height}")

    # 屏幕数量
    count = screen_count()
    print(f"屏幕数量: {count}")

    # 所有屏幕尺寸
    sizes = all_screen_sizes()
    print(f"\n所有屏幕:")
    for i, (w, h) in enumerate(sizes):
        print(f"  屏幕 {i + 1}: {w}x{h}")

    # DPI 缩放
    scale = dpi_scale()
    print(f"\nDPI 缩放比例: {scale:.2f}x ({scale * 100:.0f}%)")

    # 深色模式
    dark = is_dark_mode()
    print(f"深色模式: {'是' if dark else '否'}")

    print()


def demo_conditional_logic():
    """演示基于系统的条件逻辑"""
    print("=" * 70)
    print("4. 条件逻辑示例")
    print("=" * 70)

    print("根据操作系统选择不同的配置:\n")

    if is_windows():
        print("  当前系统: Windows")
        if is_win11():
            print("  → 使用 Windows 11 新特性")
            print("  → 启用云母效果窗口")
        else:
            print("  → 使用传统 Windows 界面")
    elif is_linux():
        print("  当前系统: Linux")
        print("  → 使用 GTK 主题")
        print("  → 启用 Wayland 支持（如果可用）")
    elif is_macos():
        print("  当前系统: macOS")
        print("  → 使用 macOS 原生界面")
        print("  → 启用触控板手势")
    else:
        print("  当前系统: 未知")
        print("  → 使用默认配置")

    print()


def demo_responsive_ui():
    """演示响应式 UI 适配"""
    print("=" * 70)
    print("5. 响应式 UI 适配")
    print("=" * 70)

    width, height = desktop_size()

    print(f"屏幕分辨率: {width}x{height}\n")

    # 根据分辨率调整窗口大小
    if width >= 2560 and height >= 1440:
        window_size = (1600, 900)
        print("  分辨率类型: 2K/4K 高分辨率")
        print(f"  建议窗口尺寸: {window_size[0]}x{window_size[1]}")
        print("  字体大小: 14px")
    elif width >= 1920 and height >= 1080:
        window_size = (1280, 720)
        print("  分辨率类型: 1080p 标准分辨率")
        print(f"  建议窗口尺寸: {window_size[0]}x{window_size[1]}")
        print("  字体大小: 12px")
    else:
        window_size = (1024, 600)
        print("  分辨率类型: 低分辨率")
        print(f"  建议窗口尺寸: {window_size[0]}x{window_size[1]}")
        print("  字体大小: 11px")

    # DPI 适配
    scale = dpi_scale()
    if scale > 1.0:
        print(f"\n  检测到高 DPI 屏幕 ({scale}x)")
        print(f"  自动缩放界面元素")

    print()


def demo_multi_monitor():
    """演示多显示器支持"""
    print("=" * 70)
    print("6. 多显示器支持")
    print("=" * 70)

    count = screen_count()
    print(f"检测到 {count} 个显示器\n")

    if count > 1:
        sizes = all_screen_sizes()
        for i, (w, h) in enumerate(sizes):
            aspect_ratio = w / h
            print(f"显示器 {i + 1}:")
            print(f"  分辨率: {w}x{h}")
            print(f"  宽高比: {aspect_ratio:.2f}:1")

            # 判断显示器类型
            if aspect_ratio >= 2.3:
                print(f"  类型: 超宽屏")
            elif aspect_ratio >= 1.7:
                print(f"  类型: 宽屏 (16:9 或 16:10)")
            else:
                print(f"  类型: 标准屏 (4:3 或 5:4)")
            print()
    else:
        print("当前只有一个显示器")
        print()


def main():
    """主函数"""
    # 创建 QApplication 实例（某些功能需要）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 22 + "观澜量化 - 系统工具演示" + " " * 22 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 执行各项演示
    demo_system_info()
    demo_platform_detection()
    demo_screen_info()
    demo_conditional_logic()
    demo_responsive_ui()
    demo_multi_monitor()

    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    print()
    print("提示：")
    print("- 系统信息可用于跨平台适配")
    print("- 屏幕信息可用于响应式 UI 设计")
    print("- 深色模式检测可用于主题切换")


if __name__ == "__main__":
    main()
