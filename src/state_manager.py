"""
StateManager - 状态管理器
管理数据集的 last_updated 等状态，保存到 JSON 文件
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StateManager:
    """
    数据集状态管理器
    
    功能:
    1. 管理数据集的状态信息（last_updated, fresh_ratio 等）
    2. 持久化状态到 JSON 文件
    3. 提供读取和更新状态的方法
    """
    
    def __init__(self, state_file: str = ".state.json"):
        """
        初始化状态管理器
        
        Args:
            state_file: 状态文件路径，默认为 .state.json
        """
        self.state_file = Path(state_file)
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()  # 线程锁，保护并发访问
        self._load()
        logger.info(f"StateManager initialized: state_file={state_file}")
    
    def _load(self) -> None:
        """
        从 JSON 文件加载状态
        
        如果文件不存在或格式错误，初始化空状态
        """
        with self._lock:
            if not self.state_file.exists():
                logger.info(f"State file not found, initializing empty state: {self.state_file}")
                self._state = {}
                return
            
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self._state = json.load(f)
                logger.debug(f"State loaded from {self.state_file}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse state file, initializing empty state: {e}")
                self._state = {}
            except Exception as e:
                logger.error(f"Error loading state file: {e}")
                self._state = {}
    
    def _save(self) -> None:
        """
        原子保存状态到 JSON 文件
        
        使用"临时文件 + 原子重命名"模式，防止写入过程中崩溃导致文件损坏
        自动创建父目录（如果不存在）
        """
        with self._lock:
            try:
                # 确保父目录存在
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入临时文件
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._state, f, ensure_ascii=False, indent=2)
                
                # 原子重命名（Windows 和 Linux 都支持）
                import os
                os.replace(temp_file, self.state_file)
                
                logger.debug(f"State saved to {self.state_file}")
            except Exception as e:
                # 清理临时文件
                if 'temp_file' in locals() and temp_file.exists():
                    temp_file.unlink()
                logger.error(f"Error saving state file: {e}")
    
    def get(self, dataset: str) -> Dict[str, Any]:
        """
        获取指定数据集的状态
        
        Args:
            dataset: 数据集名称
            
        Returns:
            数据集状态字典，如果不存在返回空字典
        """
        with self._lock:
            return self._state.get(dataset, {}).copy()
    
    def update(self, dataset: str, **kwargs) -> Dict[str, Any]:
        """
        更新指定数据集的状态
        
        Args:
            dataset: 数据集名称
            **kwargs: 要更新的状态字段
            
        Returns:
            更新后的完整状态字典
            
        Example:
            >>> state_manager.update("stock-trading-data-pro", 
            ...                      last_updated="2024-01-15T10:30:00",
            ...                      fresh_ratio=0.92,
            ...                      status="ready")
        """
        with self._lock:
            # 如果数据集不存在，创建空字典
            if dataset not in self._state:
                self._state[dataset] = {}
            
            # 更新字段
            self._state[dataset].update(kwargs)
            
            # 自动添加更新时间
            self._state[dataset]['state_updated_at'] = datetime.now().isoformat()
            
            # 持久化到文件（在锁内调用_save，但_save内部也加锁，使用RLock可重入）
            self._save()
            
            logger.info(f"State updated for {dataset}: {kwargs}")
            
            return self._state[dataset].copy()
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有数据集的状态
        
        Returns:
            所有数据集状态的字典，格式为 {dataset_name: state_dict}
        """
        with self._lock:
            # 返回深拷贝，防止外部修改影响内部状态
            return {k: v.copy() for k, v in self._state.items()}
    
    def delete(self, dataset: str) -> bool:
        """
        删除指定数据集的状态
        
        Args:
            dataset: 数据集名称
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if dataset in self._state:
                del self._state[dataset]
                self._save()
                logger.info(f"State deleted for {dataset}")
                return True
            return False
    
    def clear(self) -> None:
        """
        清空所有状态
        
        谨慎使用！这会删除所有数据集的状态记录
        """
        with self._lock:
            self._state = {}
            self._save()
            logger.warning("All states cleared")
    
    def get_last_updated(self, dataset: str) -> Optional[str]:
        """
        获取数据集的最后更新时间
        
        Args:
            dataset: 数据集名称
            
        Returns:
            最后更新时间（ISO格式），如果不存在返回 None
        """
        state = self.get(dataset)
        return state.get('last_updated')
    
    def set_status(self, dataset: str, status: str) -> Dict[str, Any]:
        """
        设置数据集的状态标记
        
        Args:
            dataset: 数据集名称
            status: 状态值（如 "pending", "packaging", "ready", "error"）
            
        Returns:
            更新后的完整状态字典
        """
        return self.update(dataset, status=status)
    
    def is_packaged(self, dataset: str) -> bool:
        """
        检查数据集是否已打包
        
        Args:
            dataset: 数据集名称
            
        Returns:
            如果已打包返回 True，否则返回 False
        """
        state = self.get(dataset)
        return state.get('status') == 'ready' and 'last_packaged_at' in state
