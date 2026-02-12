# -*- coding: utf-8 -*-
"""
脚本策略运行测试

验证 ScriptTrader 引擎基本功能：日志输出、循环执行、优雅停止。

Author: 海山观澜
"""

from time import sleep


def run(engine) -> None:
    """脚本入口（由 ScriptEngine 调用）"""
    engine.write_script_log("===== 测试脚本启动 =====")

    # 查询当前所有持仓
    positions = engine.get_all_positions()
    engine.write_script_log(f"当前持仓数量: {len(positions)}")

    # 查询当前所有账户
    accounts = engine.get_all_accounts()
    engine.write_script_log(f"当前账户数量: {len(accounts)}")

    # 循环执行（每 3 秒一次，直到引擎停止）
    count = 0
    while engine.strategy_active:
        count += 1
        engine.write_script_log(f"心跳 #{count}")
        sleep(3)

    engine.write_script_log("===== 测试脚本结束 =====")
