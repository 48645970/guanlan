# -*- coding: utf-8 -*-
"""
观澜量化 - Redis 工具演示

演示 core.utils.redis_client 模块的各项功能

注意：需要安装 redis 库并运行 Redis 服务器
pip install redis

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def demo_redis_availability():
    """检查 Redis 可用性"""
    print("=" * 70)
    print("1. 检查 Redis 可用性")
    print("=" * 70)

    try:
        import redis
        print("✓ redis 库已安装")
        print(f"  版本: {redis.__version__}")
    except ImportError:
        print("✗ redis 库未安装")
        print("  请运行: pip install redis")
        return False

    print()
    return True


def demo_config_file():
    """演示从配置文件创建客户端"""
    print("=" * 70)
    print("2. 从配置文件创建客户端")
    print("=" * 70)

    try:
        from guanlan.core.utils.redis_client import RedisClient, load_redis_config

        print(">>> 使用默认配置文件 ../config/redis.json")
        print("    （与 0105 使用同一配置文件）")
        print()

        # 加载配置（会自动创建示例配置如果不存在）
        config = load_redis_config()
        print("配置内容:")
        for key, value in config.items():
            print(f"  {key}: {value}")

        print("\n>>> 从配置文件创建客户端")
        client = RedisClient.from_config()  # 使用默认配置文件
        print("  client = RedisClient.from_config()")

        if client.ping():
            print("  ✓ 连接成功")
        else:
            print("  ✗ 连接失败")

        client.close()
        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_basic_operations():
    """演示基本操作"""
    print("=" * 70)
    print("3. 基本键值操作")
    print("=" * 70)

    try:
        from guanlan.core.utils.redis_client import RedisClient

        # 从配置文件创建客户端
        client = RedisClient.from_config()

        # 测试连接
        if not client.ping():
            print("✗ 无法连接到 Redis 服务器")
            print("  请确保 Redis 服务已启动")
            return

        print("✓ 成功连接到 Redis 服务器\n")

        # 设置键值
        print(">>> 设置键值")
        client.set("test_key", "test_value")
        print("  client.set('test_key', 'test_value')")

        # 获取键值
        print("\n>>> 获取键值")
        value = client.get("test_key")
        print(f"  client.get('test_key') = '{value}'")

        # 检查键是否存在
        print("\n>>> 检查键是否存在")
        exists = client.exists("test_key")
        print(f"  client.exists('test_key') = {exists}")

        # 设置过期时间
        print("\n>>> 设置过期时间")
        client.expire("test_key", 60)
        ttl = client.ttl("test_key")
        print(f"  client.expire('test_key', 60)")
        print(f"  client.ttl('test_key') = {ttl} 秒")

        # 删除键
        print("\n>>> 删除键")
        deleted = client.delete("test_key")
        print(f"  client.delete('test_key') = {deleted}")

        client.close()
        print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_hash_operations():
    """演示哈希表操作"""
    print("=" * 70)
    print("4. 哈希表操作")
    print("=" * 70)

    try:
        from guanlan.core.utils.redis_client import RedisClient

        with RedisClient.from_config() as client:
            if not client.ping():
                print("✗ 无法连接到 Redis 服务器")
                return

            print(">>> 哈希表操作示例：存储用户信息\n")

            # 设置哈希表字段
            print("设置字段:")
            client.hset("user:1001", "name", "张三")
            client.hset("user:1001", "age", "25")
            client.hset("user:1001", "city", "北京")
            print("  client.hset('user:1001', 'name', '张三')")
            print("  client.hset('user:1001', 'age', '25')")
            print("  client.hset('user:1001', 'city', '北京')")

            # 获取单个字段
            print("\n获取单个字段:")
            name = client.hget("user:1001", "name")
            print(f"  client.hget('user:1001', 'name') = '{name}'")

            # 获取所有字段
            print("\n获取所有字段:")
            user_data = client.hgetall("user:1001")
            print(f"  client.hgetall('user:1001') =")
            for key, value in user_data.items():
                print(f"    {key}: {value}")

            # 清理
            client.delete("user:1001")
            print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_list_operations():
    """演示列表操作"""
    print("=" * 70)
    print("5. 列表操作")
    print("=" * 70)

    try:
        from guanlan.core.utils.redis_client import RedisClient

        with RedisClient.from_config() as client:
            if not client.ping():
                print("✗ 无法连接到 Redis 服务器")
                return

            print(">>> 列表操作示例：订单队列\n")

            # 从右侧推入
            print("推入订单:")
            client.rpush("orders", "订单001", "订单002", "订单003")
            print("  client.rpush('orders', '订单001', '订单002', '订单003')")

            # 获取列表长度
            print("\n获取列表内容:")
            orders = client.lrange("orders", 0, -1)
            print(f"  client.lrange('orders', 0, -1) =")
            for i, order in enumerate(orders):
                print(f"    [{i}] {order}")

            # 清理
            client.delete("orders")
            print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def demo_practical_scenario():
    """演示实际场景：缓存行情数据"""
    print("=" * 70)
    print("6. 实际场景：缓存行情数据")
    print("=" * 70)

    try:
        from guanlan.core.utils.redis_client import RedisClient
        import json

        with RedisClient.from_config() as client:
            if not client.ping():
                print("✗ 无法连接到 Redis 服务器")
                return

            print(">>> 场景：缓存期货合约的最新行情\n")

            # 模拟行情数据
            quotes = {
                "SHFE.rb2505": {
                    "symbol": "SHFE.rb2505",
                    "last_price": 3520.0,
                    "volume": 125680,
                    "datetime": "2025-12-25 14:30:00",
                },
                "SHFE.hc2505": {
                    "symbol": "SHFE.hc2505",
                    "last_price": 3280.0,
                    "volume": 98450,
                    "datetime": "2025-12-25 14:30:00",
                },
            }

            print("存储行情数据:")
            for symbol, data in quotes.items():
                # 使用哈希表存储
                for key, value in data.items():
                    client.hset(f"quote:{symbol}", key, str(value))
                print(f"  ✓ {symbol} 最新价: {data['last_price']}")

                # 设置 1 分钟过期
                client.expire(f"quote:{symbol}", 60)

            print("\n读取行情数据:")
            for symbol in quotes.keys():
                cached_data = client.hgetall(f"quote:{symbol}")
                if cached_data:
                    print(f"  {symbol}:")
                    print(f"    最新价: {cached_data.get('last_price')}")
                    print(f"    成交量: {cached_data.get('volume')}")
                    print(f"    时间: {cached_data.get('datetime')}")
                    ttl = client.ttl(f"quote:{symbol}")
                    print(f"    有效期: {ttl} 秒")

            # 清理
            for symbol in quotes.keys():
                client.delete(f"quote:{symbol}")

            print()

    except Exception as e:
        print(f"✗ 错误: {e}")
        print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 21 + "观澜量化 - Redis 工具演示" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 检查 Redis 可用性
    if not demo_redis_availability():
        print("\n提示：")
        print("1. 安装 redis 库: pip install redis")
        print("2. 启动 Redis 服务器")
        print("   - Ubuntu/Debian: sudo systemctl start redis-server")
        print("   - macOS: brew services start redis")
        print("   - Windows: 下载并运行 Redis for Windows")
        return

    # 执行各项演示
    demo_config_file()
    demo_basic_operations()
    demo_hash_operations()
    demo_list_operations()
    demo_practical_scenario()

    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    print()
    print("提示：")
    print("- Redis 可用于缓存行情数据、共享状态等")
    print("- 支持多种数据结构：字符串、哈希、列表、集合、有序集合")
    print("- 配置文件位于: examples/config/redis.json")


if __name__ == "__main__":
    main()
