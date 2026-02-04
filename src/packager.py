"""
Packager - 异步打包器
将数据目录打包为 zip，支持版本管理和清理
"""

import os
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class Packager:
    """
    数据打包器
    
    功能:
    1. 将数据目录打包为 zip
    2. 自动生成带时间戳的文件名
    3. 清理旧版本，只保留指定数量的版本
    4. 获取最新包的路径
    """
    
    def __init__(self, cache_dir: str, keep_versions: int = 5):
        """
        初始化打包器
        
        Args:
            cache_dir: zip 文件缓存目录
            keep_versions: 保留的版本数量，默认 5
        """
        self.cache_dir = Path(cache_dir)
        self.keep_versions = keep_versions
        
        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Packager initialized: cache_dir={cache_dir}, keep_versions={keep_versions}")
    
    def package(self, dataset_name: str, data_dir: str) -> Dict[str, Any]:
        """
        打包数据目录为 zip
        
        Args:
            dataset_name: 数据集名称
            data_dir: 要打包的数据目录路径
            
        Returns:
            Dict with keys:
                - success (bool): 是否成功
                - zip_path (str): zip 文件路径
                - file_count (int): 打包的文件数量
                - zip_size (int): zip 文件大小（字节）
                - error (str): 错误信息（如果失败）
        """
        data_path = Path(data_dir)
        
        # 验证数据目录是否存在
        if not data_path.exists():
            error_msg = f"Data directory does not exist: {data_dir}"
            logger.error(error_msg)
            return {
                'success': False,
                'zip_path': None,
                'file_count': 0,
                'zip_size': 0,
                'error': error_msg
            }
        
        if not data_path.is_dir():
            error_msg = f"Path is not a directory: {data_dir}"
            logger.error(error_msg)
            return {
                'success': False,
                'zip_path': None,
                'file_count': 0,
                'zip_size': 0,
                'error': error_msg
            }
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{dataset_name}_{timestamp}.zip"
        zip_path = self.cache_dir / zip_filename
        
        logger.info(f"Starting package: {dataset_name} -> {zip_path}")
        
        try:
            # 创建 zip 文件
            file_count = 0
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                # 递归遍历数据目录
                for file_path in data_path.rglob('*'):
                    if file_path.is_file():
                        # 只保留文件名（不含路径）作为 zip 内路径
                        arcname = file_path.name
                        zf.write(file_path, arcname)
                        file_count += 1
                        logger.debug(f"Added to zip: {file_path} -> {arcname}")
            
            # 获取 zip 文件大小
            zip_size = zip_path.stat().st_size
            
            logger.info(
                f"Package completed: {zip_filename}, "
                f"files={file_count}, size={zip_size} bytes"
            )
            
            # 清理旧版本
            self._cleanup_old_versions(dataset_name)
            
            return {
                'success': True,
                'zip_path': str(zip_path),
                'file_count': file_count,
                'zip_size': zip_size,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Failed to create zip: {e}"
            logger.error(error_msg)
            
            # 清理失败的 zip 文件
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            
            return {
                'success': False,
                'zip_path': None,
                'file_count': 0,
                'zip_size': 0,
                'error': error_msg
            }
    
    def _cleanup_old_versions(self, dataset_name: str) -> int:
        """
        清理旧版本，只保留最新的 keep_versions 个
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            int: 删除的文件数量
        """
        # 查找所有匹配的 zip 文件
        pattern = f"{dataset_name}_*.zip"
        zip_files = sorted(
            self.cache_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True  # 最新的在前
        )
        
        deleted_count = 0
        
        # 删除超出保留数量的旧版本
        if len(zip_files) > self.keep_versions:
            files_to_delete = zip_files[self.keep_versions:]
            
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old version: {file_path.name}")
                except OSError as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(
                f"Cleanup completed for {dataset_name}: "
                f"deleted={deleted_count}, remaining={self.keep_versions}"
            )
        
        return deleted_count
    
    def get_latest_package(self, dataset_name: str) -> Optional[str]:
        """
        获取最新的 zip 包路径
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            str: 最新 zip 文件的完整路径，如果不存在返回 None
        """
        # 查找所有匹配的 zip 文件
        pattern = f"{dataset_name}_*.zip"
        zip_files = sorted(
            self.cache_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True  # 最新的在前
        )
        
        if zip_files:
            latest = str(zip_files[0])
            logger.debug(f"Latest package for {dataset_name}: {latest}")
            return latest
        
        logger.debug(f"No packages found for {dataset_name}")
        return None
    
    def list_versions(self, dataset_name: str) -> List[Dict[str, Any]]:
        """
        列出数据集的所有版本
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            List of dicts with keys:
                - path (str): zip 文件路径
                - filename (str): 文件名
                - size (int): 文件大小
                - created (str): 创建时间 (ISO 格式)
        """
        pattern = f"{dataset_name}_*.zip"
        zip_files = sorted(
            self.cache_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        versions = []
        for file_path in zip_files:
            stat = file_path.stat()
            versions.append({
                'path': str(file_path),
                'filename': file_path.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return versions
    
    def delete_package(self, zip_path: str) -> bool:
        """
        删除指定的 zip 包
        
        Args:
            zip_path: zip 文件路径
            
        Returns:
            bool: 是否成功删除
        """
        path = Path(zip_path)
        
        if not path.exists():
            logger.warning(f"Package not found: {zip_path}")
            return False
        
        try:
            path.unlink()
            logger.info(f"Deleted package: {zip_path}")
            return True
        except OSError as e:
            logger.error(f"Failed to delete {zip_path}: {e}")
            return False
