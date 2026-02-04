#!/usr/bin/env python3
"""
DataHubSync Hub - 主入口文件

整合所有组件，提供完整的数据同步服务:
1. 定时调度器 (Scheduler) - 检查数据新鲜度并自动打包
2. HTTP 服务器 (HTTPServer) - 提供数据包下载服务

使用方法:
    python server.py              # 使用默认配置 (config.yaml)
    python server.py --config custom.yaml  # 使用自定义配置
    python server.py --state /path/to/state.json  # 指定状态文件

信号处理:
    Ctrl+C - 优雅退出，停止所有服务
"""

import os
import sys
import yaml
import signal
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from state_manager import StateManager
from scheduler import Scheduler
from http_server import DataHubServer


# 全局变量，用于信号处理
scheduler: Optional[Scheduler] = None
server: Optional[DataHubServer] = None
logger: Optional[logging.Logger] = None


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        config: 配置字典，包含 logging 配置
        
    Returns:
        配置好的 logger 实例
    """
    logging_config = config.get('logging', {})
    log_level = getattr(logging, logging_config.get('level', 'INFO'))
    log_format = logging_config.get('format', '%(asctime)s [%(levelname)s] %(message)s')
    log_file = logging_config.get('file', 'logs/server.log')
    
    # 创建日志目录
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # 配置根日志器
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8') if log_file else logging.NullHandler()
        ]
    )
    
    log = logging.getLogger(__name__)
    log.info("Logging configured")
    return log


def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
        
    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: 配置文件格式错误
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if not config:
        raise ValueError(f"Configuration file is empty: {config_path}")
    
    return config


def signal_handler(signum: int, frame) -> None:
    """
    信号处理函数 - 优雅退出
    
    捕获 SIGINT (Ctrl+C) 和 SIGTERM 信号，
    停止所有服务后退出程序
    """
    sig_name = signal.Signals(signum).name
    if logger:
        logger.info(f"Received signal {sig_name}, shutting down gracefully...")
    else:
        print(f"\nReceived signal {sig_name}, shutting down gracefully...")
    
    # 停止调度器
    if scheduler and scheduler.is_running():
        if logger:
            logger.info("Stopping scheduler...")
        scheduler.stop()
    
    # 停止 HTTP 服务器
    if server:
        if logger:
            logger.info("Stopping HTTP server...")
        server.stop()
    
    if logger:
        logger.info("Shutdown complete")
    
    sys.exit(0)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='DataHubSync Hub - 数据同步服务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python server.py                          # 使用默认配置
  python server.py -c /path/to/config.yaml  # 使用自定义配置
  python server.py -s /path/to/state.json   # 指定状态文件
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    
    parser.add_argument(
        '-s', '--state',
        default='.state.json',
        help='状态文件路径 (默认: .state.json)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='启用详细日志输出'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    主入口函数
    
    流程:
    1. 加载配置
    2. 初始化状态管理器
    3. 启动调度器（后台线程）
    4. 启动 HTTP 服务器（主线程）
    5. 等待信号优雅退出
    
    Returns:
        退出码 (0=成功, 1=失败)
    """
    global scheduler, server, logger
    
    # 解析命令行参数
    args = parse_args()
    
    try:
        # 加载配置
        config = load_config(args.config)
        
        # 如果启用详细模式，覆盖日志级别
        if args.verbose:
            config['logging'] = config.get('logging', {})
            config['logging']['level'] = 'DEBUG'
        
        # 配置日志
        logger = setup_logging(config)
        logger.info(f"Loaded configuration from {args.config}")
        
        # 初始化状态管理器
        state_file = args.state
        state_manager = StateManager(state_file)
        logger.info(f"StateManager initialized with state file: {state_file}")
        
        # 设置信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers registered")
        
        # 启动调度器（后台线程）
        scheduler = Scheduler(config, state_manager)
        scheduler.start()
        
        # 等待调度器完全启动
        import time
        time.sleep(0.5)
        
        if scheduler.is_running():
            logger.info("Scheduler started successfully")
        else:
            logger.error("Scheduler failed to start")
            return 1
        
        # 启动 HTTP 服务器（主线程，阻塞）
        # 传递状态管理器的所有状态
        server = DataHubServer(config, state_manager.get_all())
        
        # 更新服务器的状态引用（调度器会持续更新状态）
        # 使用一个定时更新机制保持状态同步
        def update_server_states():
            """定期更新服务器的状态引用"""
            while scheduler.is_running():
                try:
                    # 更新服务器的状态引用
                    DataHubServer.update_states = state_manager.get_all()
                    if hasattr(server, 'handler_class'):
                        server.handler_class.dataset_states = state_manager.get_all()
                    time.sleep(5)  # 每5秒更新一次
                except Exception as e:
                    logger.warning(f"Failed to update server states: {e}")
                    break
        
        # 启动状态更新线程
        import threading
        state_update_thread = threading.Thread(target=update_server_states, daemon=True)
        state_update_thread.start()
        
        logger.info("Starting HTTP server (Press Ctrl+C to stop)...")
        server.start()  # 阻塞直到收到信号
        
        return 0
        
    except FileNotFoundError as e:
        if logger:
            logger.error(f"Configuration error: {e}")
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1
        
    except yaml.YAMLError as e:
        if logger:
            logger.error(f"Failed to parse configuration: {e}")
        else:
            print(f"Error: Invalid configuration file: {e}", file=sys.stderr)
        return 1
        
    except Exception as e:
        if logger:
            logger.exception("Fatal error")
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
