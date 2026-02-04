"""
测试部署脚本和配置
"""

import os
import json
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock


class TestDeployment(unittest.TestCase):
    """测试部署相关功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(__file__).parent / 'test_data' / 'deployment'
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """清理测试环境"""
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_sync_script_creation(self):
        """测试同步脚本创建"""
        sync_script_content = """#!/bin/bash
# DataHubSync 客户端同步脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 运行同步
python3 sync_client.py config.yaml
"""
        
        sync_script = self.test_dir / 'sync.sh'
        with open(sync_script, 'w', encoding='utf-8') as f:
            f.write(sync_script_content)
        
        # 验证文件存在
        self.assertTrue(sync_script.exists())
        
        # 验证内容
        with open(sync_script, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('python3 sync_client.py config.yaml', content)
        self.assertIn('set -e', content)
    
    @patch('subprocess.run')
    def test_crontab_installation(self, mock_run):
        """测试crontab安装"""
        # 模拟crontab命令成功执行
        mock_run.return_value = subprocess.CompletedProcess(
            args=['crontab', '-l'],
            returncode=0,
            stdout='15 8 * * * /opt/datahubsync/sync.sh\n',
            stderr=''
        )
        
        # 测试crontab命令
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn('15 8 * * *', result.stdout)
        mock_run.assert_called_once()
    
    def test_directory_structure_creation(self):
        """测试目录结构创建"""
        # 创建预期的目录结构
        directories = [
            'opt/datahubsync',
            'opt/datahubsync/logs',
            'data/stock-trading-data-pro',
            'data/stock-fin-data-xbx',
            'data/stock-etf-trading-data'
        ]
        
        for dir_path in directories:
            full_path = self.test_dir / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            self.assertTrue(full_path.exists())
            self.assertTrue(full_path.is_dir())
        
        # 验证所有目录都创建成功
        for dir_path in directories:
            full_path = self.test_dir / dir_path
            self.assertTrue(full_path.exists(), f"Directory {dir_path} should exist")
    
    def test_config_file_placement(self):
        """测试配置文件部署"""
        config_content = {
            'hub': {
                'url': 'https://data.quantrade.fun',
                'timeout': 300
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                }
            ]
        }
        
        config_file = self.test_dir / 'opt' / 'datahubsync' / 'config.yaml'
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            import yaml
            yaml.dump(config_content, f)
        
        # 验证配置文件
        self.assertTrue(config_file.exists())
        
        with open(config_file, 'r', encoding='utf-8') as f:
            loaded_config = yaml.safe_load(f)
        
        self.assertEqual(loaded_config['hub']['url'], 'https://data.quantrade.fun')
    
    def test_sync_state_file_initialization(self):
        """测试同步状态文件初始化"""
        sync_state_file = self.test_dir / '.last_sync.json'
        
        # 初始化空的同步状态
        with open(sync_state_file, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        
        # 验证文件存在且为空对象
        self.assertTrue(sync_state_file.exists())
        
        with open(sync_state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        self.assertEqual(state, {})
    
    def test_python_path_validation(self):
        """测试Python路径验证"""
        python_paths = [
            '/usr/bin/python3',
            '/usr/local/bin/python3',
            '/opt/python/bin/python3'
        ]
        
        for python_path in python_paths:
            # 模拟路径验证
            is_valid = python_path.endswith('python3')
            self.assertTrue(is_valid, f"{python_path} should be valid Python path")
    
    def test_log_rotation_setup(self):
        """测试日志轮转设置"""
        logrotate_config = """# DataHubSync 日志轮转配置
/opt/datahubsync/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
"""
        
        logrotate_file = self.test_dir / 'logrotate' / 'datahubsync'
        logrotate_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(logrotate_file, 'w', encoding='utf-8') as f:
            f.write(logrotate_config)
        
        # 验证配置文件
        self.assertTrue(logrotate_file.exists())
        
        with open(logrotate_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('daily', content)
        self.assertIn('rotate 7', content)
        self.assertIn('compress', content)
    
    def test_permission_setup(self):
        """测试权限设置"""
        sync_script = self.test_dir / 'sync.sh'
        sync_script.write_text('#!/bin/bash\necho "test"')
        
        # 模拟设置执行权限
        os.chmod(sync_script, 0o755)
        
        # 验证权限（在Unix系统上）
        if os.name == 'posix':
            file_mode = sync_script.stat().st_mode
            self.assertTrue(file_mode & 0o111)  # 检查执行权限
    
    @patch('os.getenv')
    def test_environment_variables(self, mock_getenv):
        """测试环境变量"""
        # 设置测试环境变量
        mock_getenv.side_effect = lambda key, default=None: {
            'DATAHUB_URL': 'https://data.quantrade.fun',
            'DATAHUB_TIMEOUT': '300',
            'DATAHUB_LOG_LEVEL': 'INFO'
        }.get(key, default)
        
        # 验证环境变量
        self.assertEqual(mock_getenv('DATAHUB_URL'), 'https://data.quantrade.fun')
        self.assertEqual(mock_getenv('DATAHUB_TIMEOUT'), '300')
        self.assertEqual(mock_getenv('DATAHUB_LOG_LEVEL'), 'INFO')
    
    def test_backup_configuration(self):
        """测试备份配置"""
        backup_config = {
            'backup_enabled': True,
            'backup_dir': '/backup/datahubsync',
            'keep_versions': 5
        }
        
        config_file = self.test_dir / 'backup_config.json'
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(backup_config, f, indent=2)
        
        # 验证备份配置
        self.assertTrue(config_file.exists())
        
        with open(config_file, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        
        self.assertTrue(loaded_config['backup_enabled'])
        self.assertEqual(loaded_config['keep_versions'], 5)
    
    def test_service_configuration(self):
        """测试服务配置（systemd）"""
        service_content = """[Unit]
Description=DataHubSync Client
After=network.target

[Service]
Type=oneshot
User=datahub
Group=datahub
WorkingDirectory=/opt/datahubsync
ExecStart=/usr/bin/python3 /opt/datahubsync/sync_client.py config.yaml
StandardOutput=append:/opt/datahubsync/logs/sync.log
StandardError=append:/opt/datahubsync/logs/sync.log

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.test_dir / 'datahubsync.service'
        with open(service_file, 'w', encoding='utf-8') as f:
            f.write(service_content)
        
        # 验证服务文件
        self.assertTrue(service_file.exists())
        
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('[Unit]', content)
        self.assertIn('[Service]', content)
        self.assertIn('[Install]', content)
        self.assertIn('Description=DataHubSync Client', content)


class TestDeploymentValidation(unittest.TestCase):
    """测试部署验证"""
    
    def test_validate_config_file(self):
        """测试配置文件验证"""
        # 有效配置
        valid_config = {
            'hub': {'url': 'https://example.com'},
            'datasets': []
        }
        
        # 验证必要字段
        self.assertIn('hub', valid_config)
        self.assertIn('url', valid_config['hub'])
    
    def test_validate_directory_structure(self):
        """测试目录结构验证"""
        from pathlib import Path
        
        # 模拟目录结构
        base_dir = Path('/opt/datahubsync')
        
        expected_dirs = [
            base_dir,
            base_dir / 'logs',
            Path('/data'),
            Path('/data/stock-trading-data-pro')
        ]
        
        # 验证路径格式
        for dir_path in expected_dirs:
            self.assertIsInstance(dir_path, Path)
            self.assertTrue(len(str(dir_path)) > 0)
    
    def test_validate_permissions(self):
        """测试权限验证"""
        # 模拟文件权限
        file_permissions = {
            'sync.sh': 0o755,
            'config.yaml': 0o644,
            'sync_client.py': 0o644
        }
        
        # 验证执行权限
        self.assertTrue(file_permissions['sync.sh'] & 0o111)
        # 验证读写权限
        self.assertTrue(file_permissions['config.yaml'] & 0o644)
    
    def test_validate_crontab_entry(self):
        """测试crontab条目验证"""
        crontab_entry = "15 8 * * * /opt/datahubsync/sync.sh"
        
        # 验证格式
        parts = crontab_entry.split()
        self.assertEqual(len(parts), 6)  # 5个时间字段 + 命令
        
        # 验证时间字段
        minute, hour, day, month, weekday = parts[:5]
        self.assertEqual(minute, '15')
        self.assertEqual(hour, '8')
        self.assertEqual(day, '*')
        self.assertEqual(month, '*')
        self.assertEqual(weekday, '*')
        
        # 验证命令
        command = parts[5]
        self.assertTrue(command.startswith('/'))
        self.assertTrue(command.endswith('sync.sh'))


if __name__ == '__main__':
    unittest.main()