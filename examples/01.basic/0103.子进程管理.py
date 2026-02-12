# -*- coding: utf-8 -*-
"""
进程管理示例

演示外部进程的启动和管理：
- subprocess 模块使用
- 进程启动和终止
- 跨平台兼容处理

Author: 海山观澜
"""

import subprocess
import sys
import time
from datetime import datetime


# 进程配置（直接定义）
PROCESS_CONFIG = {
    "notepad": {
        "name": "记事本",
        "command_win": "notepad.exe",
        "command_linux": "gedit",
        "command_mac": "open -a TextEdit"
    },
    "calculator": {
        "name": "计算器",
        "command_win": "calc.exe",
        "command_linux": "gnome-calculator",
        "command_mac": "open -a Calculator"
    }
}


def get_platform_command(config: dict) -> str | None:
    """根据平台获取对应命令"""
    if sys.platform == "win32":
        return config.get("command_win")
    elif sys.platform == "darwin":
        return config.get("command_mac")
    else:  # Linux
        return config.get("command_linux")


def start_process(command: str) -> subprocess.Popen | None:
    """启动外部进程"""
    try:
        if sys.platform == "win32":
            # Windows: 使用 CREATE_NEW_CONSOLE
            process = subprocess.Popen(
                command,
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Linux/Mac: 使用 exec 前缀，确保可以正确终止进程
            # exec 使命令继承 shell 进程，而不是创建子进程
            process = subprocess.Popen(
                f"exec {command}",
                shell=True
            )
        return process
    except Exception as e:
        print(f"启动失败: {e}")
        return None


def kill_process_by_name(name: str) -> bool:
    """根据名称终止进程"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                f'taskkill /F /IM "{name}"',
                shell=True,
                capture_output=True
            )
        else:
            subprocess.run(
                f'pkill -f "{name}"',
                shell=True,
                capture_output=True
            )
        return True
    except Exception as e:
        print(f"终止失败: {e}")
        return False


def demo_process_management():
    """进程管理演示"""
    print("\n[可用进程配置]")
    for key, value in PROCESS_CONFIG.items():
        cmd = get_platform_command(value)
        print(f"  {key}: {value['name']} -> {cmd}")

    # 启动多个进程
    processes = []

    print("\n[启动进程]")
    for app_key in ["notepad", "calculator"]:
        if app_key not in PROCESS_CONFIG:
            print(f"  跳过: {app_key}")
            continue

        app_config = PROCESS_CONFIG[app_key]
        command = get_platform_command(app_config)

        if not command:
            print(f"  跳过: {app_config['name']} (当前平台无对应命令)")
            continue

        print(f"\n  启动: {app_config['name']}")
        print(f"  命令: {command}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        process = start_process(command)
        if process:
            print(f"  PID: {process.pid}")
            print(f"  状态: ✅ 运行中")
            print(f"  👉 请查看屏幕上的 {app_config['name']} 窗口！")
            processes.append((app_config['name'], process))
            time.sleep(2)  # 每个进程之间间隔2秒，让窗口有时间显示

    if not processes:
        print("\n  没有成功启动的进程")
        return

    # 等待更长时间让用户看到效果
    wait_time = 10
    print(f"\n[等待中]")
    print(f"  已启动 {len(processes)} 个进程，{wait_time} 秒后将全部关闭...")

    for i in range(wait_time, 0, -1):
        print(f"  倒计时: {i} 秒", end='\r')
        time.sleep(1)

    print("\n\n[关闭进程]")
    for name, process in processes:
        try:
            # 先尝试优雅关闭
            process.terminate()
            try:
                process.wait(timeout=1)
                print(f"  ✅ {name} 已关闭")
            except subprocess.TimeoutExpired:
                # 如果1秒后还没关闭，强制杀掉
                print(f"  ⚠️ {name} 未响应，强制关闭...")
                process.kill()
                process.wait(timeout=1)
                print(f"  ✅ {name} 已强制关闭")
        except Exception as e:
            print(f"  ⚠️ {name} 关闭失败: {e}")


def main():
    print("=" * 50)
    print("进程管理示例")
    print("=" * 50)
    print(f"当前平台: {sys.platform}")

    demo_process_management()

    print("\n进程管理示例完成！")


if __name__ == "__main__":
    main()
