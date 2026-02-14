# 示例代码

本目录包含观澜量化平台的各类功能演示代码，用于学习和测试。

## 目录结构

```
examples/
├── 01.basic/                   # 基础功能（无 UI 依赖）
│   ├── 0101.日志记录.py
│   ├── 0102.拼音转换.py
│   ├── 0103.子进程管理.py
│   ├── 0104.定时任务.py
│   ├── 0105.Redis缓存.py
│   ├── 0106.钉钉通知.py
│   ├── 0107.网页爬虫.py
│   ├── 0108.HTML解析.py
│   ├── 0109.数据验证.py
│   ├── 0110.假数据生成.py
│   ├── 0111.技术指标计算.py
│   └── 0112.订阅行情.py
│
├── 02.ui/                      # UI 界面示例
│   ├── 0201.PySide6基础.py
│   ├── 0202.Material主题.py
│   ├── 0203.Fluent设计.py
│   ├── 0204.信号槽通信.py
│   ├── 0205.重启程序.py
│   ├── 0206.股票行情图表.py
│   ├── 0207.期货实时图表.py
│   └── 0208.ArcticDB行情记录.py
│
├── 03.guanlan/                 # 观澜平台功能
│   ├── 0301.期货代码转换.py
│   ├── 0302.通用工具函数演示.py
│   ├── 0303.交易时段判断演示.py
│   ├── 0304.日志工具演示.py
│   ├── 0305.系统工具演示.py
│   ├── 0306.Redis工具演示.py
│   ├── 0307.音频播放演示.py
│   ├── 0308.AI服务演示.py
│   └── 0309.图表模拟验证.py
│
└── config/                     # 配置文件（已 gitignore，需自行创建）
    ├── ctp_connect_multi.json
    ├── dingtalk.json
    ├── redis.json
    └── ai.json
```

## 运行示例

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行基础示例
python examples/01.basic/0101.日志记录.py
python examples/01.basic/0107.网页爬虫.py

# 运行 UI 示例
python examples/02.ui/0203.Fluent设计.py
python examples/02.ui/0206.股票行情图表.py

# 运行观澜平台示例
python examples/03.guanlan/0301.期货代码转换.py
python examples/03.guanlan/0308.AI服务演示.py
```

**注意**：请从项目根目录运行示例，以确保路径正确。

## 示例说明

### 01.basic - 基础功能

无 UI 依赖的基础功能演示。

| 文件                | 说明                                      | 依赖            |
| ------------------- | ----------------------------------------- | --------------- |
| 0101.日志记录.py    | Python logging 模块、按天轮转、多 Handler | -               |
| 0102.拼音转换.py    | pypinyin 汉字转拼音、首字母提取           | pypinyin        |
| 0103.子进程管理.py  | 外部进程启动/终止、跨平台兼容             | -               |
| 0104.定时任务.py    | schedule 库定时任务、装饰器、标签管理     | schedule        |
| 0105.Redis缓存.py   | Redis 连接、String/Hash/Pipeline 操作     | redis           |
| 0106.钉钉通知.py    | 钉钉机器人消息类型（文本/Markdown/卡片）  | DingtalkChatbot |
| 0107.网页爬虫.py    | requests 库、新浪期货行情接口             | requests        |
| 0108.HTML解析.py    | BeautifulSoup HTML 解析、标签查找         | beautifulsoup4  |
| 0109.数据验证.py    | Pydantic V2 模型定义、字段约束、验证器    | pydantic        |
| 0110.假数据生成.py  | Faker 假数据生成、中文本地化              | Faker           |
| 0111.技术指标计算.py | MyTT 技术指标库、均线、MACD 等            | MyTT            |
| 0112.订阅行情.py    | VNPY CTP 行情订阅、命令行版本             | vnpy, vnpy_ctp  |

### 02.ui - UI 界面示例

基于 PySide6 和 QFluentWidgets 的界面示例。

| 文件                    | 说明                                    | 依赖                                   |
| ----------------------- | --------------------------------------- | -------------------------------------- |
| 0201.PySide6基础.py     | QMainWindow、QLabel、布局基础           | PySide6                                |
| 0202.Material主题.py    | qt-material 主题样式                    | qt-material                            |
| 0203.Fluent设计.py      | FluentWindow、InfoBar、主题切换         | qfluentwidgets                         |
| 0204.信号槽通信.py      | 自定义 Signal、Slot 装饰器、lambda 传参 | PySide6                                |
| 0205.重启程序.py        | 退出码控制、应用重启循环                | qfluentwidgets                         |
| 0206.股票行情图表.py    | efinance 股票数据、lightweight-charts   | efinance, lightweight-charts           |
| 0207.期货实时图表.py    | VNPY 实时行情、K线图、双均线策略        | vnpy-ctp, lightweight-charts, MyTT     |
| 0208.ArcticDB行情记录.py | ArcticDB 时序数据库、版本管理、快照     | arcticdb, lightweight-charts           |

**依赖说明**：
- 0206-0208 示例缺失依赖时会显示安装提示，不会直接报错
- 0207 需要配置 CTP 连接信息（`config/ctp_connect.json`）

### 03.guanlan - 观澜平台功能

观澜量化平台的核心功能演示。

| 文件                    | 说明                                  | 依赖               |
| ----------------------- | ------------------------------------- | ------------------ |
| 0301.期货代码转换.py    | 期货合约代码转换工具                  | -                  |
| 0302.通用工具函数演示.py | 日期时间、字符串处理等工具函数        | -                  |
| 0303.交易时段判断演示.py | 交易时间段判断、节假日处理            | -                  |
| 0304.日志工具演示.py    | 观澜日志系统封装                      | -                  |
| 0305.系统工具演示.py    | 系统信息获取、进程管理                | -                  |
| 0306.Redis工具演示.py   | Redis 工具类封装                      | redis              |
| 0307.音频播放演示.py    | 音频播放功能                          | -                  |
| 0308.AI服务演示.py      | AI 服务配置、多模型切换、流式对话     | openai             |
| 0309.图表模拟验证.py    | 图表窗口模拟数据验证                  | lightweight-charts |

## 配置文件

配置文件包含敏感信息，已通过 `.gitignore` 排除。首次运行相关示例时需自行创建。

### ctp_connect_multi.json - CTP 多环境连接配置

```json
{
    "说明": "CTP 多环境配置文件，支持多套连接配置",
    "默认环境": "simnow",
    "环境列表": {
        "simnow": {
            "名称": "SimNow 模拟环境",
            "用户名": "YOUR_USERNAME",
            "密码": "YOUR_PASSWORD",
            "经纪商代码": "9999",
            "交易服务器": "180.168.146.187:10202",
            "行情服务器": "180.168.146.187:10212",
            "产品名称": "simnow_client_test",
            "授权编码": "0000000000000000",
            "产品信息": "",
            "柜台环境": "实盘"
        }
    }
}
```

> **柜台环境说明**：SimNow 测试账户也需要使用"实盘"，穿透测试使用"模拟"。

### dingtalk.json - 钉钉机器人配置

```json
{
    "webhook": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
    "secret": "SECxxx"
}
```

## 依赖安装

### 基础依赖

```bash
# Python 基础库
pip install pydantic schedule requests beautifulsoup4 pypinyin Faker

# Redis（需要 Redis 服务）
pip install redis

# 钉钉通知
pip install DingtalkChatbot

# 技术指标
pip install MyTT
```

### UI 相关

```bash
# PySide6 和 QFluentWidgets
pip install PySide6 PySide6-Fluent-Widgets

# Material 主题
pip install qt-material
```

### 数据和图表

```bash
# 股票数据
pip install efinance

# 图表库
pip install lightweight-charts

# 时序数据库
pip install arcticdb
```

### VNPY 交易

```bash
# VNPY 核心和 CTP 接口
pip install vnpy vnpy_ctp
```

### 一键安装（可选）

```bash
# 安装所有依赖（不包括系统级依赖）
pip install pydantic schedule requests beautifulsoup4 pypinyin Faker \
    redis DingtalkChatbot MyTT \
    PySide6 PySide6-Fluent-Widgets qt-material \
    efinance lightweight-charts arcticdb \
    vnpy vnpy_ctp
```

## 常见问题

### 1. 图表示例无法运行

0206-0208 示例使用 lightweight-charts，如果缺失依赖会显示安装提示：

```bash
pip install lightweight-charts efinance arcticdb MyTT
```

### 2. VNPY 示例连接失败

检查 `config/ctp_connect.json` 配置：
- 确认账号密码正确
- SimNow 账户使用"实盘"环境
- 服务器地址是否可访问

### 3. Redis 相关示例无法运行

确保 Redis 服务已启动：

```bash
# Ubuntu/Debian
sudo systemctl start redis

# 或使用 Docker
docker run -d -p 6379:6379 redis
```

## 学习路径建议

1. **Python 基础** → `01.basic/` 目录
2. **UI 开发** → `02.ui/0201-0205`
3. **数据可视化** → `02.ui/0206-0208`
4. **观澜工具** → `03.guanlan/0301-0309`

---

## 致谢

示例代码使用了以下优秀的开源项目：

- [VNPY](https://www.vnpy.com) — 开源量化交易框架
- [PySide6](https://doc.qt.io/qtforpython-6/) — Qt for Python 官方绑定
- [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — Fluent Design 组件库
- [qframelesswindow](https://github.com/zhiyiYo/PyQt-Frameless-Window) — 无边框窗口框架
- [qt-material](https://github.com/UN-GCPDS/qt-material) — Material Design 主题
- [lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python) — TradingView 风格图表
- [ArcticDB](https://github.com/man-group/ArcticDB) — 高性能嵌入式时序数据库
- [OpenAI Python](https://github.com/openai/openai-python) — OpenAI API 客户端
- [Rich](https://github.com/Textualize/rich) — 终端富文本渲染
- [Pydantic](https://docs.pydantic.dev/) — 数据验证框架
- [NumPy](https://numpy.org/) — 科学计算基础库
- [pandas](https://pandas.pydata.org/) — 数据分析工具
- [MyTT](https://github.com/mpquant/MyTT) — 通达信技术指标库
- [efinance](https://github.com/Micro-sheep/efinance) — 股票行情数据
- [requests](https://github.com/psf/requests) — HTTP 请求库
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML 解析库
- [Redis-py](https://github.com/redis/redis-py) — Redis 客户端
- [DingtalkChatbot](https://github.com/zhuifengshen/DingtalkChatbot) — 钉钉机器人 SDK
- [schedule](https://github.com/dbader/schedule) — 轻量定时任务
- [pypinyin](https://github.com/mozillazg/python-pinyin) — 汉字拼音转换
- [Faker](https://github.com/joke2k/faker) — 假数据生成器

---

**提示**：所有示例都包含详细的代码注释和使用说明，建议边看边运行。
