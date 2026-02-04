"""
FreshnessChecker - 数据目录新鲜度检测器
检测数据文件的新鲜度，支持85%阈值和防抖检查
"""

import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


@dataclass
class FreshnessResult:
    """新鲜度检测结果"""
    total_count: int          # 总文件数
    fresh_count: int          # 新鲜文件数
    fresh_ratio: float        # 新鲜比例 (0.0-1.0)
    last_updated: str         # 85%分位数文件的mtime (ISO格式)
    
    def is_fresh(self, threshold: float = 0.85) -> bool:
        """
        检查是否达到新鲜度阈值
        
        Args:
            threshold: 新鲜度阈值 (默认0.85)
            
        Returns:
            bool: 是否达到阈值
        """
        return self.fresh_ratio >= threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'total_count': self.total_count,
            'fresh_count': self.fresh_count,
            'fresh_ratio': round(self.fresh_ratio, 4),
            'last_updated': self.last_updated,
            'is_fresh': self.is_fresh()
        }


class FreshnessChecker:
    """
    数据目录新鲜度检测器
    
    功能:
    1. 检查指定交易日期的数据目录新鲜度
    2. 计算新鲜度比例（基于文件mtime）
    3. 获取85%分位数文件的mtime作为last_updated
    4. 支持防抖检查，确保数据稳定
    """
    
    def __init__(self, data_root: str, datasets_config: List[Dict[str, Any]]):
        """
        初始化新鲜度检测器
        
        Args:
            data_root: 数据根目录路径
            datasets_config: 数据集配置列表，每项包含name, path, freshness_threshold
        """
        self.data_root = Path(data_root)
        self.datasets_config = datasets_config
        self._last_check_time = 0
        self._last_result: Optional[FreshnessResult] = None
        
    def _get_dataset_paths(self) -> List[Path]:
        """获取所有数据集的路径列表"""
        paths = []
        for dataset in self.datasets_config:
            path = self.data_root / dataset['path']
            if path.exists():
                paths.append(path)
            else:
                logger.warning(f"数据集路径不存在: {path}")
        return paths
    
    def _get_files_for_trade_date(self, trade_date: str) -> List[Path]:
        """
        获取数据目录中的所有CSV文件
        
        注意：文件名是股票代码（如 sh600018.csv），不是日期命名。
        新鲜度通过文件的 mtime（修改时间）判断，不是文件名。
        
        Args:
            trade_date: 交易日期 (格式: YYYY-MM-DD)，仅用于日志记录
            
        Returns:
            文件路径列表
        """
        files = []
        dataset_paths = self._get_dataset_paths()
        
        for dataset_path in dataset_paths:
            if not dataset_path.exists():
                continue
                
            # 遍历目录中的所有CSV文件
            for csv_file in dataset_path.rglob("*.csv"):
                files.append(csv_file)
                    
        return files
    
    def _calculate_percentile_mtime(self, mtimes: List[float], percentile: float = 0.85) -> Optional[float]:
        """
        计算分位数的mtime
        
        Args:
            mtimes: 修改时间列表（Unix时间戳）
            percentile: 分位数 (0.0-1.0)
            
        Returns:
            分位数对应的mtime，如果列表为空返回None
        """
        if not mtimes:
            return None
        
        sorted_mtimes = sorted(mtimes)
        index = int(len(sorted_mtimes) * percentile)
        # 确保索引在有效范围内
        index = min(index, len(sorted_mtimes) - 1)
        return sorted_mtimes[index]
    
    def check(self, trade_date: str) -> FreshnessResult:
        """
        检查指定交易日期的数据新鲜度
        
        Args:
            trade_date: 交易日期 (格式: YYYY-MM-DD 或 YYYYMMDD)
            
        Returns:
            FreshnessResult: 新鲜度检测结果
        """
        logger.info(f"检查数据新鲜度: trade_date={trade_date}")
        
        files = self._get_files_for_trade_date(trade_date)
        total_count = len(files)
        
        if total_count == 0:
            logger.warning(f"未找到交易日期的文件: {trade_date}")
            return FreshnessResult(
                total_count=0,
                fresh_count=0,
                fresh_ratio=0.0,
                last_updated=datetime.now().isoformat()
            )
        
        # 获取当前时间
        now = time.time()
        
        # 获取所有文件的mtime并计算新鲜度
        mtimes = []
        fresh_count = 0
        
        for file_path in files:
            try:
                stat = file_path.stat()
                mtime = stat.st_mtime
                mtimes.append(mtime)
                
                # 文件在24小时内更新视为新鲜
                if now - mtime < 86400:  # 24小时 = 86400秒
                    fresh_count += 1
                    
            except (OSError, IOError) as e:
                logger.warning(f"无法获取文件状态 {file_path}: {e}")
                continue
        
        # 计算新鲜度比例
        fresh_ratio = fresh_count / total_count if total_count > 0 else 0.0
        
        # 计算85%分位数的mtime
        percentile_mtime = self._calculate_percentile_mtime(mtimes, percentile=0.85)
        
        if percentile_mtime:
            last_updated = datetime.fromtimestamp(percentile_mtime).isoformat()
        else:
            last_updated = datetime.now().isoformat()
        
        result = FreshnessResult(
            total_count=total_count,
            fresh_count=fresh_count,
            fresh_ratio=fresh_ratio,
            last_updated=last_updated
        )
        
        logger.info(
            f"新鲜度检查结果: total={total_count}, fresh={fresh_count}, "
            f"ratio={fresh_ratio:.2%}, last_updated={last_updated}"
        )
        
        self._last_result = result
        self._last_check_time = now
        
        return result
    
    def check_stable(
        self, 
        trade_date: str, 
        debounce_seconds: int = 30,
        stop_event = None
    ) -> Optional[FreshnessResult]:
        """
        防抖检查，等待指定时间后再次确认数据稳定性
        
        原理:
        1. 第一次检查获取结果
        2. 等待debounce_seconds秒（分段睡眠，支持停止信号）
        3. 第二次检查获取结果
        4. 如果两次新鲜度比例差异小于1%，认为数据已稳定
        
        Args:
            trade_date: 交易日期
            debounce_seconds: 防抖等待时间（秒），默认30秒
            stop_event: threading.Event，如果设置则提前返回 None
            
        Returns:
            FreshnessResult: 如果数据稳定返回结果，否则返回None
        """
        logger.info(
            f"开始防抖检查: trade_date={trade_date}, "
            f"debounce_seconds={debounce_seconds}"
        )
        
        # 第一次检查
        result1 = self.check(trade_date)
        logger.info(
            f"第一次检查: fresh_ratio={result1.fresh_ratio:.4f}, "
            f"total={result1.total_count}"
        )
        
        # 分段睡眠，检查停止信号
        logger.debug(f"等待 {debounce_seconds} 秒（分段睡眠，可中断）...")
        for _ in range(int(debounce_seconds)):
            if stop_event and stop_event.is_set():
                logger.info("收到停止信号，中断防抖检查")
                return None
            time.sleep(1)
        
        # 第二次检查
        result2 = self.check(trade_date)
        logger.info(
            f"第二次检查: fresh_ratio={result2.fresh_ratio:.4f}, "
            f"total={result2.total_count}"
        )
        
        # 计算差异
        ratio_diff = abs(result2.fresh_ratio - result1.fresh_ratio)
        logger.info(f"新鲜度比例差异: {ratio_diff:.4f}")
        
        # 如果差异小于1%（0.01），认为数据已稳定
        if ratio_diff < 0.01:
            logger.info("数据已稳定，返回检查结果")
            return result2
        else:
            logger.warning(
                f"数据仍在变化中 (diff={ratio_diff:.4f}>0.01), "
                f"建议稍后重试"
            )
            return None
    
    def is_fresh(self, trade_date: str, threshold: float = 0.85) -> bool:
        """
        快速检查是否达到新鲜度阈值
        
        Args:
            trade_date: 交易日期
            threshold: 新鲜度阈值
            
        Returns:
            bool: 是否新鲜
        """
        result = self.check(trade_date)
        return result.is_fresh(threshold)
    
    def get_stats(self, trade_date: str) -> Dict[str, Any]:
        """
        获取详细的统计信息
        
        Args:
            trade_date: 交易日期
            
        Returns:
            统计信息字典
        """
        result = self.check(trade_date)
        
        # 获取文件详情
        files = self._get_files_for_trade_date(trade_date)
        file_details = []
        
        now = time.time()
        for file_path in files:
            try:
                stat = file_path.stat()
                file_details.append({
                    'path': str(file_path),
                    'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size,
                    'is_fresh': (now - stat.st_mtime) < 86400
                })
            except (OSError, IOError):
                continue
        
        # 按mtime排序
        file_details.sort(key=lambda x: x['mtime'])
        
        return {
            'trade_date': trade_date,
            'summary': result.to_dict(),
            'datasets': [d['name'] for d in self.datasets_config],
            'files': file_details
        }
