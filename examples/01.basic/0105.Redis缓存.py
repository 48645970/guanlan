# -*- coding: utf-8 -*-
"""
Redis 基础示例

演示 Redis 数据库操作：
- 连接配置
- String 字符串操作
- Hash 哈希表操作
- 自增计数器
- Pipeline 批量操作
- Pub/Sub 发布订阅

依赖: pip install redis

Author: 海山观澜
"""

import json
import time
import threading
from pathlib import Path


def load_config() -> dict:
    """加载 Redis 配置"""
    config_file = Path("../config/redis.json")

    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        example_config = {
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        print(f"已创建示例配置: {config_file}")
        return example_config

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


class RedisDemo:
    """Redis 操作演示类"""

    def __init__(self, config: dict):
        try:
            import redis
        except ImportError:
            print("请先安装 redis: pip install redis")
            raise

        self.config = config
        self.client = redis.StrictRedis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            password=config.get("password") or None,
            db=config.get("db", 0),
            decode_responses=True  # 自动解码为字符串
        )

    def test_string(self):
        """String 类型测试"""
        print("\n[String 测试]")
        self.client.set("guanlan:test:name", "观澜量化")
        value = self.client.get("guanlan:test:name")
        print(f"  设置值: 观澜量化")
        print(f"  读取值: {value}")

    def test_hash(self):
        """Hash 类型测试"""
        print("\n[Hash 测试]")
        data = {
            "symbol": "rb2501",
            "price": "4520.5",
            "volume": "100"
        }
        self.client.hset("guanlan:test:tick", mapping=data)
        result = self.client.hgetall("guanlan:test:tick")
        print(f"  设置值: {data}")
        print(f"  读取值: {result}")

    def test_incr(self):
        """自增计数器测试"""
        print("\n[自增测试]")
        key = "guanlan:test:counter"
        self.client.set(key, 0)
        for i in range(3):
            value = self.client.incr(key)
            print(f"  第 {i+1} 次自增: {value}")

    def test_pipeline(self):
        """Pipeline 批量操作测试"""
        print("\n[Pipeline 测试]")
        pipe = self.client.pipeline()

        # 批量写入
        pipe.set("guanlan:test:p1", "value1")
        pipe.set("guanlan:test:p2", "value2")
        pipe.set("guanlan:test:p3", "value3")
        pipe.execute()
        print("  批量写入: p1, p2, p3")

        # 批量读取
        pipe.get("guanlan:test:p1")
        pipe.get("guanlan:test:p2")
        pipe.get("guanlan:test:p3")
        results = pipe.execute()
        print(f"  批量读取: {results}")

    def test_pubsub(self):
        """发布/订阅测试"""
        print("\n[Pub/Sub 测试]")

        channel = "guanlan:test:channel"
        received_messages = []

        def subscriber():
            """订阅者线程"""
            import redis
            # 订阅需要单独的连接
            sub_client = redis.StrictRedis(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 6379),
                password=self.config.get("password") or None,
                db=self.config.get("db", 0),
                decode_responses=True
            )

            pubsub = sub_client.pubsub()
            pubsub.subscribe(channel)
            print(f"  订阅者: 已订阅频道 '{channel}'")

            # 接收消息（最多接收 3 条）
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    received_messages.append(data)
                    print(f"  订阅者: 收到消息 '{data}'")

                    if len(received_messages) >= 3:
                        break

            pubsub.unsubscribe()
            pubsub.close()

        # 启动订阅者线程
        sub_thread = threading.Thread(target=subscriber, daemon=True)
        sub_thread.start()

        # 等待订阅者准备好
        time.sleep(0.5)

        # 发布消息
        messages = ["消息1", "消息2", "消息3"]
        for msg in messages:
            self.client.publish(channel, msg)
            print(f"  发布者: 发送消息 '{msg}'")
            time.sleep(0.3)

        # 等待订阅者接收完毕
        sub_thread.join(timeout=3)

        print(f"  结果: 发送 {len(messages)} 条，接收 {len(received_messages)} 条")

    def cleanup(self):
        """清理测试数据"""
        print("\n[清理测试数据]")
        keys = self.client.keys("guanlan:test:*")
        if keys:
            self.client.delete(*keys)
            print(f"  已删除 {len(keys)} 个键")


def main():
    print("=" * 50)
    print("Redis 基础示例")
    print("=" * 50)

    config = load_config()
    print(f"连接配置: {config['host']}:{config['port']}")

    try:
        demo = RedisDemo(config)

        # 测试连接
        demo.client.ping()
        print("Redis 连接成功！")

        # 运行测试
        demo.test_string()
        demo.test_hash()
        demo.test_incr()
        demo.test_pipeline()
        demo.test_pubsub()
        demo.cleanup()

        print("\nRedis 示例完成！")

    except Exception as e:
        print(f"\n连接失败: {e}")
        print("请确保 Redis 服务已启动，并检查配置文件")


if __name__ == "__main__":
    main()
