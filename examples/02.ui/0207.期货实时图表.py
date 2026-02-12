# -*- coding: utf-8 -*-
"""
观澜量化 - 期货实时 K 线图（含双均线交易系统演示）

演示功能：
- VNPY CTP 实时行情接收和 K 线合成
- lightweight-charts-python 实时图表更新
- MA5/MA20 双均线交易系统演示（使用 MyTT 计算指标）
- 金叉（做多）/ 死叉（做空）信号自动标记
- 买卖点盈亏连线显示
- ArcticDB 实时行情记录（数据存储: data/arctic/0207)
- 历史数据加载和信号回扫
- 多环境配置选择（SimNow/实盘）

交易逻辑（参考 myquant 双均线策略）：
- 金叉做多：短期均线从下方穿越长期均线
  条件：prev_short <= prev_long AND curr_short > curr_long
- 死叉做空：短期均线从上方穿越长期均线
  条件：prev_short >= prev_long AND curr_short < curr_long

依赖安装：pip install vnpy-ctp arcticdb lightweight-charts MyTT

Author: 海山观澜
"""

import sys
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Signal, QTimer

from qfluentwidgets import (
    PushButton, LineEdit, ComboBox, BodyLabel, setTheme, Theme,
    InfoBar, InfoBarPosition, FluentIcon
)

from guanlan.ui.widgets import GuanlanWindow

# 尝试导入 lightweight_charts
try:
    from lightweight_charts.widgets import QtChart
    HAS_LIGHTWEIGHT_CHARTS = True
except ImportError:
    HAS_LIGHTWEIGHT_CHARTS = False
    QtChart = None

# 尝试导入 MyTT
try:
    from MyTT import MA, CROSS
    HAS_MYTT = True
except ImportError:
    HAS_MYTT = False
    MA = None
    CROSS = None

# VNPY 导入
from vnpy.event import Event, EventEngine
from vnpy_ctp import CtpGateway
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_TICK, EVENT_LOG, EVENT_CONTRACT
from vnpy.trader.object import TickData, SubscribeRequest, LogData

# ArcticDB 导入
try:
    import arcticdb as adb
    ARCTICDB_AVAILABLE = True
except ImportError:
    ARCTICDB_AVAILABLE = False
    print("警告: ArcticDB 未安装，行情记录功能不可用")
    print("安装命令: pip install arcticdb")

# ArcticDB 存储路径（统一存储在 data/arctic 目录）
ARCTICDB_PATH = Path(__file__).parent.parent / "data" / "arctic"


class ArcticDBManager:
    """ArcticDB 数据管理器"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.arctic = None
        self.library = None
        self._init_db()

    def _init_db(self):
        """初始化数据库连接"""
        if not ARCTICDB_AVAILABLE:
            return

        try:
            uri = f"lmdb://{self.db_path}"
            self.arctic = adb.Arctic(uri)
            self.library = self.arctic.get_library('0207', create_if_missing=True)
            print(f"ArcticDB 已连接: {uri}")
        except Exception as e:
            print(f"ArcticDB 初始化失败: {e}")
            self.arctic = None
            self.library = None

    def append_data(self, symbol: str, df: pd.DataFrame) -> bool:
        """追加 K 线数据到 ArcticDB"""
        if not self.library:
            return False

        try:
            df_to_append = df.copy()
            if 'time' in df_to_append.columns:
                df_to_append['time'] = pd.to_datetime(df_to_append['time'])
                df_to_append = df_to_append.set_index('time')

            if not self.library.has_symbol(symbol):
                self.library.write(symbol, df_to_append)
            else:
                self.library.append(symbol, df_to_append, prune_previous_versions=True)
            return True
        except Exception as e:
            print(f"追加数据失败: {e}")
            return False

    def load_data(self, symbol: str, last_n: int = 200) -> pd.DataFrame | None:
        """从 ArcticDB 加载最近 N 条 K 线数据"""
        if not self.library:
            return None

        try:
            if not self.library.has_symbol(symbol):
                return None

            result = self.library.read(symbol)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')

            # 只返回最后 N 条
            if len(df) > last_n:
                df = df.tail(last_n).reset_index(drop=True)

            return df
        except Exception as e:
            print(f"加载数据失败: {e}")
            return None

    def get_symbol_count(self, symbol: str) -> int:
        """获取 symbol 的数据条数"""
        if not self.library:
            return 0
        try:
            if not self.library.has_symbol(symbol):
                return 0
            desc = self.library.get_description(symbol)
            return desc.row_count
        except Exception:
            return 0


def load_ctp_config(env: str = None) -> tuple[dict, list[str]]:
    """加载 CTP 连接配置"""
    config_file = Path(__file__).parent.parent / "config" / "ctp_connect_multi.json"

    if not config_file.exists():
        return {}, []

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    env_list = config.get("环境列表", {})
    env_keys = list(env_list.keys())

    if not env_list:
        return {}, []

    if env is None:
        env = config.get("默认环境", env_keys[0] if env_keys else "")

    if env not in env_list:
        env = env_keys[0] if env_keys else ""

    if env and env in env_list:
        return env_list[env], env_keys

    return {}, env_keys


def calculate_ma(prices: list, period: int) -> list:
    """计算移动平均线（使用 MyTT）

    使用 MyTT.MA 计算简单移动平均线，与通达信/同花顺一致。
    前 period-1 个值为 NaN，转换为 None 返回。

    Args:
        prices: 价格序列
        period: 均线周期

    Returns:
        均线值列表，前 period-1 个为 None
    """
    prices_array = np.array(prices, dtype=np.float64)
    ma_values = MA(prices_array, period)
    # 将 NaN 转换为 None
    return [None if np.isnan(v) else v for v in ma_values]


class KlineBar:
    """K 线数据"""

    def __init__(self, dt: datetime, price: float):
        self.datetime = dt
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = 0

    def update(self, price: float, volume: int = 0):
        """更新 K 线"""
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume

    def to_dict(self) -> dict:
        """转换为字典（lightweight-charts 格式）"""
        return {
            'time': self.datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'open': round(self.open, 2),
            'high': round(self.high, 2),
            'low': round(self.low, 2),
            'close': round(self.close, 2),
            'volume': self.volume
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'KlineBar':
        """从字典创建 KlineBar"""
        dt = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S')
        bar = cls(dt, data['open'])
        bar.high = data['high']
        bar.low = data['low']
        bar.close = data['close']
        bar.volume = data.get('volume', 0)
        return bar


class KlineGenerator:
    """K 线生成器（10秒周期）"""

    def __init__(self, on_bar_callback):
        self.on_bar_callback = on_bar_callback
        self.current_bar: KlineBar | None = None
        self.last_period: datetime | None = None

    def on_tick(self, tick: TickData):
        """处理 tick 数据"""
        # 获取当前10秒周期
        current_second = tick.datetime.second // 10 * 10
        current_period = tick.datetime.replace(second=current_second, microsecond=0)

        if self.last_period is None or current_period > self.last_period:
            # 新周期：创建新 K 线
            if self.current_bar:
                self.on_bar_callback(self.current_bar, is_new=False)

            self.current_bar = KlineBar(current_period, tick.last_price)
            self.last_period = current_period
            self.on_bar_callback(self.current_bar, is_new=True)
        else:
            # 同一周期：更新当前 K 线
            if self.current_bar:
                self.current_bar.update(tick.last_price, tick.volume)
                self.on_bar_callback(self.current_bar, is_new=False)


class FuturesChartWindow(GuanlanWindow):
    """期货实时 K 线图窗口"""

    tick_signal = Signal(object)
    log_signal = Signal(object)

    def __init__(self):
        super().__init__(enable_translucent_background=False)
        self.setWindowTitle("期货实时图表 - 观澜量化")
        self.resize(1200, 800)

        # ArcticDB 管理器
        self.db_manager = ArcticDBManager(ARCTICDB_PATH)

        # VNPY 引擎
        self.event_engine: EventEngine | None = None
        self.main_engine: MainEngine | None = None
        self.contract_received = False

        # K 线数据
        self.kline_generator: KlineGenerator | None = None
        self.bars: list[KlineBar] = []
        self.current_symbol = ""
        self.chart_initialized = False  # 图表是否已初始化

        # 指标初始化状态
        self.ma5_initialized = False
        self.ma20_initialized = False

        # 交易信号
        self.position = 0  # 0: 空仓, 1: 多头
        # 用于金叉/死叉检测：需要保存前两根K线的MA值
        self.prev_ma5 = None   # 前一根K线的MA5
        self.prev_ma20 = None  # 前一根K线的MA20
        self.last_ma5 = None   # 当前K线的MA5（会随tick更新）
        self.last_ma20 = None  # 当前K线的MA20（会随tick更新）

        # 信号连接线
        self.entry_time = None    # 金叉入场时间
        self.entry_price = None   # 金叉入场价格
        self.signal_lines = []    # 保存信号连接线

        # 价格线
        self.price_line = None

        # 环境列表
        self.env_list: list[str] = []

        # 指标线（延迟创建）
        self.ma5_line = None
        self.ma20_line = None

        # DB 批量保存
        self.pending_save_buffer = pd.DataFrame()
        self.last_saved_bar_time = None  # 最后保存的K线时间（避免重复保存）
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self._batch_save_to_db)

        # 连接信号
        self.tick_signal.connect(self._handle_tick)
        self.log_signal.connect(self._on_log_event)

        self._init_ui()
        self._load_environments()

    def _init_ui(self):
        """初始化界面"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        toolbar.setFixedHeight(48)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)
        toolbar_layout.setSpacing(12)

        # 环境选择
        label_env = BodyLabel("环境:")
        label_env.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(label_env)

        self.env_combo = ComboBox()
        self.env_combo.setFixedWidth(120)
        toolbar_layout.addWidget(self.env_combo)

        # 连接按钮
        self.connect_btn = PushButton("连接")
        self.connect_btn.setIcon(FluentIcon.LINK)
        self.connect_btn.clicked.connect(self._on_connect)
        toolbar_layout.addWidget(self.connect_btn)

        # 断开按钮
        self.disconnect_btn = PushButton("断开")
        self.disconnect_btn.setIcon(FluentIcon.CLOSE)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        toolbar_layout.addWidget(self.disconnect_btn)

        # 分隔
        sep = BodyLabel("|")
        sep.setStyleSheet("color: #30363d;")
        toolbar_layout.addWidget(sep)

        # 合约输入
        label = BodyLabel("合约:")
        label.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(label)

        self.symbol_input = LineEdit()
        self.symbol_input.setPlaceholderText("例如: OI605")
        self.symbol_input.setText("OI605")
        self.symbol_input.setFixedWidth(100)
        toolbar_layout.addWidget(self.symbol_input)

        # 交易所选择
        label2 = BodyLabel("交易所:")
        label2.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(label2)

        self.exchange_combo = ComboBox()
        self.exchange_combo.addItems(["CZCE", "SHFE", "DCE", "INE", "CFFEX"])
        self.exchange_combo.setFixedWidth(100)
        toolbar_layout.addWidget(self.exchange_combo)

        # 订阅按钮
        self.subscribe_btn = PushButton("订阅行情")
        self.subscribe_btn.setIcon(FluentIcon.PLAY)
        self.subscribe_btn.setEnabled(False)
        self.subscribe_btn.clicked.connect(self._on_subscribe)
        toolbar_layout.addWidget(self.subscribe_btn)

        # 状态标签
        self.status_label = BodyLabel("")
        self.status_label.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(self.status_label)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

        # 创建图表容器
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        # 创建主图表（K线 + 均线）
        self.chart = QtChart(chart_container)
        self.chart.legend(visible=False)  # 隐藏图例

        # 创建 MA 均线（name 用于图例，列名需匹配）
        self.ma5_line = self.chart.create_line(
            name='MA5',
            color='#FFFFFF',  # 白色
            width=1,
            price_line=False,  # 不显示右侧价格线
            price_label=False
        )
        self.ma20_line = self.chart.create_line(
            name='MA20',
            color='#FFD700',  # 黄色
            width=1,
            price_line=False,  # 不显示右侧价格线
            price_label=False
        )

        chart_layout.addWidget(self.chart.get_webview(), 1)

        layout.addWidget(chart_container, 1)

        self.setCentralWidget(container)

    def _load_environments(self):
        """加载可用环境列表"""
        _, env_list = load_ctp_config()
        self.env_list = env_list

        if env_list:
            self.env_combo.addItems(env_list)
            self.env_combo.setCurrentIndex(0)
        else:
            self.env_combo.addItem("未找到配置")
            self.connect_btn.setEnabled(False)
            self.status_label.setText("配置文件缺失")

    def _on_connect(self):
        """连接 CTP"""
        selected_env = self.env_combo.currentText()

        if not selected_env or selected_env == "未找到配置":
            InfoBar.warning(
                title="配置缺失",
                content="请先配置 config/ctp_connect_multi.json",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        setting, _ = load_ctp_config(selected_env)

        if not setting or not setting.get("用户名"):
            InfoBar.error(
                title="错误",
                content=f"环境 {selected_env} 配置不完整",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        # 创建引擎
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)
        self.main_engine.add_gateway(CtpGateway)

        # 注册事件
        self.event_engine.register(EVENT_TICK, self._on_tick)
        self.event_engine.register(EVENT_LOG, self._on_log)
        self.event_engine.register(EVENT_CONTRACT, self._on_contract)

        # 连接
        self.main_engine.connect(setting, "CTP")

        self.connect_btn.setEnabled(False)
        self.env_combo.setEnabled(False)
        env_name = setting.get("名称", selected_env)
        self.status_label.setText(f"正在连接 {env_name}...")

    def _on_tick(self, event: Event):
        """tick 事件回调（VNPY 线程）"""
        tick: TickData = event.data

        if self.current_symbol and tick.vt_symbol != self.current_symbol:
            return

        self.tick_signal.emit(tick)

    def _handle_tick(self, tick: TickData):
        """处理 tick 数据（主线程）"""
        if self.kline_generator:
            self.kline_generator.on_tick(tick)

    def _on_log(self, event: Event):
        """日志事件（VNPY 线程）"""
        self.log_signal.emit(event)

    def _on_log_event(self, event: Event):
        """处理日志事件（主线程）"""
        log: LogData = event.data

        if "合约信息查询成功" in log.msg or "连接成功" in log.msg:
            if not self.contract_received:
                self.contract_received = True
                self.subscribe_btn.setEnabled(True)
                self.disconnect_btn.setEnabled(True)

                selected_env = self.env_combo.currentText()
                self.status_label.setText(f"已连接 ({selected_env})")

                InfoBar.success(
                    title="成功",
                    content="已连接 CTP 服务器",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000
                )

    def _on_contract(self, event: Event):
        """合约信息回调"""
        pass

    def _on_subscribe(self):
        """订阅行情"""
        if not self.main_engine:
            return

        symbol = self.symbol_input.text().strip()
        exchange = self.exchange_combo.currentText()

        if not symbol:
            InfoBar.warning(
                title="提示",
                content="请输入合约代码",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        vt_symbol = f"{symbol}.{exchange}"
        contract = self.main_engine.get_contract(vt_symbol)

        if not contract:
            InfoBar.error(
                title="错误",
                content=f"未找到合约: {vt_symbol}",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        # 订阅行情
        req = SubscribeRequest(
            symbol=contract.symbol,
            exchange=contract.exchange
        )
        self.main_engine.subscribe(req, "CTP")

        self.current_symbol = vt_symbol

        # 重置数据
        self.bars = []
        self.chart_initialized = False
        self.pending_save_buffer = pd.DataFrame()
        self.last_saved_bar_time = None

        # 重置指标初始化状态
        self.ma5_initialized = False
        self.ma20_initialized = False

        # 重置交易状态
        self.position = 0
        self.prev_ma5 = None
        self.prev_ma20 = None
        self.last_ma5 = None
        self.last_ma20 = None
        self.entry_time = None
        self.entry_price = None
        self.signal_lines = []
        self.price_line = None

        # 尝试加载历史数据
        history_loaded = self._load_history_data(vt_symbol)

        # 创建 K 线生成器
        self.kline_generator = KlineGenerator(self._on_bar_update)

        # 启动批量保存定时器（每分钟保存一次）
        if ARCTICDB_AVAILABLE:
            self.save_timer.start(60000)

        if history_loaded:
            self.status_label.setText(f"已订阅 {vt_symbol} (已加载历史)")
        else:
            self.status_label.setText(f"已订阅 {vt_symbol}")

        InfoBar.success(
            title="成功",
            content=f"已订阅 {vt_symbol} 实时行情",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def _load_history_data(self, symbol: str) -> bool:
        """加载历史数据"""
        if not ARCTICDB_AVAILABLE:
            return False

        df = self.db_manager.load_data(symbol, last_n=200)
        if df is None or len(df) == 0:
            return False

        # 转换为 KlineBar 列表
        for _, row in df.iterrows():
            bar = KlineBar.from_dict(row.to_dict())
            self.bars.append(bar)

        # 初始化图表
        self.chart.set(df)
        self.chart_initialized = True

        # 初始化均线
        self._init_ma_lines_from_history()

        # 记录最后一条历史数据的时间（避免重复保存）
        if self.bars:
            self.last_saved_bar_time = self.bars[-1].datetime.strftime('%Y-%m-%d %H:%M:%S')

        print(f"已加载 {len(self.bars)} 条历史数据")
        return True

    def _init_ma_lines_from_history(self):
        """从历史数据初始化均线并标记历史买卖点"""
        if len(self.bars) < 5:
            return

        times = [b.datetime.strftime('%Y-%m-%d %H:%M:%S') for b in self.bars]
        close_prices = [b.close for b in self.bars]

        ma5_values = calculate_ma(close_prices, 5)
        ma20_values = calculate_ma(close_prices, 20)

        # 初始化 MA5
        ma5_data = [{'time': times[i], 'MA5': round(ma5_values[i], 2)}
                    for i in range(len(times)) if ma5_values[i] is not None]
        if ma5_data:
            self.ma5_line.set(pd.DataFrame(ma5_data))
            self.ma5_initialized = True

        # 初始化 MA20
        if len(self.bars) >= 20:
            ma20_data = [{'time': times[i], 'MA20': round(ma20_values[i], 2)}
                         for i in range(len(times)) if ma20_values[i] is not None]
            if ma20_data:
                self.ma20_line.set(pd.DataFrame(ma20_data))
                self.ma20_initialized = True

            # 扫描历史数据中的金叉/死叉信号
            self._scan_history_signals(times, close_prices, ma5_values, ma20_values)

            # 初始化均线状态用于后续实时信号检测
            if len(self.bars) >= 21:
                self.prev_ma5 = ma5_values[-2]
                self.prev_ma20 = ma20_values[-2]
            self.last_ma5 = ma5_values[-1]
            self.last_ma20 = ma20_values[-1]

    def _scan_history_signals(self, times: list, prices: list, ma5: list, ma20: list):
        """扫描历史数据中的金叉/死叉信号"""
        if len(times) < 21:
            return

        # 从第21根K线开始检测（需要MA20有效）
        for i in range(20, len(times)):
            prev_ma5 = ma5[i - 1]
            prev_ma20 = ma20[i - 1]
            curr_ma5 = ma5[i]
            curr_ma20 = ma20[i]

            if prev_ma5 is None or prev_ma20 is None:
                continue
            if curr_ma5 is None or curr_ma20 is None:
                continue

            self._check_and_mark_signal(
                prev_ma5, prev_ma20, curr_ma5, curr_ma20,
                times[i], prices[i]
            )

    def _check_and_mark_signal(self, prev_ma5: float, prev_ma20: float,
                                curr_ma5: float, curr_ma20: float,
                                signal_time: str, signal_price: float):
        """检测并标记交易信号（共通方法）

        交易逻辑参考 myquant 双均线策略：
        https://www.myquant.cn/docs/python_strategyies/153

        金叉做多条件（短期均线从下方穿越长期均线）：
            prev_short <= prev_long AND curr_short > curr_long

        死叉做空条件（短期均线从上方穿越长期均线）：
            prev_short >= prev_long AND curr_short < curr_long

        Args:
            prev_ma5: 前一根K线的MA5（短期均线）
            prev_ma20: 前一根K线的MA20（长期均线）
            curr_ma5: 当前K线的MA5
            curr_ma20: 当前K线的MA20
            signal_time: 信号时间
            signal_price: 信号价格
        """
        # 金叉检测: 短期均线(MA5)从下方穿过长期均线(MA20) -> 做多
        # 条件: prev_ma5 <= prev_ma20 AND curr_ma5 > curr_ma20
        if prev_ma5 <= prev_ma20 and curr_ma5 > curr_ma20:
            # 如果之前是做空，先平仓
            if self.position == -1:
                profit = self.entry_price - signal_price  # 做空盈利 = 开仓价 - 平仓价
                self._draw_profit_line(signal_time, signal_price, profit)

            # 开多仓
            self.position = 1
            self.entry_time = signal_time
            self.entry_price = signal_price
            self._draw_marker(signal_time, 'below', 'arrow_up', '#EF5350', '做多 (金叉)')

        # 死叉检测: 短期均线(MA5)从上方穿过长期均线(MA20) -> 做空
        # 条件: prev_ma5 >= prev_ma20 AND curr_ma5 < curr_ma20
        elif prev_ma5 >= prev_ma20 and curr_ma5 < curr_ma20:
            # 如果之前是做多，先平仓
            if self.position == 1:
                profit = signal_price - self.entry_price  # 做多盈利 = 平仓价 - 开仓价
                self._draw_profit_line(signal_time, signal_price, profit)

            # 开空仓
            self.position = -1
            self.entry_time = signal_time
            self.entry_price = signal_price
            self._draw_marker(signal_time, 'above', 'arrow_down', '#26A69A', '做空 (死叉)')

    def _draw_profit_line(self, exit_time: str, exit_price: float, profit: float):
        """绘制盈亏连接线"""
        if not self.entry_time or not self.entry_price:
            return

        line_color = '#EF5350' if profit > 0 else '#26A69A'  # 盈利红色，亏损绿色
        try:
            line = self.chart.create_line(
                name='',
                color=line_color,
                style='dashed',
                width=1,
                price_line=False,
                price_label=False
            )
            line_data = pd.DataFrame([
                {'time': self.entry_time, 'value': self.entry_price},
                {'time': exit_time, 'value': exit_price}
            ])
            line.set(line_data)
            self.signal_lines.append(line)
        except Exception as e:
            print(f"连接线失败: {e}")

    def _draw_marker(self, time: str, position: str, shape: str, color: str, text: str):
        """绘制信号标记"""
        try:
            self.chart.marker(
                time=time,
                position=position,
                shape=shape,
                color=color,
                text=text
            )
        except Exception as e:
            print(f"标记失败: {e}")

    def _on_bar_update(self, bar: KlineBar, is_new: bool):
        """K 线更新回调"""
        if is_new:
            # 新K线开始，意味着上一根K线已完成
            if self.bars:
                completed_bar = self.bars[-1]  # 上一根K线的最终状态
                bar_time = completed_bar.datetime.strftime('%Y-%m-%d %H:%M:%S')
                # 只保存新的K线（避免重复保存历史数据）
                if self.last_saved_bar_time is None or bar_time > self.last_saved_bar_time:
                    bar_df = pd.DataFrame([completed_bar.to_dict()])
                    if len(self.pending_save_buffer) > 0:
                        self.pending_save_buffer = pd.concat([self.pending_save_buffer, bar_df], ignore_index=True)
                    else:
                        self.pending_save_buffer = bar_df
                    self.last_saved_bar_time = bar_time
            self.bars.append(bar)  # 添加新K线
        elif self.bars:
            self.bars[-1] = bar  # 更新当前K线

        # 每次 tick 都更新图表
        self._update_chart(is_new)

    def _batch_save_to_db(self):
        """批量保存缓冲区数据到 DB"""
        if len(self.pending_save_buffer) == 0:
            return

        if not self.current_symbol:
            return

        if self.db_manager.append_data(self.current_symbol, self.pending_save_buffer):
            saved_count = len(self.pending_save_buffer)
            total_count = self.db_manager.get_symbol_count(self.current_symbol)
            print(f"批量保存: {saved_count} 条, 总计: {total_count} 条")

        self.pending_save_buffer = pd.DataFrame()

    def _update_chart(self, is_new_bar: bool = False):
        """更新图表"""
        if not self.bars:
            return

        bar = self.bars[-1]
        time_str = bar.datetime.strftime('%Y-%m-%d %H:%M:%S')
        times = [b.datetime.strftime('%Y-%m-%d %H:%M:%S') for b in self.bars]

        # 提取收盘价列表
        close_prices = [b.close for b in self.bars]

        # 计算均线
        ma5_values = calculate_ma(close_prices, 5)
        ma20_values = calculate_ma(close_prices, 20)

        # === K 线图 ===
        if not self.chart_initialized:
            data = [b.to_dict() for b in self.bars]
            df = pd.DataFrame(data)
            self.chart.set(df)
            self.chart_initialized = True
        else:
            bar_series = pd.Series({
                'time': time_str,
                'open': round(bar.open, 2),
                'high': round(bar.high, 2),
                'low': round(bar.low, 2),
                'close': round(bar.close, 2),
                'volume': bar.volume
            })
            try:
                self.chart.update(bar_series)
            except Exception:
                pass

        # === MA5 均线 (name='MA5' -> 列名用 'MA5') ===
        if len(self.bars) >= 5 and ma5_values[-1] is not None:
            if not self.ma5_initialized:
                # 首次初始化：用 set() 设置全部历史数据
                ma5_data = [{'time': times[i], 'MA5': round(ma5_values[i], 2)}
                            for i in range(len(times)) if ma5_values[i] is not None]
                if ma5_data:
                    self.ma5_line.set(pd.DataFrame(ma5_data))
                    self.ma5_initialized = True
            else:
                # 增量更新
                try:
                    ma5_series = pd.Series({'time': time_str, 'MA5': round(ma5_values[-1], 2)})
                    self.ma5_line.update(ma5_series)
                except Exception:
                    pass

        # === MA20 均线 (name='MA20' -> 列名用 'MA20') ===
        if len(self.bars) >= 20 and ma20_values[-1] is not None:
            if not self.ma20_initialized:
                ma20_data = [{'time': times[i], 'MA20': round(ma20_values[i], 2)}
                             for i in range(len(times)) if ma20_values[i] is not None]
                if ma20_data:
                    self.ma20_line.set(pd.DataFrame(ma20_data))
                    self.ma20_initialized = True
            else:
                try:
                    ma20_series = pd.Series({'time': time_str, 'MA20': round(ma20_values[-1], 2)})
                    self.ma20_line.update(ma20_series)
                except Exception:
                    pass

        # 双均线交易信号检测（使用共通方法）
        if len(self.bars) >= 20:
            current_ma5 = ma5_values[-1]
            current_ma20 = ma20_values[-1]

            if current_ma5 is not None and current_ma20 is not None:
                if is_new_bar:
                    # 新K线开始：检测上一根K线是否发生交叉
                    if (self.prev_ma5 is not None and self.prev_ma20 is not None and
                        self.last_ma5 is not None and self.last_ma20 is not None and
                        len(self.bars) >= 2):
                        prev_bar = self.bars[-2]
                        prev_time = prev_bar.datetime.strftime('%Y-%m-%d %H:%M:%S')
                        prev_price = prev_bar.close
                        # 调用共通方法检测并标记信号
                        self._check_and_mark_signal(
                            self.prev_ma5, self.prev_ma20,
                            self.last_ma5, self.last_ma20,
                            prev_time, prev_price
                        )

                    # 新K线开始时：将 last 移到 prev，为下一次检测做准备
                    self.prev_ma5 = self.last_ma5
                    self.prev_ma20 = self.last_ma20

                # 每次 tick 都更新 last_ma5/last_ma20
                self.last_ma5 = current_ma5
                self.last_ma20 = current_ma20

        # 更新当前价格线（青色）
        try:
            current_price = bar.close
            if self.price_line is None:
                self.price_line = self.chart.horizontal_line(
                    price=current_price,
                    color='#00BCD4',
                    width=1,
                    style='dotted',
                    axis_label_visible=True
                )
            else:
                self.price_line.update(current_price)
        except Exception:
            pass

    def _on_disconnect(self):
        """断开连接"""
        if not self.main_engine:
            return

        # 停止保存定时器
        self.save_timer.stop()

        # 保存当前未完成的K线（如果有且是新的）
        if self.bars:
            current_bar = self.bars[-1]
            bar_time = current_bar.datetime.strftime('%Y-%m-%d %H:%M:%S')
            if self.last_saved_bar_time is None or bar_time > self.last_saved_bar_time:
                bar_df = pd.DataFrame([current_bar.to_dict()])
                if len(self.pending_save_buffer) > 0:
                    self.pending_save_buffer = pd.concat([self.pending_save_buffer, bar_df], ignore_index=True)
                else:
                    self.pending_save_buffer = bar_df

        # 保存剩余数据
        self._batch_save_to_db()

        # 注销事件
        if self.event_engine:
            self.event_engine.unregister(EVENT_TICK, self._on_tick)
            self.event_engine.unregister(EVENT_LOG, self._on_log)
            self.event_engine.unregister(EVENT_CONTRACT, self._on_contract)

        # 关闭引擎
        self.main_engine.close()

        if self.event_engine:
            self.event_engine.stop()

        # 重置状态
        self.main_engine = None
        self.event_engine = None
        self.contract_received = False
        self.current_symbol = ""
        self.kline_generator = None

        # 重置按钮
        self.connect_btn.setEnabled(True)
        self.env_combo.setEnabled(True)
        self.subscribe_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.status_label.setText("已断开")

        # 清空数据
        self.bars = []

        InfoBar.info(
            title="提示",
            content="已断开 CTP 连接",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.main_engine or self.event_engine:
            self._on_disconnect()
        event.accept()


def main():
    # 检查依赖
    if not HAS_LIGHTWEIGHT_CHARTS or not ARCTICDB_AVAILABLE or not HAS_MYTT:
        print("\n" + "=" * 60)
        print("依赖库缺失，无法运行此示例")
        print("=" * 60)

        missing_deps = []
        if not HAS_LIGHTWEIGHT_CHARTS:
            missing_deps.append("lightweight-charts")
        if not ARCTICDB_AVAILABLE:
            missing_deps.append("arcticdb")
        if not HAS_MYTT:
            missing_deps.append("MyTT")

        print(f"\n请运行以下命令安装依赖：")
        print(f"  pip install {' '.join(missing_deps)}")
        print(f"\n注意：还需要安装 vnpy-ctp")
        print(f"  pip install vnpy-ctp")
        print()
        return

    app = QApplication(sys.argv)
    setTheme(Theme.DARK)

    window = FuturesChartWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
