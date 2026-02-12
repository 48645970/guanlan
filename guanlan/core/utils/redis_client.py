# -*- coding: utf-8 -*-
"""
观澜量化 - Redis 客户端工具

提供 Redis 连接管理和常用操作封装

Author: 海山观澜
"""

import json
from typing import Any
from pathlib import Path

try:
    import redis
    from redis import StrictRedis, ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    StrictRedis = None  # type: ignore
    ConnectionPool = None  # type: ignore

from guanlan.core.utils.logger import get_logger


logger = get_logger("redis", level=20)


def load_redis_config(config_file: str = "config/redis.json") -> dict[str, Any]:
    """
    加载 Redis 配置文件

    Parameters
    ----------
    config_file : str, default "config/redis.json"
        配置文件路径

    Returns
    -------
    dict[str, Any]
        Redis 配置字典

    Notes
    -----
    配置文件格式：
    {
        "host": "localhost",
        "port": 6379,
        "password": "",
        "db": 0
    }

    如果配置文件不存在，会自动创建示例配置
    """
    config_path = Path(config_file)

    if not config_path.exists():
        # 创建配置目录
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建示例配置
        example_config = {
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)

        logger.info(f"已创建示例 Redis 配置: {config_path}")
        return example_config

    # 加载配置
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    logger.debug(f"加载 Redis 配置: {config_path}")
    return config


class RedisClient:
    """
    Redis 客户端封装

    支持连接池管理、自动重连、常用操作封装

    Examples
    --------
    >>> # 从配置文件创建客户端
    >>> client = RedisClient.from_config("redis_config.json")
    >>> client.set("key", "value")
    >>> value = client.get("key")

    >>> # 直接创建客户端
    >>> client = RedisClient(host="localhost", port=6379)
    >>> client.ping()
    True
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        decode_responses: bool = True,
        max_connections: int = 10,
    ):
        """
        初始化 Redis 客户端

        Parameters
        ----------
        host : str, default "localhost"
            Redis 服务器地址
        port : int, default 6379
            Redis 服务器端口
        db : int, default 0
            数据库编号
        password : str | None, default None
            密码（如果需要）
        decode_responses : bool, default True
            是否自动解码响应为字符串
        max_connections : int, default 10
            连接池最大连接数

        Raises
        ------
        ImportError
            如果 redis 库未安装
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis 库未安装，请运行: pip install redis"
            )

        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses

        # 创建连接池
        self.pool = ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
            max_connections=max_connections,
        )

        # 创建客户端
        self.client = StrictRedis(connection_pool=self.pool)

        logger.info(
            f"Redis 客户端初始化: {host}:{port}, DB={db}, "
            f"decode={decode_responses}"
        )

    @classmethod
    def from_config(cls, config_file: str = "config/redis.json") -> "RedisClient":
        """
        从配置文件创建 Redis 客户端

        Parameters
        ----------
        config_file : str, default "config/redis.json"
            配置文件路径

        Returns
        -------
        RedisClient
            Redis 客户端实例

        Examples
        --------
        >>> # 使用默认配置文件 ../config/redis.json
        >>> client = RedisClient.from_config()

        >>> # 使用自定义配置文件
        >>> client = RedisClient.from_config("config/redis_dev.json")

        Notes
        -----
        配置文件格式：
        {
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0
        }

        如果配置文件不存在，会自动创建示例配置
        """
        config = load_redis_config(config_file)

        # 处理密码（空字符串转为 None）
        password = config.get("password")
        if password == "":
            password = None

        return cls(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=password,
            decode_responses=True,
        )

    def ping(self) -> bool:
        """
        测试连接

        Returns
        -------
        bool
            连接是否正常

        Examples
        --------
        >>> client.ping()
        True
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping 失败: {e}")
            return False

    def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        px: int | None = None,
    ) -> bool:
        """
        设置键值

        Parameters
        ----------
        key : str
            键名
        value : Any
            值
        ex : int | None, default None
            过期时间（秒）
        px : int | None, default None
            过期时间（毫秒）

        Returns
        -------
        bool
            是否成功

        Examples
        --------
        >>> client.set("key", "value")
        True
        >>> client.set("key", "value", ex=60)  # 60秒后过期
        True
        """
        try:
            return self.client.set(key, value, ex=ex, px=px)
        except Exception as e:
            logger.error(f"Redis set 失败: {e}")
            return False

    def get(self, key: str) -> Any | None:
        """
        获取键值

        Parameters
        ----------
        key : str
            键名

        Returns
        -------
        Any | None
            键值，不存在返回 None

        Examples
        --------
        >>> client.get("key")
        'value'
        """
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get 失败: {e}")
            return None

    def delete(self, *keys: str) -> int:
        """
        删除键

        Parameters
        ----------
        *keys : str
            要删除的键名

        Returns
        -------
        int
            删除的键数量

        Examples
        --------
        >>> client.delete("key1", "key2")
        2
        """
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete 失败: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """
        检查键是否存在

        Parameters
        ----------
        *keys : str
            键名

        Returns
        -------
        int
            存在的键数量

        Examples
        --------
        >>> client.exists("key1", "key2")
        1
        """
        try:
            return self.client.exists(*keys)
        except Exception as e:
            logger.error(f"Redis exists 失败: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """
        设置键的过期时间

        Parameters
        ----------
        key : str
            键名
        seconds : int
            过期时间（秒）

        Returns
        -------
        bool
            是否成功

        Examples
        --------
        >>> client.expire("key", 60)
        True
        """
        try:
            return self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire 失败: {e}")
            return False

    def ttl(self, key: str) -> int:
        """
        获取键的剩余生存时间

        Parameters
        ----------
        key : str
            键名

        Returns
        -------
        int
            剩余时间（秒），-1 表示永久，-2 表示不存在

        Examples
        --------
        >>> client.ttl("key")
        60
        """
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl 失败: {e}")
            return -2

    def hset(self, name: str, key: str, value: Any) -> int:
        """
        设置哈希表字段

        Parameters
        ----------
        name : str
            哈希表名
        key : str
            字段名
        value : Any
            字段值

        Returns
        -------
        int
            新增字段数量

        Examples
        --------
        >>> client.hset("myhash", "field1", "value1")
        1
        """
        try:
            return self.client.hset(name, key, value)
        except Exception as e:
            logger.error(f"Redis hset 失败: {e}")
            return 0

    def hget(self, name: str, key: str) -> Any | None:
        """
        获取哈希表字段值

        Parameters
        ----------
        name : str
            哈希表名
        key : str
            字段名

        Returns
        -------
        Any | None
            字段值，不存在返回 None

        Examples
        --------
        >>> client.hget("myhash", "field1")
        'value1'
        """
        try:
            return self.client.hget(name, key)
        except Exception as e:
            logger.error(f"Redis hget 失败: {e}")
            return None

    def hgetall(self, name: str) -> dict[Any, Any]:
        """
        获取哈希表所有字段

        Parameters
        ----------
        name : str
            哈希表名

        Returns
        -------
        dict[Any, Any]
            所有字段键值对

        Examples
        --------
        >>> client.hgetall("myhash")
        {'field1': 'value1', 'field2': 'value2'}
        """
        try:
            return self.client.hgetall(name)
        except Exception as e:
            logger.error(f"Redis hgetall 失败: {e}")
            return {}

    def lpush(self, name: str, *values: Any) -> int:
        """
        从左侧推入列表

        Parameters
        ----------
        name : str
            列表名
        *values : Any
            要推入的值

        Returns
        -------
        int
            列表长度

        Examples
        --------
        >>> client.lpush("mylist", "value1", "value2")
        2
        """
        try:
            return self.client.lpush(name, *values)
        except Exception as e:
            logger.error(f"Redis lpush 失败: {e}")
            return 0

    def rpush(self, name: str, *values: Any) -> int:
        """
        从右侧推入列表

        Parameters
        ----------
        name : str
            列表名
        *values : Any
            要推入的值

        Returns
        -------
        int
            列表长度

        Examples
        --------
        >>> client.rpush("mylist", "value1", "value2")
        2
        """
        try:
            return self.client.rpush(name, *values)
        except Exception as e:
            logger.error(f"Redis rpush 失败: {e}")
            return 0

    def lrange(self, name: str, start: int, end: int) -> list[Any]:
        """
        获取列表范围

        Parameters
        ----------
        name : str
            列表名
        start : int
            起始索引
        end : int
            结束索引（-1 表示到末尾）

        Returns
        -------
        list[Any]
            列表元素

        Examples
        --------
        >>> client.lrange("mylist", 0, -1)
        ['value1', 'value2']
        """
        try:
            return self.client.lrange(name, start, end)
        except Exception as e:
            logger.error(f"Redis lrange 失败: {e}")
            return []

    def close(self) -> None:
        """
        关闭连接

        Examples
        --------
        >>> client.close()
        """
        try:
            if self.pool:
                self.pool.disconnect()
                logger.info("Redis 连接已关闭")
        except Exception as e:
            logger.error(f"关闭 Redis 连接失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 全局单例（可选使用）
_global_client: RedisClient | None = None


def get_global_client(config_file: str = "../config/redis.json") -> RedisClient:
    """
    获取全局 Redis 客户端（单例模式）

    Parameters
    ----------
    config_file : str, default "../config/redis.json"
        配置文件路径（相对于示例文件目录）

    Returns
    -------
    RedisClient
        全局 Redis 客户端实例

    Examples
    --------
    >>> client = get_global_client()
    >>> client.ping()
    True
    """
    global _global_client

    if _global_client is None:
        _global_client = RedisClient.from_config(config_file)

    return _global_client


__all__ = [
    "load_redis_config",
    "RedisClient",
    "get_global_client",
]
