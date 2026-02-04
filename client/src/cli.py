#!/usr/bin/env python3
"""
DataBorder 客户端命令行接口
"""

import sys
import argparse
import yaml
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from sync_client import DataSyncClient


def main():
    """命令行主入口"""
    parser = argparse.ArgumentParser(description='DataBorder 客户端同步工具')
    parser.add_argument('-c', '--config', default='config/config.yaml',
                       help='配置文件路径 (默认: config/config.yaml)')
    parser.add_argument('-s', '--state', default='.last_sync.json',
                       help='同步状态文件路径 (默认: .last_sync.json)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='详细输出')
    parser.add_argument('--dry-run', action='store_true',
                       help='仅检查需要同步的数据集，不实际下载')
    
    args = parser.parse_args()
    
    # 加载配置文件
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"无法加载配置文件 {args.config}: {e}")
        sys.exit(1)
    
    # 创建客户端实例
    client = DataSyncClient(config, args.state)
    
    # 设置日志级别
    if args.verbose:
        client.logger.setLevel('DEBUG')
    
    # 执行同步
    try:
        if args.dry_run:
            updates = client.check_updates()
            if updates:
                print(f"需要更新的数据集: {len(updates)}")
                for dataset, info in updates.items():
                    print(f"  - {dataset}: {info}")
            else:
                print("没有需要更新的数据集")
        else:
            updated = client.sync_all()
            print(f"同步完成，更新了 {len(updated)} 个数据集")
    except Exception as e:
        print(f"同步失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()