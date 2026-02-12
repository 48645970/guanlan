# -*- coding: utf-8 -*-
"""
钉钉机器人通知示例

演示 DingtalkChatbot 库的各种消息类型：
- 文本消息
- 图片消息
- Link 链接消息
- Markdown 消息
- FeedCard 消息
- ActionCard 消息

使用前需要：
1. 创建钉钉群并添加自定义机器人
2. 获取 webhook 和 secret
3. pip install DingtalkChatbot

参考: https://github.com/zhuifengshen/DingtalkChatbot

Author: 海山观澜
"""

import json
import os
from pathlib import Path


def load_config() -> dict:
    """加载钉钉配置"""
    config_file = Path("../config/dingtalk.json")

    if not config_file.exists():
        # 创建示例配置
        config_file.parent.mkdir(parents=True, exist_ok=True)
        example_config = {
            "webhook": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
            "secret": "YOUR_SECRET"
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        print(f"已创建示例配置文件: {config_file}")
        print("请填入正确的 webhook 和 secret 后重新运行")
        return {}

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def send_demo_messages(webhook: str, secret: str):
    """发送各种类型的演示消息"""
    try:
        from dingtalkchatbot.chatbot import DingtalkChatbot, ActionCard, CardItem
    except ImportError:
        print("请先安装 DingtalkChatbot: pip install DingtalkChatbot")
        return

    # 创建机器人实例
    ding = DingtalkChatbot(webhook, secret=secret)

    # 1. 文本消息
    print("发送文本消息...")
    ding.send_text("观澜量化交易平台测试消息")

    # 2. Markdown 消息
    print("发送 Markdown 消息...")
    ding.send_markdown(
        title="策略信号",
        text="""### 双均线策略信号

> 合约: rb2501.SHFE
> 信号: **金叉做多**
> 价格: 4520.50

---
###### 观澜量化交易平台
"""
    )

    # 3. Link 消息
    print("发送 Link 消息...")
    ding.send_link(
        title="观澜量化交易平台",
        text="基于 VeighNa 4.x 的量化交易解决方案",
        message_url="https://www.baidu.com",
        pic_url=""
    )

    # 4. ActionCard 消息（单按钮）
    print("发送 ActionCard 消息...")
    btns = [CardItem(title="查看详情", url="https://www.baidu.com")]
    actioncard = ActionCard(
        title="策略报警",
        text="### 风险提示\n\n持仓超过限额，请注意风险控制！",
        btns=btns,
        btn_orientation=1,
        hide_avatar=0
    )
    ding.send_action_card(actioncard)

    print("所有消息发送完成！")


def main():
    print("=" * 50)
    print("钉钉机器人通知示例")
    print("=" * 50)

    # 加载配置
    config = load_config()
    if not config:
        return

    webhook = config.get("webhook", "")
    secret = config.get("secret", "")

    if "YOUR_TOKEN" in webhook or "YOUR_SECRET" in secret:
        print("\n请先配置正确的 webhook 和 secret")
        print("配置文件: ./config/dingtalk.json")
        return

    # 发送演示消息
    send_demo_messages(webhook, secret)


if __name__ == "__main__":
    main()
