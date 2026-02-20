# -*- coding: utf-8 -*-
"""
观澜量化 - 全局信号总线

跨模块通信核心，所有模块间通信都通过此总线。

Author: 海山观澜
"""

from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """
    观澜全局信号总线

    设计原则：
    - 所有跨模块通信都通过此总线
    - 信号发送方不需要知道接收方
    - 支持多对多通信
    - 线程安全（Qt 信号机制）
    """

    # ==================== 导航信号 ====================
    navigate_to = Signal(str)                    # 导航到指定界面
    switch_to_route = Signal(str)                # 切换路由
    switch_to_sample = Signal(str, int)          # 切换到示例卡片
    exit_app = Signal(int)                       # 退出程序

    # ==================== 账户信号 ====================
    account_connect = Signal(str)                # 连接账户（请求）
    account_disconnect = Signal(str)             # 断开账户（请求）
    account_connected = Signal(str)              # 账户已连接（响应）
    account_disconnected = Signal(str)           # 账户已断开（响应）
    account_connect_timeout = Signal(str)        # 连接超时（环境名）
    account_login_failed = Signal(str, str)      # 登录失败 (账户, 原因)

    # ==================== 策略信号 ====================
    strategy_loaded = Signal(str, dict)          # 策略加载 (名称, 信息)
    strategy_started = Signal(str)               # 策略启动
    strategy_stopped = Signal(str)               # 策略停止
    strategy_removed = Signal(str)               # 策略移除
    strategy_params_changed = Signal(str, dict)  # 参数变化
    strategy_state_updated = Signal(str, dict)   # 状态更新
    strategy_start_all = Signal()                # 启动所有策略
    strategy_stop_all = Signal()                 # 停止所有策略

    # ==================== 交易信号 ====================
    order_placed = Signal(dict)                  # 下单
    order_cancelled = Signal(str)                # 撤单
    position_opened = Signal(dict)               # 开仓
    position_closed = Signal(dict)               # 平仓

    # ==================== 数据信号 ====================
    bar_received = Signal(dict)                  # Bar 数据
    contract_loaded = Signal(list)               # 合约列表加载
    main_contract_updated = Signal(str, str)     # 主力合约更新 (品种, 合约)

    # ==================== 合约管理信号 ====================
    contract_auto_refresh = Signal()             # 自动刷新主力合约
    data_auto_download = Signal()                # 自动下载历史数据
    symbol_subscribe = Signal(str)               # 订阅行情
    symbol_unsubscribe = Signal(str)             # 取消订阅

    # ==================== UI 信号 ====================
    theme_changed = Signal(str)                  # 主题切换
    mica_enabled_changed = Signal(bool)          # Mica 效果开关变化
    show_message = Signal(str, str, str)         # 显示消息 (标题, 内容, 级别)
    show_tooltip = Signal(str, str, str)         # 显示提示 (标题, 内容, 级别)
    status_message = Signal(str)                 # 状态栏消息
    play_sound = Signal(str)                     # 播放声音
    support_signal = Signal()                    # 打开支持页面

    # ==================== AI 信号 ====================
    ai_models_changed = Signal()                 # AI 模型列表变更


# 全局单例
signal_bus = SignalBus()
