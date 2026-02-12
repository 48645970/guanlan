# -*- coding: utf-8 -*-
"""
拼音转换示例

演示 pypinyin 库的用法：
- 汉字转拼音
- 首字母提取
- 多音字处理
- 不同输出风格

使用前需要：
1. pip install pypinyin

Author: 海山观澜
"""


def get_pinyin(text: str) -> str | None:
    """获取完整拼音"""
    try:
        from pypinyin import lazy_pinyin
    except ImportError:
        print("请先安装 pypinyin: pip install pypinyin")
        return None
    return " ".join(lazy_pinyin(text))


def get_initials(text: str) -> str | None:
    """获取拼音首字母"""
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        print("请先安装 pypinyin: pip install pypinyin")
        return None
    result = pinyin(text, style=Style.FIRST_LETTER)
    return "".join([item[0] for item in result])


def get_tone_pinyin(text: str) -> str | None:
    """获取带声调拼音"""
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        print("请先安装 pypinyin: pip install pypinyin")
        return None
    result = pinyin(text, style=Style.TONE)
    return " ".join([item[0] for item in result])


def main():
    print("=" * 50)
    print("拼音转换示例")
    print("=" * 50)

    # 期货品种示例
    products = [
        "螺纹钢",
        "白砂糖",
        "沪铜",
        "沪金",
        "原油",
        "豆粕",
        "棕榈油",
        "玻璃",
        "纯碱",
        "铁矿石",
    ]

    print("\n[期货品种拼音]")
    print("-" * 40)
    print(f"{'品种':<8} {'拼音':<15} {'首字母':<8} {'带声调'}")
    print("-" * 40)

    for name in products:
        py = get_pinyin(name)
        initials = get_initials(name)
        tone = get_tone_pinyin(name)

        # 如果导入失败，退出
        if py is None or initials is None or tone is None:
            return

        print(f"{name:<8} {py:<15} {initials:<8} {tone}")

    # 多音字示例
    print("\n[多音字处理]")
    multi_chars = ["重庆", "长春", "行情", "调整"]
    for text in multi_chars:
        py = get_pinyin(text)
        print(f"  {text}: {py}")

    # 搜索匹配示例
    print("\n[首字母搜索]")
    search_key = "lwg"
    print(f"  搜索: {search_key}")
    for name in products:
        if get_initials(name).lower().startswith(search_key):
            print(f"  匹配: {name}")

    print("\n拼音示例完成！")


if __name__ == "__main__":
    main()
