# -*- coding: utf-8 -*-
"""
定时任务示例

演示 schedule 库的各种用法：
- 每隔 N 秒/分钟执行
- 固定时间点执行
- 任务标签管理

使用前需要：
1. pip install schedule

Author: 海山观澜
"""

from datetime import datetime
import time


def job(name: str):
    """普通任务函数"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] 执行任务: {name}")


def main():
    print("=" * 50)
    print("Schedule 定时任务示例")
    print("=" * 50)
    print("按 Ctrl+C 退出\n")

    try:
        import schedule
    except ImportError:
        print("请先安装 schedule: pip install schedule")
        return

    # 每5秒执行一次
    schedule.every(5).seconds.do(job, "每5秒任务")

    # 每10-20秒随机执行一次
    schedule.every(10).to(20).seconds.do(job, "10-20秒随机任务")

    # 每分钟执行
    schedule.every(1).minutes.do(job, "每分钟任务")

    # 固定时间执行（示例：每天 09:00）
    # schedule.every().day.at("09:00").do(job, "每日09:00任务")

    # 每周一执行
    # schedule.every().monday.at("08:30").do(job, "每周一08:30任务")

    # 带标签的任务（方便批量管理）
    schedule.every(8).seconds.do(job, "带标签任务").tag("demo", "test")

    # 查看所有任务
    print("已注册的任务:")
    for task in schedule.get_jobs():
        print(f"  - {task}")
    print()

    # 立即运行所有任务一次（测试用）
    print("立即运行所有任务:")
    schedule.run_all(delay_seconds=1)
    print()

    # 持续运行
    print("开始定时循环:")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n任务已停止")

        # 清除指定标签的任务
        schedule.clear("demo")
        print("已清除 'demo' 标签的任务")


if __name__ == "__main__":
    main()
