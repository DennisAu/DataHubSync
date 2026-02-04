"""交易日历读取器模块

读取交易日历CSV文件，提供交易日查询功能。
"""

import csv
from datetime import datetime, timedelta


class CalendarReader:
    """交易日历读取器
    
    读取包含交易日期的CSV文件，提供获取交易日列表和
    查询上一交易日的方法。
    
    CSV文件格式要求:
    - 必须包含 "交易日期" 列
    - 日期格式: YYYY-MM-DD
    
    Attributes:
        csv_path: CSV文件路径
        _trade_dates: 缓存的交易日列表
    """
    
    def __init__(self, csv_path: str):
        """初始化日历读取器
        
        Args:
            csv_path: 交易日历CSV文件路径
            
        Raises:
            FileNotFoundError: 当CSV文件不存在时
            ValueError: 当CSV文件格式不正确时
        """
        self.csv_path = csv_path
        self._trade_dates = None
        self._load_csv()
    
    def _load_csv(self) -> None:
        """加载CSV文件并解析交易日期
        
        内部方法，用于加载和缓存交易日数据。
        日期按升序排序存储。
        """
        trade_dates = set()
        
        with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
            # 使用 csv.DictReader 读取带标题的CSV
            reader = csv.DictReader(f)
            
            # 检查必要的列是否存在
            if reader.fieldnames is None or '交易日期' not in reader.fieldnames:
                raise ValueError(f"CSV文件必须包含 '交易日期' 列，当前列: {reader.fieldnames}")
            
            for row in reader:
                date_str = row.get('交易日期', '').strip()
                if date_str:
                    # 验证日期格式
                    try:
                        datetime.strptime(date_str, '%Y-%m-%d')
                        trade_dates.add(date_str)
                    except ValueError:
                        # 跳过格式不正确的日期
                        continue
        
        # 转换为列表并按升序排序
        self._trade_dates = sorted(list(trade_dates))
    
    def get_trade_dates(self) -> list:
        """获取所有交易日列表
        
        Returns:
            按升序排列的交易日字符串列表，格式为 ["YYYY-MM-DD", ...]
        """
        return self._trade_dates.copy()
    
    def get_last_trade_date(self, today_str: str = None) -> str:
        """获取上一个交易日
        
        Args:
            today_str: 当前日期字符串，格式 "YYYY-MM-DD"。
                      如果为 None，则使用系统当前日期。
        
        Returns:
            上一个交易日的日期字符串，格式 "YYYY-MM-DD"
            
        Raises:
            ValueError: 当传入的日期格式不正确时
        """
        if today_str is None:
            today = datetime.now()
        else:
            try:
                today = datetime.strptime(today_str, '%Y-%m-%d')
            except ValueError as e:
                raise ValueError(f"日期格式错误，应为 'YYYY-MM-DD': {today_str}") from e
        
        today_str_formatted = today.strftime('%Y-%m-%d')
        
        # 查找上一个交易日
        # 找到小于当前日期的最大交易日
        last_trade_date = None
        for trade_date in self._trade_dates:
            if trade_date < today_str_formatted:
                last_trade_date = trade_date
            else:
                # 交易日列表已排序，遇到大于等于当前日期的可终止
                break
        
        if last_trade_date is None:
            # 如果没有找到上一个交易日，返回最早的交易日
            # 或者可以抛出异常，取决于业务需求
            if self._trade_dates:
                return self._trade_dates[0]
            return None
        
        return last_trade_date
    
    def is_trade_date(self, date_str: str) -> bool:
        """检查指定日期是否为交易日
        
        Args:
            date_str: 日期字符串，格式 "YYYY-MM-DD"
            
        Returns:
            如果是交易日返回 True，否则返回 False
            
        Raises:
            ValueError: 当日期格式不正确时
        """
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError as e:
            raise ValueError(f"日期格式错误，应为 'YYYY-MM-DD': {date_str}") from e
        
        return date_str in self._trade_dates
    
    def reload(self) -> None:
        """重新加载CSV文件
        
        当CSV文件内容发生变化时调用此方法刷新数据。
        """
        self._load_csv()
