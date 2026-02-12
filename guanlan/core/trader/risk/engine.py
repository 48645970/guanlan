# -*- coding: utf-8 -*-
"""
观澜量化 - 风控引擎

继承 VNPY vnpy_riskmanager RiskEngine，适配观澜架构：
- 配置文件使用观澜 load_json_file / save_json_file
- 风控规则使用观澜自有版本（支持多账户独立计数）
- 拦截通知使用观澜音频服务（替代 Windows winsound）

Author: 海山观澜
"""

from pathlib import Path
from typing import Any

from vnpy.event import Event
from vnpy.trader.event import EVENT_LOG
from vnpy.trader.object import LogData
from vnpy.trader.logger import ERROR

from vnpy.trader.engine import BaseEngine as VnpyBaseEngine
from vnpy_riskmanager.engine import RiskEngine as _RiskEngine
from vnpy_riskmanager.base import APP_NAME, EVENT_RISK_RULE, EVENT_RISK_NOTIFY

from guanlan.core.trader.engine import BaseEngine
from guanlan.core.setting.risk import SETTING_FILENAME
from guanlan.core.utils.common import load_json_file, save_json_file


class RiskEngine(BaseEngine, _RiskEngine):
    """观澜风控引擎

    菱形继承：BaseEngine（观澜）+ _RiskEngine（VNPY）共享 VnpyBaseEngine。
    重载配置路径、规则加载、日志通知。
    通过 main_engine.add_engine(RiskEngine) 注册，自动 patch send_order。
    """

    def __init__(self, main_engine, event_engine) -> None:
        # 跳过两个父类的 __init__，直接调用共同祖先完成引擎注册
        VnpyBaseEngine.__init__(self, main_engine, event_engine, APP_NAME)

        # 规则类收集字典
        self.rule_classes: dict[str, tuple[type, str]] = {}

        # 风控规则实例
        self.rules: dict[str, Any] = {}

        # 从观澜配置路径加载设置
        self.setting: dict = load_json_file(SETTING_FILENAME)

        # 字段名称映射（供 UI 显示）
        self.field_name_map: dict = {}

        # 回调规则缓存
        self.tick_rules: list = []
        self.order_rules: list = []
        self.trade_rules: list = []
        self.timer_rules: list = []

        self.load_rules()
        self.register_events()
        self.patch_functions()

    def load_rules(self) -> None:
        """加载风控规则（从观澜自有 rules 目录）"""
        rules_path: Path = Path(__file__).parent / "rules"
        self.load_rules_from_folder(rules_path, "guanlan.core.trader.risk.rules")

        # 实例化规则
        for class_name, (rule_class, module_name) in self.rule_classes.items():
            self.add_rule(rule_class)
            self.main_engine.write_log(
                f"风控规则[{rule_class.name}]加载成功",
                source="RiskEngine"
            )

    def write_log(self, msg: str) -> None:
        """风控拦截日志（替换 winsound 为观澜音频服务）"""
        log: LogData = LogData(
            msg="委托被拦截，" + msg,
            level=ERROR,
            gateway_name=APP_NAME,
        )
        self.event_engine.put(Event(EVENT_LOG, log))

        # 推送风险通知事件
        self.event_engine.put(Event(EVENT_RISK_NOTIFY, msg))

        # 播放报警音效
        try:
            from guanlan.core.services.sound import play as play_sound
            play_sound("alarm")
        except Exception:
            pass

    def update_rule_setting(self, rule_name: str, rule_setting: dict) -> None:
        """更新规则参数（保存到观澜配置路径）"""
        self.setting[rule_name] = rule_setting

        rule = self.rules[rule_name]
        rule.update_setting(rule_setting)
        rule.put_event()

        save_json_file(SETTING_FILENAME, self.setting)
