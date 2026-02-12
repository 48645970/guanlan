# -*- coding: utf-8 -*-
"""
观澜量化 - Lightweight Charts + ArcticDB 高级特性演示

演示功能：
- 流式数据模拟生成和实时图表更新
- ArcticDB 数据存储和加载（数据存储: data/arctic/0208）
- 版本管理：创建版本、加载历史版本、时间旅行
- 快照管理：创建快照、从快照恢复、删除快照
- 高级查询：价格过滤、时间范围查询、Head/Tail
- 存储统计：碎片检查和整理

注意事项：
- 版本由用户手动创建（点击"保存版本"按钮）
- 被快照引用的版本无法删除，需先删除相关快照
- 数据以 LMDB 格式存储，高性能读写

依赖安装：pip install arcticdb lightweight-charts

Author: 海山观澜
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidgetItem, QLabel, QAbstractItemView
)
from PySide6.QtCore import QTimer, Qt, QDateTime
from PySide6.QtGui import QColor, QDoubleValidator, QIntValidator

from qfluentwidgets import (
    PushButton, ComboBox, FluentIcon, setTheme, Theme, InfoBar, InfoBarPosition,
    BodyLabel, LineEdit, PrimaryPushButton, SubtitleLabel, CaptionLabel,
    ListWidget, CheckBox, TextEdit,
    CardWidget, SimpleCardWidget, IconWidget, TransparentPushButton,
    MessageBoxBase, TitleLabel, DateTimeEdit
)

from guanlan.ui.widgets import GuanlanWindow

# 尝试导入 lightweight_charts
try:
    from lightweight_charts.widgets import QtChart
    HAS_LIGHTWEIGHT_CHARTS = True
except ImportError:
    HAS_LIGHTWEIGHT_CHARTS = False
    QtChart = None

# ArcticDB 导入
try:
    import arcticdb as adb
    ARCTICDB_AVAILABLE = True
except ImportError:
    ARCTICDB_AVAILABLE = False


# ArcticDB 存储路径（统一存储在 data/arctic 目录）
ARCTICDB_PATH = Path(__file__).parent.parent / "data" / "arctic"

# 默认演示标的
DEFAULT_SYMBOL = "DEMO_STREAM"


class ArcticDBManager:
    """ArcticDB 数据管理器（增强版）"""

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
            self.library = self.arctic.get_library('0208', create_if_missing=True)
            print(f"ArcticDB 已连接: {uri}")
        except Exception as e:
            print(f"ArcticDB 初始化失败: {e}")
            self.arctic = None
            self.library = None

    # ==================== 基础操作 ====================

    def save_data(self, symbol: str, df: pd.DataFrame, metadata: dict = None,
                  prune_previous: bool = True) -> int | None:
        """保存数据，返回版本号"""
        if not self.library:
            return None

        try:
            df_to_save = df.copy()
            if 'time' in df_to_save.columns:
                df_to_save['time'] = pd.to_datetime(df_to_save['time'])
                df_to_save = df_to_save.set_index('time')

            result = self.library.write(
                symbol,
                df_to_save,
                metadata=metadata or {'saved_at': datetime.now().isoformat()},
                prune_previous_versions=prune_previous
            )
            return result.version
        except Exception as e:
            print(f"保存数据失败: {e}")
            return None

    def append_data(self, symbol: str, df: pd.DataFrame, keep_versions: bool = False) -> bool:
        """追加数据

        Args:
            symbol: 标的名称
            df: 要追加的数据
            keep_versions: 是否保留历史版本（演示用）
        """
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
                # keep_versions=True 时保留历史版本，可在版本管理中查看
                self.library.append(symbol, df_to_append, prune_previous_versions=not keep_versions)
            return True
        except Exception as e:
            print(f"追加数据失败: {e}")
            return False

    def load_data(self, symbol: str, version: int = None) -> pd.DataFrame | None:
        """加载数据，可指定版本"""
        if not self.library:
            return None

        try:
            if not self.library.has_symbol(symbol):
                return None

            result = self.library.read(symbol, as_of=version)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"加载数据失败: {e}")
            return None

    def list_symbols(self) -> list:
        """列出所有 symbol"""
        if not self.library:
            return []
        return self.library.list_symbols()

    def delete_symbol(self, symbol: str) -> bool:
        """删除 symbol"""
        if not self.library:
            return False
        try:
            self.library.delete(symbol)
            return True
        except Exception:
            return False

    def get_symbol_info(self, symbol: str) -> dict | None:
        """获取 symbol 信息"""
        if not self.library:
            return None
        try:
            desc = self.library.get_description(symbol)
            return {
                'rows': desc.row_count,
                'columns': list(desc.columns.keys()),
                'date_range': (str(desc.date_range[0]), str(desc.date_range[1]))
                if desc.date_range else None
            }
        except Exception:
            return None

    # ==================== 版本管理 ====================

    def list_versions(self, symbol: str) -> list:
        """列出 symbol 的所有版本"""
        if not self.library:
            return []
        try:
            # ArcticDB list_versions 返回 dict: {SymbolVersion: VersionInfo}
            versions_dict = self.library.list_versions(symbol)
            result = []
            for sv, info in versions_dict.items():
                result.append({
                    'version': sv.version,
                    'date': str(info.date),
                    'deleted': info.deleted
                })
            return result
        except Exception as e:
            print(f"获取版本列表失败: {e}")
            return []

    def read_version(self, symbol: str, version: int) -> tuple[pd.DataFrame | None, dict | None]:
        """读取特定版本的数据和元数据"""
        if not self.library:
            return None, None

        try:
            result = self.library.read(symbol, as_of=version)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df, result.metadata
        except Exception as e:
            print(f"读取版本失败: {e}")
            return None, None

    def prune_previous_versions(self, symbol: str) -> bool:
        """删除旧版本，只保留最新版本"""
        if not self.library:
            return False
        try:
            self.library.prune_previous_versions(symbol)
            return True
        except Exception:
            return False


    def get_current_version(self, symbol: str) -> int | None:
        """获取当前（最新）版本号"""
        if not self.library:
            return None
        try:
            versions = self.list_versions(symbol)
            if versions:
                # 返回最大版本号（最新）
                return max(v['version'] for v in versions if not v.get('deleted'))
            return None
        except Exception:
            return None

    # ==================== 快照管理 ====================

    def create_snapshot(self, name: str, metadata: dict = None) -> bool:
        """创建快照"""
        if not self.library:
            return False
        try:
            self.library.snapshot(name, metadata=metadata)
            return True
        except Exception as e:
            print(f"创建快照失败: {e}")
            return False

    def list_snapshots(self) -> dict:
        """列出所有快照"""
        if not self.library:
            return {}
        try:
            return self.library.list_snapshots()
        except Exception:
            return {}

    def delete_snapshot(self, name: str) -> bool:
        """删除快照"""
        if not self.library:
            return False
        try:
            self.library.delete_snapshot(name)
            return True
        except Exception:
            return False

    def read_from_snapshot(self, symbol: str, snapshot_name: str) -> pd.DataFrame | None:
        """从快照读取数据"""
        if not self.library:
            return None
        try:
            result = self.library.read(symbol, as_of=snapshot_name)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"从快照读取失败: {e}")
            return None

    # ==================== 高级查询 ====================

    def query_by_price(self, symbol: str, min_price: float = None,
                       max_price: float = None) -> pd.DataFrame | None:
        """按价格范围查询"""
        if not self.library:
            return None

        try:
            q = adb.QueryBuilder()
            if min_price is not None:
                q = q[q['close'] >= min_price]
            if max_price is not None:
                q = q[q['close'] <= max_price]

            result = self.library.read(symbol, query_builder=q)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"价格查询失败: {e}")
            return None

    def query_by_date_range(self, symbol: str, start: datetime,
                            end: datetime) -> pd.DataFrame | None:
        """按时间范围查询"""
        if not self.library:
            return None

        try:
            result = self.library.read(symbol, date_range=(start, end))
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"时间范围查询失败: {e}")
            return None

    def query_columns(self, symbol: str, columns: list) -> pd.DataFrame | None:
        """只读取指定列"""
        if not self.library:
            return None

        try:
            result = self.library.read(symbol, columns=columns)
            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"列查询失败: {e}")
            return None

    def query_head_tail(self, symbol: str, n: int, head: bool = True) -> pd.DataFrame | None:
        """读取前/后 N 行"""
        if not self.library:
            return None

        try:
            if head:
                result = self.library.head(symbol, n=n)
            else:
                result = self.library.tail(symbol, n=n)

            df = result.data.reset_index()
            df = df.rename(columns={'index': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return df
        except Exception as e:
            print(f"head/tail 查询失败: {e}")
            return None

    # ==================== 数据维护 ====================

    def is_fragmented(self, symbol: str) -> bool:
        """检查数据是否碎片化"""
        if not self.library:
            return False
        try:
            return self.library.is_symbol_fragmented(symbol)
        except Exception:
            return False

    def defragment(self, symbol: str) -> bool:
        """整理碎片数据"""
        if not self.library:
            return False
        try:
            self.library.defragment_symbol_data(symbol)
            return True
        except Exception as e:
            print(f"碎片整理失败: {e}")
            return False

    def get_storage_stats(self) -> dict:
        """获取存储统计"""
        if not self.library:
            return {}

        stats = {
            'total_symbols': len(self.list_symbols()),
            'total_snapshots': len(self.list_snapshots()),
            'symbols': {}
        }

        for symbol in self.list_symbols():
            info = self.get_symbol_info(symbol)
            versions = self.list_versions(symbol)
            fragmented = self.is_fragmented(symbol)
            if info:
                stats['symbols'][symbol] = {
                    'rows': info['rows'],
                    'versions': len(versions),
                    'fragmented': fragmented
                }

        return stats


class StreamingDataGenerator:
    """流式数据生成器"""

    def __init__(self, start_price: float = 100.0, start_time: datetime = None):
        self.price = start_price
        self.current_time = start_time or datetime.now()

    def generate_bars(self, count: int = 10) -> pd.DataFrame:
        """生成指定数量的 K 线数据"""
        data = []

        for _ in range(count):
            change = np.random.randn() * 2
            open_price = self.price
            close_price = self.price + change
            high_price = max(open_price, close_price) + abs(np.random.randn())
            low_price = min(open_price, close_price) - abs(np.random.randn())
            volume = np.random.randint(1000, 10000)

            data.append({
                'time': self.current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })

            self.price = close_price
            self.current_time += timedelta(minutes=1)

        return pd.DataFrame(data)


# ==================== 对话框 ====================

class VersionDialog(MessageBoxBase):
    """版本管理对话框

    版本功能说明：
    - ArcticDB 每次 write/append 都会自动创建新版本
    - 版本管理让你可以"时间旅行"，回到任意历史状态
    - 双击版本可以加载该版本的数据到图表
    """

    def __init__(self, db_manager: ArcticDBManager, symbol: str, loaded_version: int = None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.symbol = symbol
        self.loaded_version = loaded_version  # 当前已加载的版本
        self.selected_version = None

        # 设置标题
        self.titleLabel = TitleLabel(f"版本管理 - {symbol}")
        self.viewLayout.addWidget(self.titleLabel)

        # 当前加载版本信息卡片
        current_card = SimpleCardWidget()
        current_layout = QHBoxLayout(current_card)
        current_layout.setContentsMargins(16, 12, 16, 12)
        current_icon = IconWidget(FluentIcon.TAG)
        current_icon.setFixedSize(20, 20)
        current_layout.addWidget(current_icon)
        self.current_version_label = BodyLabel("已加载版本: --")
        current_layout.addWidget(self.current_version_label)
        current_layout.addStretch()
        self.viewLayout.addWidget(current_card)

        # 说明卡片
        help_card = SimpleCardWidget()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 12, 16, 12)
        help_icon = IconWidget(FluentIcon.INFO)
        help_icon.setFixedSize(20, 20)
        help_text = CaptionLabel(
            "双击版本可加载该时刻的数据，实现「时间旅行」。\n"
            "注意：被快照引用的版本无法删除，需先删除相关快照。"
        )
        help_text.setWordWrap(True)
        help_row = QHBoxLayout()
        help_row.addWidget(help_icon)
        help_row.addWidget(help_text, 1)
        help_layout.addLayout(help_row)
        self.viewLayout.addWidget(help_card)

        # 版本列表标题
        self.viewLayout.addWidget(SubtitleLabel("版本历史"))

        # 版本列表
        self.version_list = ListWidget()
        self.version_list.setMinimumHeight(200)
        self.version_list.itemDoubleClicked.connect(self._on_select)
        self.viewLayout.addWidget(self.version_list)

        # 版本信息
        self.info_label = CaptionLabel("")
        self.viewLayout.addWidget(self.info_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        prune_btn = TransparentPushButton("清理旧版本")
        prune_btn.setIcon(FluentIcon.DELETE)
        prune_btn.setToolTip("删除所有旧版本，只保留最新版本\n（被快照引用的版本无法删除）")
        prune_btn.clicked.connect(self._on_prune)
        btn_layout.addWidget(prune_btn)

        btn_layout.addStretch()
        self.viewLayout.addLayout(btn_layout)

        # 设置按钮文字
        self.yesButton.setText("加载此版本")
        self.cancelButton.setText("关闭")

        # 设置宽度
        self.widget.setMinimumWidth(450)

        self._load_versions()

    def _load_versions(self):
        """加载版本列表"""
        self.version_list.clear()
        versions = self.db_manager.list_versions(self.symbol)

        # 获取数据库最新版本
        latest_ver = self.db_manager.get_current_version(self.symbol)

        # 显示已加载版本（如果为 None，表示加载的是最新版本）
        if self.loaded_version is not None:
            self.current_version_label.setText(f"已加载版本: {self.loaded_version}")
        elif latest_ver is not None:
            self.current_version_label.setText(f"已加载版本: {latest_ver} (最新)")
        else:
            self.current_version_label.setText("已加载版本: --")

        if not versions:
            item = QListWidgetItem("暂无版本 - 点击「保存版本」创建")
            item.setForeground(QColor('#8b949e'))
            self.version_list.addItem(item)
            self.info_label.setText("提示：先运行演示生成数据，再点击「保存版本」按钮")
            return

        # 确定当前加载的版本号（None 表示最新）
        loaded_ver = self.loaded_version if self.loaded_version is not None else latest_ver

        # 按版本号降序排列（最新在前）
        versions_sorted = sorted(versions, key=lambda x: x['version'], reverse=True)
        for v in versions_sorted:
            ver_num = v['version']
            is_loaded = (ver_num == loaded_ver)
            is_latest = (ver_num == latest_ver)

            # 标记：★=已加载, ●=最新, 📌=其他
            if is_loaded:
                prefix = "★"
            elif is_latest:
                prefix = "●"
            else:
                prefix = "📌"

            suffix = " (最新)" if is_latest else ""
            item = QListWidgetItem(f"{prefix} 版本 {ver_num}{suffix}  —  {v['date']}")
            item.setData(Qt.UserRole, ver_num)

            if v.get('deleted'):
                item.setForeground(QColor('#666666'))
            elif is_loaded:
                item.setForeground(QColor('#4CAF50'))  # 已加载版本绿色
            elif is_latest:
                item.setForeground(QColor('#2196F3'))  # 最新版本蓝色
            self.version_list.addItem(item)

        self.info_label.setText(f"共 {len(versions)} 个版本 (★=已加载, ●=最新)")

    def _on_select(self):
        """双击选择版本"""
        item = self.version_list.currentItem()
        if item and item.data(Qt.UserRole) is not None:
            self.selected_version = item.data(Qt.UserRole)
            self.accept()

    def _on_prune(self):
        """清理旧版本（只保留当前版本）

        注意：被快照引用的版本无法删除，这是 ArcticDB 的安全机制。
        如需删除这些版本，请先删除相关快照。
        """
        versions_before = self.db_manager.list_versions(self.symbol)
        active_before = [v for v in versions_before if not v.get('deleted')]

        if len(active_before) <= 1:
            self.info_label.setText("只有一个版本，无需清理")
            return

        # 检查是否有快照（可能阻止版本删除）
        snapshots = self.db_manager.list_snapshots()
        has_snapshots = len(snapshots) > 0

        if self.db_manager.prune_previous_versions(self.symbol):
            self._load_versions()

            # 检查清理后的版本数量
            versions_after = self.db_manager.list_versions(self.symbol)
            active_after = [v for v in versions_after if not v.get('deleted')]
            deleted_count = len(active_before) - len(active_after)

            if deleted_count == len(active_before) - 1:
                # 全部清理成功
                self.info_label.setText(f"✓ 已清理 {deleted_count} 个旧版本")
            elif deleted_count > 0:
                # 部分清理（可能有快照引用）
                remaining = len(active_after) - 1
                msg = f"✓ 已清理 {deleted_count} 个版本，{remaining} 个版本被快照引用无法删除"
                self.info_label.setText(msg)
            else:
                # 无法清理（所有旧版本都被快照引用）
                if has_snapshots:
                    self.info_label.setText("⚠ 版本被快照引用，无法删除。请先删除相关快照")
                else:
                    self.info_label.setText("清理完成")
        else:
            self.info_label.setText("清理失败")

    def _validateInput(self):
        """验证输入"""
        item = self.version_list.currentItem()
        if item:
            self.selected_version = item.data(Qt.UserRole)
            return True
        return False


class SnapshotDialog(MessageBoxBase):
    """快照管理对话框

    快照功能说明：
    - 快照是某一时刻所有数据的"照片"
    - 创建快照后，即使数据被修改或删除，也可以从快照恢复
    - 适用于重要数据的备份点
    """

    def __init__(self, db_manager: ArcticDBManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_snapshot = None

        # 设置标题
        self.titleLabel = TitleLabel("快照管理")
        self.viewLayout.addWidget(self.titleLabel)

        # 说明卡片
        help_card = SimpleCardWidget()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 12, 16, 12)
        help_icon = IconWidget(FluentIcon.PHOTO)
        help_icon.setFixedSize(20, 20)
        help_text = CaptionLabel(
            "快照保存当前所有数据的状态，即使数据被修改或删除，也可以从快照恢复。"
        )
        help_text.setWordWrap(True)
        help_row = QHBoxLayout()
        help_row.addWidget(help_icon)
        help_row.addWidget(help_text, 1)
        help_layout.addLayout(help_row)
        self.viewLayout.addWidget(help_card)

        # 创建快照区域
        create_card = CardWidget()
        create_layout = QHBoxLayout(create_card)
        create_layout.setContentsMargins(16, 12, 16, 12)

        self.snapshot_name_input = LineEdit()
        self.snapshot_name_input.setPlaceholderText("输入快照名称...")
        create_layout.addWidget(self.snapshot_name_input, 1)

        create_btn = PrimaryPushButton("创建快照")
        create_btn.setIcon(FluentIcon.ADD)
        create_btn.clicked.connect(self._on_create)
        create_layout.addWidget(create_btn)

        self.viewLayout.addWidget(create_card)

        # 快照列表标题
        self.viewLayout.addWidget(SubtitleLabel("现有快照"))

        # 快照列表
        self.snapshot_list = ListWidget()
        self.snapshot_list.setMinimumHeight(150)
        self.snapshot_list.itemDoubleClicked.connect(self._on_select)
        self.viewLayout.addWidget(self.snapshot_list)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        delete_btn = TransparentPushButton("删除快照")
        delete_btn.setIcon(FluentIcon.DELETE)
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        self.viewLayout.addLayout(btn_layout)

        # 设置按钮文字
        self.yesButton.setText("从此快照恢复")
        self.cancelButton.setText("关闭")

        # 设置宽度
        self.widget.setMinimumWidth(450)

        self._load_snapshots()

    def _load_snapshots(self):
        """加载快照列表"""
        self.snapshot_list.clear()
        snapshots = self.db_manager.list_snapshots()

        for name, metadata in snapshots.items():
            item = QListWidgetItem(f"📷 {name}")
            item.setData(Qt.UserRole, name)
            self.snapshot_list.addItem(item)

    def _on_create(self):
        """创建快照"""
        name = self.snapshot_name_input.text().strip()
        if not name:
            return

        if self.db_manager.create_snapshot(name, {'created_at': datetime.now().isoformat()}):
            self._load_snapshots()
            self.snapshot_name_input.clear()

    def _on_select(self):
        """选择快照"""
        item = self.snapshot_list.currentItem()
        if item:
            self.selected_snapshot = item.data(Qt.UserRole)
            self.accept()

    def _on_delete(self):
        """删除快照"""
        item = self.snapshot_list.currentItem()
        if item:
            name = item.data(Qt.UserRole)
            if self.db_manager.delete_snapshot(name):
                self._load_snapshots()

    def _validateInput(self):
        """验证输入"""
        item = self.snapshot_list.currentItem()
        if item:
            self.selected_snapshot = item.data(Qt.UserRole)
            return True
        return False


class QueryDialog(MessageBoxBase):
    """查询对话框

    查询功能说明：
    - 价格过滤：只查询指定价格范围内的数据
    - 时间范围：只查询指定时间段的数据
    - Head/Tail：只查询前 N 条或后 N 条数据
    """

    def __init__(self, db_manager: ArcticDBManager, symbol: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.symbol = symbol
        self.result_df = None

        # 设置标题
        self.titleLabel = TitleLabel(f"数据查询 - {symbol}")
        self.viewLayout.addWidget(self.titleLabel)

        # 说明卡片
        help_card = SimpleCardWidget()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 12, 16, 12)
        help_icon = IconWidget(FluentIcon.SEARCH)
        help_icon.setFixedSize(20, 20)
        help_text = CaptionLabel("勾选启用过滤条件后点击执行查询。结果可直接显示到图表。")
        help_text.setWordWrap(True)
        help_row = QHBoxLayout()
        help_row.addWidget(help_icon)
        help_row.addWidget(help_text, 1)
        help_layout.addLayout(help_row)
        self.viewLayout.addWidget(help_card)

        # === 价格过滤卡片 ===
        price_card = CardWidget()
        price_layout = QVBoxLayout(price_card)
        price_layout.setContentsMargins(16, 12, 16, 12)

        price_header = QHBoxLayout()
        price_header.addWidget(BodyLabel("💰 价格过滤"))
        self.price_filter_check = CheckBox("启用")
        price_header.addStretch()
        price_header.addWidget(self.price_filter_check)
        price_layout.addLayout(price_header)

        price_input_layout = QHBoxLayout()
        price_input_layout.addWidget(CaptionLabel("最低:"))
        self.min_price = LineEdit()
        self.min_price.setPlaceholderText("0")
        self.min_price.setText("0")
        self.min_price.setValidator(QDoubleValidator(0, 999999, 2))
        self.min_price.setFixedWidth(100)
        price_input_layout.addWidget(self.min_price)
        price_input_layout.addWidget(CaptionLabel("最高:"))
        self.max_price = LineEdit()
        self.max_price.setPlaceholderText("999999")
        self.max_price.setText("999999")
        self.max_price.setValidator(QDoubleValidator(0, 999999, 2))
        self.max_price.setFixedWidth(100)
        price_input_layout.addWidget(self.max_price)
        price_input_layout.addStretch()
        price_layout.addLayout(price_input_layout)

        self.viewLayout.addWidget(price_card)

        # === 时间范围卡片 ===
        time_card = CardWidget()
        time_layout = QVBoxLayout(time_card)
        time_layout.setContentsMargins(16, 12, 16, 12)

        time_header = QHBoxLayout()
        time_header.addWidget(BodyLabel("📅 时间范围"))
        self.time_filter_check = CheckBox("启用")
        time_header.addStretch()
        time_header.addWidget(self.time_filter_check)
        time_layout.addLayout(time_header)

        # 开始时间
        start_layout = QHBoxLayout()
        start_layout.addWidget(CaptionLabel("从:"))
        self.start_datetime = DateTimeEdit()
        self.start_datetime.setDateTime(QDateTime.currentDateTime().addDays(-30))
        start_layout.addWidget(self.start_datetime)
        start_layout.addStretch()
        time_layout.addLayout(start_layout)

        # 结束时间
        end_layout = QHBoxLayout()
        end_layout.addWidget(CaptionLabel("到:"))
        self.end_datetime = DateTimeEdit()
        self.end_datetime.setDateTime(QDateTime.currentDateTime())
        end_layout.addWidget(self.end_datetime)
        end_layout.addStretch()
        time_layout.addLayout(end_layout)

        self.viewLayout.addWidget(time_card)

        # === 行数限制卡片 ===
        limit_card = CardWidget()
        limit_layout = QVBoxLayout(limit_card)
        limit_layout.setContentsMargins(16, 12, 16, 12)

        limit_layout.addWidget(BodyLabel("📊 行数限制"))

        limit_input_layout = QHBoxLayout()
        self.head_tail_input = LineEdit()
        self.head_tail_input.setPlaceholderText("50")
        self.head_tail_input.setText("50")
        self.head_tail_input.setValidator(QIntValidator(1, 10000))
        self.head_tail_input.setFixedWidth(80)
        limit_input_layout.addWidget(self.head_tail_input)

        self.head_radio = CheckBox("前 N 行")
        self.head_radio.setChecked(True)
        limit_input_layout.addWidget(self.head_radio)

        self.tail_radio = CheckBox("后 N 行")
        limit_input_layout.addWidget(self.tail_radio)

        limit_input_layout.addStretch()
        limit_layout.addLayout(limit_input_layout)

        self.viewLayout.addWidget(limit_card)

        # 查询按钮
        query_btn = PrimaryPushButton("执行查询")
        query_btn.setIcon(FluentIcon.SEARCH)
        query_btn.clicked.connect(self._on_query)
        self.viewLayout.addWidget(query_btn)

        # 结果显示
        self.viewLayout.addWidget(SubtitleLabel("查询结果"))
        self.result_text = TextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(120)
        self.viewLayout.addWidget(self.result_text)

        # 设置按钮文字
        self.yesButton.setText("使用结果显示图表")
        self.cancelButton.setText("关闭")

        # 设置宽度
        self.widget.setMinimumWidth(500)

    def _on_query(self):
        """执行查询"""
        df = None

        # 价格过滤
        if self.price_filter_check.isChecked():
            try:
                min_val = float(self.min_price.text()) if self.min_price.text() else 0
                max_val = float(self.max_price.text()) if self.max_price.text() else 999999
            except ValueError:
                min_val, max_val = 0, 999999
            df = self.db_manager.query_by_price(
                self.symbol,
                min_price=min_val if min_val > 0 else None,
                max_price=max_val if max_val < 999999 else None
            )
        # 时间范围过滤
        elif self.time_filter_check.isChecked():
            start = self.start_datetime.dateTime().toPython()
            end = self.end_datetime.dateTime().toPython()
            df = self.db_manager.query_by_date_range(self.symbol, start, end)
        # Head/Tail
        elif self.head_radio.isChecked() or self.tail_radio.isChecked():
            try:
                n = int(self.head_tail_input.text()) if self.head_tail_input.text() else 50
            except ValueError:
                n = 50
            df = self.db_manager.query_head_tail(self.symbol, n, head=self.head_radio.isChecked())
        else:
            df = self.db_manager.load_data(self.symbol)

        if df is not None and len(df) > 0:
            self.result_df = df
            # 显示结果摘要
            summary = f"✓ 查询结果: {len(df)} 行\n\n"
            summary += f"时间范围: {df['time'].iloc[0]} ~ {df['time'].iloc[-1]}\n"
            summary += f"价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}\n\n"
            summary += "前5行:\n"
            summary += df.head().to_string()
            self.result_text.setText(summary)
        else:
            self.result_text.setText("无数据")
            self.result_df = None

    def _validateInput(self):
        """验证输入"""
        return self.result_df is not None


class StatsDialog(MessageBoxBase):
    """存储统计对话框

    说明：
    - 显示所有 Symbol 的数据量、版本数、碎片状态
    - 碎片化：频繁小批量写入会导致数据碎片化，影响读取性能
    - 点击"整理所有碎片数据"可以合并碎片，提升性能
    """

    def __init__(self, db_manager: ArcticDBManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

        # 设置标题
        self.titleLabel = TitleLabel("存储统计")
        self.viewLayout.addWidget(self.titleLabel)

        # 说明卡片
        help_card = SimpleCardWidget()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 12, 16, 12)
        help_icon = IconWidget(FluentIcon.PIE_SINGLE)
        help_icon.setFixedSize(20, 20)
        help_text = CaptionLabel(
            "显示所有数据的存储状态。碎片化会影响性能，建议定期整理。"
        )
        help_text.setWordWrap(True)
        help_row = QHBoxLayout()
        help_row.addWidget(help_icon)
        help_row.addWidget(help_text, 1)
        help_layout.addLayout(help_row)
        self.viewLayout.addWidget(help_card)

        # 统计信息显示
        self.stats_text = TextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMinimumHeight(250)
        self.viewLayout.addWidget(self.stats_text)

        # 碎片整理按钮
        defrag_btn = PushButton("整理所有碎片数据")
        defrag_btn.setIcon(FluentIcon.SYNC)
        defrag_btn.clicked.connect(self._on_defrag_all)
        self.viewLayout.addWidget(defrag_btn)

        # 设置按钮文字
        self.yesButton.hide()
        self.cancelButton.setText("关闭")

        # 设置宽度
        self.widget.setMinimumWidth(450)

        self._load_stats()

    def _load_stats(self):
        """加载统计信息"""
        stats = self.db_manager.get_storage_stats()

        text = "📦 总 Symbol 数: {}\n".format(stats.get('total_symbols', 0))
        text += "📷 总快照数: {}\n\n".format(stats.get('total_snapshots', 0))

        symbols = stats.get('symbols', {})
        if symbols:
            text += "▸ Symbol 详情\n\n"
            for symbol, info in symbols.items():
                frag_icon = "⚠" if info['fragmented'] else "✓"
                frag_status = "需整理" if info['fragmented'] else "正常"
                text += f"【{symbol}】\n"
                text += f"  行数: {info['rows']:,}\n"
                text += f"  版本: {info['versions']}\n"
                text += f"  碎片: {frag_icon} {frag_status}\n\n"
        else:
            text += "暂无数据\n"

        self.stats_text.setText(text)

    def _on_defrag_all(self):
        """整理所有碎片"""
        stats = self.db_manager.get_storage_stats()
        defragged = 0

        for symbol, info in stats.get('symbols', {}).items():
            if info['fragmented']:
                if self.db_manager.defragment(symbol):
                    defragged += 1

        self._load_stats()
        if defragged > 0:
            current_text = self.stats_text.toPlainText()
            self.stats_text.setText(current_text + f"\n✓ 已整理 {defragged} 个 Symbol 的碎片数据")


# ==================== 主窗口 ====================

class ChartWindow(GuanlanWindow):
    """K 线图表窗口（增强版）"""

    def __init__(self):
        super().__init__(enable_translucent_background=False)
        self.setWindowTitle("ArcticDB 高级特性演示 - 观澜量化")
        self.resize(1400, 900)

        # 初始化 ArcticDB 管理器
        self.db_manager = ArcticDBManager(ARCTICDB_PATH)

        # 当前显示的 symbol
        self.current_symbol = DEFAULT_SYMBOL

        # 当前加载的版本号（None 表示最新版本）
        self.loaded_version: int | None = None

        # 当前数据
        self.current_df = pd.DataFrame()

        # 流式数据生成器
        self.data_generator: StreamingDataGenerator | None = None

        # 定时器
        self.stream_timer = QTimer()
        self.stream_timer.timeout.connect(self._on_stream_tick)

        # DB 批量保存定时器
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self._batch_save_to_db)

        # 待保存的数据缓冲区
        self.pending_save_buffer = pd.DataFrame()

        # 统计
        self.total_bars = 0
        self.stream_running = False

        self._init_ui()
        self._auto_load_on_startup()

    def _init_ui(self):
        """初始化界面"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ===== 工具栏1: 基础操作 =====
        toolbar1 = QWidget()
        toolbar1.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        toolbar1.setFixedHeight(48)
        tb1_layout = QHBoxLayout(toolbar1)
        tb1_layout.setContentsMargins(16, 8, 16, 8)
        tb1_layout.setSpacing(12)

        # Symbol 选择
        self.symbol_combo = ComboBox()
        self.symbol_combo.setFixedWidth(150)
        self.symbol_combo.setPlaceholderText("选择标的")
        self._refresh_symbol_list()
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        tb1_layout.addWidget(self.symbol_combo)

        # 开始/停止演示
        self.stream_btn = PushButton("开始演示")
        self.stream_btn.setIcon(FluentIcon.PLAY)
        self.stream_btn.clicked.connect(self._toggle_stream)
        self.stream_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb1_layout.addWidget(self.stream_btn)

        # 手动保存（创建新版本）
        save_btn = PushButton("保存版本")
        save_btn.setIcon(FluentIcon.SAVE)
        save_btn.clicked.connect(self._manual_save)
        save_btn.setEnabled(ARCTICDB_AVAILABLE)
        save_btn.setToolTip("手动保存当前数据，创建新版本")
        tb1_layout.addWidget(save_btn)

        # 清空数据
        clear_btn = PushButton("清空")
        clear_btn.setIcon(FluentIcon.DELETE)
        clear_btn.clicked.connect(self._clear_data)
        clear_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb1_layout.addWidget(clear_btn)

        tb1_layout.addWidget(self._separator())

        # 状态标签
        self.status_label = BodyLabel("")
        self.status_label.setStyleSheet("color: #8b949e;")
        tb1_layout.addWidget(self.status_label)

        tb1_layout.addStretch()
        layout.addWidget(toolbar1)

        # ===== 工具栏2: 高级功能 =====
        toolbar2 = QWidget()
        toolbar2.setStyleSheet("background-color: #0d1117; border-bottom: 1px solid #30363d;")
        toolbar2.setFixedHeight(48)
        tb2_layout = QHBoxLayout(toolbar2)
        tb2_layout.setContentsMargins(16, 8, 16, 8)
        tb2_layout.setSpacing(12)

        tb2_layout.addWidget(BodyLabel("高级功能:"))

        # 版本管理
        version_btn = PushButton("版本管理")
        version_btn.setIcon(FluentIcon.HISTORY)
        version_btn.clicked.connect(self._show_version_dialog)
        version_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(version_btn)

        # 快照管理
        snapshot_btn = PushButton("快照管理")
        snapshot_btn.setIcon(FluentIcon.PHOTO)
        snapshot_btn.clicked.connect(self._show_snapshot_dialog)
        snapshot_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(snapshot_btn)

        # 数据查询
        query_btn = PushButton("数据查询")
        query_btn.setIcon(FluentIcon.SEARCH)
        query_btn.clicked.connect(self._show_query_dialog)
        query_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(query_btn)

        # 存储统计
        stats_btn = PushButton("存储统计")
        stats_btn.setIcon(FluentIcon.PIE_SINGLE)
        stats_btn.clicked.connect(self._show_stats_dialog)
        stats_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(stats_btn)

        tb2_layout.addWidget(self._separator())

        # 快速操作
        head_btn = PushButton("前50条")
        head_btn.clicked.connect(lambda: self._quick_query('head', 50))
        head_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(head_btn)

        tail_btn = PushButton("后50条")
        tail_btn.clicked.connect(lambda: self._quick_query('tail', 50))
        tail_btn.setEnabled(ARCTICDB_AVAILABLE)
        tb2_layout.addWidget(tail_btn)

        tb2_layout.addStretch()
        layout.addWidget(toolbar2)

        # 创建图表
        self.chart = QtChart(container)
        layout.addWidget(self.chart.get_webview(), 1)

        self.setCentralWidget(container)

    def _separator(self) -> QLabel:
        """创建分隔符"""
        sep = QLabel("|")
        sep.setStyleSheet("color: #30363d;")
        return sep

    def _refresh_symbol_list(self):
        """刷新 symbol 列表"""
        self.symbol_combo.clear()
        self.symbol_combo.addItem(DEFAULT_SYMBOL)
        symbols = self.db_manager.list_symbols()
        for symbol in symbols:
            if symbol != DEFAULT_SYMBOL:
                self.symbol_combo.addItem(symbol)

    def _on_symbol_changed(self, symbol: str):
        """Symbol 改变"""
        if symbol and symbol != self.current_symbol:
            if self.stream_running:
                self._stop_stream()
            self.current_symbol = symbol
            self._load_from_db()

    def _auto_load_on_startup(self):
        """启动时自动加载"""
        if not ARCTICDB_AVAILABLE:
            self._show_empty_chart()
            return

        df = self.db_manager.load_data(DEFAULT_SYMBOL)
        if df is not None and len(df) > 0:
            self.current_df = df
            self.total_bars = len(df)
            self.chart.set(df)
            self._update_status()
            self._show_info("数据已加载", f"从 DB 加载了 {len(df)} 条历史数据")

            last_price = df.iloc[-1]['close']
            last_time = pd.to_datetime(df.iloc[-1]['time'])
            self.data_generator = StreamingDataGenerator(
                start_price=last_price,
                start_time=last_time + timedelta(minutes=1)
            )
        else:
            self._show_empty_chart()
            self._show_info("开始演示", "点击「开始演示」按钮生成实时数据")

    def _show_empty_chart(self):
        """显示空图表"""
        self.data_generator = StreamingDataGenerator()
        self.current_df = self.data_generator.generate_bars(10)
        self.total_bars = len(self.current_df)
        self.chart.set(self.current_df)
        self._update_status()

    def _load_from_db(self, version: int = None):
        """从 DB 加载数据"""
        df = self.db_manager.load_data(self.current_symbol, version)
        if df is not None and len(df) > 0:
            self.current_df = df
            self.total_bars = len(df)
            self.loaded_version = version  # 记录加载的版本
            self.chart.set(df)
            self._update_status()

            last_price = df.iloc[-1]['close']
            last_time = pd.to_datetime(df.iloc[-1]['time'])
            self.data_generator = StreamingDataGenerator(
                start_price=last_price,
                start_time=last_time + timedelta(minutes=1)
            )
        else:
            self._show_empty_chart()

    def _toggle_stream(self):
        """切换流式演示"""
        if self.stream_running:
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self):
        """开始流式演示"""
        if not ARCTICDB_AVAILABLE:
            self._show_error("ArcticDB 未安装")
            return

        if self.data_generator is None:
            if len(self.current_df) > 0:
                last_price = self.current_df.iloc[-1]['close']
                last_time = pd.to_datetime(self.current_df.iloc[-1]['time'])
                self.data_generator = StreamingDataGenerator(
                    start_price=last_price,
                    start_time=last_time + timedelta(minutes=1)
                )
            else:
                self.data_generator = StreamingDataGenerator()

        self.stream_running = True
        self.stream_btn.setText("停止演示")
        self.stream_btn.setIcon(FluentIcon.PAUSE)
        self.stream_timer.start(100)
        self.save_timer.start(5000)

    def _stop_stream(self):
        """停止流式演示"""
        self.stream_running = False
        self.stream_timer.stop()
        self.save_timer.stop()
        self._batch_save_to_db()
        self.stream_btn.setText("开始演示")
        self.stream_btn.setIcon(FluentIcon.PLAY)

    def _on_stream_tick(self):
        """生成数据"""
        if not self.data_generator:
            return

        new_bar = self.data_generator.generate_bars(1)

        if len(self.current_df) > 0:
            self.current_df = pd.concat([self.current_df, new_bar], ignore_index=True)
        else:
            self.current_df = new_bar

        if len(self.pending_save_buffer) > 0:
            self.pending_save_buffer = pd.concat([self.pending_save_buffer, new_bar], ignore_index=True)
        else:
            self.pending_save_buffer = new_bar.copy()

        self.total_bars = len(self.current_df)

        try:
            self.chart.update(new_bar.iloc[0])
        except Exception:
            self.chart.set(self.current_df)

        self._update_status()

    def _batch_save_to_db(self):
        """批量保存（不自动创建版本，只追加数据）"""
        if len(self.pending_save_buffer) == 0:
            return

        # keep_versions=False：自动追加时不保留版本，只有用户手动点击"保存版本"时才创建
        if self.db_manager.append_data(self.current_symbol, self.pending_save_buffer, keep_versions=False):
            print(f"批量保存: {len(self.pending_save_buffer)} 条数据")

        self.pending_save_buffer = pd.DataFrame()

    def _manual_save(self):
        """手动保存当前数据（创建新版本）"""
        if len(self.current_df) == 0:
            self._show_info("提示", "没有数据可保存")
            return

        # 使用 save_data 并保留版本
        version = self.db_manager.save_data(
            self.current_symbol,
            self.current_df,
            metadata={'manual_save': True, 'bars': len(self.current_df)},
            prune_previous=False  # 保留历史版本
        )

        if version is not None:
            self._show_success("保存成功", f"已创建版本 {version}，共 {len(self.current_df)} 条数据")

    def _update_status(self):
        """更新状态"""
        status = f"数据量: {self.total_bars} 条"
        if self.stream_running:
            pending = len(self.pending_save_buffer)
            status += f" | 演示中 (待保存: {pending})"
        self.status_label.setText(status)

    def _clear_data(self):
        """清空数据"""
        if self.stream_running:
            self._stop_stream()

        self.db_manager.delete_symbol(self.current_symbol)
        self.current_df = pd.DataFrame()
        self.pending_save_buffer = pd.DataFrame()
        self.total_bars = 0
        self.data_generator = StreamingDataGenerator()
        self._show_empty_chart()
        self._refresh_symbol_list()
        self._show_info("已清空", f"已清空 {self.current_symbol} 的所有数据")

    # ===== 高级功能对话框 =====

    def _show_version_dialog(self):
        """显示版本管理对话框"""
        dialog = VersionDialog(self.db_manager, self.current_symbol, self.loaded_version, self)
        if dialog.exec() and dialog.selected_version is not None:
            self._load_from_db(dialog.selected_version)
            self.loaded_version = dialog.selected_version
            self._show_success("已加载", f"已加载版本 {dialog.selected_version}")

    def _show_snapshot_dialog(self):
        """显示快照管理对话框"""
        dialog = SnapshotDialog(self.db_manager, self)
        if dialog.exec() and dialog.selected_snapshot:
            df = self.db_manager.read_from_snapshot(self.current_symbol, dialog.selected_snapshot)
            if df is not None and len(df) > 0:
                self.current_df = df
                self.total_bars = len(df)
                self.chart.set(df)
                self._update_status()
                self._show_success("已恢复", f"已从快照 {dialog.selected_snapshot} 恢复数据")

    def _show_query_dialog(self):
        """显示查询对话框"""
        df = self.db_manager.load_data(self.current_symbol)
        if df is None or len(df) == 0:
            self._show_info("提示", "当前 Symbol 没有数据")
            return

        dialog = QueryDialog(self.db_manager, self.current_symbol, self)
        if dialog.exec() and dialog.result_df is not None:
            self.current_df = dialog.result_df
            self.total_bars = len(dialog.result_df)
            self.chart.set(dialog.result_df)
            self._update_status()
            self._show_success("查询完成", f"显示 {len(dialog.result_df)} 条数据")

    def _show_stats_dialog(self):
        """显示存储统计对话框"""
        dialog = StatsDialog(self.db_manager, self)
        dialog.exec()

    def _quick_query(self, query_type: str, n: int):
        """快速查询"""
        if query_type == 'head':
            df = self.db_manager.query_head_tail(self.current_symbol, n, head=True)
        else:
            df = self.db_manager.query_head_tail(self.current_symbol, n, head=False)

        if df is not None and len(df) > 0:
            self.current_df = df
            self.total_bars = len(df)
            self.chart.set(df)
            self._update_status()

    # ===== 消息提示 =====

    def _show_success(self, title: str, content: str):
        InfoBar.success(title=title, content=content, parent=self,
                        position=InfoBarPosition.TOP, duration=3000)

    def _show_error(self, title: str, content: str = ""):
        InfoBar.error(title=title, content=content, parent=self,
                      position=InfoBarPosition.TOP, duration=3000)

    def _show_info(self, title: str, content: str):
        InfoBar.info(title=title, content=content, parent=self,
                     position=InfoBarPosition.TOP, duration=3000)

    def closeEvent(self, event):
        self._stop_stream()
        event.accept()


def main():
    # 检查依赖
    if not HAS_LIGHTWEIGHT_CHARTS or not ARCTICDB_AVAILABLE:
        print("\n" + "=" * 60)
        print("依赖库缺失，无法运行此示例")
        print("=" * 60)

        missing_deps = []
        if not HAS_LIGHTWEIGHT_CHARTS:
            missing_deps.append("lightweight-charts")
        if not ARCTICDB_AVAILABLE:
            missing_deps.append("arcticdb")

        print(f"\n请运行以下命令安装依赖：")
        print(f"  pip install {' '.join(missing_deps)}")
        print()
        return

    app = QApplication(sys.argv)
    setTheme(Theme.DARK)

    window = ChartWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
