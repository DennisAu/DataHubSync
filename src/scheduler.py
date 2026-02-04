"""
Scheduler - 定时调度器
每10分钟检查数据集新鲜度，防抖后自动打包
"""

import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from calendar_reader import CalendarReader
from freshness_checker import FreshnessChecker
from packager import Packager
from state_manager import StateManager

logger = logging.getLogger(__name__)


class Scheduler:
    """
    数据新鲜度定时调度器
    
    功能:
    1. 每10分钟执行一次数据新鲜度检查
    2. 对每个数据集:
       - 获取上一个交易日
       - 检查新鲜度（85%阈值）
       - 超过阈值 → 防抖30秒
       - 稳定 → 打包 → 更新状态
    3. 后台线程运行，不阻塞HTTP服务
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        state_manager: StateManager
    ):
        """
        初始化调度器
        
        Args:
            config: 配置字典，包含 datasets, server, check, calendar 等配置
            state_manager: 状态管理器实例
        """
        self.config = config
        self.state_manager = state_manager
        
        # 获取配置
        server_config = config.get('server', {})
        check_config = config.get('check', {})
        calendar_config = config.get('calendar', {})
        packaging_config = config.get('packaging', {})
        datasets_config = config.get('datasets', [])
        
        self.data_root = server_config.get('data_root', '.')
        self.cache_dir = server_config.get('cache_dir', '.cache')
        self.interval_minutes = check_config.get('interval_minutes', 10)
        self.debounce_seconds = check_config.get('debounce_seconds', 30)
        self.keep_versions = packaging_config.get('keep_versions', 5)
        
        # 初始化依赖组件
        self.calendar_reader = CalendarReader(calendar_config.get('period_offset_file', ''))
        self.freshness_checker = FreshnessChecker(self.data_root, datasets_config)
        self.packager = Packager(self.cache_dir, self.keep_versions)
        
        # 线程控制
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        logger.info(
            f"Scheduler initialized: interval={self.interval_minutes}min, "
            f"debounce={self.debounce_seconds}s"
        )
    
    def start(self) -> None:
        """
        启动调度器
        
        在后台线程中启动主循环
        """
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._stop_event.clear()
        self._running = True
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        
        logger.info("Scheduler started")
    
    def stop(self) -> None:
        """
        停止调度器
        
        发送停止信号并等待线程结束
        """
        if not self._running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping scheduler...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        self._running = False
        logger.info("Scheduler stopped")
    
    def _run(self) -> None:
        """
        主循环
        
        每 interval_minutes 分钟执行一次检查
        """
        interval_seconds = self.interval_minutes * 60
        
        logger.info(f"Scheduler main loop started, interval={interval_seconds}s")
        
        # 首次立即执行一次
        try:
            self._check_all_datasets()
        except Exception as e:
            logger.exception("Error in initial check")
        
        while not self._stop_event.is_set():
            # 等待间隔时间或停止信号
            if self._stop_event.wait(timeout=interval_seconds):
                break
            
            # 执行检查
            try:
                self._check_all_datasets()
            except Exception as e:
                logger.exception("Error checking datasets")
        
        logger.info("Scheduler main loop ended")
    
    def _check_all_datasets(self) -> None:
        """
        检查所有数据集的新鲜度
        
        遍历配置中的每个数据集，检查并处理
        """
        datasets_config = self.config.get('datasets', [])
        
        logger.info(f"Checking freshness for {len(datasets_config)} datasets")
        
        # 获取上一个交易日
        try:
            trade_date = self.calendar_reader.get_last_trade_date()
            logger.info(f"Last trade date: {trade_date}")
        except Exception as e:
            logger.error(f"Failed to get last trade date: {e}")
            return
        
        if not trade_date:
            logger.warning("No trade date available, skipping check")
            return
        
        # 检查每个数据集
        for dataset_config in datasets_config:
            name = dataset_config.get('name', '')
            path = dataset_config.get('path', '')
            threshold = dataset_config.get('freshness_threshold', 0.85)
            
            if not name or not path:
                logger.warning(f"Skipping invalid dataset config: {dataset_config}")
                continue
            
            try:
                self._check_dataset(name, path, trade_date, threshold)
            except Exception as e:
                logger.exception(f"Error checking dataset {name}")
    
    def _check_dataset(
        self,
        name: str,
        data_path: str,
        trade_date: str,
        threshold: float
    ) -> None:
        """
        检查单个数据集的新鲜度并处理
        
        Args:
            name: 数据集名称
            data_path: 数据路径（相对 data_root）
            trade_date: 交易日期
            threshold: 新鲜度阈值
        """
        logger.info(f"Checking dataset: {name}, trade_date={trade_date}")
        
        # 更新状态为检查中
        self.state_manager.set_status(name, 'checking')
        
        # 检查新鲜度
        result = self.freshness_checker.check(trade_date)
        
        logger.info(
            f"Freshness check result for {name}: "
            f"ratio={result.fresh_ratio:.4f}, threshold={threshold}"
        )
        
        # 保存新鲜度信息到状态
        self.state_manager.update(
            name,
            freshness=result.to_dict(),
            last_checked=time.strftime('%Y-%m-%dT%H:%M:%S')
        )
        
        # 如果未达到阈值，跳过
        if not result.is_fresh(threshold):
            logger.info(f"Dataset {name} not fresh enough, skipping")
            self.state_manager.set_status(name, 'not_fresh')
            return
        
        # 达到阈值，进行防抖检查
        logger.info(f"Dataset {name} is fresh, performing debounce check")
        self.state_manager.set_status(name, 'debounce')
        
        stable_result = self.freshness_checker.check_stable(
            trade_date,
            debounce_seconds=self.debounce_seconds,
            stop_event=self._stop_event
        )
        
        if stable_result is None:
            logger.warning(f"Dataset {name} is still changing, deferring packaging")
            self.state_manager.set_status(name, 'unstable')
            return
        
        # 数据已稳定，执行打包
        logger.info(f"Dataset {name} is stable, starting packaging")
        self.state_manager.set_status(name, 'packaging')
        
        data_dir = Path(self.data_root) / data_path
        package_result = self.packager.package(name, str(data_dir))
        
        if package_result['success']:
            logger.info(
                f"Dataset {name} packaged successfully: "
                f"{package_result['zip_path']}"
            )
            # 更新状态
            self.state_manager.update(
                name,
                status='ready',
                last_packaged_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
                package_path=package_result['zip_path'],
                package_size=package_result['zip_size'],
                file_count=package_result['file_count'],
                last_updated=stable_result.last_updated
            )
        else:
            logger.error(f"Failed to package dataset {name}: {package_result['error']}")
            self.state_manager.update(
                name,
                status='error',
                error=package_result['error']
            )
    
    def is_running(self) -> bool:
        """
        检查调度器是否正在运行
        
        Returns:
            如果正在运行返回 True，否则返回 False
        """
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def force_check(self) -> None:
        """
        强制立即执行一次检查
        
        用于手动触发检查，不影响正常调度
        """
        logger.info("Force checking all datasets")
        threading.Thread(target=self._check_all_datasets, daemon=True).start()
