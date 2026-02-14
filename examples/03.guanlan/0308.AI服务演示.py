# -*- coding: utf-8 -*-
"""
观澜量化 - AI 服务演示

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime, timedelta

# 尝试导入 rich 库用于美化输出
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.live import Live
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


# 配置文件路径（相对于 examples 目录）
CONFIG_PATH = Path(__file__).parent.parent / "config" / "ai.json"


def print_markdown(text: str) -> None:
    """打印 Markdown 格式文本"""
    if RICH_AVAILABLE:
        console.print(Markdown(text))
    else:
        print(text)


def demo_config():
    """演示配置管理"""
    print("=" * 60)
    print("1. 配置管理演示")
    print("=" * 60)

    from guanlan.core.services.ai import get_config

    # 使用自定义配置路径
    print(f"\n配置文件: {CONFIG_PATH}")

    if not CONFIG_PATH.exists():
        print(f"\n⚠️  配置文件不存在!")
        print(f"请复制示例文件并填入 API Key:")
        print(f"  cp examples/config/ai.json.example examples/config/ai.json")
        return False

    config = get_config(CONFIG_PATH)

    # 列出所有模型
    print(f"\n可用模型: {config.list_models()}")
    print(f"默认模型: {config.default_model}")
    print(f"支持图片的模型: {config.list_vision_models()}")

    # 检查配置完整性
    missing = config.validate()
    if missing:
        print(f"\n⚠️  以下模型未配置 API Key: {missing}")
        print(f"请编辑配置文件: {CONFIG_PATH}")
    else:
        print("\n✅ 所有模型已配置 API Key")

    # 查看模型配置
    print("\n模型配置详情:")
    for name in config.list_models():
        cfg = config.get_model_config(name)
        vision_tag = " [Vision]" if cfg.supports_vision else ""
        print(f"  - {name}{vision_tag}")
        print(f"    API: {cfg.api_base}")
        print(f"    Model: {cfg.model}")

    return len(missing) < len(config.list_models())


async def stream_chat_with_markdown(ai, message: str, **kwargs) -> str:
    """流式对话并实时渲染 Markdown"""
    full_response = ""

    if RICH_AVAILABLE:
        # 使用 rich Live 实时渲染 Markdown
        with Live(Markdown(""), console=console, refresh_per_second=10) as live:
            async for chunk in ai.chat_stream(message, **kwargs):
                full_response += chunk
                live.update(Markdown(full_response))
    else:
        # 普通流式输出
        async for chunk in ai.chat_stream(message, **kwargs):
            print(chunk, end="", flush=True)
            full_response += chunk
        print()

    return full_response


async def demo_chat():
    """演示基础对话（流式输出 + Markdown 渲染）"""
    print("\n" + "=" * 60)
    print("2. 基础对话演示（流式输出）")
    if RICH_AVAILABLE:
        print("   [已启用 rich Markdown 渲染]")
    print("=" * 60)

    from guanlan.core.services.ai import get_ai_client

    ai = get_ai_client(CONFIG_PATH)

    # 流式对话
    print("\n[问] 用一句话介绍量化交易")
    print("[答]")
    try:
        await stream_chat_with_markdown(ai, "用一句话介绍量化交易")
    except Exception as e:
        print(f"[错误] {e}")
        return

    # 带系统提示词
    print("\n[问] 螺纹钢期货代码是什么？（使用专业提示词）")
    print("[答]")
    await stream_chat_with_markdown(
        ai,
        "螺纹钢期货代码是什么？",
        system_prompt="你是期货交易专家，请用简洁专业的语言回答。"
    )


async def demo_conversation():
    """演示多轮对话（流式输出）"""
    print("\n" + "=" * 60)
    print("3. 多轮对话演示（流式输出）")
    print("=" * 60)

    from guanlan.core.services.ai import get_ai_client

    ai = get_ai_client(CONFIG_PATH)

    history = []

    questions = [
        "铁矿石期货在哪个交易所交易？",
        "它的交易单位是多少？",
        "最小变动价位呢？",
    ]

    for q in questions:
        print(f"\n[问] {q}")
        print("[答]")

        # 流式输出并收集完整响应
        full_response = await stream_chat_with_markdown(ai, q, history=history)

        # 更新历史
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": full_response})


async def demo_kline_analysis():
    """演示 K 线数据分析"""
    print("\n" + "=" * 60)
    print("4. K 线数据分析演示")
    print("=" * 60)

    from guanlan.core.services.ai import get_ai_client

    ai = get_ai_client(CONFIG_PATH)

    # 模拟 K 线数据
    base_time = datetime.now() - timedelta(hours=10)
    kline_data = []

    prices = [3850, 3865, 3870, 3855, 3880, 3895, 3890, 3905, 3920, 3915]
    for i, close in enumerate(prices):
        bar = {
            "datetime": base_time + timedelta(hours=i),
            "open": close - 10 + (i % 3) * 5,
            "high": close + 15,
            "low": close - 20,
            "close": close,
            "volume": 10000 + i * 500,
        }
        kline_data.append(bar)

    print(f"\n模拟数据: RB2505 1小时线 {len(kline_data)} 根")
    print(f"价格区间: {min(prices)} - {max(prices)}")

    print("\n正在分析...")
    try:
        # 使用流式输出分析 K 线
        from guanlan.core.services.ai.prompts import KLINE_ANALYSIS_SYSTEM, format_kline_prompt

        prompt = format_kline_prompt(
            kline_data,
            symbol="RB2505",
            interval="1小时",
            strategy="趋势跟踪",
        )
        print("\n[分析结果]")
        await stream_chat_with_markdown(
            ai,
            prompt,
            system_prompt=KLINE_ANALYSIS_SYSTEM,
        )
    except Exception as e:
        print(f"[错误] {e}")


async def demo_sync():
    """演示同步调用（在异步环境中演示）"""
    print("\n" + "=" * 60)
    print("5. 同步调用演示")
    print("=" * 60)

    # 注意：chat_sync 使用 asyncio.run()，不能在异步环境中调用
    # 这里改用 await 直接演示
    from guanlan.core.services.ai import get_ai_client

    ai = get_ai_client(CONFIG_PATH)

    print("\n[问] 什么是期货保证金？")
    print("[答]")
    try:
        await stream_chat_with_markdown(ai, "什么是期货保证金？用一句话解释。")
    except Exception as e:
        print(f"[错误] {e}")

    print("\n说明: chat_sync() 用于非异步环境，如：")
    print("  response = chat_sync('你好', config_path='config/ai.json')")


async def demo_image_analysis():
    """演示图片分析（需要支持 vision 的模型）"""
    print("\n" + "=" * 60)
    print("6. 图片分析演示")
    print("=" * 60)

    from guanlan.core.services.ai import get_ai_client

    ai = get_ai_client(CONFIG_PATH)

    vision_models = ai.list_vision_models()
    if not vision_models:
        print("\n⚠️  没有配置支持图片的模型，跳过此演示")
        print("请在配置中添加 glm-4v-flash 等支持 vision 的模型")
        return

    print(f"\n支持图片的模型: {vision_models}")

    # 检查是否有测试图片
    test_image = Path(__file__).parent / "test_kline.png"
    if not test_image.exists():
        print(f"\n⚠️  测试图片不存在: {test_image}")
        print("请准备一张 K 线截图进行测试")
        return

    print(f"\n正在分析图片: {test_image}")
    try:
        response = await ai.analyze_kline_image(test_image)
        print(f"\n[分析结果]\n{response}")
    except Exception as e:
        print(f"[错误] {e}")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("观澜量化 - AI 服务演示")
    print("=" * 60)

    # 1. 配置管理
    has_api_key = demo_config()

    if not has_api_key:
        print("\n" + "=" * 60)
        print("⚠️  无法运行 API 调用演示")
        print("=" * 60)
        return

    # 2-6. API 调用演示
    try:
        await demo_chat()
        await demo_conversation()
        await demo_kline_analysis()
        await demo_sync()
        await demo_image_analysis()
    except Exception as e:
        print(f"\n演示过程中出错: {e}")

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
