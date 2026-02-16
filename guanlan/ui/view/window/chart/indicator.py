# -*- coding: utf-8 -*-
"""
观澜量化 - 图表指标管理器

协调指标实例与 lightweight-charts 图表线的创建、数据绑定和更新。

Author: 海山观澜
"""

import logging

import pandas as pd

from guanlan.core.constants import COLOR_UP, COLOR_DOWN
from guanlan.core.indicators import get_indicator, BaseIndicator

logger = logging.getLogger(__name__)

# 每个副图占总高度的比例
SUBCHART_HEIGHT = 0.15


class IndicatorManager:
    """指标 ↔ 图表协调管理器

    管理指标实例的生命周期，以及对应图表线（主图叠加 / 副图独立）的
    创建、批量初始化、逐 bar 增量更新。

    Parameters
    ----------
    chart : QtChart
        lightweight-charts 主图对象
    bars : list[dict]
        K 线数据列表（外部引用，与 ChartWindow._bars 共享同一对象）
    """

    def __init__(self, chart: object, bars: list[dict]) -> None:
        self._chart = chart
        self._bars = bars

        self._indicators: dict[str, BaseIndicator] = {}
        self._overlay_lines: dict[str, dict[str, object]] = {}   # 主图指标线
        self._subcharts: dict[str, object] = {}                   # 指标名 → 副图
        self._subchart_lines: dict[str, dict[str, object]] = {}   # 副图指标线
        self._timeline_lines: dict[str, object] = {}               # 副图时间轴 Line
        self._initialized: set[str] = set()                       # 已完成 set() 的指标

    # ── 绑定 / 清理 ──────────────────────────────────

    def bind_chart(self, chart: object) -> None:
        """重新绑定 chart 实例（chart 重建后调用）"""
        self._chart = chart

    def clear_state(self) -> None:
        """清空图表线状态（保留指标实例和参数）"""
        self._overlay_lines.clear()
        self._subcharts.clear()
        self._subchart_lines.clear()
        self._timeline_lines.clear()
        self._initialized.clear()

    def clear_all(self) -> None:
        """清空所有指标实例和图表线状态"""
        self._indicators.clear()
        self.clear_state()

    # ── 查询 ─────────────────────────────────────────

    def has(self, name: str) -> bool:
        """指标是否已添加"""
        return name in self._indicators

    def get(self, name: str) -> BaseIndicator | None:
        """获取指标实例"""
        return self._indicators.get(name)

    def subchart_count(self) -> int:
        """当前副图指标数量"""
        return sum(1 for ind in self._indicators.values() if not ind.overlay)

    def has_subchart_indicators(self) -> bool:
        """是否存在副图指标"""
        return self.subchart_count() > 0

    def calc_inner_height(self) -> float:
        """根据副图数量计算主图高度比例"""
        n = self.subchart_count()
        if n == 0:
            return 1.0
        return max(0.5, 1.0 - n * SUBCHART_HEIGHT)

    def get_analysis_state(self) -> dict:
        """收集所有指标的当前状态用于 AI 分析

        Returns
        -------
        dict
            指标状态字典，格式：
            {
                "指标名": {
                    "values": {"线名": 数值, ...},
                    "signal": {"type": "long/short", "text": "信号描述"} | None
                },
                ...
            }
        """
        state = {}
        if not self._bars:
            return state

        last_bar = self._bars[-1]

        for name, ind in self._indicators.items():
            # 只收集已初始化的指标
            if name not in self._initialized:
                continue

            # 获取最新数值
            values = ind.on_bar(last_bar)

            # 获取信号（如果有）
            signal = ind.on_bar_signal(last_bar)

            state[name] = {
                "values": values,
                "signal": signal
            }

        return state

    # ── 添加 / 移除 ──────────────────────────────────

    def add(self, name: str, saved_params: dict | None = None) -> None:
        """添加指标：创建实例 → 图表线 → 尝试初始化数据"""
        ind_cls = get_indicator(name)
        ind = ind_cls()
        if saved_params:
            ind.update_setting(saved_params)

        self._indicators[name] = ind
        self._create_lines(name, ind)
        self._try_init(name, ind)

    def remove(self, name: str) -> None:
        """移除指标实例及其图表线"""
        ind = self._indicators.get(name)
        if not ind:
            return

        # 1. 删除主图线（overlay）
        if ind.overlay:
            lines = self._overlay_lines.get(name, {})
            for line in lines.values():
                if line:
                    # 清理 Legend 条目 + 移除 Series
                    self._chart.run_script(f"""
                        var _li = {self._chart.id}.legend._lines.find(
                            function(l) {{ return l.series === {line.id}.series; }}
                        );
                        if (_li) {{
                            {self._chart.id}.legend._lines =
                                {self._chart.id}.legend._lines.filter(
                                    function(l) {{ return l !== _li; }}
                                );
                            _li.row.remove();
                        }}
                        {self._chart.id}.chart.removeSeries({line.id}.series);
                    """)

        # 2. 删除副图及其所有线
        else:
            subchart = self._subcharts.get(name)
            if subchart:
                # 删除副图中的所有指标线
                lines = self._subchart_lines.get(name, {})
                for line in lines.values():
                    if line:
                        subchart.run_script(f"{subchart.id}.chart.removeSeries({line.id}.series);")

                # 删除时间轴线
                timeline = self._timeline_lines.get(name)
                if timeline:
                    subchart.run_script(f"{subchart.id}.chart.removeSeries({timeline.id}.series);")

                # 删除整个副图容器（DOM 元素）
                subchart.run_script(f"{subchart.id}.wrapper.remove();")

        # 3. 清理 Python 引用
        self._indicators.pop(name, None)
        self._overlay_lines.pop(name, None)
        self._subcharts.pop(name, None)
        self._subchart_lines.pop(name, None)
        self._timeline_lines.pop(name, None)
        self._initialized.discard(name)

    # ── 数据更新 ─────────────────────────────────────

    def on_bar(self, bar_dict: dict) -> None:
        """新 K 线完成时更新所有指标"""
        for name, ind in self._indicators.items():
            # 尚未初始化：立即初始化副图，保证时间轴同步
            # lookback 只用于指标内部判断数据是否足够计算
            if name not in self._initialized:
                # 取 display_offset 根用于显示，避免指标线只从当前位置开始
                n = min(ind.display_offset, len(self._bars)) if ind.display_offset > 0 else len(self._bars)
                init_bars = self._bars[-n:]
                data = ind.on_init(init_bars)
                if not ind.overlay:
                    # 注意：调用方 (window.py _on_bar) 已包裹 bulk_run
                    self._create_subchart_lines(name, ind)
                    self._set_line_data(name, ind, data, init_bars)
                    subchart = self._subcharts.get(name)
                    if subchart:
                        for ref in ind.reference_lines():
                            try:
                                subchart.horizontal_line(
                                    price=ref["price"],
                                    color=ref.get("color", "#888888"),
                                    width=1,
                                    style=ref.get("style", "dashed"),
                                )
                            except Exception:
                                logger.exception(
                                    "[%s] on_bar 初始化阶段：添加参考线失败, "
                                    "price=%s", name, ref.get("price"),
                                )
                else:
                    self._set_line_data(name, ind, data, init_bars)
                # 信号统一渲染到主图
                for s in ind.get_signals(init_bars):
                    self._render_signal(name, s["time"], s)
                self._initialized.add(name)
                continue

            result = ind.on_bar(bar_dict)
            lines = self._get_lines(name, ind)
            ld_map = {ld["name"]: ld for ld in ind.lines()}

            # 注意：调用方 (window.py _on_bar) 已包裹 bulk_run，
            # 所有 JS 操作会打包为单次执行，浏览器 rAF 不会在中间触发渲染。
            # 顺序关键：时间轴线必须先于指标线更新。

            # 1. 先更新副图时间轴 Line（新时间点的数据基底）
            if not ind.overlay:
                tl = self._timeline_lines.get(name)
                if tl and tl._last_bar is not None:
                    try:
                        rec = {"time": bar_dict["time"], " ": bar_dict["close"]}
                        tl.update(pd.Series(rec))
                    except Exception:
                        logger.exception(
                            "[%s] on_bar：时间轴 Line update 失败, "
                            "time=%s", name, bar_dict.get("time"),
                        )

            # 2. 再更新指标线（扩展同一时间轴，时间轴线已有数据）
            # 即使 value 为 None 也必须发送 whitespace 占位，
            # 否则渲染器在该时间点找不到数据会触发 "Value is null"
            for line_name, value in result.items():
                line = lines.get(line_name)
                if not line:
                    continue
                try:
                    rec = {"time": bar_dict["time"]}
                    if value is not None:
                        rec[line_name] = value
                        ld = ld_map.get(line_name, {})
                        if ld.get("color_up") and ld.get("color_down"):
                            rec["color"] = ld["color_up"] if value >= 0 else ld["color_down"]

                    if line._last_bar is None:
                        line.set(pd.DataFrame([rec]))
                    else:
                        line.update(pd.Series(rec))
                except Exception:
                    logger.exception(
                        "[%s] on_bar：指标线 '%s' 更新失败, "
                        "time=%s, value=%s, _last_bar=%s",
                        name, line_name, bar_dict.get("time"),
                        value, line._last_bar is not None,
                    )

            # 实时信号标记
            signal = ind.on_bar_signal(bar_dict)
            if signal:
                self._render_signal(name, bar_dict["time"], signal)

    def on_tick_update(self, bar_dict: dict) -> None:
        """Tick 更新在建 bar 时同步副图所有 series

        确保副图的时间轴 Line 和所有指标线始终覆盖主图最新的时间点。
        如果只更新时间轴 Line 而不更新指标线，渲染器在新时间点上
        找不到指标线的数据会触发 "Value is null"，导致整个副图不显示。
        """
        for name, ind in self._indicators.items():
            if ind.overlay or name not in self._initialized:
                continue

            tl = self._timeline_lines.get(name)
            if not tl or tl._last_bar is None:
                continue

            try:
                tl.update(pd.Series({"time": bar_dict["time"], " ": bar_dict["close"]}))
            except Exception:
                logger.exception(
                    "[%s] on_tick_update：时间轴 Line update 失败, "
                    "time=%s", name, bar_dict.get("time"),
                )
                continue

            # 关键：同步指标线到新时间点（whitespace 占位）
            # 仅在时间轴推进到新时间时才补 whitespace，
            # 避免覆盖 on_bar 已设置的实际指标值
            tl_time = tl._last_bar["time"]
            lines = self._subchart_lines.get(name, {})
            for line_name, line in lines.items():
                if line._last_bar is None:
                    continue
                if line._last_bar["time"] == tl_time:
                    continue  # 已有数据（同一时间），不覆盖
                try:
                    line.update(pd.Series({"time": bar_dict["time"]}))
                except Exception:
                    logger.exception(
                        "[%s] on_tick_update：指标线 '%s' whitespace 失败, "
                        "time=%s", name, line_name, bar_dict.get("time"),
                    )

    # ── 批量加载 ─────────────────────────────────────

    def load_instances(self, saved_indicators: dict[str, dict]) -> None:
        """仅创建指标实例，不创建图表线

        用于在创建 chart 之前计算正确的 inner_height。
        图表线的创建和数据初始化由 init_all() 完成。
        """
        for name, params in saved_indicators.items():
            try:
                ind_cls = get_indicator(name)
            except KeyError:
                continue

            ind = ind_cls()
            if params:
                ind.update_setting(params)
            self._indicators[name] = ind

    def init_all(self) -> None:
        """为所有已加载的指标创建图表线和初始化数据

        必须在 chart 创建且 K 线数据加载之后调用。
        """
        for name, ind in self._indicators.items():
            self._create_lines(name, ind)
            self._try_init(name, ind)

    def load_saved(self, saved_indicators: dict[str, dict]) -> None:
        """从保存的配置恢复所有指标（创建实例 + 图表线 + 初始化）"""
        for name, params in saved_indicators.items():
            try:
                ind_cls = get_indicator(name)
            except KeyError:
                continue

            ind = ind_cls()
            if params:
                ind.update_setting(params)

            self._indicators[name] = ind
            self._create_lines(name, ind)
            self._try_init(name, ind)

    def rebuild(self, chart: object) -> None:
        """chart 重建后重建所有指标线和数据

        保留当前指标实例和参数，在新的 chart 上重新创建线对象并初始化数据。
        """
        # 保存旧配置
        saved = {
            name: ind.get_params().model_dump()
            for name, ind in self._indicators.items()
        }
        old_names = list(self._indicators.keys())

        # 重置状态
        self._indicators.clear()
        self.clear_state()
        self._chart = chart

        # 重建
        for name in old_names:
            self.add(name, saved.get(name, {}))

    # ── 持久化辅助 ───────────────────────────────────

    def get_settings(self) -> dict[str, dict]:
        """获取所有指标参数（用于序列化保存）"""
        return {
            name: ind.get_params().model_dump()
            for name, ind in self._indicators.items()
        }

    # ── 内部方法 ─────────────────────────────────────

    def _create_series(self, chart: object, ld: dict) -> object:
        """根据线定义创建对应的 series 对象

        支持的 type:
            - "line"（默认）: 折线，支持 color/width/style
            - "histogram": 柱状图，支持 color

        style 可选值: solid / dotted / dashed / large_dashed / sparse_dotted
        """
        series_type = ld.get("type", "line")
        if series_type == "histogram":
            return chart.create_histogram(
                name=ld["name"],
                color=ld.get("color", "#FFFFFF"),
                price_line=False,
                price_label=False,
            )
        return chart.create_line(
            name=ld["name"],
            color=ld.get("color", "#FFFFFF"),
            style=ld.get("style", "solid"),
            width=ld.get("width", 1),
            price_line=False,
            price_label=False,
        )

    def _create_lines(self, name: str, ind: BaseIndicator) -> None:
        """为指标创建图表线对象

        注意：副图指标的线对象在 _create_subchart_lines() 中延迟创建，
        必须在 set() 数据前才创建，避免 sync 模式下空线触发 "Value is null"。
        """
        if not ind.overlay:
            return

        lines = {}
        for ld in ind.lines():
            lines[ld["name"]] = self._create_series(self._chart, ld)
        self._overlay_lines[name] = lines

    def _create_subchart_lines(self, name: str, ind: BaseIndicator) -> None:
        """创建独立副图及其线对象

        副图时间轴必须覆盖主图所有时间点，否则 syncCharts 的
        legendHandler 在做 timeToCoordinate 映射时会失败。

        方案：用透明 Line 系列（而非 Candlestick）承载时间轴数据。
        Candlestick 着色器（barStyleFn）对数据一致性要求极高，
        浮点时间戳微小偏差就会导致二分查找失败 → "Value is null"。
        Line 系列天然支持省略值、不触发 null 断言，更加安全。

        重要：不能在 create_subchart 中传 sync=True！
        库内部 syncCharts 使用 run_last=True，但 bulk_run 会忽略 run_last，
        导致 syncCharts 在 setData 之前执行。空副图上的 setVisibleLogicalRange
        会永久损坏时间轴状态，之后每次渲染都报 "Value is null"。
        必须在所有数据填充完成后，手动调用 syncCharts。
        """
        # 不传 sync：避免 syncCharts 在空副图上执行
        subchart = self._chart.create_subchart(
            position="bottom", width=1.0, height=SUBCHART_HEIGHT,
        )
        subchart.legend(
            visible=True, ohlc=False, percent=False, lines=True,
        )

        # 创建透明 Line 系列覆盖时间轴
        # Line 系列对时间戳容错更好，不会触发 Candlestick 着色器的 null 断言
        timeline_line = subchart.create_line(
            name=" ", color="transparent",
            price_line=False, price_label=False,
            price_scale_id="__timeline__",
        )

        # 彻底移除内建 Candlestick 和 Volume series
        # 仅 applyOptions({visible:false}) 不够：即使不可见，Candlestick 着色器
        # 仍在渲染循环中被调用，触发 "Value is null" 断言。
        # removeSeries 从 chart 内部数据结构中完全清除，渲染循环不再访问它们。
        # 将 handler.series 指向 timeline Line，让 syncCharts 兼容。
        subchart.run_script(f"""
            {subchart.id}.chart.removeSeries({subchart.id}.series);
            {subchart.id}.chart.removeSeries({subchart.id}.volumeSeries);
            {subchart.id}.series = {timeline_line.id}.series;
            {subchart.id}.volumeSeries = null;
            {subchart.id}.chart.priceScale('__timeline__').applyOptions({{
                visible: false
            }});
        """)

        # 设置时间轴 Line 的数据
        if self._bars:
            records = [
                {"time": b["time"], " ": b["close"]}
                for b in self._bars
            ]
            timeline_line.set(pd.DataFrame(records))
            # 修复：防止时间戳重复导致 _interval=0 引发除零错误
            # 库的 _set_interval 在数据异常时可能设置 _interval=0
            if timeline_line._interval == 0:
                logger.warning(
                    "[%s] timeline_line._interval=0（数据异常），强制设为60秒",
                    name,
                )
                timeline_line._interval = 60  # 1分钟K线默认间隔

        self._subcharts[name] = subchart
        self._timeline_lines[name] = timeline_line

        lines = {}
        for ld in ind.lines():
            lines[ld["name"]] = self._create_series(subchart, ld)
        self._subchart_lines[name] = lines

        # 所有数据填充完成后，手动建立主副图同步连接
        # 此时副图已有完整的时间轴数据，syncCharts 的
        # setVisibleLogicalRange 不会在空图上执行
        subchart.run_script(
            f"Lib.Handler.syncCharts({subchart.id}, {self._chart.id}, false)"
        )

    def _try_init(self, name: str, ind: BaseIndicator) -> None:
        """尝试用已有 bars 初始化指标数据

        总是初始化副图以保证时间轴同步，lookback 只用于指标内部判断。
        """
        if not self._bars:
            return

        # 取 display_offset 根用于显示，避免指标线只从当前位置开始
        n = min(ind.display_offset, len(self._bars)) if ind.display_offset > 0 else len(self._bars)
        init_bars = self._bars[-n:]
        data = ind.on_init(init_bars)

        if not ind.overlay:
            # 副图：用 bulk_run 将所有 JS 操作打包，防止异步渲染中间插入
            with self._chart.win.bulk_run:
                self._create_subchart_lines(name, ind)
                self._set_line_data(name, ind, data, init_bars)
                subchart = self._subcharts.get(name)
                if subchart:
                    for ref in ind.reference_lines():
                        try:
                            subchart.horizontal_line(
                                price=ref["price"],
                                color=ref.get("color", "#888888"),
                                width=1,
                                style=ref.get("style", "dashed"),
                            )
                        except Exception:
                            logger.exception(
                                "[%s] _try_init：添加参考线失败, price=%s",
                                name, ref.get("price"),
                            )
        else:
            self._set_line_data(name, ind, data, init_bars)

        self._initialized.add(name)

        # 信号统一渲染到主图
        for s in ind.get_signals(init_bars):
            self._render_signal(name, s["time"], s)

    def _set_line_data(
        self, name: str, ind: BaseIndicator,
        data: dict[str, list], bars: list[dict],
    ) -> None:
        """批量设置指标线数据"""
        lines = self._get_lines(name, ind)
        ld_map = {ld["name"]: ld for ld in ind.lines()}

        for line_name, values in data.items():
            line = lines.get(line_name)
            if not line:
                continue

            ld = ld_map.get(line_name, {})
            color_up = ld.get("color_up")
            color_down = ld.get("color_down")

            records = []
            for i, v in enumerate(values):
                if i >= len(bars):
                    break
                rec = {"time": bars[i]["time"]}
                # 即使值为None也要添加列名，避免DataFrame缺少列导致错误
                rec[line_name] = v
                if v is not None and color_up and color_down:
                    rec["color"] = color_up if v >= 0 else color_down
                records.append(rec)

            # 总是设置数据，即使为空，避免 series 未初始化导致 JS 错误
            line.set(pd.DataFrame(records) if records else pd.DataFrame())

    def _get_lines(self, name: str, ind: BaseIndicator) -> dict[str, object]:
        """获取指标对应的线字典"""
        if ind.overlay:
            return self._overlay_lines.get(name, {})
        return self._subchart_lines.get(name, {})

    # 信号类型 → 渲染样式
    _SIGNAL_STYLE = {
        "long": {"position": "below", "shape": "arrow_up", "color": COLOR_UP},
        "short": {"position": "above", "shape": "arrow_down", "color": COLOR_DOWN},
    }

    def _render_signal(self, name: str, time: str, signal: dict) -> None:
        """根据标准信号格式渲染 marker 到主图

        所有指标的信号统一显示在主图（价格图）上：
        lightweight-charts 的 marker 绑定在 candlestick series 上，
        副图的 candlestick 已隐藏，无法显示 marker。
        从交易角度看，做多/做空信号标记在价格图上也更直观。
        """
        style = self._SIGNAL_STYLE.get(signal["type"])
        if not style:
            return
        try:
            self._chart.marker(
                time=time, text=signal.get("text", ""),
                **style,
            )
        except Exception:
            logger.exception(
                "[%s] _render_signal：渲染信号标记失败, time=%s, signal=%s",
                name, time, signal,
            )
