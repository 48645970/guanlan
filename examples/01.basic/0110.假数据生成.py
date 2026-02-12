# -*- coding: utf-8 -*-
"""
Faker 假数据生成演示

演示使用 Faker 库生成各类测试数据：
- 中文姓名、地址、公司名
- 金融相关数据（账户、交易）
- 日期时间数据
- 自定义 Provider

依赖安装:
    pip install faker

Author: 海山观澜
"""

from datetime import datetime
import random

try:
    from faker import Faker
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False


def demo_basic_chinese():
    """演示中文基础数据生成"""
    print("\n" + "=" * 50)
    print("1. 中文基础数据")
    print("=" * 50)

    fake = Faker('zh_CN')

    print("\n【个人信息】")
    for i in range(3):
        print(f"  姓名: {fake.name()}")
        print(f"  身份证: {fake.ssn()}")
        print(f"  手机号: {fake.phone_number()}")
        print(f"  邮箱: {fake.email()}")
        print(f"  地址: {fake.address()}")
        print()

    print("【公司信息】")
    for i in range(3):
        print(f"  公司: {fake.company()}")
        print(f"  职位: {fake.job()}")
        print()


def demo_financial_data():
    """演示金融相关数据生成"""
    print("\n" + "=" * 50)
    print("2. 金融数据生成")
    print("=" * 50)

    fake = Faker('zh_CN')

    print("\n【银行账户】")
    for i in range(3):
        # 生成银行卡号（16位）
        card_no = fake.credit_card_number()
        # 生成银行名称
        banks = ["中国工商银行", "中国建设银行", "中国农业银行", "中国银行", "招商银行", "交通银行"]
        print(f"  开户行: {random.choice(banks)}")
        print(f"  卡号: {card_no}")
        print(f"  户名: {fake.name()}")
        print()

    print("【模拟交易记录】")
    symbols = ["600519.SH", "000001.SZ", "601318.SH", "000858.SZ", "002594.SZ"]
    directions = ["买入", "卖出"]

    for i in range(5):
        symbol = random.choice(symbols)
        direction = random.choice(directions)
        price = round(random.uniform(10, 500), 2)
        volume = random.randint(1, 100) * 100
        amount = price * volume

        print(f"  {fake.date_this_month()} {fake.time()}")
        print(f"  {symbol} {direction} {volume}股 @ {price}元")
        print(f"  成交金额: {amount:,.2f}元")
        print()


def demo_datetime_data():
    """演示日期时间数据生成"""
    print("\n" + "=" * 50)
    print("3. 日期时间数据")
    print("=" * 50)

    fake = Faker('zh_CN')

    print("\n【随机日期】")
    print(f"  今年某天: {fake.date_this_year()}")
    print(f"  本月某天: {fake.date_this_month()}")
    print(f"  过去30天: {fake.date_between(start_date='-30d', end_date='today')}")
    print(f"  未来7天: {fake.date_between(start_date='today', end_date='+7d')}")

    print("\n【时间范围】")
    print(f"  随机时间: {fake.time()}")
    print(f"  完整时间戳: {fake.date_time_this_year()}")

    print("\n【交易时段模拟】")
    # 模拟交易时间段
    trading_hours = [
        ("09:30", "11:30"),
        ("13:00", "15:00"),
    ]
    for start, end in trading_hours:
        # 生成该时段内的随机时间
        base_date = datetime.now().date()
        start_time = datetime.strptime(f"{base_date} {start}", "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(f"{base_date} {end}", "%Y-%m-%d %H:%M")
        random_time = fake.date_time_between(start_date=start_time, end_date=end_time)
        print(f"  {start}-{end} 时段: {random_time.strftime('%H:%M:%S')}")


def demo_text_data():
    """演示文本数据生成"""
    print("\n" + "=" * 50)
    print("4. 文本数据生成")
    print("=" * 50)

    fake = Faker('zh_CN')

    print("\n【随机文本】")
    print(f"  一句话: {fake.sentence()}")
    print(f"  一段话: {fake.paragraph()[:100]}...")

    print("\n【模拟公告标题】")
    templates = [
        "关于{}的公告",
        "{}实施方案",
        "{}管理办法（试行）",
        "关于调整{}的通知",
    ]
    topics = ["股权激励", "分红派息", "重大资产重组", "股票回购", "董事会换届"]

    for _ in range(3):
        template = random.choice(templates)
        topic = random.choice(topics)
        print(f"  {template.format(topic)}")


def demo_custom_provider():
    """演示自定义 Provider"""
    print("\n" + "=" * 50)
    print("5. 自定义数据生成器")
    print("=" * 50)

    from faker.providers import BaseProvider

    class StockProvider(BaseProvider):
        """股票数据生成器"""

        # A股代码前缀
        SH_PREFIXES = ["600", "601", "603", "605", "688"]
        SZ_PREFIXES = ["000", "001", "002", "003", "300", "301"]

        # 行业列表
        INDUSTRIES = [
            "银行", "保险", "证券", "房地产", "医药生物",
            "食品饮料", "家用电器", "汽车", "电子", "计算机",
            "通信", "传媒", "电力设备", "机械设备", "化工"
        ]

        def stock_code(self):
            """生成随机股票代码"""
            if random.random() > 0.5:
                prefix = random.choice(self.SH_PREFIXES)
                suffix = f"{random.randint(0, 999):03d}"
                return f"{prefix}{suffix}.SH"
            else:
                prefix = random.choice(self.SZ_PREFIXES)
                suffix = f"{random.randint(0, 999):03d}"
                return f"{prefix}{suffix}.SZ"

        def stock_name(self):
            """生成随机股票名称"""
            prefixes = ["中国", "华", "国", "东方", "南方", "北方", "新", "大", "中"]
            suffixes = ["科技", "电子", "医药", "银行", "证券", "能源", "材料", "控股", "集团"]
            return random.choice(prefixes) + random.choice(suffixes)

        def stock_price(self, min_price=5.0, max_price=200.0):
            """生成随机股价"""
            return round(random.uniform(min_price, max_price), 2)

        def stock_change(self):
            """生成随机涨跌幅（-10% ~ +10%）"""
            return round(random.uniform(-10, 10), 2)

        def industry(self):
            """生成随机行业"""
            return random.choice(self.INDUSTRIES)

    # 使用自定义 Provider
    fake = Faker('zh_CN')
    fake.add_provider(StockProvider)

    print("\n【模拟股票数据】")
    for _ in range(5):
        code = fake.stock_code()
        name = fake.stock_name()
        price = fake.stock_price()
        change = fake.stock_change()
        industry = fake.industry()
        change_symbol = "+" if change > 0 else ""

        print(f"  {code} {name}")
        print(f"    价格: {price}元  涨跌: {change_symbol}{change}%  行业: {industry}")
        print()


def demo_batch_generation():
    """演示批量数据生成"""
    print("\n" + "=" * 50)
    print("6. 批量数据生成")
    print("=" * 50)

    fake = Faker('zh_CN')

    print("\n【生成测试用户列表】")
    users = []
    for _ in range(5):
        user = {
            "id": fake.uuid4()[:8],
            "name": fake.name(),
            "phone": fake.phone_number(),
            "email": fake.email(),
            "company": fake.company(),
            "created_at": str(fake.date_this_year()),
        }
        users.append(user)

    for user in users:
        print(f"  {user['id']} | {user['name']} | {user['phone']}")

    print(f"\n  共生成 {len(users)} 条用户数据")

    # 使用 Faker 的批量生成
    print("\n【快速批量生成】")
    names = [fake.name() for _ in range(10)]
    print(f"  10个姓名: {', '.join(names)}")


def main():
    print("=" * 50)
    print("Faker 假数据生成演示")
    print("=" * 50)

    if not HAS_FAKER:
        print("\n[错误] 未安装 faker 库")
        print("安装方法: pip install faker")
        return

    print("\nFaker 是一个用于生成假数据的 Python 库")
    print("支持多种语言和数据类型，非常适合测试和开发")

    # 运行各项演示
    demo_basic_chinese()
    demo_financial_data()
    demo_datetime_data()
    demo_text_data()
    demo_custom_provider()
    demo_batch_generation()

    print("\n" + "=" * 50)
    print("演示完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
