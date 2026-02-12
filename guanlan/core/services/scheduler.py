# -*- coding: utf-8 -*-
"""
观澜量化 - 定时任务调度服务

Author: 海山观澜
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Any

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

from guanlan.core.utils.logger import get_logger


logger = get_logger("scheduler", level=20)


@dataclass
class TaskRecord:
    """任务执行记录"""
    task_id: str
    task_name: str
    execute_time: datetime
    success: bool
    error: str | None = None


class TaskScheduler:
    """
    定时任务调度器（单例模式）

    基于 schedule 库，支持动态添加/删除任务、任务执行历史记录

    Examples
    --------
    >>> # 获取调度器实例
    >>> scheduler = TaskScheduler.get_instance()
    >>>
    >>> # 添加任务
    >>> def my_task():
    ...     print("Task executed")
    >>> scheduler.add_task("task1", my_task, interval=10)
    >>>
    >>> # 启动调度器
    >>> scheduler.start()
    >>>
    >>> # 停止调度器
    >>> scheduler.stop()
    """

    _instance: "TaskScheduler | None" = None
    _initialized: bool = False

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化调度器"""
        if self._initialized:
            return

        if not SCHEDULE_AVAILABLE:
            logger.warning("schedule 库未安装，定时任务功能不可用")
            self._available = False
            self._initialized = True
            return

        self._available = True
        self._running = False
        self._stop_flag = Event()
        self._thread: Thread | None = None
        self._lock = Lock()

        # 任务管理
        self._tasks: dict[str, schedule.Job] = {}

        # 任务执行历史（最多保留 100 条）
        self._history: list[TaskRecord] = []
        self._max_history = 100

        logger.info("定时任务调度器初始化成功")
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "TaskScheduler":
        """
        获取调度器实例

        Returns
        -------
        TaskScheduler
            调度器单例

        Examples
        --------
        >>> scheduler = TaskScheduler.get_instance()
        """
        return cls()

    def is_available(self) -> bool:
        """
        检查调度器是否可用

        Returns
        -------
        bool
            调度器是否可用
        """
        return self._available

    def is_running(self) -> bool:
        """
        检查调度器是否正在运行

        Returns
        -------
        bool
            是否正在运行

        Examples
        --------
        >>> scheduler.is_running()
        True
        """
        return self._running

    def start(self) -> bool:
        """
        启动调度器

        Returns
        -------
        bool
            是否成功启动

        Examples
        --------
        >>> scheduler.start()
        True
        """
        if not self._available:
            logger.error("调度器不可用")
            return False

        with self._lock:
            if self._running:
                logger.warning("调度器已在运行")
                return False

            self._stop_flag.clear()
            self._thread = Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._running = True

            logger.info("定时任务调度器已启动")
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止调度器

        Parameters
        ----------
        timeout : float, default 5.0
            等待停止的超时时间（秒）

        Returns
        -------
        bool
            是否成功停止

        Examples
        --------
        >>> scheduler.stop()
        True
        """
        if not self._running:
            logger.warning("调度器未运行")
            return False

        with self._lock:
            self._stop_flag.set()

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout)

                if self._thread.is_alive():
                    logger.error("调度器停止超时")
                    return False

            self._running = False
            logger.info("定时任务调度器已停止")
            return True

    def add_task(
        self,
        task_id: str,
        task_func: Callable,
        interval: int,
        unit: str = "seconds",
        start_immediately: bool = False,
        **kwargs: Any,
    ) -> bool:
        """
        添加定时任务

        Parameters
        ----------
        task_id : str
            任务唯一标识
        task_func : Callable
            任务函数
        interval : int
            执行间隔
        unit : str, default "seconds"
            时间单位（seconds/minutes/hours/days）
        start_immediately : bool, default False
            是否立即执行一次
        **kwargs : Any
            传递给任务函数的参数

        Returns
        -------
        bool
            是否成功添加

        Examples
        --------
        >>> def my_task(name):
        ...     print(f"Hello {name}")
        >>> scheduler.add_task("task1", my_task, 10, name="World")
        True
        """
        if not self._available:
            logger.error("调度器不可用")
            return False

        with self._lock:
            if task_id in self._tasks:
                logger.warning(f"任务已存在: {task_id}")
                return False

            try:
                # 创建任务
                if unit == "seconds":
                    job = schedule.every(interval).seconds
                elif unit == "minutes":
                    job = schedule.every(interval).minutes
                elif unit == "hours":
                    job = schedule.every(interval).hours
                elif unit == "days":
                    job = schedule.every(interval).days
                else:
                    logger.error(f"不支持的时间单位: {unit}")
                    return False

                # 包装任务函数以记录执行历史
                def wrapped_task():
                    self._execute_task(task_id, task_func.__name__, task_func, **kwargs)

                job.do(wrapped_task)

                # 保存任务
                self._tasks[task_id] = job

                logger.info(
                    f"添加定时任务: {task_id}, 间隔: {interval} {unit}, "
                    f"函数: {task_func.__name__}"
                )

                # 立即执行一次
                if start_immediately:
                    wrapped_task()

                return True

            except Exception as e:
                logger.error(f"添加任务失败: {e}")
                return False

    def remove_task(self, task_id: str) -> bool:
        """
        移除定时任务

        Parameters
        ----------
        task_id : str
            任务唯一标识

        Returns
        -------
        bool
            是否成功移除

        Examples
        --------
        >>> scheduler.remove_task("task1")
        True
        """
        if not self._available:
            return False

        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return False

            try:
                job = self._tasks.pop(task_id)
                schedule.cancel_job(job)
                logger.info(f"移除定时任务: {task_id}")
                return True

            except Exception as e:
                logger.error(f"移除任务失败: {e}")
                return False

    def get_tasks(self) -> list[str]:
        """
        获取所有任务 ID

        Returns
        -------
        list[str]
            任务 ID 列表

        Examples
        --------
        >>> scheduler.get_tasks()
        ['task1', 'task2']
        """
        with self._lock:
            return list(self._tasks.keys())

    def clear_tasks(self) -> None:
        """
        清除所有任务

        Examples
        --------
        >>> scheduler.clear_tasks()
        """
        if not self._available:
            return

        with self._lock:
            schedule.clear()
            self._tasks.clear()
            logger.info("已清除所有定时任务")

    def get_history(self, limit: int = 50) -> list[TaskRecord]:
        """
        获取任务执行历史

        Parameters
        ----------
        limit : int, default 50
            返回的记录数量

        Returns
        -------
        list[TaskRecord]
            执行历史记录

        Examples
        --------
        >>> history = scheduler.get_history(10)
        >>> for record in history:
        ...     print(f"{record.task_name}: {record.success}")
        """
        with self._lock:
            return self._history[-limit:]

    def clear_history(self) -> None:
        """
        清除执行历史

        Examples
        --------
        >>> scheduler.clear_history()
        """
        with self._lock:
            self._history.clear()
            logger.info("已清除任务执行历史")

    def _run_loop(self) -> None:
        """调度循环（后台线程）"""
        logger.info("定时任务调度循环已启动")

        while not self._stop_flag.is_set():
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"调度循环出错: {e}")

        logger.info("定时任务调度循环已停止")

    def _execute_task(
        self,
        task_id: str,
        task_name: str,
        task_func: Callable,
        **kwargs: Any,
    ) -> None:
        """执行任务并记录历史"""
        start_time = datetime.now()

        try:
            task_func(**kwargs)

            # 记录成功
            record = TaskRecord(
                task_id=task_id,
                task_name=task_name,
                execute_time=start_time,
                success=True,
            )
            self._add_history(record)

        except Exception as e:
            # 记录失败
            error_msg = str(e)
            logger.error(f"任务执行失败 [{task_name}]: {error_msg}")

            record = TaskRecord(
                task_id=task_id,
                task_name=task_name,
                execute_time=start_time,
                success=False,
                error=error_msg,
            )
            self._add_history(record)

    def _add_history(self, record: TaskRecord) -> None:
        """添加执行历史"""
        with self._lock:
            self._history.append(record)

            # 限制历史记录数量
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]


# 全局调度器实例
_scheduler: TaskScheduler | None = None


def get_scheduler() -> TaskScheduler:
    """
    获取全局调度器实例

    Returns
    -------
    TaskScheduler
        全局调度器实例

    Examples
    --------
    >>> from guanlan.core.services.scheduler import get_scheduler
    >>> scheduler = get_scheduler()
    >>> scheduler.start()
    """
    global _scheduler

    if _scheduler is None:
        _scheduler = TaskScheduler.get_instance()

    return _scheduler


__all__ = [
    "TaskRecord",
    "TaskScheduler",
    "get_scheduler",
]
