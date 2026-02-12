# -*- coding: utf-8 -*-
"""
观澜量化 - 全局引擎

应用级单例，持有 EventEngine + MainEngine，支持多 CTP 账户同时连接。
应用启动时创建，退出时销毁。所有需要交易引擎的模块通过此类获取。

Author: 海山观澜
"""

from __future__ import annotations

from vnpy.trader.event import EVENT_CONTRACT
from vnpy.trader.object import ContractData, SubscribeRequest
from guanlan.core.trader.gateway import CtpGateway, EVENT_CONTRACT_INITED

from guanlan.core.trader.event import EventEngine, Event
from guanlan.core.trader.engine import MainEngine
from guanlan.core.setting import account
from guanlan.core.setting.contract import load_contracts
from guanlan.core.events import signal_bus


class AppEngine:
    """观澜全局引擎（单例）

    管理 EventEngine + MainEngine 的生命周期，
    支持多 CTP 账户同时连接（用环境名作为 gateway_name）。

    事件分发由各 UI 组件自行向 EventEngine 注册，
    本类仅处理应用级事件（合约→连接状态跟踪）。
    """

    _instance: AppEngine | None = None

    @classmethod
    def instance(cls) -> AppEngine:
        """获取全局引擎实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        if AppEngine._instance is not None:
            raise RuntimeError("请使用 AppEngine.instance() 获取单例")
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)

        # 已连接的环境: env_name → gateway_name（两者相同）
        self._connections: dict[str, str] = {}

        # 正在连接中的环境（防止重复点击）
        self._connecting: set[str] = set()

        # 品种手续费配置缓存（启动时加载，供手续费计算使用）
        self.contracts: dict = load_contracts()

        # 全局合约代码表（所有网关推送的合约汇总）
        self._vt_symbols: list[str] = []
        self._vt_symbols_set: set[str] = set()

        # 行情订阅管理（合约到齐前排队，到齐后一次性补订）
        self._contract_ready: bool = False
        self._subscribed: set[str] = set()
        self._pending_subscribes: list[str] = []

        # 注册应用级事件
        self.event_engine.register(EVENT_CONTRACT, self._on_contract)
        self.event_engine.register(EVENT_CONTRACT_INITED, self._on_contract_inited)

        # 监听超时信号，清理连接中状态
        signal_bus.account_connect_timeout.connect(self._on_connect_timeout)

    def connect(self, env_name: str) -> None:
        """连接 CTP

        用环境名作为 gateway_name，按需创建网关实例。

        Parameters
        ----------
        env_name : str
            账户环境名称（对应 account.json 中的环境键名）
        """
        if env_name in self._connections:
            self.main_engine.write_log(f"环境已连接：{env_name}", "AppEngine")
            return

        if env_name in self._connecting:
            self.main_engine.write_log(f"环境正在连接中，请勿重复操作：{env_name}", "AppEngine")
            return

        config = account.load_config()
        envs = account.get_accounts(config)
        setting = envs.get(env_name, {})

        if not setting:
            self.main_engine.write_log(f"未找到环境配置：{env_name}", "AppEngine")
            return

        self._connecting.add(env_name)

        # 按需创建网关实例（用环境名作为 gateway_name）
        gateway_name = env_name
        self.main_engine.add_gateway(CtpGateway, gateway_name)

        self.main_engine.connect(setting, gateway_name)

    def disconnect(self, env_name: str) -> None:
        """断开指定环境的 CTP 连接"""
        self._connecting.discard(env_name)

        gateway_name = self._connections.pop(env_name, None)
        if not gateway_name:
            return

        gateway = self.main_engine.get_gateway(gateway_name)
        if gateway:
            gateway.close()

        signal_bus.account_disconnected.emit(env_name)

    def _on_connect_timeout(self, env_name: str) -> None:
        """连接超时处理（由 CTP Gateway 通过 signal_bus 触发）"""
        self._connecting.discard(env_name)

    def is_connected(self, env_name: str = "") -> bool:
        """查询连接状态

        Parameters
        ----------
        env_name : str
            环境名。为空时返回是否有任何连接。
        """
        if env_name:
            return env_name in self._connections
        return len(self._connections) > 0

    def is_connecting(self, env_name: str) -> bool:
        """查询是否正在连接中"""
        return env_name in self._connecting

    @property
    def connected_envs(self) -> list[str]:
        """所有已连接的环境名列表"""
        return list(self._connections.keys())

    @property
    def market_gateway(self) -> str:
        """行情数据源的网关名（环境名）"""
        config = account.load_config()
        envs = account.get_accounts(config)
        for env_name, data in envs.items():
            if account.is_market_source(data):
                return env_name
        return ""

    def auto_connect(self) -> None:
        """自动连接标记了自动登录的账户"""
        config = account.load_config()
        envs = account.get_accounts(config)
        for env_name, data in envs.items():
            if account.is_auto_login(data):
                self.connect(env_name)

    def close(self) -> None:
        """关闭引擎（应用退出时调用）

        MainEngine.close() 会遍历所有通过 add_engine 注册的引擎并调用 close()。
        """
        self._connecting.clear()
        self._connections.clear()

        try:
            self.main_engine.close()
        except Exception:
            pass

    @property
    def vt_symbols(self) -> list[str]:
        """所有已收到的合约代码列表"""
        return self._vt_symbols

    def _on_contract(self, event: Event) -> None:
        """合约事件处理（连接状态跟踪 + 合约累积）"""
        contract: ContractData = event.data
        gateway_name = contract.gateway_name

        # 首次收到该网关的合约 → 连接完成
        if gateway_name not in self._connections:
            self._connecting.discard(gateway_name)
            self._connections[gateway_name] = gateway_name
            signal_bus.account_connected.emit(gateway_name)

        vt_symbol = f"{contract.symbol}.{contract.exchange.value}"

        # 累积合约代码（O(1) 去重）
        if vt_symbol not in self._vt_symbols_set:
            self._vt_symbols_set.add(vt_symbol)
            self._vt_symbols.append(vt_symbol)

    def _on_contract_inited(self, event: Event) -> None:
        """合约查询完毕：标记就绪 + 补订排队中的品种"""
        self._contract_ready = True

        # 补订排队中的品种
        pending = self._pending_subscribes
        self._pending_subscribes = []
        for vt_symbol in pending:
            self.subscribe(vt_symbol)

    def subscribe(self, vt_symbol: str) -> bool:
        """统一行情订阅入口

        - 自动查合约信息、构造请求、使用行情网关
        - 去重（已订阅的直接跳过）
        - 合约未到齐时入队列，到齐后自动补订

        Parameters
        ----------
        vt_symbol : str
            本地合约代码（如 rb2510.SHFE）

        Returns
        -------
        bool
            True=已订阅或已入队，False=失败
        """
        if vt_symbol in self._subscribed:
            return True

        # 合约未到齐，入队列等待
        if not self._contract_ready:
            if vt_symbol not in self._pending_subscribes:
                self._pending_subscribes.append(vt_symbol)
            return True

        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if not contract:
            return False

        market_gw = self.market_gateway
        if not market_gw:
            return False

        req = SubscribeRequest(symbol=contract.symbol, exchange=contract.exchange)
        self.main_engine.subscribe(req, market_gw)
        self._subscribed.add(vt_symbol)
        return True
