# -*- coding: utf-8 -*-
"""
观澜量化 - 期货代码转换工具

Author: 海山观澜
"""

import re
from datetime import datetime
from vnpy.trader.constant import Exchange


class SymbolConverter:
    """
    期货合约代码格式转换工具类

    功能:
        1. 统一内部格式: 全大写 + 4位年月 (如 RB2505)
        2. 交易所格式转换: 根据各交易所规范自动转换
        3. 双向转换: 统一格式 ↔ 交易所格式
        4. 格式验证与解析

    支持交易所:
        SHFE (上海期货交易所)
        DCE (大连商品交易所)
        CZCE (郑州商品交易所)
        CFFEX (中国金融期货交易所)
        INE (上海国际能源交易中心)
        GFEX (广州期货交易所)

    使用示例:
        # 从交易所格式转为统一格式
        >>> SymbolConverter.to_standard("rb2505", Exchange.SHFE)
        'RB2505'
        >>> SymbolConverter.to_standard("TA505", Exchange.CZCE)
        'TA2505'

        # 从统一格式转为交易所格式
        >>> SymbolConverter.to_exchange("RB2505", Exchange.SHFE)
        'rb2505'
        >>> SymbolConverter.to_exchange("TA2505", Exchange.CZCE)
        'TA505'

        # 提取信息
        >>> SymbolConverter.extract_commodity("RB2505")
        'RB'
        >>> SymbolConverter.extract_date("RB2505")
        (25, 5)  # 年份25, 月份5

        # 验证格式
        >>> SymbolConverter.validate("rb2505", Exchange.SHFE)
        True
    """

    # 正则表达式模式（预编译以提高性能）
    _PATTERN_STANDARD = re.compile(r'^([A-Z]+)(\d{4})$')     # 统一格式: 大写字母 + 4位数字
    _PATTERN_EXCHANGE_4 = re.compile(r'^([a-zA-Z]+)(\d{4})$')  # 4位年月格式
    _PATTERN_EXCHANGE_3 = re.compile(r'^([A-Z]+)(\d{3})$')    # 3位年月格式(CZCE)

    # 交易所格式配置
    _EXCHANGE_CONFIG = {
        Exchange.SHFE: {'case': 'lower', 'date_digits': 4},
        Exchange.DCE: {'case': 'lower', 'date_digits': 4},
        Exchange.CZCE: {'case': 'upper', 'date_digits': 3},
        Exchange.CFFEX: {'case': 'upper', 'date_digits': 4},
        Exchange.INE: {'case': 'lower', 'date_digits': 4},
        Exchange.GFEX: {'case': 'lower', 'date_digits': 4},
    }

    @staticmethod
    def to_standard(symbol: str, exchange: Exchange) -> str:
        """
        将交易所格式转换为统一格式(全大写 + 4位年月)

        统一格式定义: 全大写品种代码 + 4位年月（年2位+月2位）
        例如: RB2505 表示螺纹钢2025年5月合约

        Args:
            symbol: 交易所格式的合约代码
                - SHFE/DCE/INE/GFEX: 小写+4位（如 rb2505）
                - CZCE: 大写+3位（如 TA505）
                - CFFEX: 大写+4位（如 IF2412）
            exchange: 交易所枚举，来自 vnpy.trader.constant.Exchange

        Returns:
            统一格式的合约代码（大写+4位年月），格式无法识别时返回原值

        Examples:
            >>> SymbolConverter.to_standard("rb2505", Exchange.SHFE)
            'RB2505'

            >>> SymbolConverter.to_standard("TA505", Exchange.CZCE)
            'TA2505'

        Note:
            - CZCE的3位年月会自动扩展为4位（505 -> 2505）
            - 年份推断基于当前时间，假设合约有效期不超过10年
        """
        config = SymbolConverter._EXCHANGE_CONFIG.get(exchange)
        if not config:
            return symbol

        # 根据交易所格式解析
        if config['date_digits'] == 4:
            match = SymbolConverter._PATTERN_EXCHANGE_4.match(symbol)
            if not match:
                return symbol
            commodity, date_str = match.groups()
            return f"{commodity.upper()}{date_str}"

        else:  # CZCE: 3位年月
            match = SymbolConverter._PATTERN_EXCHANGE_3.match(symbol)
            if not match:
                return symbol
            commodity, date_str = match.groups()

            year_digit = date_str[0]
            month = date_str[1:3]
            year_2digit = SymbolConverter._infer_full_year(int(year_digit))

            return f"{commodity.upper()}{year_2digit:02d}{month}"

    @staticmethod
    def to_exchange(symbol: str, exchange: Exchange) -> str:
        """
        将统一格式转换为交易所格式

        Args:
            symbol: 统一格式的合约代码 (如 'RB2505')
            exchange: 目标交易所枚举

        Returns:
            交易所格式的合约代码，格式无法识别时返回原值

        Examples:
            >>> SymbolConverter.to_exchange("RB2505", Exchange.SHFE)
            'rb2505'
            >>> SymbolConverter.to_exchange("TA2505", Exchange.CZCE)
            'TA505'
            >>> SymbolConverter.to_exchange("IF2412", Exchange.CFFEX)
            'IF2412'
        """
        config = SymbolConverter._EXCHANGE_CONFIG.get(exchange)
        if not config:
            return symbol

        # 统一转大写后匹配标准格式
        match = SymbolConverter._PATTERN_STANDARD.match(symbol.upper())
        if not match:
            return symbol

        commodity, date_str = match.groups()

        # 处理年月格式
        if config['date_digits'] == 4:
            # 4位年月：直接使用
            result_symbol = f"{commodity}{date_str}"
        else:
            # 3位年月(CZCE)：2505 -> 505
            year_2digit = date_str[0:2]
            month = date_str[2:4]
            year_1digit = year_2digit[1]  # 取年份个位
            result_symbol = f"{commodity}{year_1digit}{month}"

        # 处理大小写
        if config['case'] == 'lower':
            return result_symbol.lower()
        else:
            return result_symbol.upper()

    @staticmethod
    def extract_commodity(symbol: str) -> str:
        """
        提取合约的品种代码（字母部分）

        Args:
            symbol: 合约代码（统一格式或交易所格式均可）

        Returns:
            品种代码（大写），格式无法识别时返回空字符串

        Examples:
            >>> SymbolConverter.extract_commodity("RB2505")
            'RB'
            >>> SymbolConverter.extract_commodity("rb2505")
            'RB'
            >>> SymbolConverter.extract_commodity("TA505")
            'TA'
        """
        # 使用正则提取字母部分
        match = re.match(r'^([a-zA-Z]+)', symbol)
        if not match:
            return ""

        return match.group(1).upper()

    @staticmethod
    def extract_date(symbol: str, exchange: Exchange | None = None) -> tuple[int, int]:
        """
        提取合约的年月信息

        Args:
            symbol: 合约代码
            exchange: 交易所（如果提供，用于更准确地解析3位格式）

        Returns:
            (年份2位, 月份) 例如 (25, 5) 表示2025年5月，格式无法识别时返回 (0, 0)

        Examples:
            >>> SymbolConverter.extract_date("RB2505")
            (25, 5)
            >>> SymbolConverter.extract_date("TA505", Exchange.CZCE)
            (25, 5)
            >>> SymbolConverter.extract_date("IF2412")
            (24, 12)
        """
        # 提取数字部分
        match = re.search(r'(\d{3,4})$', symbol)
        if not match:
            return (0, 0)

        date_str = match.group(1)

        if len(date_str) == 4:
            # 4位格式: 2505 -> (25, 5)
            year = int(date_str[0:2])
            month = int(date_str[2:4])
        elif len(date_str) == 3:
            # 3位格式: 505 -> (25, 5)
            year_digit = int(date_str[0])
            month = int(date_str[1:3])
            year = SymbolConverter._infer_full_year(year_digit)
        else:
            return (0, 0)

        # 验证月份有效性
        if not (1 <= month <= 12):
            return (0, 0)

        return (year, month)

    @staticmethod
    def validate(symbol: str, exchange: Exchange) -> bool:
        """
        验证合约代码格式是否正确

        Args:
            symbol: 合约代码
            exchange: 交易所

        Returns:
            True 如果格式有效，False 否则

        Examples:
            >>> SymbolConverter.validate("rb2505", Exchange.SHFE)
            True
            >>> SymbolConverter.validate("RB2505", Exchange.SHFE)
            False  # SHFE要求小写
            >>> SymbolConverter.validate("TA505", Exchange.CZCE)
            True
        """
        if exchange not in SymbolConverter._EXCHANGE_CONFIG:
            return False

        config = SymbolConverter._EXCHANGE_CONFIG[exchange]

        # 根据配置验证格式
        if config['date_digits'] == 4:
            match = SymbolConverter._PATTERN_EXCHANGE_4.match(symbol)
            if not match:
                return False
            commodity, date_str = match.groups()

            # 验证大小写
            if config['case'] == 'lower':
                if commodity != commodity.lower():
                    return False
            else:
                if commodity != commodity.upper():
                    return False

        else:  # CZCE 3位
            match = SymbolConverter._PATTERN_EXCHANGE_3.match(symbol)
            if not match:
                return False

        # 验证月份范围
        _, month = SymbolConverter.extract_date(symbol, exchange)
        if not (1 <= month <= 12):
            return False

        return True

    @staticmethod
    def _infer_full_year(year_digit: int) -> int:
        """
        从年份个位数推断完整的2位年份

        规则:
            - 当前年份作为参考点
            - 向后推算最多10年的有效期

        Args:
            year_digit: 年份个位数 (0-9)

        Returns:
            2位年份 (如 25 表示2025年)

        Examples:
            假设当前是2024年:
            >>> SymbolConverter._infer_full_year(5)  # 2025
            25
            >>> SymbolConverter._infer_full_year(3)  # 2033
            33
            >>> SymbolConverter._infer_full_year(9)  # 2029
            29
        """
        current_year = datetime.now().year
        current_year_2digit = current_year % 100  # 24 (for 2024)
        current_decade = current_year // 10 % 10  # 2 (for 202x)

        # 当前年份的个位
        current_digit = current_year_2digit % 10

        # 如果输入年份个位 >= 当前年份个位，则在当前十年
        if year_digit >= current_digit:
            return current_decade * 10 + year_digit
        else:
            # 否则在下一个十年
            return (current_decade + 1) * 10 + year_digit
