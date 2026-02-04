#!/usr/bin/env python3
"""
DataBorder Hub 端主启动脚本
"""

import sys
import signal
import logging
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from http_server import DataHubServer
from state_manager import StateManager
from scheduler import Scheduler
from calendar_reader import CalendarReader


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def signal_handler(signum, frame):
    """信号处理器"""
    logging.info(f"Received signal {signum}, shutting down...")
    if 'scheduler' in globals():
        scheduler.stop()
    sys.exit(0)


def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Starting DataBorder Hub Server...")
        
        # 初始化组件
        logger.info("Initializing components...")
        
        # 读取配置
        config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return 1
            
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 初始化状态管理器
        state_file = config['hub'].get('state_file', 'hub_state.json')
        # 使用相对于main.py的路径
        state_file_path = Path(__file__).parent.parent / state_file
        state_manager = StateManager(str(state_file_path))
        
        # 初始化日历读取器
        calendar_file = config['hub'].get('calendar_file', 'trading_calendar.csv')
        # 使用相对于main.py的路径
        calendar_file_path = Path(__file__).parent.parent / calendar_file
        calendar_reader = CalendarReader(str(calendar_file_path))
        
        # 初始化调度器
        scheduler = Scheduler(
            config=config,
            state_manager=state_manager
        )
        
        # 初始化HTTP服务器
        server = DataHubServer(config, state_manager)
        
        logger.info("All components initialized successfully")
        
        # 启动调度器
        scheduler.start()
        logger.info("Scheduler started")
        
        # 启动HTTP服务器（这会阻塞直到程序结束）
        server.start()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        if 'scheduler' in globals():
            scheduler.stop()
        return 0
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())