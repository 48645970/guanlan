# -*- coding: utf-8 -*-
"""
观澜量化 - CTP 交易网关

继承 vnpy_ctp 原版 Gateway，仅覆写以下差异：
- 流文件路径：改为 .guanlan/ctp/<gateway_name>/ 目录，适配 Linux
- close()：规避 CTP exit() segfault，支持运行中断开单个账户
- write_log()：日志来源标注 [CTP] 前缀
- connect()：增加连接参数日志

Author: 海山观澜
"""

from pathlib import Path

from vnpy.event import Event, EventEngine
from vnpy.trader.object import LogData
from vnpy.trader.event import EVENT_TIMER

from vnpy_ctp.gateway.ctp_gateway import (
    CtpGateway as VnpyCtpGateway,
    CtpMdApi as VnpyCtpMdApi,
    CtpTdApi as VnpyCtpTdApi,
)

from guanlan.core.constants import CTP_FLOW_DIR
from guanlan.core.events import signal_bus

# 合约查询完毕事件（CTP 推送 ~4000 合约后 last=True 触发，仅一次）
EVENT_CONTRACT_INITED = "eContractInited"

# 连接超时时间（秒），EVENT_TIMER 每秒触发一次
CONNECT_TIMEOUT: int = 60

# 连续断开次数阈值：从未登录成功的情况下连续断开达到此次数，判定连接失败
MAX_DISCONNECT_BEFORE_LOGIN: int = 3


def _get_flow_path(gateway_name: str) -> Path:
    """获取 CTP 流文件目录，不存在则自动创建"""
    path = CTP_FLOW_DIR / gateway_name.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


class CtpMdApi(VnpyCtpMdApi):
    """观澜行情 API：覆写 connect() 适配 Linux 路径和编码"""

    def onFrontDisconnected(self, reason: int) -> None:
        """服务器断开回调：已关闭时静默"""
        if not self.connect_status:
            return
        super().onFrontDisconnected(reason)

    def connect(
        self,
        address: str,
        userid: str,
        password: str,
        brokerid: str,
        production_mode: bool
    ) -> None:
        """连接服务器（Linux 路径 + UTF-8 编码 + 日志）"""
        self.userid = userid
        self.password = password
        self.brokerid = brokerid

        # 禁止重复发起连接，会导致异常崩溃
        if not self.connect_status:
            path = _get_flow_path(self.gateway_name)
            flow_path = str(path / "Md")
            self.gateway.write_log(f"行情流文件路径：{flow_path}")

            self.createFtdcMdApi(flow_path.encode("utf-8"), production_mode)

            self.registerFront(address)
            self.init()

            self.connect_status = True
            self.gateway.write_log("行情API已初始化，等待连接回调...")


class CtpTdApi(VnpyCtpTdApi):
    """观澜交易 API：覆写 connect() 适配 Linux 路径和编码"""

    def onRspQryInstrument(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """合约查询回报：最后一条时通知网关"""
        super().onRspQryInstrument(data, error, reqid, last)
        if last:
            self.gateway.on_contract_inited()

    def onFrontDisconnected(self, reason: int) -> None:
        """服务器断开回调：已关闭时静默，未登录时通知网关计数"""
        if not self.connect_status:
            return
        super().onFrontDisconnected(reason)
        # 从未登录成功就断开，通知网关判断是否放弃
        if not self.login_status:
            self.gateway.on_td_disconnect_before_login()

    def connect(
        self,
        address: str,
        userid: str,
        password: str,
        brokerid: str,
        auth_code: str,
        appid: str,
        production_mode: bool
    ) -> None:
        """连接服务器（Linux 路径 + UTF-8 编码 + 日志）"""
        self.userid = userid
        self.password = password
        self.brokerid = brokerid
        self.auth_code = auth_code
        self.appid = appid

        if not self.connect_status:
            path = _get_flow_path(self.gateway_name)
            flow_path = str(path / "Td")
            self.gateway.write_log(f"交易流文件路径：{flow_path}")

            self.createFtdcTraderApi(flow_path.encode("utf-8"), production_mode)

            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)

            self.registerFront(address)
            self.init()

            self.connect_status = True
            self.gateway.write_log("交易API已初始化，等待连接回调...")
        else:
            self.authenticate()


class CtpGateway(VnpyCtpGateway):
    """观澜量化 CTP 交易网关

    继承 vnpy_ctp 原版，覆写 close / write_log / connect，
    其余 30+ 个回调和交易方法全部复用原版。
    """

    # CTP C++ API 的 exit() 存在 segfault 缺陷（RegisterSpi(NULL)
    # 在 Release() 之前调用），close 后保持引用防止 GC 触发析构函数
    _abandoned: list = []
    _MAX_ABANDONED: int = 5

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """构造函数：替换为观澜子类化的 MdApi / TdApi"""
        super().__init__(event_engine, gateway_name)

        self.td_api: CtpTdApi = CtpTdApi(self)
        self.md_api: CtpMdApi = CtpMdApi(self)

        # 连接超时计数
        self._timeout_count: int = 0
        self._timeout_checking: bool = False

        # 登录前连续断开计数（用于快速判定连接失败）
        self._pre_login_disconnect_count: int = 0

    def connect(self, setting: dict) -> None:
        """连接交易接口

        非行情账户只连交易服务器，跳过行情连接，减少不必要的连接开销。
        """
        userid: str = setting["用户名"]
        password: str = setting["密码"]
        brokerid: str = setting["经纪商代码"]
        td_address: str = setting["交易服务器"]
        md_address: str = setting["行情服务器"]
        appid: str = setting["产品名称"]
        auth_code: str = setting["授权编码"]
        production_mode: bool = setting["柜台环境"] == "实盘"
        is_market: bool = setting.get("行情服务", "") == "1"

        self.write_log(
            f"开始连接，用户={userid}，经纪商={brokerid}，"
            f"柜台={'实盘' if production_mode else '测试'}，"
            f"行情={'是' if is_market else '否'}"
        )

        # 地址协议补全
        if not td_address.startswith(("tcp://", "ssl://", "socks")):
            td_address = "tcp://" + td_address
        if not md_address.startswith(("tcp://", "ssl://", "socks")):
            md_address = "tcp://" + md_address

        # 启动超时检测
        self._timeout_count = 0
        self._pre_login_disconnect_count = 0
        self._timeout_checking = True
        self.event_engine.register(EVENT_TIMER, self._on_connect_timer)

        # 交易API始终连接
        self.td_api.connect(td_address, userid, password, brokerid, auth_code, appid, production_mode)

        # 行情API仅行情账户连接
        if is_market:
            self.md_api.connect(md_address, userid, password, brokerid, production_mode)
        else:
            self.write_log("非行情账户，跳过行情连接")

        self.init_query()

    def _on_connect_timer(self, event: Event) -> None:
        """连接超时检测（EVENT_TIMER 每秒触发）"""
        if not self._timeout_checking:
            return

        # 登录成功 → 连接成功，停止检测（合约查询较慢但不影响交易）
        if self.td_api.login_status:
            self._stop_timeout_check()
            return

        # 登录已明确失败，停止检测（AppEngine 会通过其他途径处理）
        if self.td_api.login_failed or self.td_api.auth_failed:
            self._stop_timeout_check()
            return

        self._timeout_count += 1
        if self._timeout_count >= CONNECT_TIMEOUT:
            self._stop_timeout_check()
            self.write_log(f"连接超时（{CONNECT_TIMEOUT}秒），正在关闭")
            self.close()
            signal_bus.account_connect_timeout.emit(self.gateway_name)

    def _stop_timeout_check(self) -> None:
        """停止超时检测"""
        self._timeout_checking = False
        self.event_engine.unregister(EVENT_TIMER, self._on_connect_timer)

    def on_td_disconnect_before_login(self) -> None:
        """交易API在登录成功之前断开（由 CtpTdApi 回调）

        连续断开达到阈值时判定为连接失败，立即停止。
        典型场景：非交易时段、服务器地址错误、网络不通。
        """
        self._pre_login_disconnect_count += 1
        if self._pre_login_disconnect_count >= MAX_DISCONNECT_BEFORE_LOGIN:
            self.write_log(
                f"连接失败（连续{self._pre_login_disconnect_count}次断开，"
                f"服务器无法访问），停止重试"
            )
            self.close()
            signal_bus.account_connect_timeout.emit(self.gateway_name)

    def on_contract_inited(self) -> None:
        """合约查询完毕（由 CtpTdApi.onRspQryInstrument last=True 触发）"""
        event = Event(EVENT_CONTRACT_INITED, self.gateway_name)
        self.event_engine.put(event)

    def close(self) -> None:
        """关闭接口

        不使用原版的 exit()（内部先 RegisterSpi(NULL) 再 Release()，
        存在竞态条件导致 segfault），改用 release() 直接停止 C++ 内部线程。

        release() 只调用 Release()，不清空 SPI 指针，因此：
        - 停止期间若有回调到达，仍走我们的 Python SPI（connect_status=False 静默）
        - 无 NULL SPI 竞态风险

        release() 后 C++ 资源已释放，但 Python 包装对象的析构函数
        可能再次调用 exit() 导致 double-free，因此仍需保持引用防止 GC。
        """
        if self._timeout_checking:
            self._stop_timeout_check()
        self.event_engine.unregister(EVENT_TIMER, self.process_timer_event)

        # 先标记断开（确保 release 期间回调静默），再停止 C++ 线程
        td_was_connected = self.td_api.connect_status
        md_was_connected = self.md_api.connect_status

        self.td_api.connect_status = False
        self.md_api.connect_status = False

        if td_was_connected:
            self.td_api.release()
        if md_was_connected:
            self.md_api.release()

        # 保持引用防止 GC 触发 C++ 析构函数
        CtpGateway._abandoned.append(self)
        while len(CtpGateway._abandoned) > CtpGateway._MAX_ABANDONED:
            CtpGateway._abandoned.pop(0)

    def write_log(self, msg: str) -> None:
        """输出日志（来源标注网关类型）"""
        log: LogData = LogData(msg=msg, gateway_name=f"[CTP]{self.gateway_name}")
        self.on_log(log)
