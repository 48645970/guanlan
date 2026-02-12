# -*- coding: utf-8 -*-
"""
行情订阅示例

演示 VNPY CTP 接口的基础用法：
- 事件引擎和主引擎
- CTP 网关连接
- 行情订阅和回调
- 登录状态管理
- 多环境配置选择

使用前需要：
1. pip install vnpy vnpy_ctp
2. 配置 ../config/ctp_connect_multi.json

Author: 海山观澜
"""

import json
from datetime import datetime
from pathlib import Path
from time import sleep

from vnpy.event import Event, EventEngine
from vnpy_ctp import CtpGateway
from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_TICK, EVENT_LOG, EVENT_CONTRACT
from vnpy.trader.object import TickData, SubscribeRequest, LogData, ContractData


def get_future_contracts() -> list[tuple[str, str]]:
    """
    动态生成当前有效的期货合约代码

    返回: [(合约代码, 交易所), ...]
    例如：当前 2512，返回 [("rb2503", "SHFE"), ("au2506", "SHFE")]
    """
    now = datetime.now()

    contracts = []

    # 螺纹钢 rb - 每月都有合约，取3个月后的
    rb_month = now.month + 3
    rb_year = now.year
    if rb_month > 12:
        rb_month -= 12
        rb_year += 1
    contracts.append((f"rb{rb_year % 100:02d}{rb_month:02d}", "SHFE"))

    # 黄金 au - 双月合约(2,4,6,8,10,12)，取最近的双月
    au_month = now.month + 3
    au_year = now.year
    if au_month > 12:
        au_month -= 12
        au_year += 1
    # 调整到最近的双月
    if au_month % 2 == 1:
        au_month += 1
        if au_month > 12:
            au_month = 2
            au_year += 1
    contracts.append((f"au{au_year % 100:02d}{au_month:02d}", "SHFE"))

    return contracts


def load_ctp_config(env: str = None) -> dict:
    """
    加载 CTP 连接配置

    Args:
        env: 环境名称，如 "simnow", "7x24" 等
             如果为 None，则提示用户选择

    Returns:
        CTP 连接配置字典
    """
    config_file = Path("../config/ctp_connect_multi.json")

    if not config_file.exists():
        print(f"\n配置文件不存在: {config_file}")
        print("请先复制 ctp_connect_multi.json.example 并修改为 ctp_connect_multi.json")
        print("\nSimNow 测试账户申请: https://www.simnow.com.cn/")
        return {}

    # 读取配置文件
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    env_list = config.get("环境列表", {})
    if not env_list:
        print("配置文件中没有环境列表")
        return {}

    # 如果未指定环境，显示列表让用户选择
    if env is None:
        print("\n可用环境:")
        env_keys = list(env_list.keys())
        for i, key in enumerate(env_keys, 1):
            env_info = env_list[key]
            env_name = env_info.get("名称", key)
            print(f"  {i}. {key:10s} - {env_name}")

        # 获取默认环境
        default_env = config.get("默认环境", env_keys[0] if env_keys else "")
        default_idx = env_keys.index(default_env) + 1 if default_env in env_keys else 1

        # 用户选择
        try:
            choice = input(f"\n请选择环境 [1-{len(env_keys)}] (默认: {default_idx}): ").strip()
            if not choice:
                idx = default_idx - 1
            else:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(env_keys):
                    print(f"无效选择，使用默认环境: {env_keys[default_idx - 1]}")
                    idx = default_idx - 1
        except (ValueError, KeyError):
            print(f"无效输入，使用默认环境: {env_keys[default_idx - 1]}")
            idx = default_idx - 1

        env = env_keys[idx]

    # 获取指定环境的配置
    if env not in env_list:
        available = ", ".join(env_list.keys())
        print(f"环境 '{env}' 不存在。可用环境: {available}")
        return {}

    env_config = env_list[env]
    env_name = env_config.get("名称", env)
    print(f"\n已选择环境: {env_name} ({env})")

    return env_config


# 全局状态
contract_received = False


def on_tick(event: Event):
    """行情回调"""
    tick: TickData = event.data
    print(f"[TICK] {tick.vt_symbol} "
          f"最新: {tick.last_price:.2f} "
          f"买一: {tick.bid_price_1:.2f} "
          f"卖一: {tick.ask_price_1:.2f} "
          f"成交量: {tick.volume}")


def on_log(event: Event):
    """日志回调"""
    log: LogData = event.data
    print(f"[LOG] {log.time.strftime('%H:%M:%S')} {log.msg}")


def on_contract(event: Event):
    """合约回调"""
    global contract_received
    contract: ContractData = event.data
    # 只打印第一个合约，表示已收到合约信息
    if not contract_received:
        print(f"[CONTRACT] 已收到合约信息，如: {contract.vt_symbol}")
        contract_received = True


def main():
    print("=" * 50)
    print("CTP 行情订阅示例")
    print("=" * 50)

    # 加载配置（用户选择环境）
    setting = load_ctp_config()
    if not setting or not setting.get("用户名"):
        return

    print(f"用户: {setting.get('用户名')}")
    print(f"行情服务器: {setting.get('行情服务器')}")
    print(f"交易服务器: {setting.get('交易服务器')}")

    # 1. 创建事件引擎和主引擎
    print("\n[1] 创建引擎...")
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    # 2. 注册事件回调
    print("[2] 注册事件回调...")
    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_LOG, on_log)
    event_engine.register(EVENT_CONTRACT, on_contract)

    # 3. 连接 CTP 服务器
    print("[3] 连接 CTP 服务器...")
    main_engine.connect(setting, "CTP")

    # 4. 等待合约信息
    print("[4] 等待合约信息（最多30秒）...")
    for i in range(30):
        if contract_received:
            break
        sleep(1)

    if not contract_received:
        print("\n未收到合约信息，请检查：")
        print("  1. 网络连接")
        print("  2. CTP 服务器地址")
        print("  3. 用户名密码")
        main_engine.close()
        return

    # 5. 订阅行情（动态生成合约代码）
    print("\n[5] 订阅行情...")
    contracts = get_future_contracts()
    for symbol, exchange in contracts:
        vt_symbol = f"{symbol}.{exchange}"
        contract = main_engine.get_contract(vt_symbol)
        if contract:
            req = SubscribeRequest(
                symbol=contract.symbol,
                exchange=contract.exchange
            )
            main_engine.subscribe(req, "CTP")
            print(f"  已订阅: {vt_symbol}")
        else:
            print(f"  未找到合约: {vt_symbol}")

    # 6. 保持运行
    print("\n" + "=" * 50)
    print("行情接收中... 按 Ctrl+C 退出")
    print("=" * 50 + "\n")

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭...")

    main_engine.close()
    print("已退出")


if __name__ == "__main__":
    main()
