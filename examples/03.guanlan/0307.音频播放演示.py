# -*- coding: utf-8 -*-
"""
观澜量化 - 音频播放演示

演示 core.services.sound 模块的各项功能

注意：需要安装 pygame 库
pip install pygame

Author: 海山观澜
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def demo_availability():
    """检查音频播放器可用性"""
    print("=" * 70)
    print("1. 检查音频播放器可用性")
    print("=" * 70)

    try:
        import pygame
        print("✓ pygame 库已安装")
        print(f"  版本: {pygame.version.ver}")
    except ImportError:
        print("✗ pygame 库未安装")
        print("  请运行: pip install pygame")
        return False

    print()
    return True


def demo_basic_playback():
    """演示基本播放功能"""
    print("=" * 70)
    print("2. 基本播放功能")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import get_player

        # 获取播放器实例
        player = get_player()

        if not player.is_available():
            print("✗ 音频播放器不可用")
            return

        print("✓ 音频播放器已就绪\n")

        # 播放预定义音效
        print(">>> 播放预定义音效")
        sounds = ["buy", "sell", "con_buy", "con_sell", "cancel", "error", "alarm"]

        for sound in sounds:
            print(f"  播放: {sound}.wav")
            player.play(sound, async_play=False)  # 同步播放，方便演示
            time.sleep(0.5)  # 间隔 0.5 秒

        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_volume_control():
    """演示音量控制"""
    print("=" * 70)
    print("3. 音量控制")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import get_player

        player = get_player()

        if not player.is_available():
            print("✗ 音频播放器不可用")
            return

        print(">>> 测试不同音量")

        volumes = [1.0, 0.7, 0.5, 0.3, 0.1]

        for vol in volumes:
            player.set_volume(vol)
            current_vol = player.get_volume()
            print(f"  音量: {current_vol:.0%}")
            player.play("buy", async_play=False)
            time.sleep(0.5)

        # 恢复默认音量
        player.set_volume(1.0)
        print(f"\n  已恢复默认音量: {player.get_volume():.0%}")
        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_async_playback():
    """演示异步播放"""
    print("=" * 70)
    print("4. 异步播放")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import get_player

        player = get_player()

        if not player.is_available():
            print("✗ 音频播放器不可用")
            return

        print(">>> 异步播放多个音效（不等待播放完成）\n")

        # 异步播放
        print("  开始异步播放...")
        player.play("buy", async_play=True)
        print("  函数立即返回，音频在后台播放")

        # 等待播放完成
        time.sleep(1)

        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_playback_control():
    """演示播放控制"""
    print("=" * 70)
    print("5. 播放控制")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import get_player

        player = get_player()

        if not player.is_available():
            print("✗ 音频播放器不可用")
            return

        print(">>> 播放控制示例\n")

        # 开始播放
        print("  开始播放 alarm.wav（较长音频）")
        player.play("alarm", async_play=True)

        time.sleep(1)

        # 暂停
        if player.is_playing():
            print("  暂停播放...")
            player.pause()
            time.sleep(1)

            # 恢复
            print("  恢复播放...")
            player.unpause()
            time.sleep(1)

            # 停止
            print("  停止播放...")
            player.stop()

        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_convenience_functions():
    """演示便捷函数"""
    print("=" * 70)
    print("6. 便捷函数")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import play, play_file

        print(">>> 使用便捷函数播放音效\n")

        print("  使用 play() 函数:")
        play("buy", async_play=False)
        print("    play('buy') - 完成")

        time.sleep(0.5)

        print("\n  使用 play_file() 函数:")
        play_file("sell.wav", async_play=False)
        print("    play_file('sell.wav') - 完成")

        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_practical_scenario():
    """演示实际场景：交易事件音效"""
    print("=" * 70)
    print("7. 实际场景：交易事件音效")
    print("=" * 70)

    try:
        from guanlan.core.services.sound import play

        print(">>> 场景：模拟交易流程\n")

        # 下单
        print("  1. 下买单...")
        play("buy", async_play=False)
        time.sleep(0.5)

        print("  2. 买单成交...")
        play("con_buy", async_play=False)
        time.sleep(0.5)

        print("  3. 下卖单...")
        play("sell", async_play=False)
        time.sleep(0.5)

        print("  4. 卖单成交...")
        play("con_sell", async_play=False)
        time.sleep(0.5)

        print("  5. 下单被拒...")
        play("error", async_play=False)
        time.sleep(0.5)

        print("  6. 撤单成功...")
        play("cancel", async_play=False)

        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 21 + "观澜量化 - 音频播放演示" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 检查 pygame 可用性
    if not demo_availability():
        print("\n提示：")
        print("1. 安装 pygame 库: pip install pygame")
        print("2. 确保系统音频设备正常")
        return

    # 执行各项演示
    demo_basic_playback()
    demo_volume_control()
    demo_async_playback()
    demo_playback_control()
    demo_convenience_functions()
    demo_practical_scenario()

    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    print()
    print("提示：")
    print("- 音频文件位于: resources/sounds/")
    print("- 支持的音效: buy, sell, con_buy, con_sell, cancel, error, alarm")
    print("- 可以播放自定义 WAV 文件")
    print("- 支持音量控制和异步播放")


if __name__ == "__main__":
    main()
